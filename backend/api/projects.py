"""项目与 runtime 快照接口。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from manimind.bootstrap import build_runtime_layout, sanitize_identifier
from manimind.contract_store import load_contract_for_role
from manimind.runtime_store import persist_plan_snapshot

from .common import build_plan_from_manifest_payload, read_json_if_exists

router = APIRouter()


class PlanRequest(BaseModel):
    manifest: dict[str, Any]
    session_id: str = Field(default="manual-session")


@router.post("/plan")
def create_project_plan(request: PlanRequest) -> dict[str, Any]:
    plan = build_plan_from_manifest_payload(request.manifest)
    persisted = persist_plan_snapshot(
        plan=plan,
        session_id=request.session_id,
        source_manifest="api_payload",
    )
    return {
        "plan": plan.to_dict(),
        "persisted_paths": persisted,
    }


@router.get("/contracts")
def get_contract_schemas(roles: str | None = None) -> dict[str, Any]:
    if roles:
        role_ids = [item.strip() for item in roles.split(",") if item.strip()]
    else:
        role_ids = ["planner", "coordinator", "reviewer", "html_worker", "manim_worker", "svg_worker"]
    payload: dict[str, Any] = {}
    for role_id in role_ids:
        payload[role_id] = load_contract_for_role(role_id)
    return {"contracts": payload}


@router.get("/{project_id}/runtime")
def get_project_runtime(project_id: str) -> dict[str, Any]:
    layout = build_runtime_layout(project_id)
    project_dir = Path(layout.project_context_dir)
    return {
        "project_id": project_id,
        "paths": {
            "project_dir": str(project_dir),
            "state": str(project_dir / "state.json"),
            "context_records": str(project_dir / "context-records.json"),
            "execution_tasks": str(project_dir / "execution-tasks.json"),
            "project_plan": str(project_dir / "project-plan.json"),
            "events": str(project_dir / "events.jsonl"),
        },
        "state": read_json_if_exists(project_dir / "state.json"),
        "context_records": read_json_if_exists(project_dir / "context-records.json"),
        "execution_tasks": read_json_if_exists(project_dir / "execution-tasks.json"),
        "project_plan": read_json_if_exists(project_dir / "project-plan.json"),
    }


@router.get("/{project_id}/review-evidence")
def get_review_evidence(project_id: str) -> dict[str, Any]:
    layout = build_runtime_layout(project_id)
    project_dir = Path(layout.project_context_dir)
    artifacts_dir = project_dir / "artifacts"
    evidence_path = artifacts_dir / f"{project_id}.review.evidence.json"
    evidence = read_json_if_exists(evidence_path)
    return {
        "project_id": project_id,
        "evidence": evidence,
    }


@router.get("/{project_id}/narration-script")
def get_narration_script(project_id: str) -> dict[str, Any]:
    layout = build_runtime_layout(project_id)
    project_dir = Path(layout.project_context_dir)
    artifacts_dir = project_dir / "artifacts"
    script_path = artifacts_dir / f"{project_id}.narration.script.json"
    script = read_json_if_exists(script_path)
    return {
        "project_id": project_id,
        "script": script,
    }


@router.get("/{project_id}/trace")
def get_project_traces(
    project_id: str,
    session_id: str = "manual-session",
    stage: str | None = None,
    role: str | None = None,
    failed_only: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    layout = build_runtime_layout(project_id)
    safe_session = sanitize_identifier(session_id)
    trace_dir = Path(layout.session_context_root) / safe_session / "traces"
    summary_path = Path(layout.project_context_dir) / "trace-summary.json"
    items: list[dict[str, Any]] = []

    if trace_dir.exists():
        for path in sorted(trace_dir.glob("*.json"), reverse=True):
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
            items.append(payload)
            if limit > 0 and len(items) >= limit:
                break

    summary = read_json_if_exists(summary_path)
    return {
        "project_id": project_id,
        "session_id": safe_session,
        "total": len(items),
        "items": items,
        "summary": summary,
    }
