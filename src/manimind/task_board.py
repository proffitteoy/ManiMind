"""执行任务状态机与验证关卡检查。"""

from __future__ import annotations

from dataclasses import dataclass

from .models import ExecutionTask, ProjectPlan, TaskStatus


@dataclass(slots=True)
class TaskMutationResult:
    success: bool
    task_id: str
    from_status: str | None
    to_status: str | None
    reason: str | None = None
    verification_nudge_needed: bool = False


def _task_index(plan: ProjectPlan) -> dict[str, ExecutionTask]:
    return {task.id: task for task in plan.execution_tasks}


def _is_unblocked(task: ExecutionTask, index: dict[str, ExecutionTask]) -> bool:
    for blocker in task.blocked_by:
        blocker_task = index.get(blocker)
        if blocker_task is None:
            continue
        if blocker_task.status != TaskStatus.COMPLETED:
            return False
    return True


def list_available_tasks(plan: ProjectPlan, owner_role: str | None = None) -> list[ExecutionTask]:
    """列出可执行任务（pending 且 blocker 已完成）。"""
    index = _task_index(plan)
    candidates = [
        task
        for task in plan.execution_tasks
        if task.status == TaskStatus.PENDING and _is_unblocked(task, index)
    ]
    if owner_role is not None:
        candidates = [task for task in candidates if task.owner_role == owner_role]
    return candidates


def update_execution_task_status(
    plan: ProjectPlan,
    task_id: str,
    new_status: TaskStatus,
    actor_role: str,
) -> TaskMutationResult:
    """按依赖规则更新任务状态。"""
    index = _task_index(plan)
    task = index.get(task_id)
    if task is None:
        return TaskMutationResult(
            success=False,
            task_id=task_id,
            from_status=None,
            to_status=new_status.value,
            reason="task_not_found",
        )

    if actor_role not in {task.owner_role, "lead"}:
        return TaskMutationResult(
            success=False,
            task_id=task_id,
            from_status=task.status.value,
            to_status=new_status.value,
            reason="owner_mismatch",
        )

    if new_status in {TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED} and not _is_unblocked(task, index):
        return TaskMutationResult(
            success=False,
            task_id=task_id,
            from_status=task.status.value,
            to_status=new_status.value,
            reason="task_blocked",
        )

    previous = task.status
    task.status = new_status

    review_task = index.get("review.outputs")
    pre_review_tasks = [
        item
        for item in plan.execution_tasks
        if item.id != "review.outputs"
        and "review.outputs" not in item.blocked_by
    ]
    non_review_done = all(
        item.status == TaskStatus.COMPLETED for item in pre_review_tasks
    )
    review_done = review_task is not None and review_task.status == TaskStatus.COMPLETED
    verification_nudge_needed = non_review_done and not review_done

    return TaskMutationResult(
        success=True,
        task_id=task_id,
        from_status=previous.value,
        to_status=new_status.value,
        verification_nudge_needed=verification_nudge_needed,
    )
