"""真实 worker 适配层：HTML / SVG / Manim。"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from .models import ExecutionTask, ProjectPlan, SegmentSpec


def _safe_id(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "-", value).strip("-").lower() or "segment"


def _strip_formula(value: str) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    compact = compact.replace("\\", " ")
    return compact[:120]


def _find_tool(primary_name: str, env_var: str) -> str | None:
    from shutil import which

    direct = which(primary_name)
    if direct:
        return direct
    configured = os.environ.get(env_var)
    if configured and Path(configured).exists():
        return configured
    return None


@dataclass(slots=True)
class WorkerRunResult:
    worker_role: str
    segment_id: str
    summary: str
    artifact_files: list[str]
    metadata: dict[str, Any]


class WorkerExecutionError(RuntimeError):
    pass


class HtmlWorkerAdapter:
    def render(
        self,
        *,
        plan: ProjectPlan,
        segment: SegmentSpec,
        task: ExecutionTask,
    ) -> WorkerRunResult:
        out_dir = Path(plan.runtime_layout.output_dir) / "html" / _safe_id(segment.id)
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / "index.html"

        formula_items = "".join(
            f"<li><code>{escape(item)}</code></li>"
            for item in segment.formulas[:6]
        ) or "<li>（无公式）</li>"
        note_items = "".join(
            f"<li>{escape(item)}</li>"
            for item in segment.html_motion_notes[:6]
        ) or "<li>（无）</li>"
        payload = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(segment.title)} | ManiMind</title>
  <style>
    :root {{
      --bg1: #f0f7ff;
      --bg2: #edf6ef;
      --ink: #12212f;
      --accent: #1d4ed8;
      --panel: rgba(255,255,255,0.88);
    }}
    body {{
      margin: 0; font-family: "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at 10% 10%, #dbeafe 0%, transparent 35%),
                  radial-gradient(circle at 80% 20%, #dcfce7 0%, transparent 30%),
                  linear-gradient(180deg, var(--bg1), var(--bg2));
      min-height: 100vh;
      display: grid; place-items: center;
      padding: 20px;
    }}
    .card {{
      width: min(920px, 100%);
      border: 1px solid rgba(17,24,39,0.08);
      border-radius: 20px;
      background: var(--panel);
      box-shadow: 0 20px 60px rgba(15,23,42,0.08);
      padding: 28px;
      animation: rise 560ms ease-out;
    }}
    h1 {{ margin: 0 0 10px; font-size: 30px; }}
    h2 {{ margin: 18px 0 8px; font-size: 18px; color: var(--accent); }}
    p {{ margin: 0; line-height: 1.8; }}
    ul {{ margin: 8px 0 0; padding-left: 20px; line-height: 1.8; }}
    code {{ background: #eef2ff; padding: 2px 6px; border-radius: 6px; }}
    @keyframes rise {{
      from {{ transform: translateY(8px); opacity: 0; }}
      to {{ transform: translateY(0); opacity: 1; }}
    }}
  </style>
</head>
<body>
  <article class="card">
    <h1>{escape(segment.title)}</h1>
    <p>{escape(segment.goal)}</p>
    <h2>叙述脚本</h2>
    <p>{escape(segment.narration)}</p>
    <h2>公式</h2>
    <ul>{formula_items}</ul>
    <h2>动效备注</h2>
    <ul>{note_items}</ul>
  </article>
</body>
</html>
"""
        html_path.write_text(payload, encoding="utf-8")
        return WorkerRunResult(
            worker_role=task.owner_role,
            segment_id=segment.id,
            summary=f"HTML rendered: {segment.title}",
            artifact_files=[str(html_path)],
            metadata={
                "worker": "html",
                "segment_id": segment.id,
                "title": segment.title,
            },
        )


class SvgWorkerAdapter:
    def render(
        self,
        *,
        plan: ProjectPlan,
        segment: SegmentSpec,
        task: ExecutionTask,
    ) -> WorkerRunResult:
        out_dir = Path(plan.runtime_layout.output_dir) / "svg" / _safe_id(segment.id)
        out_dir.mkdir(parents=True, exist_ok=True)
        svg_path = out_dir / "scene.svg"

        title = escape(segment.title)
        goal = escape(segment.goal[:88])
        svg = f"""<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#e0f2fe"/>
      <stop offset="100%" stop-color="#ecfeff"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="720" fill="url(#bg)"/>
  <rect x="120" y="120" width="1040" height="480" rx="28" fill="white" fill-opacity="0.86" stroke="#cbd5e1"/>
  <text x="170" y="220" font-size="54" fill="#0f172a" font-family="Segoe UI, Microsoft YaHei">{title}</text>
  <text x="170" y="300" font-size="32" fill="#1d4ed8" font-family="Segoe UI, Microsoft YaHei">{goal}</text>
  <circle cx="1020" cy="230" r="26" fill="#2563eb">
    <animate attributeName="r" values="24;32;24" dur="2.2s" repeatCount="indefinite"/>
  </circle>
  <rect x="170" y="360" width="860" height="16" rx="8" fill="#bfdbfe">
    <animate attributeName="width" values="320;860;320" dur="2.8s" repeatCount="indefinite"/>
  </rect>
  <rect x="170" y="420" width="700" height="16" rx="8" fill="#93c5fd">
    <animate attributeName="width" values="220;700;220" dur="2.4s" repeatCount="indefinite"/>
  </rect>
</svg>
"""
        svg_path.write_text(svg, encoding="utf-8")
        return WorkerRunResult(
            worker_role=task.owner_role,
            segment_id=segment.id,
            summary=f"SVG rendered: {segment.title}",
            artifact_files=[str(svg_path)],
            metadata={
                "worker": "svg",
                "segment_id": segment.id,
                "title": segment.title,
            },
        )


