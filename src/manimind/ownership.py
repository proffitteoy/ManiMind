"""角色边界与写入所有权校验。"""

from __future__ import annotations

from .models import ProjectPlan


def _profile_for_role(plan: ProjectPlan, role_id: str):
    for profile in plan.agent_profiles:
        if profile.id == role_id:
            return profile
    return None


def ensure_role_can_write_key(plan: ProjectPlan, role_id: str, output_key: str) -> None:
    profile = _profile_for_role(plan, role_id)
    if profile is None:
        raise PermissionError(f"unknown_role:{role_id}")
    allowed = set(profile.owned_outputs)
    if output_key in allowed:
        return
    if role_id == "lead" and output_key.startswith(f"{plan.project_id}.session."):
        # lead 允许写会话交接类信息
        return
    raise PermissionError(
        f"ownership_violation: role={role_id} output_key={output_key}"
    )

