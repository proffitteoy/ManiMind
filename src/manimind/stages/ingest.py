"""Ingest runner。"""

from __future__ import annotations

from ..failure import classify_failure
from ..models import PipelineStage
from . import StageInput, StageOutput


class IngestRunner:
    name = "ingest"
    stage = PipelineStage.INGEST
    task_ids = ("ingest.sources",)

    def run(self, stage_input: StageInput) -> StageOutput:
        from .. import executor as _executor

        try:
            data = _executor.run_ingest_stage(
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

