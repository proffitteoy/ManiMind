"""LLM trace 落盘与查询。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from .bootstrap import sanitize_identifier
from .models import FailureCategory, ProjectPlan


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


@dataclass(slots=True)
class LLMTrace:
    trace_id: str
    role_id: str
    stage: str
    task_id: str
    timestamp: str
    input_context_keys: list[str]
    prompt_sections: list[str]
    model_route: str
    model_output_excerpt: str
    parsed_output_keys: list[str]
    schema_validation: str
    artifact_files: list[str]
    render_command: str | None
    render_exit_code: int | None
    duration_ms: int
    token_usage: dict[str, int] | None
    retry_count: int
    failure_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _trace_file_name(trace: LLMTrace) -> str:
    stamp = trace.timestamp.replace(":", "").replace("-", "")
    safe_role = sanitize_identifier(trace.role_id)
    safe_stage = sanitize_identifier(trace.stage)
    return f"{stamp}-{safe_role}-{safe_stage}.json"


def _session_trace_dir(plan: ProjectPlan, session_id: str) -> Path:
    safe_session = sanitize_identifier(session_id)
    return Path(plan.runtime_layout.session_context_root) / safe_session / "traces"


def _project_trace_summary_path(plan: ProjectPlan) -> Path:
    return Path(plan.runtime_layout.project_context_dir) / "trace-summary.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def persist_llm_trace(
    plan: ProjectPlan,
    session_id: str,
    trace: LLMTrace,
) -> str:
    trace_dir = _session_trace_dir(plan, session_id)
    trace_path = trace_dir / _trace_file_name(trace)
    _write_json(trace_path, trace.to_dict())
    _update_trace_summary(plan, session_id, trace)
    return str(trace_path)


def _update_trace_summary(plan: ProjectPlan, session_id: str, trace: LLMTrace) -> None:
    path = _project_trace_summary_path(plan)
    payload = _load_json(path)
    total = int(payload.get("total_traces") or 0)
    failed = int(payload.get("failed_traces") or 0)
    by_role = payload.get("by_role")
    by_stage = payload.get("by_stage")
    by_failure = payload.get("by_failure")
    if not isinstance(by_role, dict):
        by_role = {}
    if not isinstance(by_stage, dict):
        by_stage = {}
    if not isinstance(by_failure, dict):
        by_failure = {}

    total += 1
    by_role[trace.role_id] = int(by_role.get(trace.role_id) or 0) + 1
    by_stage[trace.stage] = int(by_stage.get(trace.stage) or 0) + 1
    if trace.failure_reason:
        failed += 1
        category = FailureCategory.UNKNOWN.value
        if ":" in trace.failure_reason:
            candidate = trace.failure_reason.split(":", 1)[0].strip()
            if candidate:
                category = candidate
        by_failure[category] = int(by_failure.get(category) or 0) + 1

    _write_json(
        path,
        {
            "project_id": plan.project_id,
            "updated_at": _utc_now(),
            "last_session_id": sanitize_identifier(session_id),
            "total_traces": total,
            "failed_traces": failed,
            "by_role": by_role,
            "by_stage": by_stage,
            "by_failure": by_failure,
        },
    )


def query_traces(
    plan: ProjectPlan,
    session_id: str,
    *,
    stage: str | None = None,
    role: str | None = None,
    failed_only: bool = False,
) -> list[dict[str, Any]]:
    trace_dir = _session_trace_dir(plan, session_id)
    if not trace_dir.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(trace_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if stage and str(payload.get("stage")) != stage:
            continue
        if role and str(payload.get("role_id")) != role:
            continue
        if failed_only and not payload.get("failure_reason"):
            continue
        payload["trace_path"] = str(path)
        records.append(payload)
    return records

