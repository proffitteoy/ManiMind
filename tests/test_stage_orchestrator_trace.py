"""Stage orchestrator / rerun / trace / selective rerun 测试。"""

from pathlib import Path

import pytest

from manimind.bootstrap import build_runtime_layout
from manimind.executor import run_to_review
from manimind.models import RuntimeLayout, SegmentModality, SegmentSpec, SourceBundle
from manimind.review_workflow import apply_human_review_decision
from manimind.runtime import load_project_runtime
from manimind.stage_orchestrator import rerun as rerun_stage
from manimind.trace_store import query_traces
from manimind.worker_adapters import WorkerRunResult
from manimind.workflow import build_project_plan


def _build_demo_plan(root: Path, source_file: Path):
    plan = build_project_plan(
        project_id="demo-stage",
        title="demo-stage",
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
    layout = build_runtime_layout("demo-stage", root=root)
    plan.runtime_layout = RuntimeLayout(
        project_context_dir=layout.project_context_dir,
        session_context_root=layout.session_context_root,
        output_dir=layout.output_dir,
        bootstrap_report=layout.bootstrap_report,
        doctor_report=layout.doctor_report,
    )
    return plan


def _install_executor_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("manimind.executor.load_llm_runtime_config", lambda: object())

    def _fake_call_json_role(**kwargs):
        role_id = kwargs["role_id"]
        payload = kwargs["payload"]
        if role_id == "explorer":
            return (
                {
                    "document_findings": payload["documents"],
                    "formula_candidates": ["x^2"],
                    "glossary_candidates": ["term"],
                    "story_beats": ["beat-1", "beat-2"],
                    "risk_flags": ["keep-notation-stable"],
                    "source_highlights": ["highlight"],
                },
                {"route": "worker", "model": "stub-explorer"},
            )
        if role_id == "lead":
            return (
                {
                    "research_summary": "summary",
                    "glossary_terms": ["term"],
                    "formula_catalog": [{"formula": "x^2", "explanation": "", "usage": ""}],
                    "style_guide": ["short"],
                },
                {"route": "primary", "model": "stub-lead"},
            )
        if role_id == "planner":
            return (
                {
                    "segment_priorities": [
                        {
                            "segment_id": "seg-1",
                            "objective": "goal",
                            "primary_worker_path": "hybrid",
                            "estimated_seconds": 20,
                            "semantic_type": "hook",
                            "cognitive_goal": "understand",
                            "why_this_worker": "mixed",
                            "density_level": "medium",
                            "prerequisites": [],
                        }
                    ],
                    "must_checks": ["math"],
                    "risk_flags": ["risk"],
                    "visual_briefs": [],
                    "narrative_arc": ["setup"],
                },
                {"route": "worker", "model": "stub-planner"},
            )
        if role_id == "coordinator":
            return (
                {
                    "script_outline": [
                        {
                            "segment_id": "seg-1",
                            "title": "hybrid",
                            "goal": "goal",
                            "narration": "narration",
                            "modality": "hybrid",
                            "estimated_seconds": 20,
                            "formulas": ["x^2"],
                            "html_motion_notes": [],
                            "scene_beats": ["beat"],
                            "worker_instructions": {"html": "", "manim": "", "svg": ""},
                        }
                    ],
                    "storyboard_master": {"theme": "demo"},
                    "handoff_notes": {"seg-1": {"narration_text": "narration"}},
                },
                {"route": "worker", "model": "stub-coordinator"},
            )
        if role_id == "reviewer":
            return (
                {
                    "summary": "review draft",
                    "decision": "pending_human_confirmation",
                    "risk_notes": ["spot-check formulas"],
                    "must_check": ["final terminology"],
                    "evidence_checks": [{"name": "rendered-assets", "status": "ok"}],
                },
                {"route": "review", "model": "stub-reviewer"},
            )
        raise AssertionError(f"unexpected role: {role_id}")

    def _fake_render_with_worker(
        *,
        plan,
        segment,
        task,
        session_id,
        shared_context,
        prompt_cache=None,
    ):
        del session_id, shared_context, prompt_cache
        out_root = Path(plan.runtime_layout.output_dir)
        if task.owner_role == "html_worker":
            out_dir = out_root / "html" / segment.id
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / "index.html"
            target.write_text("<!doctype html><html><body>demo</body></html>", encoding="utf-8")
            return WorkerRunResult(task.owner_role, segment.id, "html ok", [str(target)], {"worker": "html"})
        if task.owner_role == "svg_worker":
            out_dir = out_root / "svg" / segment.id
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / "scene.svg"
            target.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>", encoding="utf-8")
            return WorkerRunResult(task.owner_role, segment.id, "svg ok", [str(target)], {"worker": "svg"})
        out_dir = out_root / "manim" / segment.id
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "scene.mp4"
        target.write_bytes(b"fake-mp4")
        return WorkerRunResult(task.owner_role, segment.id, "manim ok", [str(target)], {"worker": "manim"})

    monkeypatch.setattr("manimind.executor._call_json_role", _fake_call_json_role)
    monkeypatch.setattr("manimind.executor.render_with_worker", _fake_render_with_worker)


def _install_trace_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("manimind.executor.load_llm_runtime_config", lambda: object())

    def _fake_generate_json_for_role(*, cfg, role_id, instructions, prompt):
        del cfg, instructions, prompt
        if role_id == "explorer":
            return (
                {
                    "document_findings": [],
                    "formula_candidates": ["x^2"],
                    "glossary_candidates": ["term"],
                    "story_beats": ["beat-1"],
                    "risk_flags": ["risk"],
                    "source_highlights": ["highlight"],
                },
                {"route": "worker", "model": "stub-explorer"},
            )
        if role_id == "lead":
            return (
                {
                    "research_summary": "summary",
                    "glossary_terms": ["term"],
                    "formula_catalog": [{"formula": "x^2", "explanation": "", "usage": ""}],
                    "style_guide": ["short"],
                },
                {"route": "primary", "model": "stub-lead"},
            )
        if role_id == "planner":
            return (
                {
                    "segment_priorities": [
                        {
                            "segment_id": "seg-1",
                            "objective": "goal",
                            "primary_worker_path": "hybrid",
                            "estimated_seconds": 20,
                            "semantic_type": "hook",
                            "cognitive_goal": "understand",
                            "why_this_worker": "mixed",
                            "density_level": "medium",
                            "prerequisites": [],
                        }
                    ],
                    "must_checks": ["math"],
                    "risk_flags": ["risk"],
                    "visual_briefs": [],
                    "narrative_arc": ["setup"],
                },
                {"route": "worker", "model": "stub-planner"},
            )
        if role_id == "coordinator":
            return (
                {
                    "script_outline": [
                        {
                            "segment_id": "seg-1",
                            "title": "hybrid",
                            "goal": "goal",
                            "narration": "narration",
                            "modality": "hybrid",
                            "estimated_seconds": 20,
                            "formulas": ["x^2"],
                            "html_motion_notes": [],
                            "scene_beats": ["beat"],
                            "worker_instructions": {"html": "", "manim": "", "svg": ""},
                        }
                    ],
                    "storyboard_master": {"theme": "demo"},
                    "handoff_notes": {"seg-1": {"narration_text": "narration"}},
                },
                {"route": "worker", "model": "stub-coordinator"},
            )
        if role_id == "reviewer":
            return (
                {
                    "summary": "review draft",
                    "decision": "pending_human_confirmation",
                    "risk_notes": ["spot-check formulas"],
                    "must_check": ["final terminology"],
                    "evidence_checks": [{"name": "rendered-assets", "status": "ok"}],
                },
                {"route": "review", "model": "stub-reviewer"},
            )
        raise AssertionError(f"unexpected role: {role_id}")

    def _fake_render_with_worker(
        *,
        plan,
        segment,
        task,
        session_id,
        shared_context,
        prompt_cache=None,
    ):
        del session_id, shared_context, prompt_cache
        out_root = Path(plan.runtime_layout.output_dir)
        out_dir = out_root / task.owner_role / segment.id
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "artifact.txt"
        target.write_text("ok", encoding="utf-8")
        return WorkerRunResult(task.owner_role, segment.id, "ok", [str(target)], {"worker": task.owner_role})

    monkeypatch.setattr("manimind.executor.generate_json_for_role", _fake_generate_json_for_role)
    monkeypatch.setattr("manimind.executor.render_with_worker", _fake_render_with_worker)


def test_rerun_plan_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text("proof $$x^2$$", encoding="utf-8")
    plan = _build_demo_plan(tmp_path, source_file)
    _install_executor_stubs(monkeypatch)

    run_to_review(plan=plan, session_id="session-1", source_manifest="demo.json")
    result = rerun_stage(
        plan=plan,
        session_id="session-1",
        source_manifest="demo.json",
        runner_name="plan",
    )

    assert result["runner"] == "plan"
    assert "planner_brief" in result["data"]


def test_trace_query_returns_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text("proof $$x^2$$", encoding="utf-8")
    plan = _build_demo_plan(tmp_path, source_file)
    _install_trace_stubs(monkeypatch)

    run_to_review(plan=plan, session_id="session-1", source_manifest="demo.json")
    traces = query_traces(plan=plan, session_id="session-1")

    assert traces
    assert any(item.get("role_id") == "planner" for item in traces)


def test_return_selective_rerun_resets_target_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text("proof $$x^2$$", encoding="utf-8")
    plan = _build_demo_plan(tmp_path, source_file)
    _install_executor_stubs(monkeypatch)

    run_to_review(plan=plan, session_id="session-1", source_manifest="demo.json")
    result = apply_human_review_decision(
        plan=plan,
        session_id="session-1",
        decision="return",
        reason="needs update",
        target_roles=["coordinator"],
    )

    assert result["decision"] == "return"
    assert "plan.storyboard" in result["reset_tasks"]
    runtime = load_project_runtime(plan)
    task_by_id = {item["id"]: item for item in runtime.execution_tasks}
    assert task_by_id["plan.storyboard"]["status"] == "pending"
    assert task_by_id["review.outputs"]["status"] == "pending"
