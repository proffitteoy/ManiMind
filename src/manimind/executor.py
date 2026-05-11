"""执行器：推进主链路到审核阶段，并产出真实 worker 资产。"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .artifact_store import has_output_key, write_output_key
from .ingest import concatenate_documents, load_source_documents
from .llm_client import (
    LLMRequestError,
    generate_json_with_fallback,
    load_llm_runtime_config,
)
from .models import EventType, ExecutionTask, PipelineStage, ProjectPlan, TaskStatus
from .runtime_store import (
    load_execution_task_snapshot,
    persist_agent_message,
    persist_plan_snapshot,
    persist_task_update,
)
from .task_board import update_execution_task_status
from .worker_adapters import WorkerExecutionError, WorkerRunResult, render_with_worker


def _extract_formulas(text: str) -> list[str]:
    formulas: list[str] = []
    for match in re.findall(r"\$\$(.+?)\$\$", text, flags=re.DOTALL):
        value = match.strip()
        if value:
            formulas.append(value)
    if formulas:
        return formulas[:12]

    for match in re.findall(r"\$(.+?)\$", text):
        value = match.strip()
        if value:
            formulas.append(value)
    return formulas[:12]


def _extract_glossary(source_text: str) -> list[str]:
    seeds = [
        "极大函数",
        "Vitali 覆盖",
        "下半连续",
        "可测",
        "积分平均",
        "测度",
    ]
    found = [item for item in seeds if item in source_text]
    if len(found) >= 3:
        return found[:8]
    return seeds[:6]


def _build_explorer_findings(
    *,
    plan: ProjectPlan,
    source_text: str,
    formulas: list[str],
    docs: list[Any],
) -> dict[str, Any]:
    document_findings: list[dict[str, Any]] = []
    for item in docs:
        document_findings.append(
            {
                "path": getattr(item, "path", ""),
                "kind": getattr(item, "kind", ""),
                "text_length": len(getattr(item, "text", "") or ""),
                "warning": getattr(item, "warning", None),
            }
        )
    segment_focus = [
        {
            "segment_id": segment.id,
            "title": segment.title,
            "modality": segment.modality.value,
            "formula_count": len(segment.formulas),
            "requires_svg_motion": segment.requires_svg_motion,
        }
        for segment in plan.segments
    ]
    risk_flags: list[str] = []
    if not formulas:
        risk_flags.append("source_formula_missing")
    if not source_text.strip():
        risk_flags.append("source_text_empty")
    if any(item.get("warning") for item in document_findings):
        risk_flags.append("source_warning_present")
    return {
        "documents": document_findings,
        "segment_focus": segment_focus,
        "formula_candidates": formulas[:12],
        "risk_flags": risk_flags,
    }


def _build_planner_brief(
    *,
    plan: ProjectPlan,
    glossary: list[str],
    explorer_findings: dict[str, Any],
) -> dict[str, Any]:
    segment_priorities = [
        {
            "segment_id": segment.id,
            "objective": segment.goal,
            "primary_worker_path": segment.modality.value,
            "estimated_seconds": segment.estimated_seconds,
        }
        for segment in plan.segments
    ]
    risk_flags = explorer_findings.get("risk_flags", [])
    if not isinstance(risk_flags, list):
        risk_flags = []
    return {
        "segment_priorities": segment_priorities,
        "glossary_terms": glossary[:8],
        "must_checks": [
            "术语口径一致",
            "公式解释与镜头叙事对齐",
            "每个片段产物必须可追溯到 approved 记录",
        ],
        "risk_flags": risk_flags,
    }


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


def _default_storyboard_outline(plan: ProjectPlan) -> list[dict[str, Any]]:
    return [
        {
            "segment_id": segment.id,
            "title": segment.title,
            "goal": segment.goal,
            "narration": segment.narration,
            "modality": segment.modality.value,
            "formulas": segment.formulas,
            "html_motion_notes": segment.html_motion_notes,
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

        formulas = _coerce_str_list(item.get("formulas"), limit=8)
        if formulas:
            segment.formulas = formulas

        motion_notes = _coerce_str_list(item.get("html_motion_notes"), limit=8)
        if motion_notes:
            segment.html_motion_notes = motion_notes

        merged.append(
            {
                "segment_id": segment.id,
                "title": segment.title,
                "goal": segment.goal,
                "narration": segment.narration,
                "modality": segment.modality.value,
                "formulas": segment.formulas,
                "html_motion_notes": segment.html_motion_notes,
            }
        )
    return merged


def _generate_main_outputs_with_llm(
    *,
    plan: ProjectPlan,
    source_text: str,
    fallback_formulas: list[str],
    fallback_glossary: list[str],
    fallback_planner_brief: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = load_llm_runtime_config()
    source_excerpt = source_text[:16000] if source_text else ""
    payload = {
        "project_id": plan.project_id,
        "title": plan.title,
        "audience": plan.source_bundle.audience,
        "style_refs": plan.source_bundle.style_refs,
        "segments": [
            {
                "segment_id": segment.id,
                "title": segment.title,
                "goal": segment.goal,
                "narration": segment.narration,
                "modality": segment.modality.value,
                "formulas": segment.formulas,
                "html_motion_notes": segment.html_motion_notes,
                "estimated_seconds": segment.estimated_seconds,
            }
            for segment in plan.segments
        ],
        "fallback_formulas": fallback_formulas[:12],
        "fallback_glossary": fallback_glossary[:8],
        "source_excerpt": source_excerpt,
    }
    instructions = (
        "你是数学科普视频总编导。"
        "请只输出一个 JSON 对象，不要输出 Markdown。"
        "内容必须忠于输入，术语统一，可直接用于动画制作。"
    )
    prompt = (
        "请基于输入材料生成可执行编排内容，输出 JSON schema：\n"
        "{\n"
        '  "research_summary": "string",\n'
        '  "glossary_terms": ["string"],\n'
        '  "formula_candidates": ["string"],\n'
        '  "planner_brief": {\n'
        '    "segment_priorities": [{"segment_id":"string","objective":"string","primary_worker_path":"string","estimated_seconds":20}],\n'
        '    "glossary_terms": ["string"],\n'
        '    "must_checks": ["string"],\n'
        '    "risk_flags": ["string"]\n'
        "  },\n"
        '  "storyboard_outline": [\n'
        '    {"segment_id":"string","narration":"string","formulas":["string"],"html_motion_notes":["string"]}\n'
        "  ]\n"
        "}\n\n"
        "输入：\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    generated, meta = generate_json_with_fallback(
        cfg=cfg,
        instructions=instructions,
        prompt=prompt,
        request_kind="main",
    )
    research_summary = generated.get("research_summary")
    if not isinstance(research_summary, str) or not research_summary.strip():
        research_summary = source_excerpt or "no source text loaded"

    glossary_terms = _coerce_str_list(generated.get("glossary_terms"), limit=8)
    if not glossary_terms:
        glossary_terms = fallback_glossary[:8]

    formula_candidates = _coerce_str_list(generated.get("formula_candidates"), limit=12)
    if not formula_candidates:
        formula_candidates = fallback_formulas[:12]

    planner_brief = generated.get("planner_brief")
    if not isinstance(planner_brief, dict):
        planner_brief = fallback_planner_brief
    else:
        planner_brief = {
            "segment_priorities": planner_brief.get(
                "segment_priorities",
                fallback_planner_brief.get("segment_priorities", []),
            ),
            "glossary_terms": _coerce_str_list(
                planner_brief.get("glossary_terms"), limit=8
            )
            or fallback_planner_brief.get("glossary_terms", []),
            "must_checks": _coerce_str_list(planner_brief.get("must_checks"), limit=8)
            or fallback_planner_brief.get("must_checks", []),
            "risk_flags": _coerce_str_list(planner_brief.get("risk_flags"), limit=8),
        }

    storyboard_outline = _normalize_storyboard_outline(
        plan,
        generated.get("storyboard_outline"),
    )
    return (
        {
            "research_summary": research_summary.strip(),
            "glossary_terms": glossary_terms,
            "formula_candidates": formula_candidates,
            "planner_brief": planner_brief,
            "storyboard_outline": storyboard_outline,
        },
        meta,
    )


def _generate_review_draft_with_llm(
    *,
    plan: ProjectPlan,
    render_evidence: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg = load_llm_runtime_config()
    payload = {
        "project_id": plan.project_id,
        "title": plan.title,
        "review_checkpoints": [item.to_dict() for item in plan.review_checkpoints],
        "render_evidence": render_evidence,
    }
    instructions = (
        "你是审核 Agent。"
        "你只能输出审核草案，不能直接 approve。"
        "请输出 JSON 对象，不要输出 Markdown。"
    )
    prompt = (
        "请输出 JSON schema：\n"
        "{\n"
        '  "summary": "string",\n'
        '  "decision": "pending_human_confirmation",\n'
        '  "risk_notes": ["string"],\n'
        '  "must_check": ["string"]\n'
        "}\n\n"
        "输入：\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    generated, meta = generate_json_with_fallback(
        cfg=cfg,
        instructions=instructions,
        prompt=prompt,
        request_kind="review",
    )
    summary = generated.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        summary = "AI reviewer draft generated. Awaiting human approval."
    risk_notes = _coerce_str_list(generated.get("risk_notes"), limit=8)
    must_check = _coerce_str_list(generated.get("must_check"), limit=8)
    return (
        {
            "summary": summary.strip(),
            "decision": "pending_human_confirmation",
            "risk_notes": risk_notes,
            "must_check": must_check,
        },
        meta,
    )


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


def _write_required_outputs(
    plan: ProjectPlan,
    session_id: str,
    task_id: str,
    payload_builder: dict[str, Any],
) -> list[str]:
    task = _task_by_id(plan, task_id)
    paths: list[str] = []
    for output_key in task.required_outputs:
        payload = {
            "project_id": plan.project_id,
            "task_id": task_id,
            "output_key": output_key,
            **payload_builder,
        }
        written = write_output_key(plan, session_id, output_key, payload)
        paths.append(str(written))
    return paths


def _complete_task(plan: ProjectPlan, session_id: str, task_id: str, actor_role: str) -> None:
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


def _fallback_manim_result(
    plan: ProjectPlan,
    segment_id: str,
    reason: str,
) -> WorkerRunResult:
    out_dir = Path(plan.runtime_layout.output_dir) / "manim" / re.sub(
        r"[^0-9A-Za-z_-]+", "-", segment_id
    ).strip("-").lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    note_path = out_dir / "fallback-note.txt"
    note_path.write_text(
        "\n".join(
            [
                "Manim render fallback",
                f"segment_id={segment_id}",
                f"reason={reason}",
            ]
        ),
        encoding="utf-8",
    )
    return WorkerRunResult(
        worker_role="manim_worker",
        segment_id=segment_id,
        summary=f"Manim fallback used: {reason}",
        artifact_files=[str(note_path)],
        metadata={
            "worker": "manim",
            "fallback": True,
            "reason": reason,
        },
    )


def run_to_review(
    plan: ProjectPlan,
    session_id: str,
    source_manifest: str,
) -> dict[str, Any]:
    """把计划推进到 REVIEW 阶段（含 review.draft）。"""
    persist_plan_snapshot(plan=plan, session_id=session_id, source_manifest=source_manifest)
    load_execution_task_snapshot(plan)

    docs = load_source_documents(plan.source_bundle, base_dir=Path.cwd())
    source_text = concatenate_documents(docs)
    formulas = _extract_formulas(source_text)
    glossary = _extract_glossary(source_text)
    research_summary = source_text[:4800] if source_text else "no source text loaded"
    llm_main_meta: dict[str, Any] | None = None
    llm_main_error: str | None = None

    _write_required_outputs(
        plan,
        session_id,
        "ingest.sources",
        {
            "handoff": {
                "source_bundle": plan.source_bundle.to_dict(),
                "documents": [item.to_dict() for item in docs],
                "note": "ingest complete",
            }
        },
    )
    _complete_task(plan, session_id, "ingest.sources", "lead")

    explorer_findings = _build_explorer_findings(
        plan=plan,
        source_text=source_text,
        formulas=formulas,
        docs=docs,
    )
    fallback_planner_brief = _build_planner_brief(
        plan=plan,
        glossary=glossary,
        explorer_findings=explorer_findings,
    )
    planner_brief = fallback_planner_brief
    storyboard_outline = _default_storyboard_outline(plan)
    try:
        llm_main_outputs, llm_main_meta = _generate_main_outputs_with_llm(
            plan=plan,
            source_text=source_text,
            fallback_formulas=formulas,
            fallback_glossary=glossary,
            fallback_planner_brief=fallback_planner_brief,
        )
        research_summary = llm_main_outputs["research_summary"]
        glossary = llm_main_outputs["glossary_terms"]
        formulas = llm_main_outputs["formula_candidates"]
        planner_brief = llm_main_outputs["planner_brief"]
        storyboard_outline = llm_main_outputs["storyboard_outline"]
    except (LLMRequestError, ValueError, TypeError, KeyError) as exc:
        llm_main_error = str(exc)

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
            "summary": "Explorer reference scan complete.",
            "findings": explorer_findings,
        },
    )

    _write_required_outputs(
        plan,
        session_id,
        "summarize.research",
        {
            "summary": research_summary,
            "glossary": glossary,
            "formulas": formulas,
            "source_documents": [item.to_dict() for item in docs],
            "explorer_findings": explorer_findings,
            "llm_generation": {
                "meta": llm_main_meta,
                "error": llm_main_error,
            },
        },
    )
    _complete_task(plan, session_id, "summarize.research", "lead")
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
            "llm_generation": {
                "meta": llm_main_meta,
                "error": llm_main_error,
            },
        },
    )
    _write_required_outputs(
        plan,
        session_id,
        "plan.storyboard",
        {
            "script_outline": storyboard_outline,
            "style": plan.source_bundle.style_refs,
            "planner_brief": planner_brief,
            "llm_generation": {
                "meta": llm_main_meta,
                "error": llm_main_error,
            },
        },
    )
    _complete_task(plan, session_id, "plan.storyboard", "coordinator")

    render_tasks = [
        task
        for task in plan.execution_tasks
        if task.stage == PipelineStage.DISPATCH
    ]
    render_evidence: list[dict[str, Any]] = []

    for task in render_tasks:
        worker_role = task.owner_role
        persist_agent_message(
            plan=plan,
            session_id=session_id,
            event_type=EventType.WORKER_PROGRESS,
            role_id=worker_role,
            stage=PipelineStage.DISPATCH,
            task_id=task.id,
            payload={"progress_label": "start_render"},
        )

        segment_id = _segment_id_from_task(task)
        segment = _segment_by_id(plan, segment_id)

        try:
            render_result = render_with_worker(plan=plan, segment=segment, task=task)
        except WorkerExecutionError as exc:
            if worker_role == "manim_worker":
                render_result = _fallback_manim_result(plan, segment_id, str(exc))
            else:
                persist_agent_message(
                    plan=plan,
                    session_id=session_id,
                    event_type=EventType.WORKER_BLOCKER,
                    role_id=worker_role,
                    stage=PipelineStage.DISPATCH,
                    task_id=task.id,
                    payload={"blocked_reason": str(exc)},
                )
                raise RuntimeError(f"render_failed:{task.id}:{exc}") from exc

        output_paths = _write_required_outputs(
            plan,
            session_id,
            task.id,
            {
                "render_summary": render_result.summary,
                "artifact_files": render_result.artifact_files,
                "artifact_metadata": render_result.metadata,
            },
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

    review_evidence_path = write_output_key(
        plan=plan,
        session_id=session_id,
        key=f"{plan.project_id}.review.evidence",
        payload={
            "project_id": plan.project_id,
            "session_id": session_id,
            "render_evidence": render_evidence,
            "checkpoints": [item.to_dict() for item in plan.review_checkpoints],
        },
    )

    draft_payload: dict[str, Any] = {
        "summary": "AI reviewer draft generated. Awaiting human approval.",
        "decision": "pending_human_confirmation",
        "risk_notes": [],
        "must_check": [],
        "checkpoints": [item.to_dict() for item in plan.review_checkpoints],
        "evidence_path": str(review_evidence_path),
        "llm_generation": {"meta": None, "error": None},
    }
    try:
        review_draft, review_meta = _generate_review_draft_with_llm(
            plan=plan,
            render_evidence=render_evidence,
        )
        draft_payload["summary"] = review_draft["summary"]
        draft_payload["decision"] = review_draft["decision"]
        draft_payload["risk_notes"] = review_draft["risk_notes"]
        draft_payload["must_check"] = review_draft["must_check"]
        draft_payload["llm_generation"] = {"meta": review_meta, "error": None}
    except (LLMRequestError, ValueError, TypeError, KeyError) as exc:
        draft_payload["llm_generation"] = {"meta": None, "error": str(exc)}

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
