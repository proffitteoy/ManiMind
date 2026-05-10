"""执行任务状态机测试。"""

from manimind.models import SegmentModality, SegmentSpec, SourceBundle, TaskStatus
from manimind.task_board import list_available_tasks, update_execution_task_status
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


def test_only_unblocked_tasks_are_available() -> None:
    plan = _demo_plan()
    available = {task.id for task in list_available_tasks(plan)}
    assert available == {"ingest.sources"}


def test_task_status_update_blocks_on_dependencies() -> None:
    plan = _demo_plan()
    result = update_execution_task_status(
        plan=plan,
        task_id="plan.storyboard",
        new_status=TaskStatus.IN_PROGRESS,
        actor_role="coordinator",
    )
    assert result.success is False
    assert result.reason == "task_blocked"


def test_verification_nudge_when_non_review_tasks_done() -> None:
    plan = _demo_plan()

    update_execution_task_status(
        plan=plan,
        task_id="ingest.sources",
        new_status=TaskStatus.COMPLETED,
        actor_role="lead",
    )
    update_execution_task_status(
        plan=plan,
        task_id="explore.references",
        new_status=TaskStatus.COMPLETED,
        actor_role="explorer",
    )
    update_execution_task_status(
        plan=plan,
        task_id="summarize.research",
        new_status=TaskStatus.COMPLETED,
        actor_role="lead",
    )
    update_execution_task_status(
        plan=plan,
        task_id="plan.research_brief",
        new_status=TaskStatus.COMPLETED,
        actor_role="planner",
    )
    update_execution_task_status(
        plan=plan,
        task_id="plan.storyboard",
        new_status=TaskStatus.COMPLETED,
        actor_role="coordinator",
    )
    update_execution_task_status(
        plan=plan,
        task_id="render.seg-1.html",
        new_status=TaskStatus.COMPLETED,
        actor_role="html_worker",
    )
    update_execution_task_status(
        plan=plan,
        task_id="render.seg-1.manim",
        new_status=TaskStatus.COMPLETED,
        actor_role="manim_worker",
    )
    last_non_review = update_execution_task_status(
        plan=plan,
        task_id="render.seg-1.svg",
        new_status=TaskStatus.COMPLETED,
        actor_role="svg_worker",
    )
    assert last_non_review.success is True
    assert last_non_review.verification_nudge_needed is True

    result = update_execution_task_status(
        plan=plan,
        task_id="post_produce.outputs",
        new_status=TaskStatus.IN_PROGRESS,
        actor_role="lead",
    )

    assert result.success is False
    assert result.reason == "task_blocked"

    review_done = update_execution_task_status(
        plan=plan,
        task_id="review.outputs",
        new_status=TaskStatus.COMPLETED,
        actor_role="reviewer",
    )
    assert review_done.success is False
    assert review_done.reason == "owner_mismatch"

    review_done_by_human = update_execution_task_status(
        plan=plan,
        task_id="review.outputs",
        new_status=TaskStatus.COMPLETED,
        actor_role="human_reviewer",
    )
    assert review_done_by_human.success is True
    assert review_done_by_human.verification_nudge_needed is False

    package_before_post = update_execution_task_status(
        plan=plan,
        task_id="package.delivery",
        new_status=TaskStatus.IN_PROGRESS,
        actor_role="lead",
    )
    assert package_before_post.success is False
    assert package_before_post.reason == "task_blocked"
