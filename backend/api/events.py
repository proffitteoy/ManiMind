"""事件消息接口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from manimind.bootstrap import sanitize_identifier
from manimind.models import EventType, PipelineStage
from manimind.runtime_store import load_execution_task_snapshot, persist_agent_message

from .common import build_plan_from_manifest_payload, read_jsonl_events

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
                Path(plan.runtime_layout.session_context_root) / safe_session_id / "events.jsonl"
            ),
        },
    }


@router.get("/{project_id}/events")
def get_events(
    project_id: str,
    session_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict[str, Any]:
    from manimind.bootstrap import build_runtime_layout

    layout = build_runtime_layout(project_id)
    project_path = Path(layout.project_context_dir) / "events.jsonl"
    payload: dict[str, Any] = {
        "project_id": project_id,
        "project_events": read_jsonl_events(project_path, limit=limit),
        "project_events_path": str(project_path),
    }
    if session_id:
        safe_session_id = sanitize_identifier(session_id)
        session_path = Path(layout.session_context_root) / safe_session_id / "events.jsonl"
        payload["session_id"] = safe_session_id
        payload["session_events"] = read_jsonl_events(session_path, limit=limit)
        payload["session_events_path"] = str(session_path)
    return payload
