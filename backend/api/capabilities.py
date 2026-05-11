"""能力注册表查询路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from manimind.capability_registry import capabilities_for_role, resolve_capabilities

router = APIRouter()


@router.get("/capabilities")
async def list_capabilities() -> dict[str, Any]:
    """列出所有已注册能力及其可用状态。"""
    caps = resolve_capabilities()
    return {
        "capabilities": [cap.to_dict() for cap in caps],
        "total": len(caps),
        "available": sum(1 for cap in caps if cap.available),
    }


@router.get("/{project_id}/capabilities/{role_id}")
async def capabilities_for_project_role(
    project_id: str,
    role_id: str,
    stage: str = "dispatch",
) -> dict[str, Any]:
    """查看某角色在某阶段的能力分发。"""
    caps = capabilities_for_role(role_id, stage)
    return {
        "project_id": project_id,
        "role_id": role_id,
        "stage": stage,
        "capabilities": [cap.to_dict() for cap in caps],
    }
