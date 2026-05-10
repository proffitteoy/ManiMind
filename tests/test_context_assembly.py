"""上下文装配与提示词分段测试。"""

from manimind.context_assembly import (
    PromptSectionCache,
    build_context_packet,
    build_default_prompt_sections,
)
from manimind.models import PipelineStage, SegmentModality, SegmentSpec, SourceBundle
from manimind.workflow import build_project_plan


def _demo_plan():
    return build_project_plan(
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
    assert packet["write_targets"] == ["demo.review.report"]
    constraints = packet["constraints"]
    assert "审核未通过前不得进入后处理。" in constraints
    assert "当前角色仅可输出审核结论。" in constraints


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
