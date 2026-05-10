"""API 层公共工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException

from manimind.models import SegmentModality, SegmentSpec, SourceBundle
from manimind.workflow import build_project_plan


def build_plan_from_manifest_payload(payload: dict[str, Any]):
    try:
        source_bundle = SourceBundle(**payload["source_bundle"])
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
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise HTTPException(status_code=500, detail=f"invalid_json_object: {path}")
