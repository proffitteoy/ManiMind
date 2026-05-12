/**
 * HTML-to-video renderer using puppeteer-core + ffmpeg.
 *
 * Usage:
 *   node scripts/html_to_video.js <html_dir> <output.mp4> [--fps 30] [--width 1280] [--height 720]
 *
 * The HTML file must expose a GSAP timeline at window.__timelines[compositionId].
 * Duration is read from tl.duration(). Frames are captured by seeking the timeline.
 */

const puppeteer = require('puppeteer-core');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

const CHROME_PATH = process.env.MANIMIND_CHROME_PATH
  || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const FFMPEG_PATH = process.env.MANIMIND_FFMPEG_PATH || 'D:/ffmpeg/bin/ffmpeg.exe';

function parseArgs() {
  const args = process.argv.slice(2);
  if (args.length < 2) {
    console.error('Usage: node html_to_video.js <html_dir> <output.mp4> [--fps N] [--width N] [--height N]');
    process.exit(1);
  }
  const opts = { htmlDir: args[0], output: args[1], fps: 30, width: 1280, height: 720 };
  for (let i = 2; i < args.length; i += 2) {
    if (args[i] === '--fps') opts.fps = parseInt(args[i + 1], 10);
    if (args[i] === '--width') opts.width = parseInt(args[i + 1], 10);
    if (args[i] === '--height') opts.height = parseInt(args[i + 1], 10);
  }
  return opts;
}

function startServer(dir) {
  const mimeTypes = {
    '.html': 'text/html', '.js': 'application/javascript',
    '.css': 'text/css', '.json': 'application/json',
    '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml',
  };
  const server = http.createServer((req, res) => {
    let filePath = path.join(dir, req.url === '/' ? 'index.html' : req.url);
    const ext = path.extname(filePath).toLowerCase();
    const contentType = mimeTypes[ext] || 'application/octet-stream';
    fs.readFile(filePath, (err, data) => {
      if (err) { res.writeHead(404); res.end(); return; }
      res.writeHead(200, { 'Content-Type': contentType });
      res.end(data);
    });
  });
  return new Promise(resolve => {
    server.listen(0, '127.0.0.1', () => {
      resolve({ server, port: server.address().port });
    });
  });
}

function spawnFfmpeg(opts, totalFrames) {
  const outputDir = path.dirname(opts.output);
  if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

  const ffmpegArgs = [
    '-y',
    '-f', 'rawvideo',
    '-pix_fmt', 'rgba',
    '-s', `${opts.width}x${opts.height}`,
    '-r', String(opts.fps),
    '-i', 'pipe:0',
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-preset', 'fast',
    '-crf', '23',
    '-movflags', '+faststart',
    opts.output,
  ];
  const proc = spawn(FFMPEG_PATH, ffmpegArgs, { stdio: ['pipe', 'pipe', 'pipe'] });
  proc.stderr.on('data', () => {});
  return proc;
}

async function captureFrames(page, opts) {
  const timelineInfo = await page.evaluate(() => {
    const keys = Object.keys(window.__timelines || {});
    if (keys.length === 0) return null;
    const tl = window.__timelines[keys[0]];
    return { id: keys[0], duration: tl.duration() };
  });

  if (!timelineInfo) {
    throw new Error('No GSAP timeline found at window.__timelines');
  }

  const duration = timelineInfo.duration;
  const totalFrames = Math.ceil(duration * opts.fps);
  console.error(`Timeline "${timelineInfo.id}": ${duration.toFixed(2)}s, ${totalFrames} frames @ ${opts.fps}fps`);

  const ffmpeg = spawnFfmpeg(opts, totalFrames);
  const cdp = await page.createCDPSession();

  for (let i = 0; i < totalFrames; i++) {
    const time = i / opts.fps;
    await page.evaluate((t) => {
      const keys = Object.keys(window.__timelines);
      const tl = window.__timelines[keys[0]];
      tl.seek(t, false);
    }, time);

    await cdp.send('Page.startScreencast', { format: 'png', quality: 100 });
    await cdp.send('Page.stopScreencast');

    const screenshot = await page.screenshot({ type: 'png', omitBackground: false });
    const raw = await pngToRaw(screenshot, opts.width, opts.height);

    const canWrite = ffmpeg.stdin.write(raw);
    if (!canWrite) {
      await new Promise(resolve => ffmpeg.stdin.once('drain', resolve));
    }

    if ((i + 1) % opts.fps === 0) {
      console.error(`  frame ${i + 1}/${totalFrames}`);
    }
  }

  ffmpeg.stdin.end();
  await new Promise((resolve, reject) => {
    ffmpeg.on('close', code => {
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg exited with code ${code}`));
    });
  });

  console.error(`Output: ${opts.output}`);
}

async function pngToRaw(pngBuffer, width, height) {
  const { PNG } = require('pngjs');
  return new Promise((resolve, reject) => {
    const png = new PNG();
    png.parse(pngBuffer, (err, data) => {
      if (err) return reject(err);
      resolve(Buffer.from(data.data));
    });
  });
}

async function main() {
  const opts = parseArgs();

  if (!fs.existsSync(path.join(opts.htmlDir, 'index.html'))) {
    console.error(`Error: ${opts.htmlDir}/index.html not found`);
    process.exit(1);
  }

  const { server, port } = await startServer(opts.htmlDir);
  const url = `http://127.0.0.1:${port}/`;

  let browser;
  try {
    browser = await puppeteer.launch({
      executablePath: CHROME_PATH,
      headless: 'new',
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-gpu',
        `--window-size=${opts.width},${opts.height}`,
      ],
    });

    const page = await browser.newPage();
    await page.setViewport({ width: opts.width, height: opts.height });
    await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 });

    // Wait for GSAP to load and timeline to register
    await page.waitForFunction(
      () => window.__timelines && Object.keys(window.__timelines).length > 0,
      { timeout: 10000 }
    );

    await captureFrames(page, opts);
    console.log(JSON.stringify({ success: true, output: opts.output }));
  } catch (err) {
    console.error(`Capture failed: ${err.message}`);
    console.log(JSON.stringify({ success: false, error: err.message }));
    process.exit(1);
  } finally {
    if (browser) await browser.close();
    server.close();
  }
}

main();
