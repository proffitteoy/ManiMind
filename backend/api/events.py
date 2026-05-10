"""事件消息接口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from manimind.bootstrap import sanitize_identifier
from manimind.models import EventType, PipelineStage
from manimind.runtime_store import load_execution_task_snapshot, persist_agent_message

from .common import build_plan_from_manifest_payload

router = APIRouter()


class AgentMessageRequest(BaseModel):
    manifest: dict[str, Any]
    event_type: EventType
    role_id: str
    stage: PipelineStage
    payload: dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None
    session_id: str = Field(default="manual-session")


@router.post("/events/message")
def append_agent_message(request: AgentMessageRequest) -> dict[str, Any]:
    plan = build_plan_from_manifest_payload(request.manifest)
    load_execution_task_snapshot(plan)
    safe_session_id = sanitize_identifier(request.session_id)
    try:
        persist_agent_message(
            plan=plan,
            session_id=request.session_id,
            event_type=request.event_type,
            role_id=request.role_id,
            stage=request.stage,
            payload=request.payload,
            task_id=request.task_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "event_type": request.event_type.value,
        "role_id": request.role_id,
        "stage": request.stage.value,
        "task_id": request.task_id,
        "current_stage": plan.current_stage.value,
        "persisted_paths": {
            "project_events": str(
                Path(plan.runtime_layout.project_context_dir) / "events.jsonl"
            ),
            "session_events": str(
                Path(plan.runtime_layout.session_context_root)
                / safe_session_id
                / "events.jsonl"
            ),
        },
    }
