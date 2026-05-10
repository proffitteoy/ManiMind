"""产物键与落盘路径映射工具。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .bootstrap import sanitize_identifier
from .models import ProjectPlan


def _safe_key_name(key: str) -> str:
    return re.sub(r"[^0-9A-Za-z_.-]+", "-", key).strip("-")


def output_path_for_key(plan: ProjectPlan, session_id: str, key: str) -> Path:
    """根据输出键推导实际文件路径。"""
    safe_key = _safe_key_name(key)
    safe_session = sanitize_identifier(session_id)
    output_dir = Path(plan.runtime_layout.output_dir)
    project_dir = Path(plan.runtime_layout.project_context_dir)
    session_dir = Path(plan.runtime_layout.session_context_root) / safe_session

    if ".session." in key:
        return session_dir / "artifacts" / f"{safe_key}.json"
    if key.endswith(".approved") or key.endswith(".asset.manifest"):
        return output_dir / "artifacts" / f"{safe_key}.json"
    return project_dir / "artifacts" / f"{safe_key}.json"


def write_output_key(
    plan: ProjectPlan,
    session_id: str,
    key: str,
    payload: dict[str, Any],
) -> Path:
    """按键写入结构化产物文件。"""
    target = output_path_for_key(plan, session_id, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def has_output_key(plan: ProjectPlan, session_id: str, key: str) -> bool:
    """检查产物键对应文件是否存在。"""
    return output_path_for_key(plan, session_id, key).exists()