class ManimWorkerAdapter:
    def __init__(self, quality: str = "ql", timeout: int = 240) -> None:
        self.quality = quality
        self.timeout = timeout

    def _scene_code(self, segment: SegmentSpec, class_name: str) -> str:
        formula_lines = [_strip_formula(item) for item in segment.formulas[:3]]
        if not formula_lines:
            formula_lines = ["（本段无显式公式，强调概念解释）"]
        rendered_formulas = "\n".join(
            [
                "        formula_{idx} = Text({text!r}, font_size=30).next_to(prev, DOWN, aligned_edge=LEFT)".format(
                    idx=i,
                    text=f"公式 {i + 1}: {line}",
                )
                + "\n        self.play(FadeIn(formula_{idx}, shift=UP * 0.2), run_time=0.5)\n        prev = formula_{idx}".format(
                    idx=i
                )
                for i, line in enumerate(formula_lines)
            ]
        )

        return f"""from manim import *

class {class_name}(Scene):
    def construct(self):
        title = Text({segment.title!r}, font_size=48)
        goal = Text({segment.goal!r}, font_size=30).next_to(title, DOWN)
        self.play(FadeIn(title, shift=UP * 0.3), run_time=0.6)
        self.play(FadeIn(goal, shift=UP * 0.2), run_time=0.6)
        prev = goal
{rendered_formulas}
        ending = Text("ManiMind 渲染验证通过", font_size=28).next_to(prev, DOWN)
        self.play(FadeIn(ending, shift=UP * 0.2), run_time=0.6)
        self.wait(0.4)
"""

    def render(
        self,
        *,
        plan: ProjectPlan,
        segment: SegmentSpec,
        task: ExecutionTask,
    ) -> WorkerRunResult:
        manim_bin = _find_tool("manim", "MANIMIND_MANIM_PATH")
        if not manim_bin:
            raise WorkerExecutionError("missing_manim_executable")

        seg = _safe_id(segment.id)
        out_dir = Path(plan.runtime_layout.output_dir) / "manim" / seg
        out_dir.mkdir(parents=True, exist_ok=True)
        class_name = f"Segment{re.sub(r'[^0-9A-Za-z]+', '', seg).title()}Scene"
        if not class_name[7:]:
            class_name = "SegmentScene"

        scene_file = out_dir / "scene.py"
        log_file = out_dir / "render.log"
        media_dir = out_dir / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        scene_file.write_text(self._scene_code(segment, class_name), encoding="utf-8")

        cmd = [
            manim_bin,
            f"-{self.quality}",
            str(scene_file),
            class_name,
            "--media_dir",
            str(media_dir),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout,
        )
        combined_log = f"{proc.stdout}\n{proc.stderr}"
        log_file.write_text(combined_log, encoding="utf-8")
        if proc.returncode != 0:
            raise WorkerExecutionError(f"manim_render_failed:{log_file}")

        mp4_candidates = sorted(
            media_dir.rglob(f"{class_name}.mp4"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if not mp4_candidates:
            mp4_candidates = sorted(
                media_dir.rglob("*.mp4"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
        if not mp4_candidates:
            raise WorkerExecutionError("manim_output_not_found")

        source_mp4 = mp4_candidates[0]
        output_mp4 = out_dir / "scene.mp4"
        shutil.copyfile(source_mp4, output_mp4)
        return WorkerRunResult(
            worker_role=task.owner_role,
            segment_id=segment.id,
            summary=f"Manim rendered: {segment.title}",
            artifact_files=[str(scene_file), str(output_mp4), str(log_file)],
            metadata={
                "worker": "manim",
                "segment_id": segment.id,
                "title": segment.title,
                "scene_class": class_name,
                "render_command": cmd,
            },
        )


def render_with_worker(
    *,
    plan: ProjectPlan,
    segment: SegmentSpec,
    task: ExecutionTask,
) -> WorkerRunResult:
    if task.owner_role == "html_worker":
        return HtmlWorkerAdapter().render(plan=plan, segment=segment, task=task)
    if task.owner_role == "svg_worker":
        return SvgWorkerAdapter().render(plan=plan, segment=segment, task=task)
    if task.owner_role == "manim_worker":
        return ManimWorkerAdapter().render(plan=plan, segment=segment, task=task)
    raise WorkerExecutionError(f"unsupported_worker_role:{task.owner_role}")
