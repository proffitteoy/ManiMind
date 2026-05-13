"""html_worker 契约与资源接线验证。"""

from manimind.bootstrap import check_external_paths, repo_root
from manimind.context_assembly import build_context_packet
from manimind.models import PipelineStage, SegmentModality, SegmentSpec, SourceBundle
from manimind.workflow import build_project_plan


def _html_plan():
    return build_project_plan(
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
                html_motion_notes=["use cards"],
            )
        ],
    )


def test_repo_includes_html_worker_reference_assets() -> None:
    root = repo_root()
    capability_paths = check_external_paths(root)

    assert capability_paths["html_skill_root"] is True
    assert capability_paths["hyperframes_root"] is True
    assert (
        root / "resources" / "skills" / "html-animation" / "SKILL.md"
    ).is_file()
    assert (
        root
        / "resources"
        / "references"
        / "hyperframes"
        / "skills"
        / "hyperframes"
        / "SKILL.md"
    ).is_file()
    assert (
        root
        / "resources"
        / "references"
        / "hyperframes"
        / "docs"
        / "reference"
        / "html-schema.mdx"
    ).is_file()


def test_html_worker_profile_and_execution_task_are_scoped_to_html_outputs() -> None:
    plan = _html_plan()

    profile = next(item for item in plan.agent_profiles if item.id == "html_worker")
    assert profile.allowed_stages == [PipelineStage.DISPATCH]
    assert profile.owned_outputs == [
        "demo.html.seg-1.approved",
        "demo.session.html.seg-1",
    ]
    assert "HTML 片段" in profile.output_contract

    render_task = next(
        item for item in plan.execution_tasks if item.id == "render.seg-1.html"
    )
    assert render_task.owner_role == "html_worker"
    assert render_task.required_outputs == [
        "demo.html.seg-1.approved",
        "demo.session.html.seg-1",
    ]


def test_html_worker_context_packet_contains_expected_inputs_and_write_targets() -> None:
    packet = build_context_packet(
        plan=_html_plan(),
        role_id="html_worker",
        stage=PipelineStage.DISPATCH,
    )

    assert packet["mode"] == "structured_write"
    assert packet["write_targets"] == [
        "demo.html.seg-1.approved",
        "demo.session.html.seg-1",
    ]

    keys = {item["key"] for item in packet["context_specs"]}
    assert keys >= {
        "demo.research.summary",
        "demo.glossary",
        "demo.formula.catalog",
        "demo.style.guide",
        "demo.narration.script",
        "demo.storyboard.master",
        "demo.session.handoff",
    }
    assert "demo.review.report" not in keys
