"""Dispatch runner（并发 worker 调度）。"""

from __future__ import annotations

from ..failure import classify_failure
from ..models import PipelineStage
from . import StageInput, StageOutput


class DispatchRunner:
    name = "dispatch"
    stage = PipelineStage.DISPATCH
    task_ids = ()

    def run(self, stage_input: StageInput) -> StageOutput:
        from .. import executor as _executor

        try:
            data = _executor.run_dispatch_stage(
                plan=stage_input.plan,
                session_id=stage_input.session_id,
                segment_id=stage_input.segment_id,
            )
            return StageOutput(stage=self.stage, success=True, data=data)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return StageOutput(
                stage=self.stage,
                success=False,
                error=classify_failure(exc),
                detail=str(exc),
            )

