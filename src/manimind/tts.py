"""TTS 适配层：支持 noop / powershell_sapi / command。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Protocol


@dataclass(slots=True)
class TTSJob:
    project_id: str
    script_text: str
    output_path: str
    voice: str = "neutral"
    language: str = "zh-CN"


class TTSAdapter(Protocol):
    def synthesize(self, job: TTSJob) -> str:
        """执行 TTS 并返回产物路径。"""


class NoopTTSAdapter:
    """占位实现。"""

    def synthesize(self, job: TTSJob) -> str:
        target = Path(job.output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "\n".join(
                [
                    "# TTS Placeholder",
                    f"project_id={job.project_id}",
                    f"voice={job.voice}",
                    f"language={job.language}",
                    "",
                    job.script_text,
                ]
            ),
            encoding="utf-8",
        )
        return str(target)


class PowerShellSapiTTSAdapter:
    """Windows 本地语音合成（System.Speech）。"""

    def synthesize(self, job: TTSJob) -> str:
        target = Path(job.output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # System.Speech SaveToWaveFile 只支持 wav。
        if target.suffix.lower() != ".wav":
            target = target.with_suffix(".wav")

        text_file = target.with_suffix(".txt")
        text_file.write_text(job.script_text, encoding="utf-8")
        script_file = target.with_suffix(".sapi.ps1")

        script = r"""
