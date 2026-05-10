"""流程执行接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from manimind.executor import run_to_review
from manimind.post_produce import finalize_delivery

from .common import build_plan_from_manifest_payload, resolve_manifest_payload

router = APIRouter()


class RunToReviewRequest(BaseModel):
    manifest: dict[str, Any] | None = None
    manifest_path: str | None = None
    session_id: str = Field(default="manual-session")


class FinalizeRequest(BaseModel):
    manifest: dict[str, Any] | None = None
    manifest_path: str | None = None
    session_id: str = Field(default="manual-session")
    tts_provider: str = Field(default="powershell_sapi")


@router.post("/run-to-review")
def execute_run_to_review(request: RunToReviewRequest) -> dict[str, Any]:
    payload = resolve_manifest_payload(
        manifest=request.manifest,
        manifest_path=request.manifest_path,
    )
    plan = build_plan_from_manifest_payload(payload)
    source_manifest = request.manifest_path or "api_payload"
    try:
        result = run_to_review(
            plan=plan,
            session_id=request.session_id,
            source_manifest=source_manifest,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "result": result,
        "project_id": plan.project_id,
        "current_stage": plan.current_stage.value,
        "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
    }


@router.post("/finalize")
def execute_finalize(request: FinalizeRequest) -> dict[str, Any]:
    payload = resolve_manifest_payload(
        manifest=request.manifest,
        manifest_path=request.manifest_path,
    )
    plan = build_plan_from_manifest_payload(payload)
    try:
        result = finalize_delivery(
            plan=plan,
            session_id=request.session_id,
            tts_provider=request.tts_provider,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "result": result,
        "project_id": plan.project_id,
        "current_stage": plan.current_stage.value,
        "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
    }
