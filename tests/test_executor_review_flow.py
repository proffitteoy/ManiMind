"""执行器与人工审核闭环测试。"""

import json
from pathlib import Path

import pytest

from manimind.bootstrap import build_runtime_layout
from manimind.context_assembly import build_context_packet
from manimind.executor import run_to_review
from manimind.models import (
    PipelineStage,
    RuntimeLayout,
    SegmentModality,
    SegmentSpec,
    SourceBundle,
)
from manimind.post_produce import finalize_delivery
from manimind.review_workflow import apply_human_review_decision
from manimind.runtime import load_project_runtime
from manimind.worker_adapters import WorkerRunResult
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
                    "formula_catalog": [
                        {
                            "formula": "x^2",
                            "explanation": "demo explanation",
                            "usage": "demo usage",
                        }
                    ],
                    "style_guide": ["short sentences", "consistent notation"],
                },
                {"route": "primary", "model": "stub-lead"},
            )
        if role_id == "planner":
            segment_priorities = [
                {
                    "segment_id": item["id"],
                    "objective": item["goal"],
                    "primary_worker_path": item["modality"],
                    "estimated_seconds": item["estimated_seconds"],
                }
                for item in payload["segments"]
            ]
            return (
                {
                    "segment_priorities": segment_priorities,
                    "must_checks": ["math-correctness"],
                    "risk_flags": ["keep-notation-stable"],
                    "visual_briefs": [{"segment_id": "seg-1", "brief": "demo"}],
                    "narrative_arc": ["setup", "proof"],
                },
                {"route": "worker", "model": "stub-planner"},
            )
        if role_id == "coordinator":
            outline = []
            for item in payload["segments"]:
                outline.append(
                    {
                        "segment_id": item["id"],
                        "title": item["title"],
                        "goal": item["goal"],
                        "narration": item["narration"],
                        "modality": item["modality"],
                        "estimated_seconds": item["estimated_seconds"],
                        "formulas": item.get("formulas", []),
                        "html_motion_notes": item.get("html_motion_notes", []),
                        "scene_beats": ["beat"],
                        "worker_instructions": {
                            "html": "html instruction",
                            "manim": "manim instruction",
                            "svg": "svg instruction",
                        },
                    }
                )
            return (
                {
                    "script_outline": outline,
                    "storyboard_master": {"theme": "demo"},
                    "handoff_notes": {"review_focus": ["consistency"]},
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
        root = Path(plan.runtime_layout.output_dir)
        if task.owner_role == "html_worker":
            out_dir = root / "html" / segment.id
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / "index.html"
            target.write_text("<!doctype html><html><body>demo</body></html>", encoding="utf-8")
            return WorkerRunResult(
                worker_role=task.owner_role,
                segment_id=segment.id,
                summary="html ok",
                artifact_files=[str(target)],
                metadata={"worker": "html"},
            )
        if task.owner_role == "svg_worker":
            out_dir = root / "svg" / segment.id
            out_dir.mkdir(parents=True, exist_ok=True)
            target = out_dir / "scene.svg"
            target.write_text(
                "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 1280 720\"></svg>",
                encoding="utf-8",
            )
            return WorkerRunResult(
                worker_role=task.owner_role,
                segment_id=segment.id,
                summary="svg ok",
                artifact_files=[str(target)],
                metadata={"worker": "svg"},
            )

        out_dir = root / "manim" / segment.id
        out_dir.mkdir(parents=True, exist_ok=True)
        scene_py = out_dir / "scene.py"
        scene_mp4 = out_dir / "scene.mp4"
        render_log = out_dir / "render.log"
        scene_py.write_text("from manim import *\n", encoding="utf-8")
        scene_mp4.write_bytes(b"fake-mp4")
        render_log.write_text("ok", encoding="utf-8")
        return WorkerRunResult(
            worker_role=task.owner_role,
            segment_id=segment.id,
            summary="manim ok",
            artifact_files=[str(scene_py), str(scene_mp4), str(render_log)],
            metadata={"worker": "manim"},
        )

    monkeypatch.setattr("manimind.executor._call_json_role", _fake_call_json_role)
    monkeypatch.setattr("manimind.executor.render_with_worker", _fake_render_with_worker)


def test_run_to_review_reaches_review_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text(
        "极大函数定义 $$f^*(x)=\\sup_{r>0}\\frac{1}{|B|}\\int_B|f|$$",
        encoding="utf-8",
    )
    plan = _build_demo_plan(tmp_path, source_file)
    _install_executor_stubs(monkeypatch)

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
    assert (tmp_path / "runtime" / "projects" / "demo-review" / "artifacts" / "demo-review.style.guide.json").exists()


def test_planner_can_skip_non_primary_worker_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text("proof $$x^2$$", encoding="utf-8")
    plan = _build_demo_plan(tmp_path, source_file)
    _install_executor_stubs(monkeypatch)

    original_call = run_to_review.__globals__["_call_json_role"]

    def _planner_prefers_html(**kwargs):
        payload, meta = original_call(**kwargs)
        if kwargs["role_id"] == "planner":
            payload["segment_priorities"][0]["primary_worker_path"] = "html"
        return payload, meta

    monkeypatch.setattr("manimind.executor._call_json_role", _planner_prefers_html)

    run_to_review(plan=plan, session_id="session-1", source_manifest="demo.json")

    assert (tmp_path / "outputs" / "demo-review" / "html" / "seg-1" / "index.html").exists()
    assert not (tmp_path / "outputs" / "demo-review" / "svg" / "seg-1" / "scene.svg").exists()
    assert not (tmp_path / "outputs" / "demo-review" / "manim" / "seg-1" / "scene.mp4").exists()

    runtime = load_project_runtime(plan)
    task_by_id = {item["id"]: item for item in runtime.execution_tasks}
    assert task_by_id["render.seg-1.svg"]["status"] == "completed"
    assert task_by_id["render.seg-1.manim"]["status"] == "completed"

    events_path = Path(plan.runtime_layout.project_context_dir) / "events.jsonl"
    events_text = events_path.read_text(encoding="utf-8")
    assert "skipped_by_plan" in events_text


def test_human_review_approve_unlocks_post_produce(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text("proof $$m(E)=\\frac{1}{\\alpha}\\int_E|f|$$", encoding="utf-8")
    plan = _build_demo_plan(tmp_path, source_file)
    _install_executor_stubs(monkeypatch)
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


def test_human_review_return_writes_feedback_and_injects_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text("proof $$a>b$$", encoding="utf-8")
    plan = _build_demo_plan(tmp_path, source_file)
    _install_executor_stubs(monkeypatch)
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


def test_finalize_delivery_builds_asset_manifest_and_done_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_file = tmp_path / "source.md"
    source_file.write_text("proof $$a>b$$", encoding="utf-8")
    plan = _build_demo_plan(tmp_path, source_file)
    _install_executor_stubs(monkeypatch)
    run_to_review(plan=plan, session_id="session-1", source_manifest="demo.json")
    apply_human_review_decision(
        plan=plan,
        session_id="session-1",
        decision="approve",
        reason="ok",
    )

    def _fake_build_final_video(**kwargs):
        output_dir = kwargs["output_dir"]
        video_dir = Path(output_dir) / "video"
        video_dir.mkdir(parents=True, exist_ok=True)
        target = video_dir / "final.mp4"
        target.write_bytes(b"fake-video")
        return str(target), None

    monkeypatch.setattr("manimind.post_produce._build_final_video", _fake_build_final_video)

    result = finalize_delivery(
        plan=plan,
        session_id="session-1",
        tts_provider="noop",
    )
    assert Path(result["asset_manifest"]).exists()
    assert result["subtitle_file"] is not None
    assert Path(result["subtitle_file"]).exists()
    runtime = load_project_runtime(plan)
    assert runtime.state["current_stage"] == "done"
