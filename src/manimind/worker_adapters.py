"""真实 worker 适配层：HTML / SVG / Manim。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any

from .llm_client import (
    LLMRequestError,
    generate_text_for_role,
    load_llm_runtime_config,
)
from .models import ExecutionTask, PipelineStage, ProjectPlan, SegmentSpec
from .prompt_system import (
    build_prompt_bundle,
    html_worker_recipe,
    manim_generate_recipe,
    manim_repair_recipe,
    svg_worker_recipe,
)
from .runtime_store import persist_context_packet
from .trace_store import LLMTrace, persist_llm_trace


def _safe_id(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z_-]+", "-", value).strip("-").lower() or "segment"


def _find_tool(primary_name: str, env_var: str) -> str | None:
    from shutil import which

    direct = which(primary_name)
    if direct:
        return direct
    configured = os.environ.get(env_var)
    if configured and Path(configured).exists():
        return configured
    return None


def _strip_markdown_fences(text: str) -> str:
    stripped = text.strip()
    fenced = re.search(
        r"```(?:html|svg|xml|python)?\s*(.*?)```",
        stripped,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        return fenced.group(1).strip()
    return stripped


def _storyboard_entry(
    shared_context: dict[str, Any],
    segment_id: str,
) -> dict[str, Any]:
    outline = shared_context.get("storyboard_outline")
    if not isinstance(outline, list):
        return {}
    for item in outline:
        if not isinstance(item, dict):
            continue
        if item.get("segment_id") == segment_id:
            return item
    return {}


def _formula_catalog(shared_context: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = shared_context.get("formula_catalog")
    if isinstance(catalog, list):
        return [item for item in catalog if isinstance(item, dict)]
    return []


def _ensure_html_document(text: str) -> str:
    candidate = _strip_markdown_fences(text)
    lowered = candidate.lower()
    if "<html" not in lowered or "<body" not in lowered:
        raise WorkerExecutionError("html_output_not_document")
    if "<!doctype html" not in lowered:
        raise WorkerExecutionError("html_missing_doctype")
    return candidate + ("\n" if not candidate.endswith("\n") else "")


def _ensure_svg_document(text: str) -> str:
    candidate = _strip_markdown_fences(text)
    if not candidate.lstrip().startswith("<svg"):
        raise WorkerExecutionError("svg_output_not_document")
    return candidate + ("\n" if not candidate.endswith("\n") else "")


def _validate_scene_code(code: str, scene_class: str) -> None:
    class_defs = re.findall(
        r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        code,
        flags=re.MULTILINE,
    )
    if len(class_defs) != 1:
        raise WorkerExecutionError(
            f"expected_single_scene_class:found_{len(class_defs)}"
        )
    if class_defs[0] != scene_class:
        raise WorkerExecutionError(
            f"scene_class_mismatch:expected_{scene_class}:got_{class_defs[0]}"
        )
    if "from manim import *" not in code:
        raise WorkerExecutionError("missing_manim_star_import")


def _classify_manim_error(render_log: str) -> str:
    lowered = render_log.lower()
    if "latex error" in lowered or "tex" in lowered:
        return "latex_error"
    if "attributeerror" in lowered:
        return "attribute_error"
    if "syntaxerror" in lowered:
        return "syntax_error"
    if "typeerror" in lowered:
        return "type_error"
    if "nameerror" in lowered:
        return "name_error"
    if "pre_render_validation_error" in lowered:
        return "validation_error"
    return "render_error"


def _locate_rendered_video(media_dir: Path, scene_class: str) -> Path | None:
    exact_matches = sorted(
        media_dir.rglob(f"{scene_class}.mp4"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if exact_matches:
        return exact_matches[0]
    any_matches = sorted(
        media_dir.rglob("*.mp4"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if any_matches:
        return any_matches[0]
    return None


def _context_keys_from_packet(packet: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    specs = packet.get("context_specs")
    if not isinstance(specs, list):
        return keys
    for item in specs:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if isinstance(key, str):
            keys.append(key)
    return keys


def _render_scene(
    *,
    manim_bin: str,
    scene_file: Path,
    scene_class: str,
    quality: str,
    timeout: int,
    media_dir: Path,
) -> tuple[bool, str]:
    cmd = [
        manim_bin,
        f"-{quality}",
        str(scene_file),
        scene_class,
        "--media_dir",
        str(media_dir),
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    combined_log = f"{proc.stdout}\n{proc.stderr}"
    return proc.returncode == 0, combined_log


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
        session_id: str,
        shared_context: dict[str, Any],
        prompt_cache: Any | None = None,
    ) -> WorkerRunResult:
        out_dir = Path(plan.runtime_layout.output_dir) / "html" / _safe_id(segment.id)
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / "index.html"

        payload = {
            "project_id": plan.project_id,
            "project_title": plan.title,
            "audience": plan.source_bundle.audience,
            "style_refs": plan.source_bundle.style_refs,
            "style_guide": shared_context.get("style_guide"),
            "segment": segment.to_dict(),
            "task": task.to_dict(),
            "research_summary": shared_context.get("research_summary"),
            "glossary_terms": shared_context.get("glossary_terms"),
            "formula_catalog": _formula_catalog(shared_context),
            "planner_brief": shared_context.get("planner_brief"),
            "storyboard_entry": _storyboard_entry(shared_context, segment.id),
        }
        bundle = build_prompt_bundle(
            plan=plan,
            session_id=session_id,
            role_id=task.owner_role,
            stage=PipelineStage.DISPATCH,
            recipe=html_worker_recipe(),
            payload=payload,
            cache=prompt_cache,
        )
        persist_context_packet(
            plan=plan,
            session_id=session_id,
            packet=bundle.packet,
            prompt_sections=bundle.prompt_sections,
        )
        cfg = load_llm_runtime_config()
        t0 = time.perf_counter()
        try:
            html_text, meta = generate_text_for_role(
                cfg=cfg,
                role_id=task.owner_role,
                instructions=bundle.system_prompt,
                prompt=bundle.user_prompt,
            )
        except LLMRequestError as exc:
            persist_llm_trace(
                plan=plan,
                session_id=session_id,
                trace=LLMTrace(
                    trace_id=f"{task.id}-{int(time.time() * 1000)}",
                    role_id=task.owner_role,
                    stage=PipelineStage.DISPATCH.value,
                    task_id=task.id,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    input_context_keys=_context_keys_from_packet(bundle.packet),
                    prompt_sections=bundle.prompt_sections,
                    model_route="worker",
                    model_output_excerpt=str(exc)[:2000],
                    parsed_output_keys=[],
                    schema_validation="n/a",
                    artifact_files=[],
                    render_command=None,
                    render_exit_code=None,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    token_usage=None,
                    retry_count=0,
                    failure_reason=f"worker_output_invalid:{exc}",
                ),
            )
            raise WorkerExecutionError(f"html_llm_failed:{exc}") from exc

        persist_llm_trace(
            plan=plan,
            session_id=session_id,
            trace=LLMTrace(
                trace_id=f"{task.id}-{int(time.time() * 1000)}",
                role_id=task.owner_role,
                stage=PipelineStage.DISPATCH.value,
                task_id=task.id,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                input_context_keys=_context_keys_from_packet(bundle.packet),
                prompt_sections=bundle.prompt_sections,
                model_route=str(meta.get("route") or "worker"),
                model_output_excerpt=html_text[:2000],
                parsed_output_keys=[],
                schema_validation="n/a",
                artifact_files=[],
                render_command=None,
                render_exit_code=None,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                token_usage=None,
                retry_count=0,
                failure_reason=None,
            ),
        )

        html_path.write_text(_ensure_html_document(html_text), encoding="utf-8")

        artifact_files = [str(html_path)]
        video_path = out_dir / "scene.mp4"
        try:
            render_html_to_video(out_dir, video_path)
            artifact_files.append(str(video_path))
        except (WorkerExecutionError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            artifact_files.append(f"html_video_render_skipped:{exc}")

        return WorkerRunResult(
            worker_role=task.owner_role,
            segment_id=segment.id,
            summary=f"HTML rendered: {segment.title}",
            artifact_files=artifact_files,
            metadata={
                "worker": "html",
                "segment_id": segment.id,
                "title": segment.title,
                "llm_generation": meta,
                "has_video": video_path.exists(),
            },
        )


class SvgWorkerAdapter:
    def render(
        self,
        *,
        plan: ProjectPlan,
        segment: SegmentSpec,
        task: ExecutionTask,
        session_id: str,
        shared_context: dict[str, Any],
        prompt_cache: Any | None = None,
    ) -> WorkerRunResult:
        out_dir = Path(plan.runtime_layout.output_dir) / "svg" / _safe_id(segment.id)
        out_dir.mkdir(parents=True, exist_ok=True)
        svg_path = out_dir / "scene.svg"

        payload = {
            "project_id": plan.project_id,
            "project_title": plan.title,
            "audience": plan.source_bundle.audience,
            "style_refs": plan.source_bundle.style_refs,
            "style_guide": shared_context.get("style_guide"),
            "segment": segment.to_dict(),
            "task": task.to_dict(),
            "research_summary": shared_context.get("research_summary"),
            "glossary_terms": shared_context.get("glossary_terms"),
            "formula_catalog": _formula_catalog(shared_context),
            "planner_brief": shared_context.get("planner_brief"),
            "storyboard_entry": _storyboard_entry(shared_context, segment.id),
        }
        bundle = build_prompt_bundle(
            plan=plan,
            session_id=session_id,
            role_id=task.owner_role,
            stage=PipelineStage.DISPATCH,
            recipe=svg_worker_recipe(),
            payload=payload,
            cache=prompt_cache,
        )
        persist_context_packet(
            plan=plan,
            session_id=session_id,
            packet=bundle.packet,
            prompt_sections=bundle.prompt_sections,
        )
        cfg = load_llm_runtime_config()
        t0 = time.perf_counter()
        try:
            svg_text, meta = generate_text_for_role(
                cfg=cfg,
                role_id=task.owner_role,
                instructions=bundle.system_prompt,
                prompt=bundle.user_prompt,
            )
        except LLMRequestError as exc:
            persist_llm_trace(
                plan=plan,
                session_id=session_id,
                trace=LLMTrace(
                    trace_id=f"{task.id}-{int(time.time() * 1000)}",
                    role_id=task.owner_role,
                    stage=PipelineStage.DISPATCH.value,
                    task_id=task.id,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    input_context_keys=_context_keys_from_packet(bundle.packet),
                    prompt_sections=bundle.prompt_sections,
                    model_route="worker",
                    model_output_excerpt=str(exc)[:2000],
                    parsed_output_keys=[],
                    schema_validation="n/a",
                    artifact_files=[],
                    render_command=None,
                    render_exit_code=None,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    token_usage=None,
                    retry_count=0,
                    failure_reason=f"worker_output_invalid:{exc}",
                ),
            )
            raise WorkerExecutionError(f"svg_llm_failed:{exc}") from exc

        persist_llm_trace(
            plan=plan,
            session_id=session_id,
            trace=LLMTrace(
                trace_id=f"{task.id}-{int(time.time() * 1000)}",
                role_id=task.owner_role,
                stage=PipelineStage.DISPATCH.value,
                task_id=task.id,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                input_context_keys=_context_keys_from_packet(bundle.packet),
                prompt_sections=bundle.prompt_sections,
                model_route=str(meta.get("route") or "worker"),
                model_output_excerpt=svg_text[:2000],
                parsed_output_keys=[],
                schema_validation="n/a",
                artifact_files=[],
                render_command=None,
                render_exit_code=None,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                token_usage=None,
                retry_count=0,
                failure_reason=None,
            ),
        )

        svg_path.write_text(_ensure_svg_document(svg_text), encoding="utf-8")
        return WorkerRunResult(
            worker_role=task.owner_role,
            segment_id=segment.id,
            summary=f"SVG rendered: {segment.title}",
            artifact_files=[str(svg_path)],
            metadata={
                "worker": "svg",
                "segment_id": segment.id,
                "title": segment.title,
                "llm_generation": meta,
            },
        )


class ManimWorkerAdapter:
    def __init__(
        self,
        quality: str = "ql",
        timeout: int = 240,
        max_repair_rounds: int = 3,
    ) -> None:
        self.quality = quality
        self.timeout = timeout
        self.max_repair_rounds = max_repair_rounds

    def _scene_class_name(self, segment: SegmentSpec) -> str:
        seg = _safe_id(segment.id)
        class_name = f"Segment{re.sub(r'[^0-9A-Za-z]+', '', seg).title()}Scene"
        if not class_name[7:]:
            return "SegmentScene"
        return class_name

    def _scene_payload(
        self,
        *,
        plan: ProjectPlan,
        segment: SegmentSpec,
        task: ExecutionTask,
        scene_class: str,
        shared_context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "project_id": plan.project_id,
            "project_title": plan.title,
            "audience": plan.source_bundle.audience,
            "style_refs": plan.source_bundle.style_refs,
            "style_guide": shared_context.get("style_guide"),
            "segment": segment.to_dict(),
            "task": task.to_dict(),
            "scene_class": scene_class,
            "render_quality": self.quality,
            "research_summary": shared_context.get("research_summary"),
            "glossary_terms": shared_context.get("glossary_terms"),
            "formula_catalog": _formula_catalog(shared_context),
            "planner_brief": shared_context.get("planner_brief"),
            "storyboard_entry": _storyboard_entry(shared_context, segment.id),
        }

    def render(
        self,
        *,
        plan: ProjectPlan,
        segment: SegmentSpec,
        task: ExecutionTask,
        session_id: str,
        shared_context: dict[str, Any],
        prompt_cache: Any | None = None,
    ) -> WorkerRunResult:
        manim_bin = _find_tool("manim", "MANIMIND_MANIM_PATH")
        if not manim_bin:
            raise WorkerExecutionError("missing_manim_executable")

        scene_class = self._scene_class_name(segment)
        seg = _safe_id(segment.id)
        out_dir = Path(plan.runtime_layout.output_dir) / "manim" / seg
        out_dir.mkdir(parents=True, exist_ok=True)
        media_dir = out_dir / "media"
        media_dir.mkdir(parents=True, exist_ok=True)

        scene_payload = self._scene_payload(
            plan=plan,
            segment=segment,
            task=task,
            scene_class=scene_class,
            shared_context=shared_context,
        )
        bundle = build_prompt_bundle(
            plan=plan,
            session_id=session_id,
            role_id=task.owner_role,
            stage=PipelineStage.DISPATCH,
            recipe=manim_generate_recipe(),
            payload=scene_payload,
            cache=prompt_cache,
        )
        persist_context_packet(
            plan=plan,
            session_id=session_id,
            packet=bundle.packet,
            prompt_sections=bundle.prompt_sections,
        )

        cfg = load_llm_runtime_config()
        t0 = time.perf_counter()
        try:
            code, meta = generate_text_for_role(
                cfg=cfg,
                role_id=task.owner_role,
                instructions=bundle.system_prompt,
                prompt=bundle.user_prompt,
            )
        except LLMRequestError as exc:
            persist_llm_trace(
                plan=plan,
                session_id=session_id,
                trace=LLMTrace(
                    trace_id=f"{task.id}-{int(time.time() * 1000)}",
                    role_id=task.owner_role,
                    stage=PipelineStage.DISPATCH.value,
                    task_id=task.id,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    input_context_keys=_context_keys_from_packet(bundle.packet),
                    prompt_sections=bundle.prompt_sections,
                    model_route="worker",
                    model_output_excerpt=str(exc)[:2000],
                    parsed_output_keys=[],
                    schema_validation="n/a",
                    artifact_files=[],
                    render_command=None,
                    render_exit_code=None,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    token_usage=None,
                    retry_count=0,
                    failure_reason=f"worker_output_invalid:{exc}",
                ),
            )
            raise WorkerExecutionError(f"manim_llm_failed:{exc}") from exc

        persist_llm_trace(
            plan=plan,
            session_id=session_id,
            trace=LLMTrace(
                trace_id=f"{task.id}-{int(time.time() * 1000)}",
                role_id=task.owner_role,
                stage=PipelineStage.DISPATCH.value,
                task_id=task.id,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                input_context_keys=_context_keys_from_packet(bundle.packet),
                prompt_sections=bundle.prompt_sections,
                model_route=str(meta.get("route") or "worker"),
                model_output_excerpt=code[:2000],
                parsed_output_keys=[],
                schema_validation="n/a",
                artifact_files=[],
                render_command=None,
                render_exit_code=None,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                token_usage=None,
                retry_count=0,
                failure_reason=None,
            ),
        )

        current_code = _strip_markdown_fences(code) + "\n"
        final_log = ""
        last_meta = meta

        for attempt in range(1, self.max_repair_rounds + 2):
            attempt_scene = out_dir / f"attempt_{attempt:03d}.py"
            attempt_log = out_dir / f"attempt_{attempt:03d}.log"
            attempt_scene.write_text(current_code, encoding="utf-8")

            try:
                _validate_scene_code(current_code, scene_class)
                success, render_log = _render_scene(
                    manim_bin=manim_bin,
                    scene_file=attempt_scene,
                    scene_class=scene_class,
                    quality=self.quality,
                    timeout=self.timeout,
                    media_dir=media_dir,
                )
            except WorkerExecutionError as exc:
                success = False
                render_log = f"PRE_RENDER_VALIDATION_ERROR: {exc}"

            attempt_log.write_text(render_log, encoding="utf-8")
            final_log = render_log

            if success:
                source_mp4 = _locate_rendered_video(media_dir, scene_class)
                if source_mp4 is None:
                    raise WorkerExecutionError("manim_output_not_found")
                output_scene = out_dir / "scene.py"
                output_log = out_dir / "render.log"
                output_mp4 = out_dir / "scene.mp4"
                output_scene.write_text(current_code, encoding="utf-8")
                output_log.write_text(render_log, encoding="utf-8")
                shutil.copyfile(source_mp4, output_mp4)
                return WorkerRunResult(
                    worker_role=task.owner_role,
                    segment_id=segment.id,
                    summary=f"Manim rendered: {segment.title}",
                    artifact_files=[
                        str(output_scene),
                        str(output_mp4),
                        str(output_log),
                    ],
                    metadata={
                        "worker": "manim",
                        "segment_id": segment.id,
                        "title": segment.title,
                        "scene_class": scene_class,
                        "llm_generation": last_meta,
                        "attempts": attempt,
                    },
                )

            if attempt > self.max_repair_rounds:
                raise WorkerExecutionError(
                    f"manim_render_failed:{attempt_log}:{_classify_manim_error(render_log)}"
                )

            repair_payload = {
                **scene_payload,
                "previous_code": current_code,
                "render_log": render_log,
                "error_type": _classify_manim_error(render_log),
                "attempt": attempt,
            }
            repair_bundle = build_prompt_bundle(
                plan=plan,
                session_id=session_id,
                role_id=task.owner_role,
                stage=PipelineStage.DISPATCH,
                recipe=manim_repair_recipe(),
                payload=repair_payload,
                cache=prompt_cache,
            )
            persist_context_packet(
                plan=plan,
                session_id=session_id,
                packet=repair_bundle.packet,
                prompt_sections=repair_bundle.prompt_sections,
            )
            repair_t0 = time.perf_counter()
            try:
                repaired_code, last_meta = generate_text_for_role(
                    cfg=cfg,
                    role_id=task.owner_role,
                    instructions=repair_bundle.system_prompt,
                    prompt=repair_bundle.user_prompt,
                )
            except LLMRequestError as exc:
                persist_llm_trace(
                    plan=plan,
                    session_id=session_id,
                    trace=LLMTrace(
                        trace_id=f"{task.id}-repair-{attempt}-{int(time.time() * 1000)}",
                        role_id=task.owner_role,
                        stage=PipelineStage.DISPATCH.value,
                        task_id=task.id,
                        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        input_context_keys=_context_keys_from_packet(repair_bundle.packet),
                        prompt_sections=repair_bundle.prompt_sections,
                        model_route="worker",
                        model_output_excerpt=str(exc)[:2000],
                        parsed_output_keys=[],
                        schema_validation="n/a",
                        artifact_files=[],
                        render_command=None,
                        render_exit_code=None,
                        duration_ms=int((time.perf_counter() - repair_t0) * 1000),
                        token_usage=None,
                        retry_count=attempt,
                        failure_reason=f"worker_output_invalid:{exc}",
                    ),
                )
                raise WorkerExecutionError(f"manim_repair_failed:{exc}") from exc
            persist_llm_trace(
                plan=plan,
                session_id=session_id,
                trace=LLMTrace(
                    trace_id=f"{task.id}-repair-{attempt}-{int(time.time() * 1000)}",
                    role_id=task.owner_role,
                    stage=PipelineStage.DISPATCH.value,
                    task_id=task.id,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    input_context_keys=_context_keys_from_packet(repair_bundle.packet),
                    prompt_sections=repair_bundle.prompt_sections,
                    model_route=str(last_meta.get("route") or "worker"),
                    model_output_excerpt=repaired_code[:2000],
                    parsed_output_keys=[],
                    schema_validation="n/a",
                    artifact_files=[],
                    render_command=None,
                    render_exit_code=None,
                    duration_ms=int((time.perf_counter() - repair_t0) * 1000),
                    token_usage=None,
                    retry_count=attempt,
                    failure_reason=None,
                ),
            )
            current_code = _strip_markdown_fences(repaired_code) + "\n"

        raise WorkerExecutionError("manim_repair_loop_unreachable")


def render_with_worker(
    *,
    plan: ProjectPlan,
    segment: SegmentSpec,
    task: ExecutionTask,
    session_id: str,
    shared_context: dict[str, Any],
    prompt_cache: Any | None = None,
) -> WorkerRunResult:
    if task.owner_role == "html_worker":
        return HtmlWorkerAdapter().render(
            plan=plan,
            segment=segment,
            task=task,
            session_id=session_id,
            shared_context=shared_context,
            prompt_cache=prompt_cache,
        )
    if task.owner_role == "svg_worker":
        return SvgWorkerAdapter().render(
            plan=plan,
            segment=segment,
            task=task,
            session_id=session_id,
            shared_context=shared_context,
            prompt_cache=prompt_cache,
        )
    if task.owner_role == "manim_worker":
        return ManimWorkerAdapter().render(
            plan=plan,
            segment=segment,
            task=task,
            session_id=session_id,
            shared_context=shared_context,
            prompt_cache=prompt_cache,
        )
    raise WorkerExecutionError(f"unsupported_worker_role:{task.owner_role}")


def render_html_to_video(html_dir: Path, output_path: Path, *, fps: int = 30) -> Path:
    """用 puppeteer-core + ffmpeg 将 HTML composition 渲染为 mp4。

    通过 scripts/html_to_video.js 逐帧截取 GSAP timeline 并编码。
    """
    from .bootstrap import repo_root

    node_bin = _find_tool("node", "MANIMIND_NODE_PATH") or "node"
    script = repo_root() / "scripts" / "html_to_video.js"
    if not script.exists():
        raise WorkerExecutionError("html_to_video_script_not_found")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        node_bin,
        str(script),
        str(html_dir),
        str(output_path),
        "--fps", str(fps),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if result.returncode != 0:
        raise WorkerExecutionError(
            f"html_render_failed: exit={result.returncode} stderr={result.stderr[:800]}"
        )
    if not output_path.exists():
        raise WorkerExecutionError("html_render_no_output")
    return output_path
