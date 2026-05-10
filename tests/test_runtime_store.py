"""运行时落盘与快照恢复测试。"""

import json
from pathlib import Path

from manimind.bootstrap import build_runtime_layout
from manimind.context_assembly import build_context_packet
from manimind.models import PipelineStage, RuntimeLayout, SegmentModality, SegmentSpec, SourceBundle, TaskStatus
from manimind.runtime import derive_current_stage, load_project_runtime
from manimind.runtime_store import (
    load_execution_task_snapshot,
    persist_context_packet,
    persist_plan_snapshot,
    persist_task_update,
)
from manimind.workflow import build_project_plan


def _demo_plan(root: Path):
    plan = build_project_plan(
        project_id="demo",
        title="demo",
        source_bundle=SourceBundle(paper_path="paper.pdf"),
        segments=[
            SegmentSpec(
                id="seg-1",
                title="hybrid",
                goal="goal",
                narration="narration",
                modality=SegmentModality.HYBRID,
                formulas=["x^2"],
                requires_svg_motion=True,
            )
        ],
    )
    layout = build_runtime_layout("demo", root=root)
    plan.runtime_layout = RuntimeLayout(
        project_context_dir=layout.project_context_dir,
        session_context_root=layout.session_context_root,
        output_dir=layout.output_dir,
        bootstrap_report=layout.bootstrap_report,
        doctor_report=layout.doctor_report,
    )
    return plan


def test_persist_plan_snapshot_writes_core_files(tmp_path) -> None:
    plan = _demo_plan(tmp_path)
    paths = persist_plan_snapshot(
        plan=plan,
        session_id="session-1",
        source_manifest="demo.json",
    )
    assert Path(paths["state"]).exists()
    assert Path(paths["context_records"]).exists()
    assert Path(paths["execution_tasks"]).exists()
    assert Path(paths["project_plan"]).exists()

    state_payload = json.loads(Path(paths["state"]).read_text(encoding="utf-8"))
    assert state_payload["project_id"] == "demo"
    assert state_payload["current_stage"] == "prestart"


def test_context_and_task_logs_are_persisted(tmp_path) -> None:
    plan = _demo_plan(tmp_path)
    persist_plan_snapshot(
        plan=plan,
        session_id="session-1",
        source_manifest="demo.json",
    )
    packet = build_context_packet(
        plan=plan,
        role_id="coordinator",
        stage=PipelineStage.PLAN,
    )
    context_paths = persist_context_packet(
        plan=plan,
        session_id="session-1",
        packet=packet,
        prompt_sections=["role", "context"],
    )
    assert Path(context_paths["context_packet"]).exists()

    plan.execution_tasks[0].status = TaskStatus.COMPLETED
    task_paths = persist_task_update(
        plan=plan,
        session_id="session-1",
        mutation={
            "success": True,
            "task_id": "ingest.sources",
            "from_status": "pending",
            "to_status": "completed",
            "reason": None,
            "verification_nudge_needed": False,
        },
    )
    assert Path(task_paths["task_update"]).exists()
    assert Path(task_paths["project_execution_tasks"]).exists()

    project_events = (
        Path(plan.runtime_layout.project_context_dir) / "events.jsonl"
    ).read_text(encoding="utf-8")
    assert '"event": "context_pack"' in project_events
    assert '"event": "task_update"' in project_events


def test_load_execution_task_snapshot_restores_status(tmp_path) -> None:
    plan = _demo_plan(tmp_path)
    persist_plan_snapshot(
        plan=plan,
        session_id="session-1",
        source_manifest="demo.json",
    )
    plan.execution_tasks[0].status = TaskStatus.COMPLETED
    persist_task_update(
        plan=plan,
        session_id="session-1",
        mutation={
            "success": True,
            "task_id": "ingest.sources",
            "from_status": "pending",
            "to_status": "completed",
            "reason": None,
            "verification_nudge_needed": False,
        },
    )

    fresh_plan = _demo_plan(tmp_path)
    restored = load_execution_task_snapshot(fresh_plan)

    assert restored is True
    status_by_id = {task.id: task.status for task in fresh_plan.execution_tasks}
    assert status_by_id["ingest.sources"] == TaskStatus.COMPLETED


def test_persist_task_update_syncs_state_and_project_plan(tmp_path) -> None:
    plan = _demo_plan(tmp_path)
    persist_plan_snapshot(
        plan=plan,
        session_id="session-1",
        source_manifest="demo.json",
    )
    plan.execution_tasks[0].status = TaskStatus.COMPLETED
    persist_task_update(
        plan=plan,
        session_id="session-1",
        mutation={
            "success": True,
            "task_id": "ingest.sources",
            "from_status": "pending",
            "to_status": "completed",
            "reason": None,
            "verification_nudge_needed": False,
        },
    )
    runtime = load_project_runtime(plan)
    assert runtime.state["current_stage"] == "summarize"
    assert runtime.project_plan is not None
    assert runtime.project_plan["current_stage"] == "summarize"


def test_derive_current_stage_from_task_statuses(tmp_path) -> None:
    plan = _demo_plan(tmp_path)
    assert derive_current_stage(plan) == PipelineStage.PRESTART

    task_by_id = {task.id: task for task in plan.execution_tasks}
    task_by_id["ingest.sources"].status = TaskStatus.COMPLETED
    assert derive_current_stage(plan) == PipelineStage.SUMMARIZE

    task_by_id["summarize.research"].status = TaskStatus.COMPLETED
    assert derive_current_stage(plan) == PipelineStage.PLAN

    task_by_id["plan.storyboard"].status = TaskStatus.COMPLETED
    assert derive_current_stage(plan) == PipelineStage.DISPATCH
