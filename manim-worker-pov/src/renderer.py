"""Manim 渲染器。"""

from __future__ import annotations

from pathlib import Path
import subprocess


def render_scene(
    scene_file: Path,
    scene_class: str,
    quality: str = "ql",
    timeout: int = 120,
    media_dir: Path | None = None,
) -> tuple[bool, str]:
    """执行 manim 渲染并返回成功标记与日志。"""
    cmd = [
        "manim",
        f"-{quality}",
        str(scene_file),
        scene_class,
    ]
    if media_dir is not None:
        cmd.extend(["--media_dir", str(media_dir)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False, "RENDER_TIMEOUT"

    log = f"{result.stdout}\n{result.stderr}"
    return result.returncode == 0, log
