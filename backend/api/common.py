"""API 层公共工具。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from manimind.models import InputDocRole, InputDocument, SegmentModality, SegmentSpec, SourceBundle
from manimind.workflow import build_project_plan


def _parse_source_bundle(raw: dict[str, Any]) -> SourceBundle:
    documents: list[InputDocument] = []
    for doc in raw.get("documents", []):
        documents.append(
            InputDocument(
                path=doc["path"],
                role=InputDocRole(doc.get("role", "raw_material")),
                title=doc.get("title", ""),
                consumer_roles=doc.get("consumer_roles", []),
                notes=doc.get("notes", ""),
            )
        )
    return SourceBundle(
        paper_path=raw.get("paper_path", ""),
        note_paths=raw.get("note_paths", []),
        audience=raw.get("audience", "大众观众"),
        style_refs=raw.get("style_refs", []),
        documents=documents,
    )


def build_plan_from_manifest_payload(payload: dict[str, Any]):
    try:
        source_bundle = _parse_source_bundle(payload["source_bundle"])
        segments = [
            SegmentSpec(
                id=item["id"],
                title=item["title"],
                goal=item["goal"],
                narration=item["narration"],
                modality=SegmentModality(item.get("modality", "hybrid")),
                formulas=item.get("formulas", []),
                html_motion_notes=item.get("html_motion_notes", []),
                requires_svg_motion=item.get("requires_svg_motion", False),
                estimated_seconds=item.get("estimated_seconds", 20),
            )
            for item in payload["segments"]
        ]
        return build_project_plan(
            project_id=payload["project_id"],
            title=payload["title"],
            source_bundle=source_bundle,
            segments=segments,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid_manifest: {exc}") from exc


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise HTTPException(status_code=500, detail=f"invalid_json_object: {path}")


def resolve_manifest_payload(
    manifest: dict[str, Any] | None = None,
    manifest_path: str | None = None,
) -> dict[str, Any]:
    if manifest is not None:
        return manifest
    if manifest_path is None:
        raise HTTPException(
            status_code=400,
            detail="missing_manifest: provide manifest or manifest_path",
        )
    path = Path(manifest_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"manifest_not_found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid_manifest_json_object")
    return payload


def read_jsonl_events(path: Path, limit: int = 200) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    if limit <= 0:
        return events
    return events[-limit:]
