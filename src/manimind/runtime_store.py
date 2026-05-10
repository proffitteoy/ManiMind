"""运行时落盘与可追溯日志。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any

from .bootstrap import sanitize_identifier
from .models import EventType, PipelineStage, ProjectPlan
from .runtime import apply_runtime_snapshot, derive_current_stage, load_project_runtime


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    tmp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _build_event(
    event_type: EventType,
    project_id: str,
    session_id: str,
    **payload: Any,
) -> dict[str, Any]:
    return {
        "event": event_type.value,
        "project_id": project_id,
        "session_id": session_id,
        "timestamp": _utc_now(),
        **payload,
    }


def _append_runtime_event(
    project_dir: Path,
    session_dir: Path,
    payload: dict[str, Any],
) -> None:
    _append_jsonl(project_dir / "events.jsonl", payload)
    _append_jsonl(session_dir / "events.jsonl", payload)


def _write_project_task_snapshot(project_dir: Path, plan: ProjectPlan) -> None:
    _write_json(
        project_dir / "execution-tasks.json",
        {
            "project_id": plan.project_id,
            "updated_at": _utc_now(),
            "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
        },
    )


def _write_project_plan_snapshot(project_dir: Path, plan: ProjectPlan) -> None:
    _write_json(
        project_dir / "project-plan.json",
        {
            "project_id": plan.project_id,
            "plan": plan.to_dict(),
            "updated_at": _utc_now(),
        },
    )


def ensure_runtime_targets(plan: ProjectPlan, session_id: str) -> dict[str, Path]:
    """确保项目级与会话级目录存在。"""
    safe_session_id = sanitize_identifier(session_id)
    project_dir = Path(plan.runtime_layout.project_context_dir)
    session_dir = Path(plan.runtime_layout.session_context_root) / safe_session_id
    project_dir.mkdir(parents=True, exist_ok=True)
    session_dir.mkdir(parents=True, exist_ok=True)
    return {
        "project_dir": project_dir,
        "session_dir": session_dir,
    }


def persist_plan_snapshot(
    plan: ProjectPlan,
    session_id: str,
    source_manifest: str,
) -> dict[str, str]:
    """落盘项目状态、上下文注册与任务快照。"""
    targets = ensure_runtime_targets(plan, session_id)
    project_dir = targets["project_dir"]
    session_dir = targets["session_dir"]

    state_payload = {
        "project_id": plan.project_id,
        "current_stage": plan.current_stage.value,
        "stages": [stage.value for stage in plan.stages],
        "source_manifest": source_manifest,
        "updated_at": _utc_now(),
    }
    context_payload = {
        "project_id": plan.project_id,
        "contexts": [item.to_dict() for item in plan.contexts],
        "updated_at": _utc_now(),
    }
    task_payload = {
        "project_id": plan.project_id,
        "execution_tasks": [item.to_dict() for item in plan.execution_tasks],
        "updated_at": _utc_now(),
    }
    plan_payload = {
        "project_id": plan.project_id,
        "plan": plan.to_dict(),
        "updated_at": _utc_now(),
    }

    state_path = project_dir / "state.json"
    context_path = project_dir / "context-records.json"
    task_path = project_dir / "execution-tasks.json"
    plan_path = project_dir / "project-plan.json"
    _write_json(state_path, state_payload)
    _write_json(context_path, context_payload)
    _write_json(task_path, task_payload)
    _write_json(plan_path, plan_payload)

    event = _build_event(
        EventType.PLAN_SNAPSHOT,
        plan.project_id,
        session_dir.name,
        source_manifest=source_manifest,
        paths={
            "state": str(state_path),
            "context_records": str(context_path),
            "execution_tasks": str(task_path),
            "project_plan": str(plan_path),
        },
    )
    _append_runtime_event(project_dir, session_dir, event)
    return {
        "state": str(state_path),
        "context_records": str(context_path),
        "execution_tasks": str(task_path),
        "project_plan": str(plan_path),
    }


def persist_context_packet(
    plan: ProjectPlan,
    session_id: str,
    packet: dict[str, Any],
    prompt_sections: list[str] | None = None,
) -> dict[str, str]:
    """落盘角色上下文包并追加审计日志。"""
    targets = ensure_runtime_targets(plan, session_id)
    project_dir = targets["project_dir"]
    session_dir = targets["session_dir"]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    role_id = packet["role_id"]
    stage = packet["stage"]
    packet_name = f"{timestamp}-{role_id}-{stage}.json"

    packet_payload: dict[str, Any] = {
        "project_id": plan.project_id,
        "session_id": session_dir.name,
        "timestamp": _utc_now(),
        "message_type": EventType.DISPATCH_CONTEXT_PACK.value,
        "from_role": role_id,
        "stage": stage,
        "source_context_keys": [
            item["key"] for item in packet["context_specs"]  # type: ignore[index]
        ],
        "context_packet": packet,
    }
    if prompt_sections is not None:
        packet_payload["prompt_sections"] = prompt_sections

    packet_path = session_dir / "context-packets" / packet_name
    latest_path = session_dir / "context-pack-latest.json"
    _write_json(packet_path, packet_payload)
    _write_json(latest_path, packet_payload)

    event = _build_event(
        EventType.DISPATCH_CONTEXT_PACK,
        plan.project_id,
        session_dir.name,
        role_id=role_id,
        stage=stage,
        path=str(packet_path),
    )
    _append_runtime_event(project_dir, session_dir, event)
    return {
        "context_packet": str(packet_path),
        "context_packet_latest": str(latest_path),
    }


def persist_task_update(
    plan: ProjectPlan,
    session_id: str,
    mutation: dict[str, Any],
) -> dict[str, str]:
    """落盘任务更新结果、最新任务快照并追加审计日志。"""
    targets = ensure_runtime_targets(plan, session_id)
    project_dir = targets["project_dir"]
    session_dir = targets["session_dir"]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    task_id = mutation["task_id"]
    update_name = f"{timestamp}-{task_id}.json"

    update_payload = {
        "project_id": plan.project_id,
        "session_id": session_dir.name,
        "timestamp": _utc_now(),
        "message_type": EventType.LEADER_COMMIT.value,
        "mutation": mutation,
        "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
    }

    update_path = session_dir / "task-updates" / update_name
    latest_path = session_dir / "task-update-latest.json"
    project_task_path = project_dir / "execution-tasks.json"
    state_path = project_dir / "state.json"
    project_plan_path = project_dir / "project-plan.json"

    previous_state_payload: dict[str, Any] = {}
    if state_path.exists():
        previous_state_payload = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(previous_state_payload, dict):
            previous_state_payload = {}
    previous_stage = previous_state_payload.get("current_stage")
    if not isinstance(previous_stage, str):
        previous_stage = plan.current_stage.value

    plan.current_stage = derive_current_stage(plan)

    _write_json(update_path, update_payload)
    _write_json(latest_path, update_payload)
    _write_project_task_snapshot(project_dir, plan)
    _write_json(
        state_path,
        {
            "project_id": plan.project_id,
            "current_stage": plan.current_stage.value,
            "stages": [stage.value for stage in plan.stages],
            "source_manifest": previous_state_payload.get("source_manifest"),
            "updated_at": _utc_now(),
        },
    )
    _write_project_plan_snapshot(project_dir, plan)

    event = _build_event(
        EventType.LEADER_COMMIT,
        plan.project_id,
        session_dir.name,
        action="task_update",
        task_id=task_id,
        to_status=mutation.get("to_status"),
        success=mutation.get("success"),
        path=str(update_path),
    )
    _append_runtime_event(project_dir, session_dir, event)

    if previous_stage != plan.current_stage.value:
        stage_event = _build_event(
            EventType.STAGE_CHANGED,
            plan.project_id,
            session_dir.name,
            from_stage=previous_stage,
            to_stage=plan.current_stage.value,
            cause_task_id=task_id,
        )
        _append_runtime_event(project_dir, session_dir, stage_event)
    return {
        "task_update": str(update_path),
        "task_update_latest": str(latest_path),
        "project_execution_tasks": str(project_task_path),
        "state": str(state_path),
        "project_plan": str(project_plan_path),
    }


def persist_agent_message(
    plan: ProjectPlan,
    session_id: str,
    event_type: EventType,
    role_id: str,
    stage: PipelineStage | str,
    payload: dict[str, Any] | None = None,
    task_id: str | None = None,
) -> None:
    """追加 worker/reviewer 侧结构化消息到项目级与会话级事件流。"""
    allowed_event_types = {
        EventType.WORKER_PROGRESS,
        EventType.WORKER_BLOCKER,
        EventType.WORKER_RESULT,
        EventType.REVIEW_DECISION,
    }
    if event_type not in allowed_event_types:
        raise ValueError(f"unsupported_agent_message_type: {event_type.value}")

    targets = ensure_runtime_targets(plan, session_id)
    project_dir = targets["project_dir"]
    session_dir = targets["session_dir"]
    stage_value = stage.value if isinstance(stage, PipelineStage) else stage
    event_payload_data = payload or {}
    event_payload = _build_event(
        event_type,
        plan.project_id,
        session_dir.name,
        role_id=role_id,
        stage=stage_value,
        task_id=task_id,
        payload=event_payload_data,
    )
    _append_runtime_event(project_dir, session_dir, event_payload)

    task = None
    if task_id:
        task = next((item for item in plan.execution_tasks if item.id == task_id), None)

    should_persist_tasks = False
    if task is not None:
        now = _utc_now()
        if event_type == EventType.WORKER_PROGRESS:
            progress_label = event_payload_data.get("progress_label")
            if not isinstance(progress_label, str) or not progress_label.strip():
                progress_label = event_payload_data.get("message")
            if not isinstance(progress_label, str) or not progress_label.strip():
                progress_label = EventType.WORKER_PROGRESS.value
            task.last_progress = progress_label
            task.last_progress_at = now
            should_persist_tasks = True
        elif event_type == EventType.WORKER_BLOCKER:
            blocked_reason = event_payload_data.get("blocked_reason")
            if not isinstance(blocked_reason, str) or not blocked_reason.strip():
                blocked_reason = event_payload_data.get("reason")
            if not isinstance(blocked_reason, str) or not blocked_reason.strip():
                blocked_reason = "worker_blocker"
            task.blocked_reason = blocked_reason
            task.blocked_at = now
            should_persist_tasks = True
        elif event_type == EventType.WORKER_RESULT:
            task.blocked_reason = None
            task.blocked_at = None
            result_summary = event_payload_data.get("summary")
            if isinstance(result_summary, str) and result_summary.strip():
                task.last_progress = result_summary
                task.last_progress_at = now
            should_persist_tasks = True

    previous_stage = plan.current_stage
    stage_overridden = False
    if event_type == EventType.WORKER_BLOCKER:
        plan.current_stage = PipelineStage.BLOCKED
        stage_overridden = True
    elif event_type == EventType.REVIEW_DECISION:
        decision = event_payload_data.get("decision")
        if isinstance(decision, str):
            normalized = decision.strip().lower()
            if normalized in {"blocked", "reject", "rejected"}:
                plan.current_stage = PipelineStage.BLOCKED
                stage_overridden = True

    if should_persist_tasks:
        _write_project_task_snapshot(project_dir, plan)
        _write_project_plan_snapshot(project_dir, plan)

    if stage_overridden:
        state_path = project_dir / "state.json"
        state_payload: dict[str, Any] = {}
        if state_path.exists():
            loaded = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state_payload = loaded
        _write_json(
            state_path,
            {
                "project_id": plan.project_id,
                "current_stage": plan.current_stage.value,
                "stages": [item.value for item in plan.stages],
                "source_manifest": state_payload.get("source_manifest"),
                "updated_at": _utc_now(),
            },
        )
        _write_project_plan_snapshot(project_dir, plan)

    if previous_stage != plan.current_stage:
        stage_changed_event = _build_event(
            EventType.STAGE_CHANGED,
            plan.project_id,
            session_dir.name,
            from_stage=previous_stage.value,
            to_stage=plan.current_stage.value,
            cause_event=event_type.value,
            cause_task_id=task_id,
        )
        _append_runtime_event(project_dir, session_dir, stage_changed_event)


def load_execution_task_snapshot(plan: ProjectPlan) -> bool:
    """从项目快照回填任务状态，返回是否成功回填。"""
    project_dir = Path(plan.runtime_layout.project_context_dir)
    task_path = project_dir / "execution-tasks.json"
    state_path = project_dir / "state.json"
    if not task_path.exists() and not state_path.exists():
        return False

    runtime = load_project_runtime(plan)
    apply_runtime_snapshot(plan, runtime)
    return True
