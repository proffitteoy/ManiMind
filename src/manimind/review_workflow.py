"""人工审核闭环。"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any

from .bootstrap import sanitize_identifier
from .artifact_store import has_output_key, output_path_for_key, write_output_key
from .models import EventType, PipelineStage, ProjectPlan, TaskStatus
from .runtime_store import (
    persist_agent_message,
    persist_human_review_return,
    persist_task_update,
)
from .task_board import update_execution_task_status


def _log_review(session_id: str, step: str, message: str) -> None:
    raw = os.environ.get("MANIMIND_PROGRESS_LOG", "1").strip().lower()
    if raw in {"0", "false", "off", "no"}:
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(
        f"[manimind][{stamp}][session={session_id}][review-{step}] {message}",
        file=sys.stderr,
        flush=True,
    )


def apply_human_review_decision(
    plan: ProjectPlan,
    session_id: str,
    *,
    decision: str,
    reason: str | None = None,
    must_fix: str | None = None,
    should_keep: str | None = None,
    prompt_patch: str | None = None,
    target_roles: list[str] | None = None,
) -> dict[str, Any]:
    """应用人工审核决定：approve 或 return。"""
    normalized = decision.strip().lower()
    _log_review(session_id, "decision", f"received decision={normalized}")
    if normalized not in {"approve", "approved", "return"}:
        raise ValueError(f"unsupported_review_decision:{decision}")

    if normalized in {"approve", "approved"}:
        _log_review(session_id, "approve", "writing review report")
        report_path = write_output_key(
            plan=plan,
            session_id=session_id,
            key=f"{plan.project_id}.review.report",
            payload={
                "project_id": plan.project_id,
                "decision": "approved",
                "reason": reason or "approved by human reviewer",
                "check_result": "pass",
            },
        )
        persist_agent_message(
            plan=plan,
            session_id=session_id,
            event_type=EventType.REVIEW_DECISION,
            role_id="human_reviewer",
            stage=PipelineStage.REVIEW,
            task_id="review.outputs",
            payload={
                "decision": "approved",
                "reason": reason or "approved",
            },
        )
        result = update_execution_task_status(
            plan=plan,
            task_id="review.outputs",
            new_status=TaskStatus.COMPLETED,
            actor_role="human_reviewer",
            output_checker=lambda key: has_output_key(plan, session_id, key),
        )
        persist_task_update(
            plan=plan,
            session_id=session_id,
            mutation={
                "success": result.success,
                "task_id": result.task_id,
                "from_status": result.from_status,
                "to_status": result.to_status,
                "reason": result.reason,
                "verification_nudge_needed": result.verification_nudge_needed,
            },
        )
        if not result.success:
            raise RuntimeError(f"review_complete_failed:{result.reason}")
        _log_review(session_id, "approve", "review.outputs completed")
        return {
            "decision": "approved",
            "review_report": str(report_path),
            "review_task_status": result.to_status,
        }

    _log_review(session_id, "return", "persisting return packet")
    return_payload = {
        "reason": reason or "manual return",
        "must_fix": must_fix or "",
        "should_keep": should_keep or "",
        "prompt_patch": prompt_patch or "",
        "target_roles": target_roles or ["coordinator", "reviewer"],
    }
    return_paths = persist_human_review_return(
        plan=plan,
        session_id=session_id,
        payload=return_payload,
    )
    snapshot_path = _snapshot_success_outputs(
        plan=plan,
        session_id=session_id,
        target_roles=return_payload["target_roles"],
    )
    reset_tasks = _reset_tasks_for_return(
        plan=plan,
        session_id=session_id,
        target_roles=return_payload["target_roles"],
    )
    persist_agent_message(
        plan=plan,
        session_id=session_id,
        event_type=EventType.REVIEW_DECISION,
        role_id="human_reviewer",
        stage=PipelineStage.REVIEW,
        task_id="review.outputs",
        payload={
            "decision": "return",
            "reason": return_payload["reason"],
        },
    )
    _log_review(session_id, "return", "return packet persisted")
    return {
        "decision": "return",
        "snapshot_path": snapshot_path,
        "reset_tasks": reset_tasks,
        **return_paths,
    }


def _task_by_id(plan: ProjectPlan, task_id: str):
    for task in plan.execution_tasks:
        if task.id == task_id:
            return task
    raise KeyError(f"unknown_task:{task_id}")


def _snapshot_success_outputs(
    *,
    plan: ProjectPlan,
    session_id: str,
    target_roles: list[str],
) -> str:
    safe_session = sanitize_identifier(session_id)
    review_return_dir = (
        Path(plan.runtime_layout.session_context_root)
        / safe_session
        / "review-returns"
    )
    review_return_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = review_return_dir / f"{datetime.now().strftime('%Y%m%dT%H%M%S')}-success-snapshot.json"

    records: list[dict[str, Any]] = []
    targeted = set(target_roles)
    for task in plan.execution_tasks:
        if task.status != TaskStatus.COMPLETED:
            continue
        if task.owner_role in targeted:
            continue
        available_outputs: list[str] = []
        for key in task.required_outputs:
            if has_output_key(plan, session_id, key):
                available_outputs.append(str(output_path_for_key(plan, session_id, key)))
        records.append(
            {
                "task_id": task.id,
                "owner_role": task.owner_role,
                "status": task.status.value,
                "output_files": available_outputs,
            }
        )
    snapshot_path.write_text(
        json.dumps(
            {
                "project_id": plan.project_id,
                "session_id": safe_session,
                "target_roles": target_roles,
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return str(snapshot_path)


def _reset_tasks_for_return(
    *,
    plan: ProjectPlan,
    session_id: str,
    target_roles: list[str],
) -> list[str]:
    target_role_set = {item.strip() for item in target_roles if item.strip()}
    if not target_role_set:
        target_role_set = {"coordinator", "reviewer"}

    selected: set[str] = {
        task.id
        for task in plan.execution_tasks
        if task.owner_role in target_role_set
    }
    selected.update({"review.outputs", "post_produce.outputs", "package.delivery"})

    changed = True
    while changed:
        changed = False
        for task in plan.execution_tasks:
            if task.id in selected:
                continue
            if any(blocker in selected for blocker in task.blocked_by):
                selected.add(task.id)
                changed = True

    reset_ids: list[str] = []
    for task_id in sorted(selected):
        task = _task_by_id(plan, task_id)
        if task.status == TaskStatus.PENDING and task.blocked_reason is None:
            continue
        from_status = task.status.value
        task.status = TaskStatus.PENDING
        task.blocked_reason = None
        task.blocked_at = None
        mutation = {
            "success": True,
            "task_id": task_id,
            "from_status": from_status,
            "to_status": TaskStatus.PENDING.value,
            "reason": "reset_after_human_return",
            "verification_nudge_needed": False,
        }
        persist_task_update(plan=plan, session_id=session_id, mutation=mutation)
        reset_ids.append(task_id)
    return reset_ids
