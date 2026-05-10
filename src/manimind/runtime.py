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
    snapshot_by_id: dict[str, dict[str, Any]] = {}
    for item in runtime.execution_tasks:
        if not isinstance(item, dict):
            continue
        task_id = item.get("id")
        if not isinstance(task_id, str):
            continue
        snapshot_by_id[task_id] = item

    for task in plan.execution_tasks:
        snapshot = snapshot_by_id.get(task.id)
        if snapshot is None:
            continue
        raw_status = snapshot.get("status")
        if isinstance(raw_status, str):
            try:
                task.status = TaskStatus(raw_status)
            except ValueError:
                pass
        blocked_reason = snapshot.get("blocked_reason")
        if isinstance(blocked_reason, str) or blocked_reason is None:
            task.blocked_reason = blocked_reason
        blocked_at = snapshot.get("blocked_at")
        if isinstance(blocked_at, str) or blocked_at is None:
            task.blocked_at = blocked_at
        last_progress = snapshot.get("last_progress")
        if isinstance(last_progress, str) or last_progress is None:
            task.last_progress = last_progress
        last_progress_at = snapshot.get("last_progress_at")
        if isinstance(last_progress_at, str) or last_progress_at is None:
            task.last_progress_at = last_progress_at

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
    def _tasks_for_stage(stage: PipelineStage) -> list[Any]:
        return [task for task in plan.execution_tasks if task.stage == stage]

    def _all_completed(stage: PipelineStage) -> bool:
        tasks = _tasks_for_stage(stage)
        return bool(tasks) and all(task.status == TaskStatus.COMPLETED for task in tasks)

    def _any_in_progress(stage: PipelineStage) -> bool:
        return any(
            task.status == TaskStatus.IN_PROGRESS for task in _tasks_for_stage(stage)
        )

    if _all_completed(PipelineStage.PACKAGE):
        return PipelineStage.DONE

    if _any_in_progress(PipelineStage.PACKAGE):
        return PipelineStage.PACKAGE

    if _all_completed(PipelineStage.POST_PRODUCE):
        return PipelineStage.PACKAGE

    if _any_in_progress(PipelineStage.POST_PRODUCE):
        return PipelineStage.POST_PRODUCE

    if _all_completed(PipelineStage.REVIEW):
        return PipelineStage.POST_PRODUCE

    if _any_in_progress(PipelineStage.REVIEW):
        return PipelineStage.REVIEW

    if _all_completed(PipelineStage.DISPATCH):
        return PipelineStage.REVIEW

    if _any_in_progress(PipelineStage.DISPATCH):
        return PipelineStage.DISPATCH

    if _all_completed(PipelineStage.PLAN):
        return PipelineStage.DISPATCH

    if _any_in_progress(PipelineStage.PLAN):
        return PipelineStage.PLAN

    if _all_completed(PipelineStage.SUMMARIZE):
        return PipelineStage.PLAN

    if _any_in_progress(PipelineStage.SUMMARIZE):
        return PipelineStage.SUMMARIZE

    if _all_completed(PipelineStage.INGEST):
        return PipelineStage.SUMMARIZE

    if _any_in_progress(PipelineStage.INGEST):
        return PipelineStage.INGEST

    return PipelineStage.PRESTART
