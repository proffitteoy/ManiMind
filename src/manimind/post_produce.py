"""后处理与交付打包。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
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


def _read_narration_script(plan: ProjectPlan, session_id: str) -> str:
    script_key = f"{plan.project_id}.narration.script"
    script_path = output_path_for_key(plan, session_id, script_key)
    if not script_path.exists():
        return ""
    try:
        payload = json.loads(script_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    outline = payload.get("script_outline")
    if not isinstance(outline, list):
        return ""
    lines: list[str] = []
    for item in outline:
        if not isinstance(item, dict):
            continue
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


def _collect_segment_videos(approved_records: list[dict[str, Any]]) -> list[str]:
    videos: list[str] = []
    for record in approved_records:
        files = record.get("artifact_files")
        if not isinstance(files, list):
            continue
        for item in files:
            if not isinstance(item, str):
                continue
            if item.lower().endswith(".mp4") and Path(item).exists():
                videos.append(item)
    return videos


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


def _build_final_video(
    *,
    output_dir: Path,
    approved_records: list[dict[str, Any]],
    tts_output: str | None,
) -> tuple[str | None, str | None]:
    ffmpeg = _resolve_ffmpeg_path()
    if not ffmpeg:
        return None, "ffmpeg_not_found"

    segment_videos = _collect_segment_videos(approved_records)
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
    load_execution_task_snapshot(plan)
    review_task = _task_by_id(plan, "review.outputs")
    if review_task.status != TaskStatus.COMPLETED:
        raise RuntimeError("review_not_completed")

    post_task = _task_by_id(plan, "post_produce.outputs")
    if post_task.status != TaskStatus.COMPLETED:
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
    narration_text = _read_narration_script(plan, session_id)
    tts_output: str | None = None
    tts_error: str | None = None
    if narration_text.strip():
        audio_dir = Path(plan.runtime_layout.output_dir) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        target_audio = audio_dir / "narration.wav"
        try:
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
        except Exception as exc:
            tts_error = str(exc)

    final_video, final_video_error = _build_final_video(
        output_dir=Path(plan.runtime_layout.output_dir),
        approved_records=approved_records,
        tts_output=tts_output,
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
            "final_video": final_video,
            "final_video_error": final_video_error,
            "summary": {
                "approved_count": len(approved_records),
                "has_audio": tts_output is not None,
                "has_final_video": final_video is not None,
            },
        },
    )

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

    package_start = update_execution_task_status(
        plan=plan,
        task_id="package.delivery",
        new_status=TaskStatus.IN_PROGRESS,
        actor_role="lead",
    )
    _persist_mutation(plan, session_id, package_start)
    if not package_start.success:
        raise RuntimeError(f"package_start_failed:{package_start.reason}")

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

    return {
        "project_id": plan.project_id,
        "asset_manifest": str(manifest_path),
        "tts_output": tts_output,
        "tts_error": tts_error,
        "final_video": final_video,
        "final_video_error": final_video_error,
        "current_stage": plan.current_stage.value,
    }
