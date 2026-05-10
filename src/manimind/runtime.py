"""项目运行时加载、回填与阶段派生。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import PipelineStage, ProjectPlan, TaskStatus


@dataclass(slots=True)
class ProjectRuntime:
    project_id: str
    state: dict[str, Any]
    context_records: list[dict[str, Any]]
    execution_tasks: list[dict[str, Any]]
    project_plan: dict[str, Any] | None


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return payload


def load_project_runtime(plan: ProjectPlan) -> ProjectRuntime:
    """从 runtime 目录加载项目快照，缺失时回退到内存计划。"""
    project_dir = Path(plan.runtime_layout.project_context_dir)
    state_payload = _read_json(project_dir / "state.json") or {}
    context_payload = _read_json(project_dir / "context-records.json") or {}
    task_payload = _read_json(project_dir / "execution-tasks.json") or {}
    plan_payload = _read_json(project_dir / "project-plan.json") or {}

    state = {
        "project_id": plan.project_id,
        "current_stage": plan.current_stage.value,
        **state_payload,
    }
    context_records = context_payload.get("contexts")
    if not isinstance(context_records, list):
        context_records = [item.to_dict() for item in plan.contexts]

    execution_tasks = task_payload.get("execution_tasks")
    if not isinstance(execution_tasks, list):
        execution_tasks = [item.to_dict() for item in plan.execution_tasks]

    project_plan = plan_payload.get("plan")
    if project_plan is not None and not isinstance(project_plan, dict):
        project_plan = None

    return ProjectRuntime(
        project_id=plan.project_id,
        state=state,
        context_records=context_records,
        execution_tasks=execution_tasks,
        project_plan=project_plan,
    )


def apply_runtime_snapshot(plan: ProjectPlan, runtime: ProjectRuntime) -> None:
    """把 runtime 快照中的任务状态与阶段回填到内存计划。"""
    status_by_id: dict[str, TaskStatus] = {}
    for item in runtime.execution_tasks:
        if not isinstance(item, dict):
            continue
        task_id = item.get("id")
        raw_status = item.get("status")
        if not isinstance(task_id, str) or not isinstance(raw_status, str):
            continue
        try:
            status_by_id[task_id] = TaskStatus(raw_status)
        except ValueError:
            continue

    for task in plan.execution_tasks:
        if task.id in status_by_id:
            task.status = status_by_id[task.id]

    stage_value = runtime.state.get("current_stage")
    if isinstance(stage_value, str):
        try:
            plan.current_stage = PipelineStage(stage_value)
            return
        except ValueError:
            pass
    plan.current_stage = derive_current_stage(plan)


def derive_current_stage(plan: ProjectPlan) -> PipelineStage:
    """从执行任务状态派生当前阶段。"""
    status = {task.id: task.status for task in plan.execution_tasks}

    if status.get("post_produce.package") == TaskStatus.COMPLETED:
        return PipelineStage.DONE

    if status.get("post_produce.package") == TaskStatus.IN_PROGRESS:
        return PipelineStage.POST_PRODUCE

    if status.get("review.outputs") == TaskStatus.COMPLETED:
        return PipelineStage.PACKAGE

    if status.get("review.outputs") == TaskStatus.IN_PROGRESS:
        return PipelineStage.REVIEW

    render_tasks = [
        task
        for task in plan.execution_tasks
        if task.id.startswith("render.")
    ]
    if render_tasks and all(task.status == TaskStatus.COMPLETED for task in render_tasks):
        return PipelineStage.REVIEW

    if any(task.status == TaskStatus.IN_PROGRESS for task in render_tasks):
        return PipelineStage.DISPATCH

    if status.get("plan.storyboard") == TaskStatus.COMPLETED:
        return PipelineStage.DISPATCH

    if status.get("plan.storyboard") == TaskStatus.IN_PROGRESS:
        return PipelineStage.PLAN

    if status.get("summarize.research") == TaskStatus.COMPLETED:
        return PipelineStage.PLAN

    if status.get("summarize.research") == TaskStatus.IN_PROGRESS:
        return PipelineStage.SUMMARIZE

    if status.get("ingest.sources") == TaskStatus.COMPLETED:
        return PipelineStage.SUMMARIZE

    if status.get("ingest.sources") == TaskStatus.IN_PROGRESS:
        return PipelineStage.INGEST

    return PipelineStage.PRESTART
