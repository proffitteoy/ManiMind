"""执行器与人工审核闭环测试。"""

import json
from pathlib import Path

from manimind.bootstrap import build_runtime_layout
from manimind.context_assembly import build_context_packet
from manimind.executor import run_to_review
from manimind.models import PipelineStage, RuntimeLayout, SegmentModality, SegmentSpec, SourceBundle
from manimind.post_produce import finalize_delivery
from manimind.review_workflow import apply_human_review_decision
from manimind.runtime import load_project_runtime
from manimind.workflow import build_project_plan


def _build_demo_plan(root: Path, source_file: Path):
    plan = build_project_plan(
        project_id="demo-review",
        title="demo-review",
        source_bundle=SourceBundle(
            paper_path=str(source_file),
            note_paths=[],
            audience="test",
            style_refs=["minimal"],
        ),
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
    layout = build_runtime_layout("demo-review", root=root)
    plan.runtime_layout = RuntimeLayout(
        project_context_dir=layout.project_context_dir,
        session_context_root=layout.session_context_root,
        output_dir=layout.output_dir,
        bootstrap_report=layout.bootstrap_report,
        doctor_report=layout.doctor_report,
    )
    return plan


def test_run_to_review_reaches_review_stage(tmp_path: Path) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text(
        "极大函数定义 $$f^*(x)=\\sup_{r>0}\\frac{1}{|B|}\\int_B|f|$$",
        encoding="utf-8",
    )
    plan = _build_demo_plan(tmp_path, source_file)

    result = run_to_review(
        plan=plan,
        session_id="session-1",
        source_manifest="demo.json",
    )

    assert result["current_stage"] == "review"
    assert "review_evidence" in result
    assert Path(result["review_evidence"]).exists()
    runtime = load_project_runtime(plan)
    assert runtime.state["current_stage"] == "review"
    task_by_id = {item["id"]: item for item in runtime.execution_tasks}
    assert task_by_id["review.outputs"]["status"] == "in_progress"
    events_path = Path(plan.runtime_layout.project_context_dir) / "events.jsonl"
    events_text = events_path.read_text(encoding="utf-8")
    assert '"event": "review.draft"' in events_text
    assert (tmp_path / "outputs" / "demo-review" / "html" / "seg-1" / "index.html").exists()
    assert (tmp_path / "outputs" / "demo-review" / "svg" / "seg-1" / "scene.svg").exists()


def test_human_review_approve_unlocks_post_produce(tmp_path: Path) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text("proof $$m(E)=\\frac{1}{\\alpha}\\int_E|f|$$", encoding="utf-8")
    plan = _build_demo_plan(tmp_path, source_file)
    run_to_review(plan=plan, session_id="session-1", source_manifest="demo.json")

    result = apply_human_review_decision(
        plan=plan,
        session_id="session-1",
        decision="approve",
        reason="looks good",
    )

    assert result["decision"] == "approved"
    runtime = load_project_runtime(plan)
    assert runtime.state["current_stage"] == "post_produce"
    review_report = Path(result["review_report"])
    assert review_report.exists()


def test_human_review_return_writes_feedback_and_injects_context(tmp_path: Path) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text("proof $$a>b$$", encoding="utf-8")
    plan = _build_demo_plan(tmp_path, source_file)
    run_to_review(plan=plan, session_id="session-1", source_manifest="demo.json")

    result = apply_human_review_decision(
        plan=plan,
        session_id="session-1",
        decision="return",
        reason="needs fix",
        must_fix="repair notation",
        prompt_patch="use consistent alpha notation",
        target_roles=["coordinator", "reviewer"],
    )

    assert result["decision"] == "return"
    latest = Path(result["review_return_latest"])
    assert latest.exists()
    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["decision"] == "return"
    assert payload["reason"] == "needs fix"

    runtime = load_project_runtime(plan)
    assert runtime.state["current_stage"] == "blocked"

    packet = build_context_packet(
        plan=plan,
        role_id="coordinator",
        stage=PipelineStage.PLAN,
        allow_disallowed_stage=True,
        session_id="session-1",
    )
    feedback = packet["human_feedback"]
    assert isinstance(feedback, dict)
    assert feedback.get("reason") == "needs fix"


def test_finalize_delivery_builds_asset_manifest_and_done_stage(tmp_path: Path) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text("proof $$a>b$$", encoding="utf-8")
    plan = _build_demo_plan(tmp_path, source_file)
    run_to_review(plan=plan, session_id="session-1", source_manifest="demo.json")
    apply_human_review_decision(
        plan=plan,
        session_id="session-1",
        decision="approve",
        reason="ok",
    )

    result = finalize_delivery(
        plan=plan,
        session_id="session-1",
        tts_provider="noop",
    )
    assert Path(result["asset_manifest"]).exists()
    runtime = load_project_runtime(plan)
    assert runtime.state["current_stage"] == "done"
