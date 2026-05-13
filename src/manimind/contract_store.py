"""角色输出契约加载与基础校验。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_CONTRACT_DIR = Path(__file__).resolve().parent / "contracts"

_ROLE_TO_CONTRACT: dict[str, str] = {
    "explorer": "explorer_output.json",
    "lead": "lead_output.json",
    "planner": "planner_output.json",
    "coordinator": "coordinator_output.json",
    "reviewer": "reviewer_output.json",
    "html_worker": "html_worker_output.json",
    "manim_worker": "manim_worker_output.json",
    "svg_worker": "svg_worker_output.json",
}

_TYPE_CHECKERS: dict[str, Any] = {
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: (
        isinstance(value, (int, float)) and not isinstance(value, bool)
    ),
    "boolean": lambda value: isinstance(value, bool),
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
}


def contract_path_for_role(role_id: str) -> Path | None:
    filename = _ROLE_TO_CONTRACT.get(role_id)
    if not filename:
        return None
    path = _CONTRACT_DIR / filename
    if not path.exists():
        return None
    return path


def load_contract_for_role(role_id: str) -> dict[str, Any] | None:
    path = contract_path_for_role(role_id)
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return payload


def _is_type(value: Any, expected_type: str) -> bool:
    checker = _TYPE_CHECKERS.get(expected_type)
    if checker is None:
        return True
    return bool(checker(value))


def _validate_schema(
    value: Any,
    schema: dict[str, Any],
    path: str,
) -> str | None:
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _is_type(value, expected_type):
        return f"{path}.type_mismatch:expected_{expected_type}"

    if expected_type == "object":
        if not isinstance(value, dict):
            return f"{path}.type_mismatch:expected_object"
        required = schema.get("required")
        if isinstance(required, list):
            for name in required:
                if isinstance(name, str) and name not in value:
                    return f"{path}.missing_required:{name}"
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for key, field_schema in properties.items():
                if key not in value:
                    continue
                if not isinstance(field_schema, dict):
                    continue
                nested = _validate_schema(value[key], field_schema, f"{path}.{key}")
                if nested:
                    return nested

    if expected_type == "array":
        if not isinstance(value, list):
            return f"{path}.type_mismatch:expected_array"
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                nested = _validate_schema(item, item_schema, f"{path}[{idx}]")
                if nested:
                    return nested
    return None


def validate_role_output(role_id: str, payload: Any) -> str | None:
    schema = load_contract_for_role(role_id)
    if schema is None:
        return None
    return _validate_schema(payload, schema, role_id)


def required_fields_for_role(role_id: str) -> list[str]:
    schema = load_contract_for_role(role_id)
    if not isinstance(schema, dict):
        return []
    required = schema.get("required")
    if not isinstance(required, list):
        return []
    return [item for item in required if isinstance(item, str)]


def planner_segment_priority_fields() -> list[str]:
    schema = load_contract_for_role("planner")
    if not isinstance(schema, dict):
        return [
            "segment_id",
            "objective",
            "primary_worker_path",
            "estimated_seconds",
            "semantic_type",
            "cognitive_goal",
            "why_this_worker",
            "density_level",
            "prerequisites",
        ]
    props = schema.get("properties")
    if not isinstance(props, dict):
        return []
    segment_priorities = props.get("segment_priorities")
    if not isinstance(segment_priorities, dict):
        return []
    items = segment_priorities.get("items")
    if not isinstance(items, dict):
        return []
    item_props = items.get("properties")
    if not isinstance(item_props, dict):
        return []
    fields = [key for key in item_props.keys() if isinstance(key, str)]
    return fields
