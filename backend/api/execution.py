"""流程执行接口。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from manimind.bootstrap import repo_root, sanitize_identifier
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


@router.get("/{project_id}/events/stream")
async def event_stream(
    project_id: str,
    session_id: str = "manual-session",
) -> StreamingResponse:
    """SSE endpoint：推送项目事件流。"""
    safe_project_id = sanitize_identifier(project_id)
    safe_session_id = sanitize_identifier(session_id)

    project_events_path = (
        repo_root() / "runtime" / "projects" / safe_project_id / "events.jsonl"
    )
    session_events_path = (
        repo_root() / "runtime" / "sessions" / safe_session_id / "events.jsonl"
    )

    async def generate():
        last_project_pos = 0
        last_session_pos = 0

        while True:
            new_events = []

            if project_events_path.exists():
                content = project_events_path.read_text(encoding="utf-8")
                if len(content) > last_project_pos:
                    new_lines = content[last_project_pos:].strip().splitlines()
                    last_project_pos = len(content)
                    for line in new_lines:
                        if line.strip():
                            try:
                                new_events.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass

            if session_events_path.exists():
                content = session_events_path.read_text(encoding="utf-8")
                if len(content) > last_session_pos:
                    new_lines = content[last_session_pos:].strip().splitlines()
                    last_session_pos = len(content)
                    for line in new_lines:
                        if line.strip():
                            try:
                                new_events.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass

            for event in new_events:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            await asyncio.sleep(2)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