param([string]$TextFile,[string]$OutputFile,[string]$VoiceHint,[string]$LanguageHint)
Add-Type -AssemblyName System.Speech
$text = Get-Content -Raw -LiteralPath $TextFile -Encoding UTF8
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($VoiceHint -and $VoiceHint -ne 'neutral') {
  try { $synth.SelectVoice($VoiceHint) } catch {}
}
if ($LanguageHint) {
  $candidate = $synth.GetInstalledVoices() |
    Where-Object { $_.VoiceInfo.Culture.Name -like "$LanguageHint*" } |
    Select-Object -First 1
  if ($null -ne $candidate) {
    try { $synth.SelectVoice($candidate.VoiceInfo.Name) } catch {}
  }
}
$synth.SetOutputToWaveFile($OutputFile)
$synth.Speak($text)
$synth.Dispose()
"""
        script_file.write_text(script, encoding="utf-8")
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_file),
            "-TextFile",
            str(text_file),
            "-OutputFile",
            str(target),
            "-VoiceHint",
            job.voice,
            "-LanguageHint",
            job.language,
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(
                "tts_powershell_failed:"
                + (result.stderr.strip() or result.stdout.strip() or "unknown")
            )
        if script_file.exists():
            script_file.unlink()
        if text_file.exists():
            text_file.unlink()
        return str(target)


class CommandTTSAdapter:
    """外部命令适配器。命令模板通过环境变量 MANIMIND_TTS_COMMAND 提供。"""

    def __init__(self, command_template: str) -> None:
        self.command_template = command_template

    def synthesize(self, job: TTSJob) -> str:
        target = Path(job.output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        text_file = target.with_suffix(".txt")
        text_file.write_text(job.script_text, encoding="utf-8")

        rendered = (
            self.command_template.replace("{text_file}", str(text_file))
            .replace("{output}", str(target))
            .replace("{voice}", job.voice)
            .replace("{language}", job.language)
        )
        command = shlex.split(rendered, posix=False)
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise RuntimeError(
                "tts_command_failed:"
                + (result.stderr.strip() or result.stdout.strip() or "unknown")
            )
        if not target.exists():
            raise RuntimeError(f"tts_output_not_found:{target}")
        return str(target)


class F5TTSAdapter:
    """项目内固定参考音频的 F5-TTS 适配器。"""

    def __init__(
        self,
        *,
        model: str = "F5TTS_v1_Base",
        python_exe: str | None = None,
        device: str = "cpu",
        remove_silence: bool = False,
        runner_path: str | None = None,
    ) -> None:
        self.model = model
        self.python_exe = python_exe or sys.executable
        self.device = device
        self.remove_silence = remove_silence
        self.runner_path = runner_path

    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _voice_dir(self, project_id: str) -> Path:
        return self._repo_root() / "runtime" / "projects" / project_id / "voice"

    def _reference_audio(self, project_id: str) -> Path:
        configured = os.environ.get("MANIMIND_F5_REFERENCE_AUDIO", "").strip()
        if configured:
            return Path(configured)
        return self._voice_dir(project_id) / "selena_reference.m4a"

    def _reference_text(self, reference_audio: Path) -> str:
        configured = os.environ.get("MANIMIND_F5_REFERENCE_TEXT", "").strip()
        if configured:
            return configured
        configured_file = os.environ.get("MANIMIND_F5_REFERENCE_TEXT_FILE", "").strip()
        if configured_file:
            text_path = Path(configured_file)
        else:
            text_path = reference_audio.with_suffix(".txt")
        if text_path.exists():
            return text_path.read_text(encoding="utf-8").strip()
        return ""

    def _cache_root(self, project_id: str) -> Path:
        configured = os.environ.get("MANIMIND_F5_HF_CACHE_ROOT", "").strip()
        if configured:
            return Path(configured)
        return self._voice_dir(project_id) / "hf-cache"

    def _runner(self) -> Path:
        configured = self.runner_path or os.environ.get("MANIMIND_F5_RUNNER_PATH", "").strip()
        if configured:
            return Path(configured)
        return self._repo_root() / "scripts" / "f5_tts_generate.py"

    def _run_with_live_output(
        self,
        *,
        command: list[str],
        env: dict[str, str],
    ) -> tuple[int, str]:
        proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        lines: list[str] = []
        if proc.stdout is not None:
            for line in proc.stdout:
                text = line.rstrip("\r\n")
                if text:
                    print(f"[f5_tts] {text}", file=sys.stderr, flush=True)
                    lines.append(text)
                    if len(lines) > 500:
                        lines = lines[-500:]
        proc.wait()
        return proc.returncode, "\n".join(lines)

    def synthesize(self, job: TTSJob) -> str:
        target = Path(job.output_path)
        if target.suffix.lower() != ".wav":
            target = target.with_suffix(".wav")
        target.parent.mkdir(parents=True, exist_ok=True)

        reference_audio = self._reference_audio(job.project_id)
        if not reference_audio.exists():
            raise RuntimeError(f"f5_reference_audio_not_found:{reference_audio}")

        runner = self._runner()
        if not runner.exists():
            raise RuntimeError(f"f5_runner_not_found:{runner}")

        cache_root = self._cache_root(job.project_id)
        cache_root.mkdir(parents=True, exist_ok=True)
        gen_file = target.with_suffix(".txt")
        gen_file.write_text(job.script_text, encoding="utf-8")

        command = [
            self.python_exe,
            str(runner),
            "--model",
            self.model,
            "--ref-audio",
            str(reference_audio),
            "--gen-file",
            str(gen_file),
            "--output",
            str(target),
            "--hf-cache-root",
            str(cache_root),
            "--device",
            self.device,
        ]
        reference_text = self._reference_text(reference_audio)
        if reference_text:
            command.extend(["--ref-text", reference_text])
        if self.remove_silence:
            command.append("--remove-silence")

        env = os.environ.copy()
        env.setdefault("HF_HOME", str(cache_root))
        env.setdefault("HUGGINGFACE_HUB_CACHE", str(cache_root / "hub"))
        env.setdefault("TRANSFORMERS_CACHE", str(cache_root / "transformers"))
        live_log = os.environ.get("MANIMIND_F5_LIVE_LOG", "1").strip().lower()
        if live_log in {"0", "false", "off", "no"}:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            return_code = result.returncode
            raw_output = result.stderr.strip() or result.stdout.strip() or ""
        else:
            return_code, raw_output = self._run_with_live_output(command=command, env=env)

        if return_code != 0:
            if len(raw_output) > 1600:
                raw_output = raw_output[-1600:]
            raise RuntimeError(
                "tts_f5_failed:"
                + (raw_output or "unknown")
            )
        if not target.exists():
            raise RuntimeError(f"tts_output_not_found:{target}")
        return str(target)


def build_tts_adapter(provider: str = "noop") -> TTSAdapter:
    """构建 TTS 适配器。"""
    normalized = provider.strip().lower()
    if normalized == "noop":
        return NoopTTSAdapter()
    if normalized in {"powershell", "powershell_sapi", "sapi"}:
        return PowerShellSapiTTSAdapter()
    if normalized == "command":
        template = os.environ.get("MANIMIND_TTS_COMMAND", "").strip()
        if not template:
            raise ValueError("missing_MANIMIND_TTS_COMMAND")
        return CommandTTSAdapter(template)
    if normalized in {"f5_tts", "f5-tts", "f5"}:
        return F5TTSAdapter(
            model=os.environ.get("MANIMIND_F5_MODEL", "F5TTS_v1_Base").strip()
            or "F5TTS_v1_Base",
            python_exe=os.environ.get("MANIMIND_F5_PYTHON_EXE", "").strip() or None,
            device=os.environ.get("MANIMIND_F5_DEVICE", "cpu").strip() or "cpu",
            remove_silence=os.environ.get("MANIMIND_F5_REMOVE_SILENCE", "").strip().lower()
            in {"1", "true", "yes", "on"},
            runner_path=os.environ.get("MANIMIND_F5_RUNNER_PATH", "").strip() or None,
        )
    raise ValueError(f"unsupported_tts_provider: {provider}")
