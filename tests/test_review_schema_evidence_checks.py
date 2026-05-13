"""review 阶段 schema evidence checks 测试。"""

from manimind.executor import _build_schema_evidence_checks, _merge_evidence_checks


def _status_map(checks: list[dict[str, object]]) -> dict[str, str]:
    output: dict[str, str] = {}
    for item in checks:
        name = item.get("name")
        status = item.get("status")
        if isinstance(name, str) and isinstance(status, str):
            output[name] = status
    return output


def test_schema_evidence_checks_cover_planner_and_coordinator_required_fields() -> None:
    plan_context = {
        "planner_brief": {
            "segment_priorities": [{"segment_id": "seg-1"}],
            "must_checks": ["math"],
            "risk_flags": ["risk"],
            "visual_briefs": [{"segment_id": "seg-1", "brief": "demo"}],
            "narrative_arc": ["setup"],
        },
        "storyboard_outline": [{"segment_id": "seg-1"}],
        "storyboard_master": {"theme": "demo"},
        "handoff_notes": {"seg-1": {"note": "ok"}},
    }
    checks = _build_schema_evidence_checks(plan_context, render_evidence=[{"task_id": "render.seg-1.html"}])
    statuses = _status_map(checks)

    assert statuses.get("planner.segment_priorities") == "ok"
    assert statuses.get("planner.narrative_arc") == "ok"
    assert statuses.get("coordinator.script_outline") == "ok"
    assert statuses.get("coordinator.storyboard_master") == "ok"
    assert statuses.get("coordinator.handoff_notes") == "ok"
    assert statuses.get("dispatch.render_evidence") == "ok"


def test_schema_evidence_checks_mark_missing_required_fields() -> None:
    plan_context = {
        "planner_brief": {
            "segment_priorities": [],
            "must_checks": [],
            "risk_flags": [],
            "visual_briefs": [],
            # narrative_arc missing
        },
        "storyboard_outline": [],
        "storyboard_master": {},
        "handoff_notes": {},
    }
    checks = _build_schema_evidence_checks(plan_context, render_evidence=[])
    statuses = _status_map(checks)

    assert statuses.get("planner.narrative_arc") == "missing"
    assert statuses.get("coordinator.script_outline") == "missing"
    assert statuses.get("dispatch.render_evidence") == "missing"


def test_merge_evidence_checks_keeps_schema_checks_and_appends_model_checks() -> None:
    schema_checks = [{"name": "planner.segment_priorities", "status": "ok"}]
    merged = _merge_evidence_checks(
        schema_checks=schema_checks,
        reviewer_checks=[{"name": "custom.check", "status": "ok"}],
    )
    assert merged[0]["name"] == "planner.segment_priorities"
    assert merged[1]["name"] == "custom.check"
