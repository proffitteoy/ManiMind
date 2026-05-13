"""Package runner。"""

from __future__ import annotations

from ..failure import classify_failure
from ..models import PipelineStage
from ..post_produce import finalize_delivery
from . import StageInput, StageOutput


class PackageRunner:
    name = "package"
    stage = PipelineStage.PACKAGE
    task_ids = ("package.delivery",)

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

