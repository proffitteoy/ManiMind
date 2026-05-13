"""角色独立执行器：每个角色可单独测试、调试和替换模型配置。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from .context_assembly import PromptSectionCache
from .contract_store import validate_role_output
from .llm_client import (
    LLMRuntimeConfig,
    generate_json_for_role,
    generate_text_for_role,
    load_llm_runtime_config,
)
from .models import PipelineStage, ProjectPlan
from .ownership import ensure_role_can_write_key
from .prompt_system import (
    PromptBundle,
    PromptRecipe,
    build_prompt_bundle,
    coordinator_recipe,
    explorer_recipe,
    html_worker_recipe,
    lead_summary_recipe,
    manim_generate_recipe,
    planner_recipe,
    reviewer_recipe,
    svg_worker_recipe,
)
from .runtime_store import persist_context_packet
from .trace_store import LLMTrace, persist_llm_trace


@dataclass(slots=True)
class RoleExecutionResult:
    role_id: str
    stage: str
    output: dict[str, Any] | str
    llm_meta: dict[str, Any]
    duration_ms: int


_RECIPE_REGISTRY: dict[str, Any] = {
    "explorer": explorer_recipe,
    "lead": lead_summary_recipe,
    "planner": planner_recipe,
    "coordinator": coordinator_recipe,
    "reviewer": reviewer_recipe,
    "html_worker": html_worker_recipe,
    "manim_worker": manim_generate_recipe,
    "svg_worker": svg_worker_recipe,
}

_TEXT_OUTPUT_ROLES = {"html_worker", "manim_worker", "svg_worker"}


class RoleExecutor:
    """统一的角色执行入口。"""

    def __init__(self, role_id: str, cfg: LLMRuntimeConfig | str | None = None):
        if role_id not in _RECIPE_REGISTRY:
            raise ValueError(f"unknown_role: {role_id}")
        self.role_id = role_id
        if cfg == "skip":
            self._cfg = None  # type: ignore[assignment]
        else:
            self._cfg = cfg or load_llm_runtime_config()
        self._recipe = _RECIPE_REGISTRY[role_id]()

    @property
    def recipe(self) -> PromptRecipe:
        return self._recipe

    def preview_prompt(
        self,
        *,
        plan: ProjectPlan,
        session_id: str,
        stage: PipelineStage,
        payload: dict[str, Any],
        cache: PromptSectionCache | None = None,
    ) -> PromptBundle:
        return build_prompt_bundle(
            plan=plan,
            session_id=session_id,
            role_id=self.role_id,
            stage=stage,
            recipe=self._recipe,
            payload=payload,
            cache=cache,
            allow_disallowed_stage=True,
        )

    def execute(
        self,
        *,
        plan: ProjectPlan,
        session_id: str,
        stage: PipelineStage,
        payload: dict[str, Any],
        cache: PromptSectionCache | None = None,
        persist: bool = True,
        expected_output_keys: list[str] | None = None,
    ) -> RoleExecutionResult:
        cache = cache or PromptSectionCache()
        for key in expected_output_keys or []:
            ensure_role_can_write_key(plan, self.role_id, key)
        bundle = build_prompt_bundle(
            plan=plan,
            session_id=session_id,
            role_id=self.role_id,
            stage=stage,
            recipe=self._recipe,
            payload=payload,
            cache=cache,
            allow_disallowed_stage=False,
        )

        if persist:
            persist_context_packet(
                plan=plan,
                session_id=session_id,
                packet=bundle.packet,
                prompt_sections=bundle.prompt_sections,
            )

        t0 = time.perf_counter()

        if self.role_id in _TEXT_OUTPUT_ROLES:
            text, meta = generate_text_for_role(
                cfg=self._cfg,
                role_id=self.role_id,
                instructions=bundle.system_prompt,
                prompt=bundle.user_prompt,
            )
            output: dict[str, Any] | str = text
            persist_llm_trace(
                plan=plan,
                session_id=session_id,
                trace=LLMTrace(
                    trace_id=f"{self.role_id}-{int(time.time() * 1000)}",
                    role_id=self.role_id,
                    stage=stage.value,
                    task_id="role-exec",
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    input_context_keys=[
                        item.get("key")
                        for item in bundle.packet.get("context_specs", [])
                        if isinstance(item, dict) and isinstance(item.get("key"), str)
                    ],
                    prompt_sections=bundle.prompt_sections,
                    model_route=str(meta.get("route") or "unknown"),
                    model_output_excerpt=text[:2000],
                    parsed_output_keys=[],
                    schema_validation="n/a",
                    artifact_files=[],
                    render_command=None,
                    render_exit_code=None,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    token_usage=None,
                    retry_count=0,
                    failure_reason=None,
                ),
            )
        else:
            parsed, meta = generate_json_for_role(
                cfg=self._cfg,
                role_id=self.role_id,
                instructions=bundle.system_prompt,
                prompt=bundle.user_prompt,
            )
            schema_error = validate_role_output(self.role_id, parsed)
            if schema_error:
                raise ValueError(f"schema_validation_failed:{schema_error}")
            output = parsed
            persist_llm_trace(
                plan=plan,
                session_id=session_id,
                trace=LLMTrace(
                    trace_id=f"{self.role_id}-{int(time.time() * 1000)}",
                    role_id=self.role_id,
                    stage=stage.value,
                    task_id="role-exec",
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    input_context_keys=[
                        item.get("key")
                        for item in bundle.packet.get("context_specs", [])
                        if isinstance(item, dict) and isinstance(item.get("key"), str)
                    ],
                    prompt_sections=bundle.prompt_sections,
                    model_route=str(meta.get("route") or "unknown"),
                    model_output_excerpt=json.dumps(parsed, ensure_ascii=False)[:2000],
                    parsed_output_keys=list(parsed.keys()),
                    schema_validation="pass",
                    artifact_files=[],
                    render_command=None,
                    render_exit_code=None,
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                    token_usage=None,
                    retry_count=0,
                    failure_reason=None,
                ),
            )

        duration_ms = int((time.perf_counter() - t0) * 1000)

        return RoleExecutionResult(
            role_id=self.role_id,
            stage=stage.value,
            output=output,
            llm_meta=meta,
            duration_ms=duration_ms,
        )
