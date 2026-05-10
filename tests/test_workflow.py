"""工作流任务分发规则测试。"""

from manimind.models import AgentMode, SegmentModality, SegmentSpec, SourceBundle, WorkerKind
from manimind.workflow import build_project_plan


def test_hybrid_segment_dispatches_all_expected_workers() -> None:
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

    workers = {task.worker for task in plan.tasks}
    assert workers == {WorkerKind.HTML, WorkerKind.MANIM, WorkerKind.SVG}


def test_html_segment_only_dispatches_html_worker() -> None:
    plan = build_project_plan(
        project_id="demo",
        title="demo",
        source_bundle=SourceBundle(paper_path="paper.pdf"),
        segments=[
            SegmentSpec(
                id="seg-1",
                title="html",
                goal="goal",
                narration="narration",
                modality=SegmentModality.HTML,
            )
        ],
    )

    workers = [task.worker for task in plan.tasks]
    assert workers == [WorkerKind.HTML]


def test_project_plan_includes_verification_gate_and_agent_profiles() -> None:
    plan = build_project_plan(
        project_id="demo-project",
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

    execution_tasks = {task.id: task for task in plan.execution_tasks}
    assert execution_tasks["review.outputs"].verification_required is True
    assert execution_tasks["review.outputs"].blocked_by == [
        "render.seg-1.html",
        "render.seg-1.manim",
        "render.seg-1.svg",
    ]
    assert execution_tasks["review.outputs"].blocks == ["post_produce.outputs"]
    assert execution_tasks["post_produce.outputs"].blocked_by == [
        "review.outputs"
    ]
    assert execution_tasks["post_produce.outputs"].blocks == ["package.delivery"]
    assert execution_tasks["package.delivery"].blocked_by == [
        "post_produce.outputs"
    ]
    assert execution_tasks["package.delivery"].required_outputs == [
        "demo-project.asset.manifest"
    ]
    assert execution_tasks["render.seg-1.html"].stage.value == "dispatch"
    assert execution_tasks["package.delivery"].stage.value == "package"

    agent_profiles = {profile.id: profile for profile in plan.agent_profiles}
    assert agent_profiles["planner"].mode == AgentMode.READ_ONLY
    assert agent_profiles["reviewer"].mode == AgentMode.VERIFY_ONLY
    assert (
        plan.runtime_layout.project_context_dir.endswith(
            "runtime\\projects\\demo-project"
        )
        or plan.runtime_layout.project_context_dir.endswith(
            "runtime/projects/demo-project"
        )
    )
