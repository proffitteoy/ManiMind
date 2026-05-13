"""失败分类与异常归因。"""

from __future__ import annotations

from typing import Any

from .models import FailureCategory


def classify_failure(reason: str | Exception | None) -> FailureCategory:
    if reason is None:
        return FailureCategory.UNKNOWN
    if isinstance(reason, Exception):
        text = f"{type(reason).__name__}:{reason}"
    else:
        text = str(reason)
    lowered = text.lower()

    if "missing_required_outputs" in lowered:
        return FailureCategory.MISSING_REQUIRED_OUTPUTS
    if "review_not_completed" in lowered:
        return FailureCategory.REVIEW_NOT_COMPLETED
    if "model_output_not_json_object" in lowered or "llmrequesterror" in lowered:
        return FailureCategory.LLM_JSON_INVALID
    if "schema_validation_failed" in lowered:
        return FailureCategory.SCHEMA_VALIDATION_FAILED
    if "html_render_failed" in lowered:
        return FailureCategory.HTML_RENDER_FAILED
    if "manim_render_failed" in lowered and "latex_error" in lowered:
        return FailureCategory.MANIM_LATEX_ERROR
    if "manim_render_failed" in lowered and "syntax_error" in lowered:
        return FailureCategory.MANIM_SYNTAX_ERROR
    if "ffmpeg_merge_failed" in lowered or "ffmpeg_audio_mux_failed" in lowered:
        return FailureCategory.FFMPEG_MERGE_FAILED
    if "tts" in lowered and "failed" in lowered:
        return FailureCategory.TTS_SYNTHESIS_FAILED
    if "timeout" in lowered:
        return FailureCategory.TIMEOUT
    if "input" in lowered and ("missing" in lowered or "not_found" in lowered):
        return FailureCategory.INPUT_MISSING
    return FailureCategory.UNKNOWN


def failure_payload(category: FailureCategory, detail: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"category": category.value}
    if detail:
        payload["detail"] = detail
    return payload

