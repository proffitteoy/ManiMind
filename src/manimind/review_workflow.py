"""人工审核闭环。"""

from __future__ import annotations

from typing import Any

from .artifact_store import has_output_key, write_output_key
from .models import EventType, PipelineStage, ProjectPlan, TaskStatus
from .runtime_store import (
    persist_agent_message,
    persist_human_review_return,
    persist_task_update,
)
from .task_board import update_execution_task_status


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
    if normalized not in {"approve", "approved", "return"}:
        raise ValueError(f"unsupported_review_decision:{decision}")

    if normalized in {"approve", "approved"}:
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
        return {
            "decision": "approved",
            "review_report": str(report_path),
            "review_task_status": result.to_status,
        }

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
    return {
        "decision": "return",
        **return_paths,
    }
