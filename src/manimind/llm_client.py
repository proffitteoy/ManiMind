"""LLM 调用层：优先 Responses API，失败时回退到 Chat Completions。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any
from urllib import error, request


class LLMRequestError(RuntimeError):
    """模型请求失败。"""


@dataclass(slots=True)
class LLMRuntimeConfig:
    provider_name: str
    base_url: str
    model: str
    review_model: str
    fast_model: str
    fast_base_url: str
    model_reasoning_effort: str
    model_supports_reasoning_summaries: bool
    disable_response_storage: bool
    timeout_seconds: int
    api_key: str
    fast_api_key: str | None


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_base_url(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return normalized + "/v1"


def _canonicalize_model_name(model: str) -> str:
    normalized = model.strip()
    lower = normalized.lower().replace("_", "").replace("-", "")
    if lower == "deepseekv4flash":
        return "deepseek-v4-flash"
    if lower == "deepseekv4pro":
        return "deepseek-v4-pro"
    return normalized


def load_llm_runtime_config() -> LLMRuntimeConfig:
    base_url = os.environ.get("MANIMIND_MODEL_BASE_URL") or os.environ.get(
        "MODEL_BASE_URL"
    ) or "https://api.apipool.dev"
    provider_name = os.environ.get("MANIMIND_MODEL_PROVIDER") or os.environ.get(
        "model_provider"
    ) or "apipool"
    model = os.environ.get("MANIMIND_MODEL") or os.environ.get("model") or "gpt-5.5"
    model = _canonicalize_model_name(model)
    review_model = (
        os.environ.get("MANIMIND_REVIEW_MODEL")
        or os.environ.get("review_model")
        or model
    )
    review_model = _canonicalize_model_name(review_model)
    fast_model = _canonicalize_model_name(
        os.environ.get("MANIMIND_FAST_MODEL") or "deepseekv4flash"
    )
    fast_base_url = os.environ.get("MANIMIND_FAST_MODEL_BASE_URL") or os.environ.get(
        "DEEPSEEK_BASE_URL"
    ) or base_url
    effort = (
        os.environ.get("MANIMIND_MODEL_REASONING_EFFORT")
        or os.environ.get("model_reasoning_effort")
        or "medium"
    )
    supports_reasoning_summaries = _parse_bool(
        os.environ.get("MANIMIND_MODEL_SUPPORTS_REASONING_SUMMARIES")
        or os.environ.get("model_supports_reasoning_summaries"),
        default=False,
    )
    disable_storage = _parse_bool(
        os.environ.get("MANIMIND_DISABLE_RESPONSE_STORAGE")
        or os.environ.get("disable_response_storage"),
        default=True,
    )
    timeout_seconds_raw = os.environ.get("MANIMIND_LLM_TIMEOUT_SECONDS", "240")
    try:
        timeout_seconds = max(30, int(timeout_seconds_raw))
    except ValueError:
        timeout_seconds = 240

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    fast_api_key = (
        os.environ.get("MANIMIND_FAST_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or ""
    ).strip() or None
    if not api_key:
        raise LLMRequestError("missing_OPENAI_API_KEY")
    return LLMRuntimeConfig(
        provider_name=provider_name,
        base_url=_normalize_base_url(base_url),
        model=model,
        review_model=review_model,
        fast_model=fast_model,
        fast_base_url=_normalize_base_url(fast_base_url),
        model_reasoning_effort=effort,
        model_supports_reasoning_summaries=supports_reasoning_summaries,
        disable_response_storage=disable_storage,
        timeout_seconds=timeout_seconds,
        api_key=api_key,
        fast_api_key=fast_api_key,
    )


def _extract_json_from_text(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if not candidate:
        raise LLMRequestError("empty_model_output")
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for idx, char in enumerate(candidate):
        if char != "{":
            continue
        try:
            parsed, _end = decoder.raw_decode(candidate[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise LLMRequestError("model_output_not_json_object")


def _post_json(
    *,
    url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=url,
        method="POST",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            content = resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        content = exc.read().decode("utf-8", errors="replace")
        raise LLMRequestError(f"http_{exc.code}:{content[:600]}") from exc
    except error.URLError as exc:
        raise LLMRequestError(f"url_error:{exc.reason}") from exc
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LLMRequestError(f"invalid_json_response:{content[:600]}") from exc
    if not isinstance(parsed, dict):
        raise LLMRequestError("invalid_response_shape")
    return parsed


def _extract_text_from_responses(resp: dict[str, Any]) -> str:
    output_text = resp.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = resp.get("output")
    if not isinstance(output, list):
        return ""
    chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") not in {"output_text", "text"}:
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    return "\n".join(chunks).strip()


def _responses_request(
    *,
    base_url: str,
    cfg: LLMRuntimeConfig,
    model: str,
    api_key: str,
    instructions: str,
    prompt: str,
    reasoning_effort: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "instructions": instructions,
        "input": prompt,
        "store": not cfg.disable_response_storage,
        "text": {"format": {"type": "json_object"}},
    }
    if reasoning_effort:
        reasoning: dict[str, Any] = {"effort": reasoning_effort}
        if cfg.model_supports_reasoning_summaries:
            reasoning["summary"] = "auto"
        payload["reasoning"] = reasoning
    return _post_json(
        url=f"{base_url}/responses",
        api_key=api_key,
        payload=payload,
        timeout_seconds=cfg.timeout_seconds,
    )


def _chat_completions_request(
    *,
    base_url: str,
    cfg: LLMRuntimeConfig,
    model: str,
    api_key: str,
    instructions: str,
    prompt: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    return _post_json(
        url=f"{base_url}/chat/completions",
        api_key=api_key,
        payload=payload,
        timeout_seconds=cfg.timeout_seconds,
    )


def _extract_text_from_chat(resp: dict[str, Any]) -> str:
    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
        return "\n".join(chunks).strip()
    return ""


def generate_json_with_fallback(
    *,
    cfg: LLMRuntimeConfig,
    instructions: str,
    prompt: str,
    request_kind: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if request_kind not in {"main", "review"}:
        raise ValueError("request_kind must be main or review")

    primary_model = cfg.model if request_kind == "main" else cfg.review_model
    candidates: list[tuple[str, str, str, str | None]] = [
        (primary_model, cfg.base_url, cfg.api_key, cfg.model_reasoning_effort),
    ]
    fallback_key = cfg.fast_api_key or cfg.api_key
    if cfg.fast_model and cfg.fast_model != primary_model:
        candidates.append((cfg.fast_model, cfg.fast_base_url, fallback_key, "low"))

    errors: list[str] = []
    for model, base_url, api_key, effort in candidates:
        try:
            resp = _responses_request(
                base_url=base_url,
                cfg=cfg,
                model=model,
                api_key=api_key,
                instructions=instructions,
                prompt=prompt,
                reasoning_effort=effort,
            )
            text = _extract_text_from_responses(resp)
            parsed = _extract_json_from_text(text)
            return parsed, {"endpoint": "responses", "model": model}
        except Exception as exc:
            errors.append(f"responses:{model}:{exc}")
        try:
            resp = _chat_completions_request(
                base_url=base_url,
                cfg=cfg,
                model=model,
                api_key=api_key,
                instructions=instructions,
                prompt=prompt,
            )
            text = _extract_text_from_chat(resp)
            parsed = _extract_json_from_text(text)
            return parsed, {"endpoint": "chat.completions", "model": model}
        except Exception as exc:
            errors.append(f"chat.completions:{model}:{exc}")

    raise LLMRequestError("llm_all_attempts_failed: " + " | ".join(errors))
