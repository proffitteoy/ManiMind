"""真实 worker 适配层测试。"""

from pathlib import Path

import pytest

from manimind.bootstrap import build_runtime_layout
from manimind.models import ExecutionTask, PipelineStage, RuntimeLayout, SegmentModality, SegmentSpec, SourceBundle
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


def test_html_adapter_renders_html_file(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    segment = plan.segments[0]
    result = HtmlWorkerAdapter().render(
        plan=plan,
        segment=segment,
        task=_task("render.seg-1.html", "html_worker"),
    )
    assert result.artifact_files
    assert Path(result.artifact_files[0]).exists()


def test_svg_adapter_renders_svg_file(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    segment = plan.segments[0]
    result = SvgWorkerAdapter().render(
        plan=plan,
        segment=segment,
        task=_task("render.seg-1.svg", "svg_worker"),
    )
    assert result.artifact_files
    assert Path(result.artifact_files[0]).exists()


def test_manim_adapter_raises_when_binary_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _plan(tmp_path)
    segment = plan.segments[0]
    monkeypatch.setattr("manimind.worker_adapters._find_tool", lambda *_args, **_kwargs: None)
    with pytest.raises(WorkerExecutionError):
        ManimWorkerAdapter().render(
            plan=plan,
            segment=segment,
            task=_task("render.seg-1.manim", "manim_worker"),
        )
