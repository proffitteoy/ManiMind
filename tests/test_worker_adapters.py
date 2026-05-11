"""真实 worker 适配层测试。"""

from pathlib import Path

import pytest

from manimind.bootstrap import build_runtime_layout
from manimind.models import (
    ExecutionTask,
    PipelineStage,
    RuntimeLayout,
    SegmentModality,
    SegmentSpec,
    SourceBundle,
)
from manimind.worker_adapters import (
    HtmlWorkerAdapter,
    ManimWorkerAdapter,
    SvgWorkerAdapter,
    WorkerExecutionError,
)
from manimind.workflow import build_project_plan


def _plan(tmp_path: Path):
    plan = build_project_plan(
        project_id="adapter-demo",
        title="adapter-demo",
        source_bundle=SourceBundle(paper_path="demo.md"),
        segments=[
            SegmentSpec(
                id="seg-1",
                title="title",
                goal="goal",
                narration="narration",
                modality=SegmentModality.HYBRID,
                formulas=["x^2"],
                requires_svg_motion=True,
            )
        ],
    )
    layout = build_runtime_layout("adapter-demo", root=tmp_path)
    plan.runtime_layout = RuntimeLayout(
        project_context_dir=layout.project_context_dir,
        session_context_root=layout.session_context_root,
        output_dir=layout.output_dir,
        bootstrap_report=layout.bootstrap_report,
        doctor_report=layout.doctor_report,
    )
    return plan


def _task(task_id: str, role: str) -> ExecutionTask:
    return ExecutionTask(
        id=task_id,
        subject="test",
        owner_role=role,
        active_form="testing",
        stage=PipelineStage.DISPATCH,
    )


def _shared_context() -> dict:
    return {
        "research_summary": "summary",
        "glossary_terms": ["term"],
        "formula_catalog": [{"formula": "x^2", "explanation": "demo", "usage": "demo"}],
        "style_guide": ["simple", "consistent-terms"],
        "planner_brief": {"must_checks": ["consistency"]},
        "storyboard_outline": [
            {
                "segment_id": "seg-1",
                "narration": "narration",
                "estimated_seconds": 12,
            }
        ],
    }


def _install_text_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("manimind.worker_adapters.load_llm_runtime_config", lambda: object())

    def _fake_generate_text_for_role(**kwargs):
        role_id = kwargs["role_id"]
        if role_id == "html_worker":
            return (
                "<!doctype html><html><head><title>demo</title></head><body><main>demo</main></body></html>",
                {"model": "stub-html"},
            )
        if role_id == "svg_worker":
            return (
                "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 1280 720\"><text x=\"40\" y=\"80\">demo</text></svg>",
                {"model": "stub-svg"},
            )
        return (
            "from manim import *\n\nclass SegmentSeg1Scene(Scene):\n    def construct(self):\n        self.add(Text('demo'))\n",
            {"model": "stub-manim"},
        )

    monkeypatch.setattr(
        "manimind.worker_adapters.generate_text_for_role",
        _fake_generate_text_for_role,
    )


def test_html_adapter_renders_html_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(tmp_path)
    segment = plan.segments[0]
    _install_text_stub(monkeypatch)
    result = HtmlWorkerAdapter().render(
        plan=plan,
        segment=segment,
        task=_task("render.seg-1.html", "html_worker"),
        session_id="session-1",
        shared_context=_shared_context(),
    )
    assert result.artifact_files
    assert Path(result.artifact_files[0]).exists()


def test_svg_adapter_renders_svg_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(tmp_path)
    segment = plan.segments[0]
    _install_text_stub(monkeypatch)
    result = SvgWorkerAdapter().render(
        plan=plan,
        segment=segment,
        task=_task("render.seg-1.svg", "svg_worker"),
        session_id="session-1",
        shared_context=_shared_context(),
    )
    assert result.artifact_files
    assert Path(result.artifact_files[0]).exists()


def test_manim_adapter_raises_when_binary_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _plan(tmp_path)
    segment = plan.segments[0]
    monkeypatch.setattr("manimind.worker_adapters._find_tool", lambda *_args, **_kwargs: None)
    with pytest.raises(WorkerExecutionError):
        ManimWorkerAdapter().render(
            plan=plan,
            segment=segment,
            task=_task("render.seg-1.manim", "manim_worker"),
            session_id="session-1",
            shared_context=_shared_context(),
        )
