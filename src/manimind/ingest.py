"""输入摄取：支持文本/Markdown/PDF。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import SourceBundle


@dataclass(slots=True)
class SourceDocument:
    path: str
    kind: str
    text: str
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "text_length": len(self.text),
            "warning": self.warning,
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
