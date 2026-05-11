"""测试能力注册表和多文档输入系统。"""

from pathlib import Path

import pytest

from manimind.capability_registry import (
    CapabilityRef,
    build_capability_summaries,
    capabilities_for_role,
    resolve_capabilities,
)
from manimind.ingest import (
    SourceDocument,
    documents_for_role,
    load_multi_documents,
)
from manimind.models import InputDocRole, InputDocument, SourceBundle


class TestCapabilityRegistry:
    def test_resolve_capabilities_returns_all_definitions(self, tmp_path):
        (tmp_path / "pdf").mkdir()
        (tmp_path / "resources" / "skills" / "html-animation").mkdir(parents=True)
        (tmp_path / "resources" / "references" / "hyperframes").mkdir(parents=True)
        (tmp_path / "resources" / "skills" / "manim").mkdir(parents=True)

        caps = resolve_capabilities(tmp_path)
        assert len(caps) == 4
        names = {c.name for c in caps}
        assert "pdf_ingest_skill" in names
        assert "html_animation_skill" in names
        assert "hyperframes_reference" in names
        assert "manim_skill" in names

    def test_resolve_capabilities_marks_availability(self, tmp_path):
        (tmp_path / "pdf").mkdir()
        caps = resolve_capabilities(tmp_path)
        pdf_cap = next(c for c in caps if c.name == "pdf_ingest_skill")
        html_cap = next(c for c in caps if c.name == "html_animation_skill")
        assert pdf_cap.available is True
        assert html_cap.available is False

    def test_capabilities_for_role_filters_correctly(self, tmp_path):
        (tmp_path / "pdf").mkdir()
        (tmp_path / "resources" / "skills" / "html-animation").mkdir(parents=True)
        (tmp_path / "resources" / "references" / "hyperframes").mkdir(parents=True)
        (tmp_path / "resources" / "skills" / "manim").mkdir(parents=True)

        html_caps = capabilities_for_role("html_worker", "dispatch", tmp_path)
        cap_names = {c.name for c in html_caps}
        assert "html_animation_skill" in cap_names
        assert "hyperframes_reference" in cap_names
        assert "pdf_ingest_skill" not in cap_names

    def test_capabilities_for_role_lead_ingest(self, tmp_path):
        (tmp_path / "pdf").mkdir()
        caps = capabilities_for_role("lead", "ingest", tmp_path)
        assert len(caps) == 1
        assert caps[0].name == "pdf_ingest_skill"

    def test_capabilities_for_role_manim_worker(self, tmp_path):
        (tmp_path / "resources" / "skills" / "manim").mkdir(parents=True)
        caps = capabilities_for_role("manim_worker", "dispatch", tmp_path)
        assert len(caps) == 1
        assert caps[0].name == "manim_skill"

    def test_build_capability_summaries_worker_gets_detail(self, tmp_path):
        (tmp_path / "resources" / "skills" / "html-animation").mkdir(parents=True)
        (tmp_path / "resources" / "references" / "hyperframes").mkdir(parents=True)
        text = build_capability_summaries("html_worker", "dispatch", tmp_path)
        assert "可用能力资源" in text
        assert "路径：" in text
        assert "说明：" in text

    def test_build_capability_summaries_planner_gets_index(self, tmp_path):
        (tmp_path / "resources" / "skills" / "html-animation").mkdir(parents=True)
        (tmp_path / "resources" / "references" / "hyperframes").mkdir(parents=True)
        (tmp_path / "resources" / "skills" / "manim").mkdir(parents=True)
        text = build_capability_summaries("planner", "plan", tmp_path)
        assert "可用能力资源" in text
        assert "路径：" not in text

    def test_build_capability_summaries_empty_for_reviewer(self, tmp_path):
        text = build_capability_summaries("reviewer", "review", tmp_path)
        assert text == ""


class TestMultiDocumentInput:
    def test_load_multi_documents_fallback_to_legacy(self, tmp_path):
        paper = tmp_path / "paper.md"
        paper.write_text("# Test Paper\nContent here.", encoding="utf-8")
        bundle = SourceBundle(paper_path=str(paper))
        docs = load_multi_documents(bundle, tmp_path)
        assert len(docs) == 1
        assert docs[0].kind == "markdown"
        assert "Content here" in docs[0].text

    def test_load_multi_documents_new_format(self, tmp_path):
        raw = tmp_path / "raw.md"
        raw.write_text("# Raw Material", encoding="utf-8")
        focus = tmp_path / "focus.md"
        focus.write_text("# Focus Points", encoding="utf-8")

        bundle = SourceBundle(
            paper_path="",
            documents=[
                InputDocument(
                    path=str(raw),
                    role=InputDocRole.RAW_MATERIAL,
                    title="原始资料",
                    consumer_roles=["lead", "explorer"],
                ),
                InputDocument(
                    path=str(focus),
                    role=InputDocRole.FOCUS_POINTS,
                    title="重点侧重",
                    consumer_roles=["planner", "coordinator"],
                ),
            ],
        )
        docs = load_multi_documents(bundle, tmp_path)
        assert len(docs) == 2
        assert docs[0].doc_role == "raw_material"
        assert docs[0].consumer_roles == ["lead", "explorer"]
        assert docs[1].doc_role == "focus_points"

    def test_load_multi_documents_missing_file(self, tmp_path):
        bundle = SourceBundle(
            paper_path="",
            documents=[
                InputDocument(
                    path="nonexistent.pdf",
                    role=InputDocRole.RAW_MATERIAL,
                ),
            ],
        )
        docs = load_multi_documents(bundle, tmp_path)
        assert len(docs) == 1
        assert docs[0].warning == "source_not_found"

    def test_documents_for_role_lead_sees_all(self):
        docs = [
            SourceDocument(path="a.md", kind="markdown", text="A", consumer_roles=["explorer"]),
            SourceDocument(path="b.md", kind="markdown", text="B", consumer_roles=["planner"]),
        ]
        result = documents_for_role(docs, "lead")
        assert len(result) == 2

    def test_documents_for_role_filters_by_consumer(self):
        docs = [
            SourceDocument(path="a.md", kind="markdown", text="A", consumer_roles=["explorer"]),
            SourceDocument(path="b.md", kind="markdown", text="B", consumer_roles=["planner"]),
            SourceDocument(path="c.md", kind="markdown", text="C", consumer_roles=[]),
        ]
        result = documents_for_role(docs, "planner")
        assert len(result) == 2
        paths = {d.path for d in result}
        assert "b.md" in paths
        assert "c.md" in paths

    def test_documents_for_role_empty_consumers_visible_to_all(self):
        docs = [
            SourceDocument(path="shared.md", kind="markdown", text="Shared", consumer_roles=[]),
        ]
        assert len(documents_for_role(docs, "html_worker")) == 1
        assert len(documents_for_role(docs, "reviewer")) == 1


class TestInputDocumentModel:
    def test_input_document_to_dict(self):
        doc = InputDocument(
            path="test.pdf",
            role=InputDocRole.RAW_MATERIAL,
            title="Test",
            consumer_roles=["lead"],
            notes="some notes",
        )
        d = doc.to_dict()
        assert d["path"] == "test.pdf"
        assert d["role"] == "raw_material"
        assert d["consumer_roles"] == ["lead"]

    def test_source_bundle_with_documents_to_dict(self):
        bundle = SourceBundle(
            paper_path="paper.md",
            documents=[
                InputDocument(path="a.md", role=InputDocRole.FOCUS_POINTS),
            ],
        )
        d = bundle.to_dict()
        assert len(d["documents"]) == 1
        assert d["documents"][0]["role"] == "focus_points"
