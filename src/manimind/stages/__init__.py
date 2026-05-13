"""Stage Runner 协议定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..llm_client import LLMRuntimeConfig
from ..models import FailureCategory, PipelineStage, ProjectPlan
from ..context_assembly import PromptSectionCache


@dataclass(slots=True)
class StageInput:
    plan: ProjectPlan
    session_id: str
    cfg: LLMRuntimeConfig
    prompt_cache: PromptSectionCache
    source_manifest: str
    segment_id: str | None = None
    force: bool = False


@dataclass(slots=True)
class StageOutput:
    stage: PipelineStage
    success: bool
    error: FailureCategory | None = None
    detail: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


class StageRunner(Protocol):
    name: str
    stage: PipelineStage
    task_ids: tuple[str, ...]

    def run(self, stage_input: StageInput) -> StageOutput:
        ...

