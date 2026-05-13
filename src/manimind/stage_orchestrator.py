"""Stage Runner 编排入口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .context_assembly import PromptSectionCache
from .models import PipelineStage, ProjectPlan, TaskStatus
from .runtime_store import load_execution_task_snapshot, persist_plan_snapshot
from .stages import StageInput, StageRunner
from .stages.dispatch import DispatchRunner
from .stages.ingest import IngestRunner
from .stages.package import PackageRunner
from .stages.plan import PlanRunner
from .stages.post_produce import PostProduceRunner
from .stages.review import ReviewRunner
from .stages.summarize import SummarizeRunner


@dataclass(slots=True)
class OrchestratorResult:
    project_id: str
    session_id: str
    current_stage: str
    executed_runners: list[str]
    runner_results: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "session_id": self.session_id,
            "current_stage": self.current_stage,
            "executed_runners": self.executed_runners,
            "runner_results": self.runner_results,
        }


_RUNNERS: list[StageRunner] = [
    IngestRunner(),
    SummarizeRunner(),
    PlanRunner(),
    DispatchRunner(),
    ReviewRunner(),
    PostProduceRunner(),
    PackageRunner(),
]


def _runner_by_name(name: str) -> StageRunner:
    for runner in _RUNNERS:
        if runner.name == name:
            return runner
    raise ValueError(f"unknown_runner:{name}")


def _is_runner_completed(plan: ProjectPlan, runner: StageRunner) -> bool:
    if runner.name == "dispatch":
        dispatch_tasks = [
            task
            for task in plan.execution_tasks
            if task.stage == PipelineStage.DISPATCH
        ]
        return bool(dispatch_tasks) and all(
            task.status == TaskStatus.COMPLETED for task in dispatch_tasks
        )
    if not runner.task_ids:
        return False
    status_by_id = {task.id: task.status for task in plan.execution_tasks}
    return all(status_by_id.get(task_id) == TaskStatus.COMPLETED for task_id in runner.task_ids)


def _stage_input(
    *,
    plan: ProjectPlan,
    session_id: str,
    cfg,
    prompt_cache: PromptSectionCache,
    source_manifest: str,
    segment_id: str | None = None,
    force: bool = False,
) -> StageInput:
    return StageInput(
        plan=plan,
        session_id=session_id,
        cfg=cfg,
        prompt_cache=prompt_cache,
        source_manifest=source_manifest,
        segment_id=segment_id,
        force=force,
    )


def run_all(
    *,
    plan: ProjectPlan,
    session_id: str,
    source_manifest: str,
) -> dict[str, Any]:
    load_execution_task_snapshot(plan)
    persist_plan_snapshot(
        plan=plan,
        session_id=session_id,
        source_manifest=source_manifest,
    )
    from .executor import load_llm_runtime_config as _load_cfg

    cfg = _load_cfg()
    prompt_cache = PromptSectionCache()

    executed_runners: list[str] = []
    runner_results: dict[str, dict[str, Any]] = {}
    for runner in _RUNNERS[:5]:
        if _is_runner_completed(plan, runner):
            runner_results[runner.name] = {
                "stage": runner.stage.value,
                "skipped": True,
                "reason": "already_completed",
            }
            continue
        result = runner.run(
            _stage_input(
                plan=plan,
                session_id=session_id,
                cfg=cfg,
                prompt_cache=prompt_cache,
                source_manifest=source_manifest,
            )
        )
        runner_results[runner.name] = {
            "stage": result.stage.value,
            "success": result.success,
            "error": result.error.value if result.error else None,
            "detail": result.detail,
            "data": result.data,
        }
        executed_runners.append(runner.name)
        if not result.success:
            raise RuntimeError(
                f"stage_failed:{runner.name}:{result.error.value if result.error else 'unknown'}:{result.detail or ''}"
            )

    return OrchestratorResult(
        project_id=plan.project_id,
        session_id=session_id,
        current_stage=plan.current_stage.value,
        executed_runners=executed_runners,
        runner_results=runner_results,
    ).to_dict()


def rerun(
    *,
    plan: ProjectPlan,
    session_id: str,
    source_manifest: str,
    runner_name: str,
    segment_id: str | None = None,
) -> dict[str, Any]:
    load_execution_task_snapshot(plan)
    persist_plan_snapshot(
        plan=plan,
        session_id=session_id,
        source_manifest=source_manifest,
    )
    from .executor import load_llm_runtime_config as _load_cfg

    cfg = _load_cfg()
    prompt_cache = PromptSectionCache()

    normalized = runner_name.strip().lower()
    if normalized in {"html_worker", "manim_worker", "svg_worker"}:
        normalized = "dispatch"
    runner = _runner_by_name(normalized)
    result = runner.run(
        _stage_input(
            plan=plan,
            session_id=session_id,
            cfg=cfg,
            prompt_cache=prompt_cache,
            source_manifest=source_manifest,
            segment_id=segment_id,
            force=True,
        )
    )
    if not result.success:
        raise RuntimeError(
            f"stage_failed:{runner.name}:{result.error.value if result.error else 'unknown'}:{result.detail or ''}"
        )
    return {
        "project_id": plan.project_id,
        "session_id": session_id,
        "runner": runner.name,
        "stage": runner.stage.value,
        "current_stage": plan.current_stage.value,
        "data": result.data,
    }
