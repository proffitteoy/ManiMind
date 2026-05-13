"""Schema contract 基础测试。"""

from manimind.contract_store import planner_segment_priority_fields, validate_role_output


def test_planner_segment_priority_fields_include_enhanced_keys() -> None:
    fields = set(planner_segment_priority_fields())
    assert "semantic_type" in fields
    assert "cognitive_goal" in fields
    assert "why_this_worker" in fields
    assert "density_level" in fields
    assert "prerequisites" in fields


def test_validate_role_output_returns_error_for_missing_required_field() -> None:
    error = validate_role_output(
        "planner",
        {
            "segment_priorities": [],
            "must_checks": [],
            "risk_flags": [],
            "visual_briefs": [],
            # 缺 narrative_arc
        },
    )
    assert isinstance(error, str)
    assert "missing_required" in error
