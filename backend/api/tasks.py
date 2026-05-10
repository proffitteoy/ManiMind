"""任务查询与推进接口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from manimind.artifact_store import has_output_key
from manimind.models import TaskStatus
from manimind.runtime_store import load_execution_task_snapshot, persist_task_update
from manimind.task_board import update_execution_task_status

from .common import build_plan_from_manifest_payload

router = APIRouter()


class TaskUpdateRequest(BaseModel):
    manifest: dict[str, Any]
    task_id: str
    status: TaskStatus
    actor_role: str
    session_id: str = Field(default="manual-session")


class TaskListRequest(BaseModel):
    manifest: dict[str, Any]


@router.post("/tasks")
def list_tasks(request: TaskListRequest) -> dict[str, Any]:
    plan = build_plan_from_manifest_payload(request.manifest)
    load_execution_task_snapshot(plan)
    return {
        "project_id": plan.project_id,
        "current_stage": plan.current_stage.value,
        "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
    }


@router.post("/tasks/update")
def update_task(request: TaskUpdateRequest) -> dict[str, Any]:
    plan = build_plan_from_manifest_payload(request.manifest)
    load_execution_task_snapshot(plan)
    result = update_execution_task_status(
        plan=plan,
        task_id=request.task_id,
        new_status=request.status,
        actor_role=request.actor_role,
        output_checker=lambda key: has_output_key(plan, request.session_id, key),
    )
    mutation = {
        "success": result.success,
        "task_id": result.task_id,
        "from_status": result.from_status,
        "to_status": result.to_status,
        "reason": result.reason,
        "verification_nudge_needed": result.verification_nudge_needed,
    }
    persisted = persist_task_update(
        plan=plan,
        session_id=request.session_id,
        mutation=mutation,
    )
    return {
        "mutation": mutation,
        "current_stage": plan.current_stage.value,
        "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
        "persisted_paths": persisted,
    }
