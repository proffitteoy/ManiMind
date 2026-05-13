"""后处理与交付打包。"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from .artifact_store import has_output_key, output_path_for_key, write_output_key
from .models import ProjectPlan, TaskStatus
from .runtime_store import load_execution_task_snapshot, persist_task_update
from .task_board import update_execution_task_status
from .tts import TTSJob, build_tts_adapter


def _task_by_id(plan: ProjectPlan, task_id: str):
    for task in plan.execution_tasks:
        if task.id == task_id:
            return task
    raise KeyError(f"unknown_task:{task_id}")


def _persist_mutation(plan: ProjectPlan, session_id: str, result) -> None:
    persist_task_update(
        plan=plan,
        session_id=session_id,
        mutation={
            "success": result.success,
            "task_id": result.task_id,
            "from_status": result.from_status,
            "to_status": result.to_status,
            "reason": result.reason,
            "verification_nudge_needed": result.verification_nudge_needed,
        },
    )


def _log_finalize(session_id: str, step: str, message: str) -> None:
    raw = os.environ.get("MANIMIND_PROGRESS_LOG", "1").strip().lower()
    if raw in {"0", "false", "off", "no"}:
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"[manimind][{stamp}][session={session_id}][finalize-{step}] {message}",
        file=sys.stderr,
        flush=True,
    )


def _collect_approved_records(plan: ProjectPlan) -> list[dict[str, Any]]:
    root = Path(plan.runtime_layout.output_dir) / "artifacts"
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        output_key = payload.get("output_key")
        if isinstance(output_key, str) and output_key.endswith(".approved"):
            records.append(
                {
                    "output_key": output_key,
                    "record_path": str(path),
                    "artifact_files": payload.get("artifact_files", []),
                    "summary": payload.get("render_summary"),
                }
            )
    return records


def _load_script_outline(plan: ProjectPlan, session_id: str) -> list[dict[str, Any]]:
    script_key = f"{plan.project_id}.narration.script"
    script_path = output_path_for_key(plan, session_id, script_key)
    if not script_path.exists():
        return []
    try:
        payload = json.loads(script_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    outline = payload.get("script_outline")
    if not isinstance(outline, list):
        return []
    return [item for item in outline if isinstance(item, dict)]


def _read_narration_script(plan: ProjectPlan, session_id: str) -> str:
    outline = _load_script_outline(plan, session_id)
    lines: list[str] = []
    for item in outline:
        narration = item.get("narration")
        if isinstance(narration, str) and narration.strip():
            lines.append(narration.strip())
    return "\n".join(lines)


def _resolve_ffmpeg_path() -> str | None:
    from shutil import which

    direct = which("ffmpeg")
    if direct:
        return direct
    configured = os.environ.get("MANIMIND_FFMPEG_PATH")
    if configured and Path(configured).exists():
        return configured
    candidates = [
        r"D:\ffmpeg\bin\ffmpeg.exe",
        str(
            Path.home()
            / "scoop"
            / "apps"
            / "ffmpeg"
            / "current"
            / "bin"
            / "ffmpeg.exe"
        ),
    ]
    for item in candidates:
        if Path(item).exists():
            return item
    return None


def _collect_segment_videos(
    plan: ProjectPlan,
    approved_records: list[dict[str, Any]],
) -> list[str]:
    ordered_videos: list[str] = []
    record_by_key: dict[str, dict[str, Any]] = {}
    for record in approved_records:
        output_key = record.get("output_key")
        if isinstance(output_key, str):
            record_by_key[output_key] = record

    for segment in plan.segments:
        segment_videos: list[str] = []

        # Manim 产物
        manim_key = f"{plan.project_id}.manim.{segment.id}.approved"
        record = record_by_key.get(manim_key)
        if isinstance(record, dict):
            files = record.get("artifact_files")
            if isinstance(files, list):
                for item in files:
                    if isinstance(item, str) and item.lower().endswith(".mp4") and Path(item).exists():
                        segment_videos.append(item)
                        break

        # HTML 产物：先查 approved record 中的 mp4，没有则现场渲染
        html_key = f"{plan.project_id}.html.{segment.id}.approved"
        record = record_by_key.get(html_key)
        if isinstance(record, dict):
            files = record.get("artifact_files")
            if isinstance(files, list):
                html_mp4: str | None = None
                for item in files:
                    if isinstance(item, str) and item.lower().endswith(".mp4") and Path(item).exists():
                        html_mp4 = item
                        break
                if html_mp4:
                    segment_videos.append(html_mp4)
                else:
                    # 没有现成 mp4，尝试从 HTML 渲染
                    html_video = _render_html_segment_video(plan, segment.id, files)
                    if html_video:
                        segment_videos.append(html_video)

        # SVG 产物（如存在可用 mp4，同样参与拼接）
        svg_key = f"{plan.project_id}.svg.{segment.id}.approved"
        record = record_by_key.get(svg_key)
        if isinstance(record, dict):
            files = record.get("artifact_files")
            if isinstance(files, list):
                for item in files:
                    if isinstance(item, str) and item.lower().endswith(".mp4") and Path(item).exists():
                        segment_videos.append(item)
                        break

        ordered_videos.extend(segment_videos)

    if ordered_videos:
        return ordered_videos

    fallback_videos: list[str] = []
    for record in approved_records:
        files = record.get("artifact_files")
        if not isinstance(files, list):
            continue
        for item in files:
            if isinstance(item, str) and item.lower().endswith(".mp4") and Path(item).exists():
                fallback_videos.append(item)
    return fallback_videos


def _render_html_segment_video(
    plan: ProjectPlan,
    segment_id: str,
    artifact_files: list[str],
) -> str | None:
    """从 HTML artifact 渲染 mp4，返回路径或 None。"""
    html_dir: Path | None = None
    for item in artifact_files:
        if isinstance(item, str) and item.lower().endswith(".html") and Path(item).exists():
            html_dir = Path(item).parent
            break
    if not html_dir:
        return None

    from .worker_adapters import render_html_to_video, WorkerExecutionError

    output_path = html_dir / "scene.mp4"
    try:
        render_html_to_video(html_dir, output_path)
        return str(output_path)
    except (WorkerExecutionError, Exception) as exc:
        _log_finalize("", "html-render", f"segment={segment_id} failed: {exc}")
        return None


def _format_srt_time(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},000"


def _write_subtitle_file(
    *,
    output_dir: Path,
    outline: list[dict[str, Any]],
) -> str | None:
    entries: list[str] = []
    cursor = 0
    index = 1
    for item in outline:
        narration = item.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            continue
        duration = item.get("estimated_seconds")
        if not isinstance(duration, int) or duration <= 0:
            duration = 20
        start = _format_srt_time(cursor)
        cursor += duration
        end = _format_srt_time(cursor)
        entries.append(f"{index}\n{start} --> {end}\n{narration.strip()}\n")
        index += 1

    if not entries:
        return None

    subtitle_dir = output_dir / "subtitles"
    subtitle_dir.mkdir(parents=True, exist_ok=True)
    subtitle_path = subtitle_dir / "narration.srt"
    subtitle_path.write_text("\n".join(entries), encoding="utf-8")
    return str(subtitle_path)


def _is_real_wav(path: str | None) -> bool:
    if not path:
        return False
    target = Path(path)
    if not target.exists() or target.suffix.lower() != ".wav":
        return False
    try:
        header = target.read_bytes()[:4]
    except OSError:
        return False
    return header == b"RIFF"


def align_video_to_audio(video_path: Path, target_duration: float) -> Path:
    """兜底微调：仅处理 < 5% 的时长偏差。超过 5% 应在 review 阶段被拦住。"""
    ffmpeg = _resolve_ffmpeg_path()
    if not ffmpeg or not video_path.exists():
        return video_path

    probe_cmd = [
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(video_path),
    ]
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0 or not result.stdout.strip():
            return video_path
        actual = float(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return video_path

    if target_duration <= 0 or abs(actual - target_duration) < 0.5:
        return video_path

    ratio = actual / target_duration
    output = video_path.with_stem(video_path.stem + "-aligned")

    if 0.95 <= ratio <= 1.05:
        speed = actual / target_duration
        subprocess.run(
            [ffmpeg, "-y", "-i", str(video_path), "-filter:v", f"setpts={1/speed}*PTS", "-an", str(output)],
            capture_output=True, text=True,
        )
    elif ratio < 0.95:
        # 视频太短，末尾补静帧
        pad_duration = target_duration - actual
        subprocess.run(
            [ffmpeg, "-y", "-i", str(video_path), "-vf", f"tpad=stop_mode=clone:stop_duration={pad_duration:.2f}", str(output)],
            capture_output=True, text=True,
        )
    else:
        # 视频太长，裁剪
        subprocess.run(
            [ffmpeg, "-y", "-i", str(video_path), "-t", f"{target_duration:.2f}", "-c", "copy", str(output)],
            capture_output=True, text=True,
        )

    return output if output.exists() else video_path


def _build_final_video(
    *,
    plan: ProjectPlan,
    output_dir: Path,
    approved_records: list[dict[str, Any]],
    tts_output: str | None,
) -> tuple[str | None, str | None]:
    ffmpeg = _resolve_ffmpeg_path()
    if not ffmpeg:
        return None, "ffmpeg_not_found"

    segment_videos = _collect_segment_videos(plan, approved_records)
    if not segment_videos:
        return None, "no_segment_mp4_found"

    video_dir = output_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    concat_file = video_dir / "concat-list.txt"
    concat_file.write_text(
        "\n".join(
            [
                f"file '{item.replace('\\', '/')}'"
                for item in segment_videos
            ]
        ),
        encoding="utf-8",
    )

    merged_video = video_dir / "segments-merged.mp4"
    merge_cmd = [
        ffmpeg,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(merged_video),
    ]
    merge_proc = subprocess.run(
        merge_cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if merge_proc.returncode != 0:
        # copy codec 合并失败时回退到重编码，保证可以出片
        merge_cmd = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(merged_video),
        ]
        merge_proc = subprocess.run(
            merge_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if merge_proc.returncode != 0:
            return None, (
                "ffmpeg_merge_failed:"
                + (merge_proc.stderr.strip() or merge_proc.stdout.strip() or "unknown")
            )

    if _is_real_wav(tts_output):
        final_video = video_dir / "final-with-audio.mp4"
        mux_cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(merged_video),
            "-i",
            str(tts_output),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(final_video),
        ]
        mux_proc = subprocess.run(
            mux_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if mux_proc.returncode == 0:
            return str(final_video), None
        return str(merged_video), (
            "ffmpeg_audio_mux_failed:"
            + (mux_proc.stderr.strip() or mux_proc.stdout.strip() or "unknown")
        )

    return str(merged_video), None


def finalize_delivery(
    plan: ProjectPlan,
    session_id: str,
    *,
    tts_provider: str = "powershell_sapi",
) -> dict[str, Any]:
    """在审核通过后执行 post_produce 与 package。"""
    _log_finalize(
        session_id,
        "start",
        f"project={plan.project_id} tts_provider={tts_provider}",
    )
    load_execution_task_snapshot(plan)
    review_task = _task_by_id(plan, "review.outputs")
    if review_task.status != TaskStatus.COMPLETED:
        _log_finalize(session_id, "start", "blocked: review_not_completed")
        raise RuntimeError("review_not_completed")

    post_task = _task_by_id(plan, "post_produce.outputs")
    if post_task.status != TaskStatus.COMPLETED:
        _log_finalize(session_id, "post", "mark post_produce.outputs in_progress")
        post_result = update_execution_task_status(
            plan=plan,
            task_id=post_task.id,
            new_status=TaskStatus.IN_PROGRESS,
            actor_role="lead",
        )
        _persist_mutation(plan, session_id, post_result)
        if not post_result.success:
            raise RuntimeError(f"post_produce_start_failed:{post_result.reason}")

    approved_records = _collect_approved_records(plan)
    script_outline = _load_script_outline(plan, session_id)
    narration_text = _read_narration_script(plan, session_id)
    _log_finalize(
        session_id,
        "collect",
        (
            "approved_records="
            f"{len(approved_records)} script_segments={len(script_outline)} "
            f"narration_chars={len(narration_text)}"
        ),
    )
    subtitle_path = _write_subtitle_file(
        output_dir=Path(plan.runtime_layout.output_dir),
        outline=script_outline,
    )
    _log_finalize(
        session_id,
        "subtitle",
        f"subtitle_file={subtitle_path or 'none'}",
    )
    tts_output: str | None = None
    tts_error: str | None = None

    # 优先从 timing_manifest 读取已有的 TTS 音频（TTS 已前移到 run_to_review）
    timing_manifest_path = Path(plan.runtime_layout.project_context_dir) / "timing_manifest.json"
    if timing_manifest_path.exists():
        try:
            timing_data = json.loads(timing_manifest_path.read_text(encoding="utf-8"))
            audio_files = [
                seg["audio_path"]
                for seg in timing_data.get("segments", {}).values()
                if isinstance(seg.get("audio_path"), str) and Path(seg["audio_path"]).exists()
            ]
            if audio_files:
                # 拼接所有 segment 音频为一个完整音频
                ffmpeg = _resolve_ffmpeg_path()
                if ffmpeg and len(audio_files) > 1:
                    audio_dir = Path(plan.runtime_layout.output_dir) / "audio"
                    audio_dir.mkdir(parents=True, exist_ok=True)
                    concat_audio = audio_dir / "narration-concat.txt"
                    concat_audio.write_text(
                        "\n".join(f"file '{p.replace(chr(92), '/')}'" for p in audio_files),
                        encoding="utf-8",
                    )
                    merged_audio = audio_dir / "narration.wav"
                    subprocess.run(
                        [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_audio), "-c", "copy", str(merged_audio)],
                        capture_output=True, text=True,
                    )
                    if merged_audio.exists():
                        tts_output = str(merged_audio)
                elif audio_files:
                    tts_output = audio_files[0]
                _log_finalize(session_id, "tts", f"using timing_manifest audio: {tts_output}")
        except (json.JSONDecodeError, KeyError) as exc:
            _log_finalize(session_id, "tts", f"timing_manifest read failed: {exc}")

    # 降级：如果 timing_manifest 不存在或无音频，走原有 TTS 合成
    if not tts_output and narration_text.strip():
        audio_dir = Path(plan.runtime_layout.output_dir) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        target_audio = audio_dir / "narration.wav"
        try:
            _log_finalize(session_id, "tts", "synthesize narration start")
            adapter = build_tts_adapter(tts_provider)
            tts_output = adapter.synthesize(
                TTSJob(
                    project_id=plan.project_id,
                    script_text=narration_text,
                    output_path=str(target_audio),
                    voice="neutral",
                    language="zh-CN",
                )
            )
            _log_finalize(
                session_id,
                "tts",
                f"synthesize done output={tts_output}",
            )
        except Exception as exc:
            tts_error = str(exc)
            _log_finalize(
                session_id,
                "tts",
                f"synthesize failed error={tts_error}",
            )

    _log_finalize(session_id, "video", "building final video")
    final_video, final_video_error = _build_final_video(
        plan=plan,
        output_dir=Path(plan.runtime_layout.output_dir),
        approved_records=approved_records,
        tts_output=tts_output,
    )
    _log_finalize(
        session_id,
        "video",
        (
            "final_video="
            f"{final_video or 'none'} final_video_error={final_video_error or 'none'}"
        ),
    )

    manifest_path = write_output_key(
        plan=plan,
        session_id=session_id,
        key=f"{plan.project_id}.asset.manifest",
        payload={
            "project_id": plan.project_id,
            "session_id": session_id,
            "approved_records": approved_records,
            "tts_output": tts_output,
            "tts_error": tts_error,
            "subtitle_file": subtitle_path,
            "final_video": final_video,
            "final_video_error": final_video_error,
            "summary": {
                "approved_count": len(approved_records),
                "has_audio": tts_output is not None,
                "has_subtitles": subtitle_path is not None,
                "has_final_video": final_video is not None,
            },
        },
    )
    _log_finalize(session_id, "manifest", f"asset_manifest={manifest_path}")

    post_complete = update_execution_task_status(
        plan=plan,
        task_id="post_produce.outputs",
        new_status=TaskStatus.COMPLETED,
        actor_role="lead",
        output_checker=lambda key: has_output_key(plan, session_id, key),
    )
    _persist_mutation(plan, session_id, post_complete)
    if not post_complete.success:
        raise RuntimeError(f"post_produce_complete_failed:{post_complete.reason}")
    _log_finalize(session_id, "post", "post_produce.outputs completed")

    package_start = update_execution_task_status(
        plan=plan,
        task_id="package.delivery",
        new_status=TaskStatus.IN_PROGRESS,
        actor_role="lead",
    )
    _persist_mutation(plan, session_id, package_start)
    if not package_start.success:
        raise RuntimeError(f"package_start_failed:{package_start.reason}")
    _log_finalize(session_id, "package", "package.delivery in_progress")

    package_complete = update_execution_task_status(
        plan=plan,
        task_id="package.delivery",
        new_status=TaskStatus.COMPLETED,
        actor_role="lead",
        output_checker=lambda key: has_output_key(plan, session_id, key),
    )
    _persist_mutation(plan, session_id, package_complete)
    if not package_complete.success:
        raise RuntimeError(f"package_complete_failed:{package_complete.reason}")
    _log_finalize(session_id, "package", "package.delivery completed")

    _log_finalize(session_id, "done", "finalize completed")
    return {
        "project_id": plan.project_id,
        "asset_manifest": str(manifest_path),
        "tts_output": tts_output,
        "tts_error": tts_error,
        "subtitle_file": subtitle_path,
        "final_video": final_video,
        "final_video_error": final_video_error,
        "current_stage": plan.current_stage.value,
    }
