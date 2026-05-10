"""上下文装配与系统提示词分段解析。"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Callable

from .bootstrap import sanitize_identifier
from .models import AgentMode, ContextRecord, ContextScope, PipelineStage, ProjectPlan


RenderPromptSection = Callable[[], str | None]


@dataclass(slots=True)
class PromptSection:
    name: str
    render: RenderPromptSection
    cache_break: bool = False


@dataclass(slots=True)
class PromptSectionCache:
    """缓存可复用的系统提示词段，避免重复构建。"""

    _values: dict[str, str | None] = field(default_factory=dict)

    def clear(self) -> None:
        self._values.clear()

    def resolve(self, sections: list[PromptSection]) -> list[str]:
        resolved: list[str] = []
        for section in sections:
            if not section.cache_break and section.name in self._values:
                value = self._values[section.name]
            else:
                value = section.render()
                self._values[section.name] = value
            if value:
                resolved.append(value)
        return resolved


def section(name: str, render: RenderPromptSection) -> PromptSection:
    """创建可缓存提示词段。"""
    return PromptSection(name=name, render=render, cache_break=False)


def volatile_section(name: str, render: RenderPromptSection) -> PromptSection:
    """创建每轮重算提示词段。"""
    return PromptSection(name=name, render=render, cache_break=True)


def _context_map(plan: ProjectPlan) -> dict[str, ContextRecord]:
    return {record.key: record for record in plan.contexts}


def _can_consume(record: ContextRecord, role_id: str) -> bool:
    if role_id == "lead":
        return True
    if role_id == record.writer_role:
        return True
    if not record.consumer_roles:
        return True
    return role_id in record.consumer_roles


def _collect_mode_defaults(plan: ProjectPlan, mode: AgentMode) -> set[str]:
    selected: set[str] = set()
    if mode == AgentMode.READ_ONLY:
        selected.update(
            record.key
            for record in plan.contexts
            if record.scope == ContextScope.LONG_TERM and record.sticky
        )
    elif mode == AgentMode.STRUCTURED_WRITE:
        selected.update(
            record.key
            for record in plan.contexts
            if record.scope == ContextScope.LONG_TERM and record.sticky
        )
        selected.update(
            record.key
            for record in plan.contexts
            if record.scope == ContextScope.SHORT_TERM
        )
    elif mode == AgentMode.VERIFY_ONLY:
        selected.update(
            record.key
            for record in plan.contexts
            if record.scope == ContextScope.LONG_TERM
            and record.key.endswith(".review.report") is False
        )
        selected.update(
            record.key
            for record in plan.contexts
            if record.scope == ContextScope.SHORT_TERM
            and record.key.endswith(".session.handoff")
        )
    return selected


def build_context_packet(
    plan: ProjectPlan,
    role_id: str,
    stage: PipelineStage,
    allow_disallowed_stage: bool = False,
    session_id: str | None = None,
) -> dict[str, object]:
    """按角色和阶段装配上下文包。"""
    profile = next((item for item in plan.agent_profiles if item.id == role_id), None)
    if profile is None:
        raise ValueError(f"unknown role_id: {role_id}")
    stage_allowed = stage in profile.allowed_stages
    if not stage_allowed and not allow_disallowed_stage:
        raise PermissionError(
            f"stage_not_allowed: role={role_id} stage={stage.value}"
        )

    context_by_key = _context_map(plan)
    selected_keys = _collect_mode_defaults(plan, profile.mode)
    selected_keys.update(profile.required_inputs)
    selected_keys = {
        key
        for key in selected_keys
        if key in context_by_key and _can_consume(context_by_key[key], role_id)
    }

    context_specs = [
        {
            "key": key,
            "scope": context_by_key[key].scope.value,
            "summary": context_by_key[key].summary,
            "writer_role": context_by_key[key].writer_role,
            "consumer_roles": context_by_key[key].consumer_roles,
            "lifecycle": context_by_key[key].lifecycle,
            "invalidation_rule": context_by_key[key].invalidation_rule,
            "sticky": context_by_key[key].sticky,
        }
        for key in sorted(selected_keys)
    ]

    constraints = [
        "长期上下文只能写入 runtime/projects/<project_id>/",
        "短期上下文只能写入 runtime/sessions/<session_id>/",
        "审核未通过前不得进入后处理。",
    ]
    if profile.mode == AgentMode.READ_ONLY:
        constraints.append("当前角色只读，不允许写入产物。")
    if profile.mode == AgentMode.VERIFY_ONLY:
        constraints.append("当前角色仅可输出审核结论。")

    human_feedback: dict[str, object] | None = None
    if session_id:
        safe_session_id = sanitize_identifier(session_id)
        latest_return_path = (
            Path(plan.runtime_layout.session_context_root)
            / safe_session_id
            / "review-returns"
            / "latest.json"
        )
        if latest_return_path.exists():
            payload = json.loads(latest_return_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                target_roles = payload.get("target_roles")
                if isinstance(target_roles, list) and role_id not in target_roles:
                    human_feedback = None
                else:
                    human_feedback = payload

    return {
        "project_id": plan.project_id,
        "role_id": profile.id,
        "mode": profile.mode.value,
        "stage": stage.value,
        "stage_allowed": stage_allowed,
        "responsibility": profile.responsibility,
        "required_inputs": profile.required_inputs,
        "context_specs": context_specs,
        "write_targets": profile.owned_outputs,
        "output_contract": profile.output_contract,
        "constraints": constraints,
        "runtime_layout": plan.runtime_layout.to_dict(),
        "human_feedback": human_feedback,
    }


def build_default_prompt_sections(packet: dict[str, object]) -> list[PromptSection]:
    """把上下文包转成可缓存提示词分段。"""

    def _role_section() -> str:
        return (
            f"角色：{packet['role_id']}（{packet['mode']}）\n"
            f"职责：{packet['responsibility']}\n"
            f"阶段：{packet['stage']}（allowed={packet['stage_allowed']}）"
        )

    def _context_section() -> str:
        lines = [
            f"- {item['key']} [{item['scope']}] writer={item['writer_role']} "
            f"lifecycle={item['lifecycle']} invalidation={item['invalidation_rule']}"
            for item in packet["context_specs"]  # type: ignore[index]
        ]
        header = "可用上下文："
        return "\n".join([header, *lines]) if lines else f"{header}\n- （空）"

    def _human_feedback_section() -> str | None:
        raw_feedback = packet.get("human_feedback")
        if not isinstance(raw_feedback, dict):
            return None
        decision = raw_feedback.get("decision")
        if not isinstance(decision, str) or decision.lower() != "return":
            return None
        reason = raw_feedback.get("reason")
        must_fix = raw_feedback.get("must_fix")
        should_keep = raw_feedback.get("should_keep")
        prompt_patch = raw_feedback.get("prompt_patch")
        lines = ["人工审核打回意见："]
        if isinstance(reason, str) and reason.strip():
            lines.append(f"- 打回原因：{reason.strip()}")
        if isinstance(must_fix, str) and must_fix.strip():
            lines.append(f"- 必须修改：{must_fix.strip()}")
        if isinstance(should_keep, str) and should_keep.strip():
            lines.append(f"- 保持不变：{should_keep.strip()}")
        if isinstance(prompt_patch, str) and prompt_patch.strip():
            lines.append(f"- 返工指令：{prompt_patch.strip()}")
        return "\n".join(lines)

    def _output_section() -> str:
        targets = packet["write_targets"]  # type: ignore[index]
        if not targets:
            return "输出写入目标：只读角色，无写入目标。"
        return "输出写入目标：\n" + "\n".join(f"- {item}" for item in targets)

    def _guardrail_section() -> str:
        lines = [f"- {rule}" for rule in packet["constraints"]]  # type: ignore[index]
        return "硬约束：\n" + "\n".join(lines)

    return [
        section("role", _role_section),
        volatile_section("human_review_feedback", _human_feedback_section),
        section("context", _context_section),
        section("output", _output_section),
        volatile_section("guardrails", _guardrail_section),
    ]
