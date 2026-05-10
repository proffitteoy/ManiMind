"""人工审核接口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from manimind.bootstrap import build_runtime_layout, sanitize_identifier
from manimind.review_workflow import apply_human_review_decision
from manimind.runtime_store import load_execution_task_snapshot

from .common import build_plan_from_manifest_payload, read_json_if_exists, resolve_manifest_payload

router = APIRouter()


class ReviewDecisionRequest(BaseModel):
    manifest: dict[str, Any] | None = None
    manifest_path: str | None = None
    decision: str
    session_id: str = Field(default="manual-session")
    reason: str | None = None
    must_fix: str | None = None
    should_keep: str | None = None
    prompt_patch: str | None = None
    target_roles: list[str] | None = None


@router.post("/review/decision")
def submit_review_decision(request: ReviewDecisionRequest) -> dict[str, Any]:
    payload = resolve_manifest_payload(
        manifest=request.manifest,
        manifest_path=request.manifest_path,
    )
    plan = build_plan_from_manifest_payload(payload)
    load_execution_task_snapshot(plan)
    try:
        result = apply_human_review_decision(
            plan=plan,
            session_id=request.session_id,
            decision=request.decision,
            reason=request.reason,
            must_fix=request.must_fix,
            should_keep=request.should_keep,
            prompt_patch=request.prompt_patch,
            target_roles=request.target_roles,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "result": result,
        "project_id": plan.project_id,
        "current_stage": plan.current_stage.value,
        "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
    }


@router.get("/{project_id}/review-return")
def get_latest_review_return(
    project_id: str,
    session_id: str = Query(default="manual-session"),
) -> dict[str, Any]:
    layout = build_runtime_layout(project_id)
    safe_session_id = sanitize_identifier(session_id)
    latest_path = (
        Path(layout.session_context_root) / safe_session_id / "review-returns" / "latest.json"
    )
    payload = read_json_if_exists(latest_path)
    return {
        "project_id": project_id,
        "session_id": safe_session_id,
        "path": str(latest_path),
        "payload": payload,
    }
