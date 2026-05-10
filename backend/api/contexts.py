"""上下文包生成接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from manimind.context_assembly import (
    PromptSectionCache,
    build_context_packet,
    build_default_prompt_sections,
)
from manimind.models import PipelineStage
from manimind.runtime_store import load_execution_task_snapshot, persist_context_packet

from .common import build_plan_from_manifest_payload

router = APIRouter()


class ContextPackRequest(BaseModel):
    manifest: dict[str, Any]
    role_id: str
    stage: PipelineStage
    session_id: str = Field(default="manual-session")
    render_prompt_sections: bool = False
    allow_disallowed_stage: bool = False


@router.post("/context-pack")
def create_context_pack(request: ContextPackRequest) -> dict[str, Any]:
    plan = build_plan_from_manifest_payload(request.manifest)
    load_execution_task_snapshot(plan)
    try:
        packet = build_context_packet(
            plan=plan,
            role_id=request.role_id,
            stage=request.stage,
            allow_disallowed_stage=request.allow_disallowed_stage,
            session_id=request.session_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    output: dict[str, Any] = {"context_packet": packet}
    prompt_sections: list[str] | None = None
    if request.render_prompt_sections:
        cache = PromptSectionCache()
        prompt_sections = cache.resolve(build_default_prompt_sections(packet))
        output["prompt_sections"] = prompt_sections
    output["persisted_paths"] = persist_context_packet(
        plan=plan,
        session_id=request.session_id,
        packet=packet,
        prompt_sections=prompt_sections,
    )
    return output
