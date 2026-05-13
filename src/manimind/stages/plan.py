"""Plan runner（planner + coordinator）。"""

from __future__ import annotations

from ..failure import classify_failure
from ..models import PipelineStage
from . import StageInput, StageOutput


class PlanRunner:
    name = "plan"
    stage = PipelineStage.PLAN
    task_ids = ("plan.research_brief", "plan.storyboard")

    def run(self, stage_input: StageInput) -> StageOutput:
        from .. import executor as _executor

        try:
            data = _executor.run_plan_stage(
                plan=stage_input.plan,
                session_id=stage_input.session_id,
                cfg=stage_input.cfg,
                prompt_cache=stage_input.prompt_cache,
            )
            return StageOutput(stage=self.stage, success=True, data=data)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return StageOutput(
                stage=self.stage,
                success=False,
                error=classify_failure(exc),
                detail=str(exc),
            )

