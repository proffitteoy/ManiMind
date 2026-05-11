"""项目与 runtime 快照接口。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from manimind.bootstrap import build_runtime_layout
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
