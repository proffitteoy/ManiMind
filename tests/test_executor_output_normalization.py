from __future__ import annotations

from manimind.executor import _normalize_role_output
from manimind.models import SegmentModality, SegmentSpec


class _PlanStub:
    def __init__(self) -> None:
        self.segments = [
            SegmentSpec(
                id="seg-1",
                title="segment-1",
                goal="goal-1",
                narration="narration-1",
                modality=SegmentModality.HYBRID,
                estimated_seconds=20,
            ),
            SegmentSpec(
                id="seg-2",
                title="segment-2",
                goal="goal-2",
                narration="narration-2",
                modality=SegmentModality.MANIM,
                estimated_seconds=35,
            ),
        ]


def _build_plan_stub() -> _PlanStub:
    return _PlanStub()


def test_normalize_explorer_output_ensures_required_arrays() -> None:
    plan = _build_plan_stub()
    payload = {
        "document_findings": {"path": "a.md"},
        "formula_candidates": None,
        "glossary_candidates": "term",
        "story_beats": ["beat"],
        "risk_flags": "risk",
        "source_highlights": {"quote": "x"},
    }

    normalized = _normalize_role_output("explorer", payload, plan)

    assert normalized["document_findings"] == [{"path": "a.md"}]
    assert normalized["formula_candidates"] == []
    assert normalized["glossary_candidates"] == ["term"]
    assert normalized["story_beats"] == ["beat"]
    assert normalized["risk_flags"] == ["risk"]
    assert normalized["source_highlights"] == [{"quote": "x"}]


def test_normalize_lead_output_converts_summary_and_lists() -> None:
    plan = _build_plan_stub()
    payload = {
        "research_summary": {"summary": "core-summary"},
        "glossary_terms": [" term-a ", "", 1],
        "formula_catalog": ["f(x)", {"formula": "g(x)", "explanation": "e", "usage": "u"}],
        "style_guide": [" fast ", None],
    }

    normalized = _normalize_role_output("lead", payload, plan)

    assert normalized["research_summary"] == "core-summary"
    assert normalized["glossary_terms"] == ["term-a"]
    assert normalized["formula_catalog"] == [
        {"formula": "f(x)", "explanation": "", "usage": ""},
        {"formula": "g(x)", "explanation": "e", "usage": "u"},
    ]
    assert normalized["style_guide"] == ["fast"]


def test_normalize_planner_output_fills_segment_priority_required_fields() -> None:
    plan = _build_plan_stub()
    payload = {
        "segment_priorities": [
            {"objective": "ignored-without-segment-id"},
            {
                "segment_id": "seg-1",
                "primary_worker_path": "html",
                "estimated_seconds": "25",
                "prerequisites": ["pre", 1],
            },
        ],
        "must_checks": [" math-check ", "", 1],
        "risk_flags": "risk-as-string",
        "visual_briefs": {"segment_id": "seg-1", "brief": "demo"},
        "narrative_arc": ["opening", None],
    }

    normalized = _normalize_role_output("planner", payload, plan)
    priorities = normalized["segment_priorities"]

    assert len(priorities) == 2
    assert priorities[0]["segment_id"] == "seg-1"
    assert priorities[0]["objective"] == "goal-1"
    assert priorities[0]["primary_worker_path"] == "html"
    assert priorities[0]["estimated_seconds"] == 25
    assert priorities[0]["semantic_type"] == ""
    assert priorities[0]["cognitive_goal"] == ""
    assert priorities[0]["why_this_worker"] == ""
    assert priorities[0]["density_level"] == "medium"
    assert priorities[0]["prerequisites"] == ["pre"]

    assert priorities[1]["segment_id"] == "seg-2"
    assert priorities[1]["objective"] == "goal-2"
    assert priorities[1]["primary_worker_path"] == "manim"
    assert priorities[1]["estimated_seconds"] == 35

    assert normalized["must_checks"] == ["math-check"]
    assert normalized["risk_flags"] == []
    assert normalized["visual_briefs"] == [{"segment_id": "seg-1", "brief": "demo"}]
    assert normalized["narrative_arc"] == ["opening"]


def test_normalize_coordinator_output_guards_object_fields() -> None:
    plan = _build_plan_stub()
    payload = {
        "script_outline": [
            {
                "segment_id": "seg-1",
                "estimated_seconds": "30",
                "formulas": [" x+y "],
                "html_motion_notes": [" move "],
                "scene_beats": ["b1", 1],
                "worker_instructions": {"html": " html ", "manim": None},
            }
        ],
        "storyboard_master": ["invalid"],
        "handoff_notes": "invalid",
        "quality_self_check": "invalid",
    }

    normalized = _normalize_role_output("coordinator", payload, plan)
    outline = normalized["script_outline"]

    assert len(outline) == 2
    assert outline[0]["segment_id"] == "seg-1"
    assert outline[0]["estimated_seconds"] == 30
    assert outline[0]["formulas"] == ["x+y"]
    assert outline[0]["html_motion_notes"] == ["move"]
    assert outline[0]["scene_beats"] == ["b1"]
    assert outline[0]["worker_instructions"] == {"html": "html", "manim": "", "svg": ""}
    assert normalized["storyboard_master"] == {}
    assert normalized["handoff_notes"] == {}
    assert normalized["quality_self_check"] == {}


def test_normalize_reviewer_output_sets_defaults_and_arrays() -> None:
    plan = _build_plan_stub()
    payload = {
        "summary": {"text": "review-summary"},
        "decision": "",
        "risk_notes": [" risk ", 1],
        "must_check": "not-array",
        "evidence_checks": {"name": "check-1", "status": "ok"},
        "script_quality": "invalid",
        "return_recommendation_if_needed": ["invalid"],
    }

    normalized = _normalize_role_output("reviewer", payload, plan)

    assert normalized["summary"] == "review-summary"
    assert normalized["decision"] == "pending_human_confirmation"
    assert normalized["risk_notes"] == ["risk"]
    assert normalized["must_check"] == []
    assert normalized["evidence_checks"] == [{"name": "check-1", "status": "ok"}]
    assert normalized["script_quality"] == {}
    assert normalized["return_recommendation_if_needed"] == {}
