"""Post-produce runner。"""

from __future__ import annotations

from ..failure import classify_failure
from ..models import PipelineStage
from ..post_produce import finalize_delivery
from . import StageInput, StageOutput


class PostProduceRunner:
    name = "post_produce"
    stage = PipelineStage.POST_PRODUCE
    task_ids = ("post_produce.outputs",)

    def run(self, stage_input: StageInput) -> StageOutput:
        try:
            data = finalize_delivery(
                plan=stage_input.plan,
                session_id=stage_input.session_id,
            )
            return StageOutput(stage=self.stage, success=True, data=data)
        except Exception as exc:  # pragma: no cover - defensive fallback
            return StageOutput(
                stage=self.stage,
                success=False,
                error=classify_failure(exc),
                detail=str(exc),
            )

