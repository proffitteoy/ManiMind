"""post_produce 分段视频收集回归测试。"""

from pathlib import Path

from manimind.bootstrap import build_runtime_layout
from manimind.models import RuntimeLayout, SegmentModality, SegmentSpec, SourceBundle
from manimind.post_produce import _collect_segment_videos
from manimind.workflow import build_project_plan


def _build_hybrid_plan(tmp_path: Path):
    plan = build_project_plan(
        project_id="demo-post",
        title="demo-post",
        source_bundle=SourceBundle(paper_path=str(tmp_path / "paper.md")),
        segments=[
            SegmentSpec(
                id="seg-1",
                title="hybrid",
                goal="goal",
                narration="narration",
                modality=SegmentModality.HYBRID,
                formulas=["x^2"],
            )
        ],
    )
    layout = build_runtime_layout("demo-post", root=tmp_path)
    plan.runtime_layout = RuntimeLayout(
        project_context_dir=layout.project_context_dir,
        session_context_root=layout.session_context_root,
        output_dir=layout.output_dir,
        bootstrap_report=layout.bootstrap_report,
        doctor_report=layout.doctor_report,
    )
    return plan


def test_collect_segment_videos_keeps_manim_and_html_outputs(tmp_path: Path) -> None:
    plan = _build_hybrid_plan(tmp_path)
    output_root = Path(plan.runtime_layout.output_dir)
    manim_mp4 = output_root / "manim" / "seg-1" / "scene.mp4"
    html_mp4 = output_root / "html" / "seg-1" / "scene.mp4"
    manim_mp4.parent.mkdir(parents=True, exist_ok=True)
    html_mp4.parent.mkdir(parents=True, exist_ok=True)
    manim_mp4.write_bytes(b"manim")
    html_mp4.write_bytes(b"html")

    approved_records = [
        {
            "output_key": f"{plan.project_id}.manim.seg-1.approved",
            "artifact_files": [str(manim_mp4)],
        },
        {
            "output_key": f"{plan.project_id}.html.seg-1.approved",
            "artifact_files": [str(html_mp4)],
        },
    ]

    videos = _collect_segment_videos(plan, approved_records)
    assert videos == [str(manim_mp4), str(html_mp4)]
