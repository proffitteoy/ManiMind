"""运行时落盘与可追溯日志。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any

from .bootstrap import sanitize_identifier
from .models import ProjectPlan
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

    event = {
        "event": "plan_snapshot",
        "project_id": plan.project_id,
        "session_id": session_dir.name,
        "source_manifest": source_manifest,
        "timestamp": _utc_now(),
        "paths": {
            "state": str(state_path),
            "context_records": str(context_path),
            "execution_tasks": str(task_path),
            "project_plan": str(plan_path),
        },
    }
    _append_jsonl(project_dir / "events.jsonl", event)
    _append_jsonl(session_dir / "events.jsonl", event)
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
        "context_packet": packet,
    }
    if prompt_sections is not None:
        packet_payload["prompt_sections"] = prompt_sections

    packet_path = session_dir / "context-packets" / packet_name
    latest_path = session_dir / "context-pack-latest.json"
    _write_json(packet_path, packet_payload)
    _write_json(latest_path, packet_payload)

    event = {
        "event": "context_pack",
        "project_id": plan.project_id,
        "session_id": session_dir.name,
        "role_id": role_id,
        "stage": stage,
        "timestamp": _utc_now(),
        "path": str(packet_path),
    }
    _append_jsonl(project_dir / "events.jsonl", event)
    _append_jsonl(session_dir / "events.jsonl", event)
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
        "mutation": mutation,
        "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
    }

    update_path = session_dir / "task-updates" / update_name
    latest_path = session_dir / "task-update-latest.json"
    project_task_path = project_dir / "execution-tasks.json"
    state_path = project_dir / "state.json"
    project_plan_path = project_dir / "project-plan.json"

    plan.current_stage = derive_current_stage(plan)

    previous_state_payload: dict[str, Any] = {}
    if state_path.exists():
        previous_state_payload = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(previous_state_payload, dict):
            previous_state_payload = {}

    _write_json(update_path, update_payload)
    _write_json(latest_path, update_payload)
    _write_json(
        project_task_path,
        {
            "project_id": plan.project_id,
            "updated_at": _utc_now(),
            "execution_tasks": [task.to_dict() for task in plan.execution_tasks],
        },
    )
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
    _write_json(
        project_plan_path,
        {
            "project_id": plan.project_id,
            "plan": plan.to_dict(),
            "updated_at": _utc_now(),
        },
    )

    event = {
        "event": "task_update",
        "project_id": plan.project_id,
        "session_id": session_dir.name,
        "task_id": task_id,
        "to_status": mutation.get("to_status"),
        "success": mutation.get("success"),
        "timestamp": _utc_now(),
        "path": str(update_path),
    }
    _append_jsonl(project_dir / "events.jsonl", event)
    _append_jsonl(session_dir / "events.jsonl", event)
    return {
        "task_update": str(update_path),
        "task_update_latest": str(latest_path),
        "project_execution_tasks": str(project_task_path),
        "state": str(state_path),
        "project_plan": str(project_plan_path),
    }


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
