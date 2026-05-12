"""执行器：推进主链路到审核阶段，并产出真实 worker 资产。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from .artifact_store import has_output_key, write_output_key
from .context_assembly import PromptSectionCache
from .ingest import concatenate_documents, load_source_documents
from .llm_client import (
    LLMRequestError,
    LLMRuntimeConfig,
    generate_json_for_role,
    load_llm_runtime_config,
)
from .models import EventType, ExecutionTask, PipelineStage, ProjectPlan, TaskStatus
from .prompt_system import (
    PromptRecipe,
    build_prompt_bundle,
    coordinator_recipe,
    explorer_recipe,
    lead_summary_recipe,
    planner_recipe,
    reviewer_recipe,
)
from .runtime_store import (
    load_execution_task_snapshot,
    persist_agent_message,
    persist_context_packet,
    persist_plan_snapshot,
    persist_task_update,
)
from .task_board import update_execution_task_status
from .worker_adapters import WorkerExecutionError, render_with_worker


def _log_progress(session_id: str, step: str, message: str) -> None:
    raw = os.environ.get("MANIMIND_PROGRESS_LOG", "1").strip().lower()
    if raw in {"0", "false", "off", "no"}:
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"[manimind][{stamp}][session={session_id}][{step}] {message}",
        file=sys.stderr,
        flush=True,
    )


def _extract_formulas(text: str) -> list[str]:
    formulas: list[str] = []
    for match in re.findall(r"\$\$(.+?)\$\$", text, flags=re.DOTALL):
        value = match.strip()
        if value:
            formulas.append(value)
    if formulas:
        return formulas[:16]

    for match in re.findall(r"\$(.+?)\$", text):
        value = match.strip()
        if value:
            formulas.append(value)
    return formulas[:16]


def _clean_glossary_candidate(value: str) -> str:
    candidate = re.sub(r"\s+", " ", value).strip("：:;；,.，。[]()（）{}\"'“”`")
    if len(candidate) < 2 or len(candidate) > 40:
        return ""
    if any(token in candidate for token in ("$$", "\\", "->", "=>")):
        return ""
    return candidate


def _extract_glossary_seeds(source_text: str) -> list[str]:
    candidates: list[str] = []
    normalized = source_text.replace("\r\n", "\n")

    for line in normalized.splitlines():
        if line.lstrip().startswith("###"):
            heading = _clean_glossary_candidate(line.lstrip("# ").strip())
            if heading:
                candidates.append(heading)

    patterns = [
        r"[“\"]([^“”\"\n]{2,40})[”\"]",
        r"\[\[([^\]#]{2,40})(?:#[^\]]*)?\]\]",
        r"\*\*([^*\n]{2,40})\*\*",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, normalized):
            candidate = _clean_glossary_candidate(match)
            if candidate:
                candidates.append(candidate)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        key = item.replace(" ", "").lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= 12:
            break
    return deduped


def _coerce_str_list(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if not stripped:
            continue
        output.append(stripped)
        if len(output) >= limit:
            break
    return output


def _coerce_formula_catalog(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    output: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            formula = item.get("formula")
            if not isinstance(formula, str) or not formula.strip():
                continue
            output.append(
                {
                    "formula": formula.strip(),
                    "explanation": str(item.get("explanation") or "").strip(),
                    "usage": str(item.get("usage") or "").strip(),
                }
            )
            continue
        if isinstance(item, str) and item.strip():
            output.append(
                {
                    "formula": item.strip(),
                    "explanation": "",
                    "usage": "",
                }
            )
    return output[:16]


def _coerce_summary_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "summary", "content"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def _default_storyboard_outline(plan: ProjectPlan) -> list[dict[str, Any]]:
    return [
        {
            "segment_id": segment.id,
            "title": segment.title,
            "goal": segment.goal,
            "narration": segment.narration,
            "modality": segment.modality.value,
            "estimated_seconds": segment.estimated_seconds,
            "formulas": segment.formulas,
            "html_motion_notes": segment.html_motion_notes,
            "scene_beats": [],
            "worker_instructions": {
                "html": "",
                "manim": "",
                "svg": "",
            },
        }
        for segment in plan.segments
    ]


def _normalize_storyboard_outline(
    plan: ProjectPlan,
    candidate_outline: Any,
) -> list[dict[str, Any]]:
    candidate_map: dict[str, dict[str, Any]] = {}
    if isinstance(candidate_outline, list):
        for item in candidate_outline:
            if not isinstance(item, dict):
                continue
            segment_id = item.get("segment_id")
            if isinstance(segment_id, str) and segment_id.strip():
                candidate_map[segment_id.strip()] = item

    merged: list[dict[str, Any]] = []
    for segment in plan.segments:
        item = candidate_map.get(segment.id, {})
        if not isinstance(item, dict):
            item = {}

        narration = item.get("narration")
        if isinstance(narration, str) and narration.strip():
            segment.narration = narration.strip()

        formulas = _coerce_str_list(item.get("formulas"), limit=10)
        if formulas:
            segment.formulas = formulas

        motion_notes = _coerce_str_list(item.get("html_motion_notes"), limit=10)
        if motion_notes:
            segment.html_motion_notes = motion_notes

        worker_instructions = item.get("worker_instructions")
        if not isinstance(worker_instructions, dict):
            worker_instructions = {}

        merged.append(
            {
                "segment_id": segment.id,
                "title": segment.title,
                "goal": segment.goal,
                "narration": segment.narration,
                "modality": segment.modality.value,
                "estimated_seconds": int(
                    item.get("estimated_seconds") or segment.estimated_seconds
                ),
                "formulas": segment.formulas,
                "html_motion_notes": segment.html_motion_notes,
                "scene_beats": _coerce_str_list(item.get("scene_beats"), limit=10),
                "worker_instructions": {
                    "html": str(worker_instructions.get("html") or "").strip(),
                    "manim": str(worker_instructions.get("manim") or "").strip(),
                    "svg": str(worker_instructions.get("svg") or "").strip(),
                },
            }
        )
    return merged


def _normalize_segment_priorities(
    plan: ProjectPlan,
    value: Any,
) -> list[dict[str, Any]]:
    candidate_map: dict[str, dict[str, Any]] = {}
    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue
            segment_id = item.get("segment_id")
            if isinstance(segment_id, str) and segment_id.strip():
                candidate_map[segment_id.strip()] = item

    normalized: list[dict[str, Any]] = []
    for segment in plan.segments:
        candidate = candidate_map.get(segment.id, {})
        objective = candidate.get("objective")
        primary_worker = candidate.get("primary_worker_path")
        estimated = candidate.get("estimated_seconds")
        normalized.append(
            {
                "segment_id": segment.id,
                "objective": (
                    objective.strip()
                    if isinstance(objective, str) and objective.strip()
                    else segment.goal
                ),
                "primary_worker_path": (
                    primary_worker.strip()
                    if isinstance(primary_worker, str) and primary_worker.strip()
                    else segment.modality.value
                ),
                "estimated_seconds": int(estimated)
                if isinstance(estimated, int) and estimated > 0
                else segment.estimated_seconds,
            }
        )
    return normalized


def _task_by_id(plan: ProjectPlan, task_id: str) -> ExecutionTask:
    for task in plan.execution_tasks:
        if task.id == task_id:
            return task
    raise KeyError(f"unknown_task:{task_id}")


def _segment_id_from_task(task: ExecutionTask) -> str:
    if not task.id.startswith("render."):
        raise ValueError(f"invalid_render_task_id:{task.id}")
    worker_suffix = "." + task.owner_role.replace("_worker", "")
    if task.id.endswith(worker_suffix):
        return task.id[len("render.") : -len(worker_suffix)]
    return task.id[len("render.") :]


def _segment_by_id(plan: ProjectPlan, segment_id: str):
    for segment in plan.segments:
        if segment.id == segment_id:
            return segment
    raise KeyError(f"unknown_segment:{segment_id}")


def _complete_task(
    plan: ProjectPlan,
    session_id: str,
    task_id: str,
    actor_role: str,
) -> None:
    result = update_execution_task_status(
        plan=plan,
        task_id=task_id,
        new_status=TaskStatus.COMPLETED,
        actor_role=actor_role,
        output_checker=lambda key: has_output_key(plan, session_id, key),
    )
    mutation = {
        "success": result.success,
        "task_id": result.task_id,
        "from_status": result.from_status,
        "to_status": result.to_status,
        "reason": result.reason,
        "verification_nudge_needed": result.verification_nudge_needed,
    }
    persist_task_update(plan=plan, session_id=session_id, mutation=mutation)
    if not result.success:
        raise RuntimeError(f"task_update_failed:{task_id}:{result.reason}")


def _complete_task_without_outputs(
    plan: ProjectPlan,
    session_id: str,
    task_id: str,
    actor_role: str,
) -> None:
    result = update_execution_task_status(
        plan=plan,
        task_id=task_id,
        new_status=TaskStatus.COMPLETED,
        actor_role=actor_role,
        output_checker=lambda _key: True,
    )
    mutation = {
        "success": result.success,
        "task_id": result.task_id,
        "from_status": result.from_status,
        "to_status": result.to_status,
        "reason": result.reason,
        "verification_nudge_needed": result.verification_nudge_needed,
    }
    persist_task_update(plan=plan, session_id=session_id, mutation=mutation)
    if not result.success:
        raise RuntimeError(f"task_update_failed:{task_id}:{result.reason}")


def _call_json_role(
    *,
    cfg: LLMRuntimeConfig,
    plan: ProjectPlan,
    session_id: str,
    role_id: str,
    stage: PipelineStage,
    recipe: PromptRecipe,
    payload: dict[str, Any],
    prompt_cache: PromptSectionCache,
    allow_disallowed_stage: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = build_prompt_bundle(
        plan=plan,
        session_id=session_id,
        role_id=role_id,
        stage=stage,
        recipe=recipe,
        payload=payload,
        cache=prompt_cache,
        allow_disallowed_stage=allow_disallowed_stage,
    )
    persist_context_packet(
        plan=plan,
        session_id=session_id,
        packet=bundle.packet,
        prompt_sections=bundle.prompt_sections,
    )
    return generate_json_for_role(
        cfg=cfg,
        role_id=role_id,
        instructions=bundle.system_prompt,
        prompt=bundle.user_prompt,
    )


def _document_payloads(docs: list[Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for item in docs:
        payloads.append(
            {
                "path": getattr(item, "path", ""),
                "kind": getattr(item, "kind", ""),
                "warning": getattr(item, "warning", None),
                "excerpt": (getattr(item, "text", "") or "")[:4000],
            }
        )
    return payloads


def _worker_kind_from_role(role_id: str) -> str:
    if not role_id.endswith("_worker"):
        return role_id
    return role_id[: -len("_worker")]


def _planned_primary_worker_path(
    planner_brief: dict[str, Any],
    segment_id: str,
) -> str | None:
    priorities = planner_brief.get("segment_priorities")
    if not isinstance(priorities, list):
        return None
    for item in priorities:
        if not isinstance(item, dict):
            continue
        if item.get("segment_id") != segment_id:
            continue
        candidate = item.get("primary_worker_path")
        if not isinstance(candidate, str):
            return None
        normalized = candidate.strip().lower()
        if normalized in {"html", "manim", "svg", "hybrid"}:
            return normalized
        return None
    return None


def _read_dispatch_worker_limit(default: int = 3) -> int:
    raw = os.environ.get("MANIMIND_DISPATCH_MAX_WORKERS", str(default)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _synthesize_and_build_timing(
    *,
    plan: ProjectPlan,
    session_id: str,
    storyboard_outline: list[dict[str, Any]],
    handoff_notes: dict[str, Any],
    cfg: LLMRuntimeConfig,
) -> dict[str, Any]:
    """在 workers 之前合成 TTS，生成 timing_manifest。

    返回 timing_manifest dict，如果 TTS 不可用则返回空 dict。
    """
    from .tts import TTSJob, build_tts_adapter

    tts_provider = os.environ.get("MANIMIND_TTS_PROVIDER", "powershell_sapi").strip()
    try:
        adapter = build_tts_adapter(tts_provider)
    except (ValueError, RuntimeError) as exc:
        _log_progress(session_id, "tts", f"adapter_unavailable: {exc}")
        return {}

    output_dir = Path(plan.runtime_layout.output_dir) / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime

    segments_timing: dict[str, Any] = {}

    for entry in storyboard_outline:
        seg_id = entry.get("segment_id", "")
        narration_text = entry.get("narration_text", "")
        if not narration_text and seg_id in handoff_notes:
            narration_text = handoff_notes[seg_id].get("narration_text", "")
        if not narration_text:
            continue

        audio_path = output_dir / f"{seg_id}.wav"
        job = TTSJob(
            project_id=plan.project_id,
            script_text=narration_text,
            output_path=str(audio_path),
            voice="default",
            language="zh",
        )
        try:
            result_path = adapter.synthesize(job)
            duration = _get_audio_duration(Path(result_path))
        except Exception as exc:
            _log_progress(session_id, "tts", f"segment={seg_id} failed: {exc}")
            duration = entry.get("estimated_seconds", 20)
            result_path = str(audio_path)

        segments_timing[seg_id] = {
            "audio_path": result_path,
            "duration_seconds": duration,
        }
        _log_progress(session_id, "tts", f"segment={seg_id} duration={duration:.1f}s")

    timing_manifest = {
        "generated_at": datetime.now().isoformat(),
        "tts_provider": tts_provider,
        "segments": segments_timing,
    }

    manifest_path = Path(plan.runtime_layout.project_context_dir) / "timing_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(timing_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _log_progress(session_id, "tts", f"timing_manifest saved segments={len(segments_timing)}")
    return timing_manifest


def _get_audio_duration(audio_path: Path) -> float:
    """获取音频文件时长（秒）。优先用 ffprobe，降级用文件大小估算。"""
    if not audio_path.exists():
        return 20.0
    try:
        import subprocess

        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet", "-show_entries",
                "format=duration", "-of", "csv=p=0", str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    # WAV 降级估算：文件大小 / (采样率 * 位深 * 声道 / 8)
    # 假设 16kHz 16bit mono = 32000 bytes/sec
    size = audio_path.stat().st_size
    return max(1.0, size / 32000.0)


def run_to_review(
    plan: ProjectPlan,
    session_id: str,
    source_manifest: str,
) -> dict[str, Any]:
    """把计划推进到 REVIEW 阶段（含 review.draft）。"""
    _log_progress(session_id, "run-to-review", f"start project={plan.project_id}")
    persist_plan_snapshot(plan=plan, session_id=session_id, source_manifest=source_manifest)
    load_execution_task_snapshot(plan)

    cfg = load_llm_runtime_config()
    prompt_cache = PromptSectionCache()

    docs = load_source_documents(plan.source_bundle, base_dir=Path.cwd())
    source_text = concatenate_documents(docs)
    source_excerpt = source_text[:12000] if source_text else ""
    seed_formulas = _extract_formulas(source_text)
    seed_glossary = _extract_glossary_seeds(source_text)
    _log_progress(
        session_id,
        "ingest",
        f"loaded_docs={len(docs)} source_chars={len(source_text)}",
    )

    ingest_payload = {
        "source_bundle": plan.source_bundle.to_dict(),
        "documents": [item.to_dict() for item in docs],
        "note": "ingest complete",
    }
    write_output_key(
        plan=plan,
        session_id=session_id,
        key=f"{plan.project_id}.session.handoff",
        payload={
            "project_id": plan.project_id,
            "stage": "ingest",
            "handoff": ingest_payload,
        },
    )
    _complete_task(plan, session_id, "ingest.sources", "lead")
    _log_progress(session_id, "ingest", "ingest.sources completed")

    explorer_payload = {
        "project_id": plan.project_id,
        "title": plan.title,
        "audience": plan.source_bundle.audience,
        "style_refs": plan.source_bundle.style_refs,
        "segments": [segment.to_dict() for segment in plan.segments],
        "documents": _document_payloads(docs),
        "source_excerpt": source_excerpt,
        "seed_formulas": seed_formulas,
        "seed_glossary": seed_glossary,
    }
    explorer_findings, explorer_meta = _call_json_role(
        cfg=cfg,
        plan=plan,
        session_id=session_id,
        role_id="explorer",
        stage=PipelineStage.SUMMARIZE,
        recipe=explorer_recipe(),
        payload=explorer_payload,
        prompt_cache=prompt_cache,
    )
    _log_progress(session_id, "explorer", "llm output received")
    explorer_formulas = _coerce_str_list(
        explorer_findings.get("formula_candidates"),
        limit=16,
    )
    if not explorer_formulas:
        explorer_formulas = seed_formulas
    explorer_glossary = _coerce_str_list(
        explorer_findings.get("glossary_candidates"),
        limit=12,
    )
    if not explorer_glossary:
        explorer_glossary = seed_glossary
    explorer_story_beats = _coerce_str_list(
        explorer_findings.get("story_beats"),
        limit=12,
    )
    explorer_risk_flags = _coerce_str_list(
        explorer_findings.get("risk_flags"),
        limit=12,
    )
    source_highlights = _coerce_str_list(
        explorer_findings.get("source_highlights"),
        limit=12,
    )
    document_findings = explorer_findings.get("document_findings")
    if not isinstance(document_findings, list):
        document_findings = _document_payloads(docs)

    persist_agent_message(
        plan=plan,
        session_id=session_id,
        event_type=EventType.WORKER_PROGRESS,
        role_id="explorer",
        stage=PipelineStage.SUMMARIZE,
        task_id="explore.references",
        payload={"progress_label": "scan_sources"},
    )
    _complete_task(plan, session_id, "explore.references", "explorer")
    persist_agent_message(
        plan=plan,
        session_id=session_id,
        event_type=EventType.WORKER_RESULT,
        role_id="explorer",
        stage=PipelineStage.SUMMARIZE,
        task_id="explore.references",
        payload={
            "summary": "Explorer findings prepared.",
            "llm_generation": explorer_meta,
            "risk_flags": explorer_risk_flags,
        },
    )
    _log_progress(
        session_id,
        "explorer",
        f"completed formulas={len(explorer_formulas)} glossary={len(explorer_glossary)}",
    )

    lead_payload = {
        "project_id": plan.project_id,
        "title": plan.title,
        "audience": plan.source_bundle.audience,
        "style_refs": plan.source_bundle.style_refs,
        "segments": [segment.to_dict() for segment in plan.segments],
        "source_excerpt": source_excerpt,
        "explorer_findings": {
            "document_findings": document_findings,
            "formula_candidates": explorer_formulas,
            "glossary_candidates": explorer_glossary,
            "story_beats": explorer_story_beats,
            "risk_flags": explorer_risk_flags,
            "source_highlights": source_highlights,
        },
    }
    lead_outputs, lead_meta = _call_json_role(
        cfg=cfg,
        plan=plan,
        session_id=session_id,
        role_id="lead",
        stage=PipelineStage.SUMMARIZE,
        recipe=lead_summary_recipe(),
        payload=lead_payload,
        prompt_cache=prompt_cache,
    )
    research_summary = _coerce_summary_text(
        lead_outputs.get("research_summary")
    ) or _coerce_summary_text(lead_outputs.get("summary"))
    if not research_summary:
        lead_retry_payload = {
            **lead_payload,
            "contract_hint": (
                "Return a non-empty string field `research_summary` in plain Chinese."
            ),
        }
        lead_outputs, lead_meta = _call_json_role(
            cfg=cfg,
            plan=plan,
            session_id=session_id,
            role_id="lead",
            stage=PipelineStage.SUMMARIZE,
            recipe=lead_summary_recipe(),
            payload=lead_retry_payload,
            prompt_cache=prompt_cache,
        )
        research_summary = _coerce_summary_text(
            lead_outputs.get("research_summary")
        ) or _coerce_summary_text(lead_outputs.get("summary"))
    if not research_summary:
        raise ValueError("invalid_research_summary")
    glossary_terms = _coerce_str_list(lead_outputs.get("glossary_terms"), limit=12)
    if not glossary_terms:
        glossary_terms = explorer_glossary
    formula_catalog = _coerce_formula_catalog(lead_outputs.get("formula_catalog"))
    if not formula_catalog and explorer_formulas:
        formula_catalog = [
            {"formula": item, "explanation": "", "usage": ""}
            for item in explorer_formulas
        ]
    style_guide = _coerce_str_list(lead_outputs.get("style_guide"), limit=12)
    if not style_guide:
        style_guide = list(plan.source_bundle.style_refs)

    write_output_key(
        plan=plan,
        session_id=session_id,
        key=f"{plan.project_id}.research.summary",
        payload={
            "project_id": plan.project_id,
            "summary": research_summary.strip(),
            "source_highlights": source_highlights,
            "risk_flags": explorer_risk_flags,
            "llm_generation": lead_meta,
        },
    )
    write_output_key(
        plan=plan,
        session_id=session_id,
        key=f"{plan.project_id}.glossary",
        payload={
            "project_id": plan.project_id,
            "terms": glossary_terms,
            "llm_generation": lead_meta,
        },
    )
    write_output_key(
        plan=plan,
        session_id=session_id,
        key=f"{plan.project_id}.formula.catalog",
        payload={
            "project_id": plan.project_id,
            "items": formula_catalog,
            "llm_generation": lead_meta,
        },
    )
    write_output_key(
        plan=plan,
        session_id=session_id,
        key=f"{plan.project_id}.style.guide",
        payload={
            "project_id": plan.project_id,
            "items": style_guide,
            "llm_generation": lead_meta,
        },
    )
    _complete_task(plan, session_id, "summarize.research", "lead")
    _log_progress(
        session_id,
        "lead",
        f"summarize.research completed glossary={len(glossary_terms)} formulas={len(formula_catalog)}",
    )

    planner_payload = {
        "project_id": plan.project_id,
        "title": plan.title,
        "segments": [segment.to_dict() for segment in plan.segments],
        "research_summary": research_summary.strip(),
        "glossary_terms": glossary_terms,
        "formula_catalog": formula_catalog,
        "style_guide": style_guide,
        "explorer_findings": {
            "story_beats": explorer_story_beats,
            "risk_flags": explorer_risk_flags,
            "source_highlights": source_highlights,
        },
    }
    planner_outputs, planner_meta = _call_json_role(
        cfg=cfg,
        plan=plan,
        session_id=session_id,
        role_id="planner",
        stage=PipelineStage.PLAN,
        recipe=planner_recipe(),
        payload=planner_payload,
        prompt_cache=prompt_cache,
    )
    planner_brief = {
        "segment_priorities": _normalize_segment_priorities(
            plan,
            planner_outputs.get("segment_priorities"),
        ),
        "must_checks": _coerce_str_list(planner_outputs.get("must_checks"), limit=12),
        "risk_flags": _coerce_str_list(planner_outputs.get("risk_flags"), limit=12)
        or explorer_risk_flags,
        "visual_briefs": planner_outputs.get("visual_briefs", []),
        "narrative_arc": _coerce_str_list(planner_outputs.get("narrative_arc"), limit=8),
    }
    persist_agent_message(
        plan=plan,
        session_id=session_id,
        event_type=EventType.WORKER_PROGRESS,
        role_id="planner",
        stage=PipelineStage.PLAN,
        task_id="plan.research_brief",
        payload={"progress_label": "build_plan_brief"},
    )
    _complete_task(plan, session_id, "plan.research_brief", "planner")
    _log_progress(
        session_id,
        "planner",
        f"plan.research_brief completed segments={len(planner_brief['segment_priorities'])}",
    )
    persist_agent_message(
        plan=plan,
        session_id=session_id,
        event_type=EventType.WORKER_RESULT,
        role_id="planner",
        stage=PipelineStage.PLAN,
        task_id="plan.research_brief",
        payload={
            "summary": "Planner brief prepared.",
            "brief": planner_brief,
            "llm_generation": planner_meta,
        },
    )

    coordinator_payload = {
        "project_id": plan.project_id,
        "title": plan.title,
        "audience": plan.source_bundle.audience,
        "style_refs": style_guide,
        "segments": [segment.to_dict() for segment in plan.segments],
        "research_summary": research_summary.strip(),
        "glossary_terms": glossary_terms,
        "formula_catalog": formula_catalog,
        "planner_brief": planner_brief,
        "story_beats": explorer_story_beats,
        "source_highlights": source_highlights,
        "seed_storyboard_outline": _default_storyboard_outline(plan),
    }
    coordinator_outputs, coordinator_meta = _call_json_role(
        cfg=cfg,
        plan=plan,
        session_id=session_id,
        role_id="coordinator",
        stage=PipelineStage.PLAN,
        recipe=coordinator_recipe(),
        payload=coordinator_payload,
        prompt_cache=prompt_cache,
    )
    storyboard_outline = _normalize_storyboard_outline(
        plan,
        coordinator_outputs.get("script_outline"),
    )
    handoff_notes = coordinator_outputs.get("handoff_notes")
    if not isinstance(handoff_notes, dict):
        handoff_notes = {}
    storyboard_master = coordinator_outputs.get("storyboard_master")
    if not isinstance(storyboard_master, dict):
        storyboard_master = {}

    write_output_key(
        plan=plan,
        session_id=session_id,
        key=f"{plan.project_id}.narration.script",
        payload={
            "project_id": plan.project_id,
            "task_id": "plan.storyboard",
            "output_key": f"{plan.project_id}.narration.script",
            "script_outline": storyboard_outline,
            "style": style_guide,
            "planner_brief": planner_brief,
            "llm_generation": coordinator_meta,
        },
    )
    write_output_key(
        plan=plan,
        session_id=session_id,
        key=f"{plan.project_id}.storyboard.master",
        payload={
            "project_id": plan.project_id,
            "task_id": "plan.storyboard",
            "output_key": f"{plan.project_id}.storyboard.master",
            "script_outline": storyboard_outline,
            "storyboard_master": storyboard_master,
            "handoff_notes": handoff_notes,
            "planner_brief": planner_brief,
            "llm_generation": coordinator_meta,
        },
    )
    write_output_key(
        plan=plan,
        session_id=session_id,
        key=f"{plan.project_id}.session.handoff",
        payload={
            "project_id": plan.project_id,
            "stage": "plan",
            "handoff_notes": handoff_notes,
            "storyboard_outline": storyboard_outline,
            "planner_brief": planner_brief,
            "llm_generation": coordinator_meta,
        },
    )
    _complete_task(plan, session_id, "plan.storyboard", "coordinator")
    _log_progress(
        session_id,
        "coordinator",
        f"plan.storyboard completed outline={len(storyboard_outline)}",
    )

    # --- TTS 前移：在 workers 之前合成配音，生成 timing_manifest ---
    timing_manifest = _synthesize_and_build_timing(
        plan=plan,
        session_id=session_id,
        storyboard_outline=storyboard_outline,
        handoff_notes=handoff_notes,
        cfg=cfg,
    )
    # 将真实时长注入 handoff_notes，供 workers 消费
    if timing_manifest:
        for seg_id, seg_timing in timing_manifest.get("segments", {}).items():
            if seg_id in handoff_notes:
                handoff_notes[seg_id]["duration_seconds"] = seg_timing["duration_seconds"]

    shared_context = {
        "research_summary": research_summary.strip(),
        "glossary_terms": glossary_terms,
        "formula_catalog": formula_catalog,
        "style_guide": style_guide,
        "planner_brief": planner_brief,
        "storyboard_outline": storyboard_outline,
        "handoff_notes": handoff_notes,
    }

    render_tasks = [
        task
        for task in plan.execution_tasks
        if task.stage == PipelineStage.DISPATCH
    ]
    render_evidence: list[dict[str, Any]] = []
    runnable_entries: list[dict[str, Any]] = []

    for task in render_tasks:
        worker_role = task.owner_role
        segment_id = _segment_id_from_task(task)
        segment = _segment_by_id(plan, segment_id)
        planned_worker_path = _planned_primary_worker_path(planner_brief, segment.id)
        worker_kind = _worker_kind_from_role(worker_role)
        _log_progress(
            session_id,
            "dispatch",
            f"task={task.id} worker={worker_kind} planned={planned_worker_path or 'auto'}",
        )

        if planned_worker_path in {"html", "manim", "svg"} and worker_kind != planned_worker_path:
            persist_agent_message(
                plan=plan,
                session_id=session_id,
                event_type=EventType.WORKER_PROGRESS,
                role_id=worker_role,
                stage=PipelineStage.DISPATCH,
                task_id=task.id,
                payload={"progress_label": "skip_dispatch"},
            )
            _complete_task_without_outputs(plan, session_id, task.id, worker_role)
            persist_agent_message(
                plan=plan,
                session_id=session_id,
                event_type=EventType.WORKER_RESULT,
                role_id=worker_role,
                stage=PipelineStage.DISPATCH,
                task_id=task.id,
                payload={
                    "summary": f"Skipped by planner. primary_worker_path={planned_worker_path}.",
                    "dispatch_decision": "skipped_by_plan",
                },
            )
            render_evidence.append(
                {
                    "task_id": task.id,
                    "worker_role": worker_role,
                    "segment_id": segment.id,
                    "summary": f"Skipped by planner. primary_worker_path={planned_worker_path}.",
                    "artifact_files": [],
                    "output_records": [],
                    "metadata": {
                        "dispatch_decision": "skipped_by_plan",
                        "planned_primary_worker_path": planned_worker_path,
                    },
                }
            )
            _log_progress(session_id, "dispatch", f"task={task.id} skipped_by_plan")
            continue

        runnable_entries.append(
            {
                "task": task,
                "worker_role": worker_role,
                "segment": segment,
            }
        )

    if runnable_entries:
        dispatch_workers = min(
            len(runnable_entries),
            _read_dispatch_worker_limit(default=3),
        )
        _log_progress(
            session_id,
            "dispatch",
            (
                "parallel_dispatch_start "
                f"tasks={len(runnable_entries)} max_workers={dispatch_workers}"
            ),
        )

        for entry in runnable_entries:
            task = entry["task"]
            worker_role = entry["worker_role"]
            persist_agent_message(
                plan=plan,
                session_id=session_id,
                event_type=EventType.WORKER_PROGRESS,
                role_id=worker_role,
                stage=PipelineStage.DISPATCH,
                task_id=task.id,
                payload={"progress_label": "start_render"},
            )

        success_by_task_id: dict[str, Any] = {}
        failure_by_task_id: dict[str, str] = {}

        with ThreadPoolExecutor(max_workers=dispatch_workers) as pool:
            future_to_entry = {
                pool.submit(
                    render_with_worker,
                    plan=plan,
                    segment=entry["segment"],
                    task=entry["task"],
                    session_id=session_id,
                    shared_context=shared_context,
                    prompt_cache=PromptSectionCache(),
                ): entry
                for entry in runnable_entries
            }

            for future in as_completed(future_to_entry):
                entry = future_to_entry[future]
                task = entry["task"]
                worker_role = entry["worker_role"]
                try:
                    render_result = future.result()
                    success_by_task_id[task.id] = render_result
                    _log_progress(session_id, "dispatch", f"task={task.id} render_done")
                except WorkerExecutionError as exc:
                    failure_by_task_id[task.id] = str(exc)
                    persist_agent_message(
                        plan=plan,
                        session_id=session_id,
                        event_type=EventType.WORKER_BLOCKER,
                        role_id=worker_role,
                        stage=PipelineStage.DISPATCH,
                        task_id=task.id,
                        payload={"blocked_reason": str(exc)},
                    )
                except Exception as exc:  # pragma: no cover - defensive fallback
                    reason = f"unexpected_render_error:{type(exc).__name__}:{exc}"
                    failure_by_task_id[task.id] = reason
                    persist_agent_message(
                        plan=plan,
                        session_id=session_id,
                        event_type=EventType.WORKER_BLOCKER,
                        role_id=worker_role,
                        stage=PipelineStage.DISPATCH,
                        task_id=task.id,
                        payload={"blocked_reason": reason},
                    )

        for entry in runnable_entries:
            task = entry["task"]
            worker_role = entry["worker_role"]
            segment = entry["segment"]

            if task.id in failure_by_task_id:
                render_evidence.append(
                    {
                        "task_id": task.id,
                        "worker_role": worker_role,
                        "segment_id": segment.id,
                        "summary": f"Failed: {failure_by_task_id[task.id]}",
                        "artifact_files": [],
                        "output_records": [],
                        "metadata": {
                            "dispatch_decision": "failed",
                            "blocked_reason": failure_by_task_id[task.id],
                        },
                    }
                )
                continue

            render_result = success_by_task_id[task.id]
            output_paths: list[str] = []
            for output_key in task.required_outputs:
                payload = {
                    "project_id": plan.project_id,
                    "task_id": task.id,
                    "output_key": output_key,
                    "render_summary": render_result.summary,
                    "artifact_files": render_result.artifact_files,
                    "artifact_metadata": render_result.metadata,
                }
                output_paths.append(
                    str(write_output_key(plan, session_id, output_key, payload))
                )
            _complete_task(plan, session_id, task.id, worker_role)
            persist_agent_message(
                plan=plan,
                session_id=session_id,
                event_type=EventType.WORKER_RESULT,
                role_id=worker_role,
                stage=PipelineStage.DISPATCH,
                task_id=task.id,
                payload={
                    "summary": render_result.summary,
                    "artifact_files": render_result.artifact_files,
                },
            )
            render_evidence.append(
                {
                    "task_id": task.id,
                    "worker_role": worker_role,
                    "segment_id": segment.id,
                    "summary": render_result.summary,
                    "artifact_files": render_result.artifact_files,
                    "output_records": output_paths,
                    "metadata": render_result.metadata,
                }
            )
            _log_progress(
                session_id,
                "dispatch",
                f"task={task.id} completed artifacts={len(render_result.artifact_files)}",
            )

        for entry in runnable_entries:
            task = entry["task"]
            if task.id in failure_by_task_id:
                raise RuntimeError(
                    f"render_failed:{task.id}:{failure_by_task_id[task.id]}"
                )

    review_evidence_path = write_output_key(
        plan=plan,
        session_id=session_id,
        key=f"{plan.project_id}.review.evidence",
        payload={
            "project_id": plan.project_id,
            "session_id": session_id,
            "render_evidence": render_evidence,
            "checkpoints": [item.to_dict() for item in plan.review_checkpoints],
            "storyboard_outline": storyboard_outline,
        },
    )

    reviewer_payload = {
        "project_id": plan.project_id,
        "title": plan.title,
        "research_summary": research_summary.strip(),
        "glossary_terms": glossary_terms,
        "formula_catalog": formula_catalog,
        "planner_brief": planner_brief,
        "storyboard_outline": storyboard_outline,
        "review_checkpoints": [item.to_dict() for item in plan.review_checkpoints],
        "render_evidence": render_evidence,
    }
    review_error: str | None = None
    try:
        review_draft, review_meta = _call_json_role(
            cfg=cfg,
            plan=plan,
            session_id=session_id,
            role_id="reviewer",
            stage=PipelineStage.REVIEW,
            recipe=reviewer_recipe(),
            payload=reviewer_payload,
            prompt_cache=prompt_cache,
        )
    except LLMRequestError as exc:
        review_error = str(exc)
        _log_progress(
            session_id,
            "review",
            f"reviewer json failed once error={review_error}; retry_with_contract_hint",
        )
        retry_payload = {
            **reviewer_payload,
            "contract_hint": (
                "Return exactly one JSON object. No markdown, no explanation, no code fence."
            ),
        }
        try:
            review_draft, review_meta = _call_json_role(
                cfg=cfg,
                plan=plan,
                session_id=session_id,
                role_id="reviewer",
                stage=PipelineStage.REVIEW,
                recipe=reviewer_recipe(),
                payload=retry_payload,
                prompt_cache=prompt_cache,
            )
            review_error = None
        except LLMRequestError as retry_exc:
            review_error = f"{review_error};retry:{retry_exc}"
            _log_progress(
                session_id,
                "review",
                f"reviewer json failed twice; fallback_draft error={review_error}",
            )
            review_draft = {}
            review_meta = {
                "endpoint": "fallback",
                "role_id": "reviewer",
                "route": "fallback",
                "provider": "local",
                "model": "fallback",
            }
    if not isinstance(review_draft, dict):
        review_draft = {}
    draft_payload = {
        "summary": str(review_draft.get("summary") or "").strip()
        or "AI reviewer draft generated. Awaiting human approval.",
        "decision": "pending_human_confirmation",
        "risk_notes": _coerce_str_list(review_draft.get("risk_notes"), limit=12),
        "must_check": _coerce_str_list(review_draft.get("must_check"), limit=12),
        "evidence_checks": review_draft.get("evidence_checks", []),
        "checkpoints": [item.to_dict() for item in plan.review_checkpoints],
        "evidence_path": str(review_evidence_path),
        "llm_generation": {"meta": review_meta, "error": review_error},
    }

    persist_agent_message(
        plan=plan,
        session_id=session_id,
        event_type=EventType.REVIEW_DRAFT,
        role_id="reviewer",
        stage=PipelineStage.REVIEW,
        task_id="review.outputs",
        payload=draft_payload,
    )
    review_task = update_execution_task_status(
        plan=plan,
        task_id="review.outputs",
        new_status=TaskStatus.IN_PROGRESS,
        actor_role="human_reviewer",
    )
    persist_task_update(
        plan=plan,
        session_id=session_id,
        mutation={
            "success": review_task.success,
            "task_id": review_task.task_id,
            "from_status": review_task.from_status,
            "to_status": review_task.to_status,
            "reason": review_task.reason,
            "verification_nudge_needed": review_task.verification_nudge_needed,
        },
    )
    _log_progress(
        session_id,
        "review",
        f"review.draft ready status={review_task.to_status} evidence={review_evidence_path}",
    )

    return {
        "project_id": plan.project_id,
        "session_id": session_id,
        "current_stage": plan.current_stage.value,
        "rendered_tasks": [task.id for task in render_tasks],
        "review_status": review_task.to_status,
        "review_evidence": str(review_evidence_path),
    }


def load_manifest_payload(manifest_path: Path) -> dict[str, Any]:
    return json.loads(manifest_path.read_text(encoding="utf-8"))
