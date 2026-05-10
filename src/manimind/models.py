"""ManiMind 核心数据模型定义。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class PipelineStage(str, Enum):
    PRESTART = "prestart"
    INGEST = "ingest"
    SUMMARIZE = "summarize"
    PLAN = "plan"
    DISPATCH = "dispatch"
    REVIEW = "review"
    POST_PRODUCE = "post_produce"
    PACKAGE = "package"
    DONE = "done"
    BLOCKED = "blocked"


class ContextScope(str, Enum):
    LONG_TERM = "long_term"
    SHORT_TERM = "short_term"


class AgentMode(str, Enum):
    READ_ONLY = "read_only"
    STRUCTURED_WRITE = "structured_write"
    VERIFY_ONLY = "verify_only"


class SegmentModality(str, Enum):
    HTML = "html"
    MANIM = "manim"
    HYBRID = "hybrid"
    SVG = "svg"


class WorkerKind(str, Enum):
    HTML = "html"
    MANIM = "manim"
    SVG = "svg"
    REVIEW = "review"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class EventType(str, Enum):
    PLAN_SNAPSHOT = "plan_snapshot"
    DISPATCH_CONTEXT_PACK = "dispatch.context_pack"
    WORKER_PROGRESS = "worker.progress"
    WORKER_BLOCKER = "worker.blocker"
    WORKER_RESULT = "worker.result"
    REVIEW_DRAFT = "review.draft"
    REVIEW_RETURN = "review.return"
    REVIEW_DECISION = "review.decision"
    LEADER_COMMIT = "leader.commit"
    STAGE_CHANGED = "stage.changed"


@dataclass(slots=True)
class SourceBundle:
    paper_path: str
    note_paths: list[str] = field(default_factory=list)
    audience: str = "大众观众"
    style_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ContextRecord:
    key: str
    scope: ContextScope
    summary: str
    writer_role: str = "lead"
    consumer_roles: list[str] = field(default_factory=list)
    lifecycle: str = "project"
    invalidation_rule: str = "never"
    source_ids: list[str] = field(default_factory=list)
    sticky: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SegmentSpec:
    id: str
    title: str
    goal: str
    narration: str
    modality: SegmentModality = SegmentModality.HYBRID
    formulas: list[str] = field(default_factory=list)
    html_motion_notes: list[str] = field(default_factory=list)
    requires_svg_motion: bool = False
    estimated_seconds: int = 20

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkerTask:
    worker: WorkerKind
    segment_id: str
    objective: str
    input_context_keys: list[str] = field(default_factory=list)
    long_term_outputs: list[str] = field(default_factory=list)
    short_term_outputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReviewCheckpoint:
    name: str
    stage: PipelineStage
    required_inputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentProfile:
    id: str
    mode: AgentMode
    responsibility: str
    allowed_stages: list[PipelineStage] = field(default_factory=list)
    required_inputs: list[str] = field(default_factory=list)
    owned_outputs: list[str] = field(default_factory=list)
    output_contract: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mode": self.mode.value,
            "responsibility": self.responsibility,
            "allowed_stages": [stage.value for stage in self.allowed_stages],
            "required_inputs": self.required_inputs,
            "owned_outputs": self.owned_outputs,
            "output_contract": self.output_contract,
        }


@dataclass(slots=True)
class ExecutionTask:
    id: str
    subject: str
    owner_role: str
    active_form: str
    stage: PipelineStage
    status: TaskStatus = TaskStatus.PENDING
    blocked_reason: str | None = None
    blocked_at: str | None = None
    last_progress: str | None = None
    last_progress_at: str | None = None
    blocked_by: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    required_outputs: list[str] = field(default_factory=list)
    verification_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "owner_role": self.owner_role,
            "active_form": self.active_form,
            "stage": self.stage.value,
            "status": self.status.value,
            "blocked_reason": self.blocked_reason,
            "blocked_at": self.blocked_at,
            "last_progress": self.last_progress,
            "last_progress_at": self.last_progress_at,
            "blocked_by": self.blocked_by,
            "blocks": self.blocks,
            "required_outputs": self.required_outputs,
            "verification_required": self.verification_required,
        }


@dataclass(slots=True)
class RuntimeLayout:
    project_context_dir: str
    session_context_root: str
    output_dir: str
    bootstrap_report: str
    doctor_report: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProjectPlan:
    project_id: str
    title: str
    source_bundle: SourceBundle
    stages: list[PipelineStage]
    segments: list[SegmentSpec]
    tasks: list[WorkerTask]
    contexts: list[ContextRecord]
    review_checkpoints: list[ReviewCheckpoint]
    agent_profiles: list[AgentProfile]
    execution_tasks: list[ExecutionTask]
    runtime_layout: RuntimeLayout
    current_stage: PipelineStage = PipelineStage.PRESTART

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "source_bundle": self.source_bundle.to_dict(),
            "stages": [stage.value for stage in self.stages],
            "segments": [segment.to_dict() for segment in self.segments],
            "tasks": [task.to_dict() for task in self.tasks],
            "contexts": [context.to_dict() for context in self.contexts],
            "review_checkpoints": [
                checkpoint.to_dict() for checkpoint in self.review_checkpoints
            ],
            "agent_profiles": [
                profile.to_dict() for profile in self.agent_profiles
            ],
            "execution_tasks": [
                task.to_dict() for task in self.execution_tasks
            ],
            "runtime_layout": self.runtime_layout.to_dict(),
            "current_stage": self.current_stage.value,
        }
