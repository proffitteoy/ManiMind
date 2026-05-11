"""输入摄取：支持文本/Markdown/PDF，支持多文档角色过滤。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import InputDocRole, InputDocument, SourceBundle


@dataclass(slots=True)
class SourceDocument:
    path: str
    kind: str
    text: str
    warning: str | None = None
    doc_role: str = "raw_material"
    consumer_roles: list[str] = field(default_factory=list)
    title: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "text_length": len(self.text),
            "warning": self.warning,
            "doc_role": self.doc_role,
            "consumer_roles": self.consumer_roles,
            "title": self.title,
        }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf(path: Path) -> tuple[str, str | None]:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return "", "missing_pypdf_dependency"

    try:
        reader = PdfReader(str(path))
        chunks: list[str] = []
        for page in reader.pages:
            content = page.extract_text() or ""
            if content.strip():
                chunks.append(content)
        return "\n\n".join(chunks), None
    except Exception as exc:
        return "", f"pdf_extract_failed:{type(exc).__name__}"


def _guess_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix in {".txt", ".text"}:
        return "text"
    return "unknown"


def load_source_documents(
    bundle: SourceBundle,
    base_dir: Path | None = None,
) -> list[SourceDocument]:
    root = base_dir or Path.cwd()
    raw_paths = [bundle.paper_path, *bundle.note_paths]
    docs: list[SourceDocument] = []

    for raw in raw_paths:
        path = Path(raw)
        if not path.is_absolute():
            path = root / path
        kind = _guess_kind(path)
        if not path.exists():
            docs.append(
                SourceDocument(
                    path=str(path),
                    kind=kind,
                    text="",
                    warning="source_not_found",
                )
            )
            continue

        if kind == "pdf":
            text, warning = _read_pdf(path)
        else:
            text = _read_text(path)
            warning = None

        docs.append(
            SourceDocument(
                path=str(path),
                kind=kind,
                text=text,
                warning=warning,
            )
        )
    return docs


def concatenate_documents(docs: list[SourceDocument]) -> str:
    parts: list[str] = []
    for item in docs:
        if not item.text.strip():
            continue
        parts.append(f"# source:{item.path}\n{item.text}")
    return "\n\n".join(parts)


def load_multi_documents(
    bundle: SourceBundle,
    base_dir: Path | None = None,
) -> list[SourceDocument]:
    """加载多文档输入，向后兼容旧格式。

    如果 bundle.documents 非空，优先使用新格式；
    否则回退到 paper_path + note_paths 的旧格式。
    """
    if not bundle.documents:
        return load_source_documents(bundle, base_dir)

    root = base_dir or Path.cwd()
    docs: list[SourceDocument] = []

    for input_doc in bundle.documents:
        path = Path(input_doc.path)
        if not path.is_absolute():
            path = root / path
        kind = _guess_kind(path)

        if not path.exists():
            docs.append(
                SourceDocument(
                    path=str(path),
                    kind=kind,
                    text="",
                    warning="source_not_found",
                    doc_role=input_doc.role.value,
                    consumer_roles=input_doc.consumer_roles,
                    title=input_doc.title,
                )
            )
            continue

        if kind == "pdf":
            text, warning = _read_pdf(path)
        else:
            text = _read_text(path)
            warning = None

        docs.append(
            SourceDocument(
                path=str(path),
                kind=kind,
                text=text,
                warning=warning,
                doc_role=input_doc.role.value,
                consumer_roles=input_doc.consumer_roles,
                title=input_doc.title,
            )
        )

    return docs


def documents_for_role(
    docs: list[SourceDocument],
    role_id: str,
) -> list[SourceDocument]:
    """按角色过滤文档。

    规则：
    - leader 角色可以看到所有文档
    - 如果文档的 consumer_roles 为空，所有角色都可以看到
    - 否则只有在 consumer_roles 列表中的角色可以看到
    """
    if role_id == "lead":
        return docs

    return [
        doc
        for doc in docs
        if not doc.consumer_roles or role_id in doc.consumer_roles
    ]
