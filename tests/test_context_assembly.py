"""上下文装配与提示词分段测试。"""

import json
from pathlib import Path

from manimind.bootstrap import build_runtime_layout
from manimind.context_assembly import (
    PromptSectionCache,
    build_context_packet,
    build_default_prompt_sections,
)
from manimind.models import (
    PipelineStage,
    RuntimeLayout,
    SegmentModality,
    SegmentSpec,
    SourceBundle,
)
from manimind.workflow import build_project_plan


def _demo_plan(root: Path | None = None):
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
    if root is not None:
        layout = build_runtime_layout("demo", root=root)
        plan.runtime_layout = RuntimeLayout(
            project_context_dir=layout.project_context_dir,
            session_context_root=layout.session_context_root,
            output_dir=layout.output_dir,
            bootstrap_report=layout.bootstrap_report,
            doctor_report=layout.doctor_report,
        )
    return plan


def test_context_packet_for_read_only_role_has_no_write_targets() -> None:
    packet = build_context_packet(
        plan=_demo_plan(),
        role_id="planner",
        stage=PipelineStage.PLAN,
    )

    assert packet["mode"] == "read_only"
    assert packet["write_targets"] == []
    assert packet["stage_allowed"] is True


def test_context_packet_for_verify_role_contains_review_constraints() -> None:
    packet = build_context_packet(
        plan=_demo_plan(),
        role_id="reviewer",
        stage=PipelineStage.REVIEW,
    )

    assert packet["mode"] == "verify_only"
    assert packet["write_targets"] == []
    constraints = packet["constraints"]
    assert isinstance(constraints, list)
    assert len(constraints) >= 4


def test_human_reviewer_has_review_report_write_target() -> None:
    packet = build_context_packet(
        plan=_demo_plan(),
        role_id="human_reviewer",
        stage=PipelineStage.REVIEW,
    )
    assert packet["mode"] == "verify_only"
    assert "demo.review.report" in packet["write_targets"]


def test_prompt_sections_are_cacheable() -> None:
    packet = build_context_packet(
        plan=_demo_plan(),
        role_id="coordinator",
        stage=PipelineStage.PLAN,
    )
    sections = build_default_prompt_sections(packet)
    cache = PromptSectionCache()

    first = cache.resolve(sections)
    second = cache.resolve(sections)

    assert first == second


def test_context_packet_respects_consumer_roles() -> None:
    packet = build_context_packet(
        plan=_demo_plan(),
        role_id="planner",
        stage=PipelineStage.PLAN,
    )
    keys = {item["key"] for item in packet["context_specs"]}
    assert "demo.review.report" not in keys


def test_disallowed_stage_raises_by_default() -> None:
    try:
        build_context_packet(
            plan=_demo_plan(),
            role_id="planner",
            stage=PipelineStage.DISPATCH,
        )
    except PermissionError as exc:
        assert "stage_not_allowed" in str(exc)
    else:
        raise AssertionError("expected PermissionError for disallowed stage")


def test_human_return_feedback_injected_for_target_role(tmp_path: Path) -> None:
    plan = _demo_plan(tmp_path)
    session_dir = Path(plan.runtime_layout.session_context_root) / "manual-session"
    return_dir = session_dir / "review-returns"
    return_dir.mkdir(parents=True, exist_ok=True)
    (return_dir / "latest.json").write_text(
        json.dumps(
            {
                "decision": "return",
                "reason": "needs revision",
                "must_fix": "fix formulas",
                "target_roles": ["coordinator"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    coordinator_packet = build_context_packet(
        plan=plan,
        role_id="coordinator",
        stage=PipelineStage.PLAN,
        session_id="manual-session",
        allow_disallowed_stage=True,
    )
    assert coordinator_packet["human_feedback"] is not None

    planner_packet = build_context_packet(
        plan=plan,
        role_id="planner",
        stage=PipelineStage.PLAN,
        session_id="manual-session",
    )
    assert planner_packet["human_feedback"] is None
