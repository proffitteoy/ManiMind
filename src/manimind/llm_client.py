"""LLM 调用层：按角色路由到主模型、审核模型或 worker 模型。"""

from __future__ import annotations

from dataclasses import dataclass
import http.client
import json
import os
import socket
import time
from typing import Any
from urllib import error, request


class LLMRequestError(RuntimeError):
    """模型请求失败。"""


@dataclass(slots=True)
class LLMRouteConfig:
    route_name: str
    provider_name: str
    base_url: str
    wire_api: str
    model: str
    reasoning_effort: str | None
    supports_reasoning_summaries: bool
    disable_response_storage: bool
    timeout_seconds: int
    api_key: str


@dataclass(slots=True)
class LLMRuntimeConfig:
    primary: LLMRouteConfig
    review: LLMRouteConfig
    worker: LLMRouteConfig

    def route_for_role(self, role_id: str) -> LLMRouteConfig:
        if role_id == "reviewer":
            return self.review
        if role_id in {
            "explorer",
            "planner",
            "coordinator",
            "html_worker",
            "manim_worker",
            "svg_worker",
        }:
            return self.worker
        return self.primary


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


def _normalize_wire_api(value: str | None) -> str:
    normalized = (value or "responses").strip().lower().replace("-", "_")
    if normalized in {"responses", "chat_completions"}:
        return normalized
    raise LLMRequestError(f"unsupported_wire_api:{value}")


def _read_timeout(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        return max(30, int(raw))
    except ValueError:
        return default


def _require_secret(value: str | None, name: str) -> str:
    secret = (value or "").strip()
    if not secret:
        raise LLMRequestError(f"missing_{name}")
    return secret


def load_llm_runtime_config() -> LLMRuntimeConfig:
    primary_base_url = (
        os.environ.get("MANIMIND_MODEL_BASE_URL")
        or os.environ.get("MODEL_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.apipool.dev"
    )
    primary_provider = (
        os.environ.get("MANIMIND_MODEL_PROVIDER")
        or os.environ.get("model_provider")
        or "apipool"
    )
    primary_model = _canonicalize_model_name(
        os.environ.get("MANIMIND_MODEL") or os.environ.get("model") or "gpt-5.5"
    )
    primary_wire_api = _normalize_wire_api(
        os.environ.get("MANIMIND_MODEL_WIRE_API")
        or os.environ.get("MANIMIND_WIRE_API")
        or "responses"
    )
    primary_effort = (
        os.environ.get("MANIMIND_MODEL_REASONING_EFFORT")
        or os.environ.get("model_reasoning_effort")
        or "medium"
    )
    primary_supports_summary = _parse_bool(
        os.environ.get("MANIMIND_MODEL_SUPPORTS_REASONING_SUMMARIES")
        or os.environ.get("model_supports_reasoning_summaries"),
        default=False,
    )
    disable_storage = _parse_bool(
        os.environ.get("MANIMIND_DISABLE_RESPONSE_STORAGE")
        or os.environ.get("disable_response_storage"),
        default=True,
    )
    primary_timeout = _read_timeout("MANIMIND_LLM_TIMEOUT_SECONDS", 240)
    primary_api_key = _require_secret(os.environ.get("OPENAI_API_KEY"), "OPENAI_API_KEY")

    review_model = _canonicalize_model_name(
        os.environ.get("MANIMIND_REVIEW_MODEL") or primary_model
    )
    review_wire_api = _normalize_wire_api(
        os.environ.get("MANIMIND_REVIEW_MODEL_WIRE_API") or primary_wire_api
    )
    review_base_url = (
        os.environ.get("MANIMIND_REVIEW_MODEL_BASE_URL") or primary_base_url
    )
    review_api_key = os.environ.get("MANIMIND_REVIEW_API_KEY") or primary_api_key
    review_effort = os.environ.get("MANIMIND_REVIEW_MODEL_REASONING_EFFORT") or primary_effort
    review_supports_summary = _parse_bool(
        os.environ.get("MANIMIND_REVIEW_MODEL_SUPPORTS_REASONING_SUMMARIES"),
        default=primary_supports_summary,
    )
    review_timeout = _read_timeout("MANIMIND_REVIEW_LLM_TIMEOUT_SECONDS", primary_timeout)

    worker_model = _canonicalize_model_name(
        os.environ.get("MANIMIND_WORKER_MODEL") or "deepseek-v4-flash"
    )
    worker_wire_api = _normalize_wire_api(
        os.environ.get("MANIMIND_WORKER_MODEL_WIRE_API") or primary_wire_api
    )
    worker_provider = os.environ.get("MANIMIND_WORKER_MODEL_PROVIDER") or primary_provider
    worker_base_url = (
        os.environ.get("MANIMIND_WORKER_MODEL_BASE_URL")
        or primary_base_url
    )
    worker_api_key = _require_secret(
        os.environ.get("MANIMIND_WORKER_API_KEY"),
        "MANIMIND_WORKER_API_KEY",
    )
    worker_effort = os.environ.get("MANIMIND_WORKER_MODEL_REASONING_EFFORT") or "medium"
    worker_supports_summary = _parse_bool(
        os.environ.get("MANIMIND_WORKER_MODEL_SUPPORTS_REASONING_SUMMARIES"),
        default=False,
    )
    worker_timeout = _read_timeout("MANIMIND_WORKER_LLM_TIMEOUT_SECONDS", primary_timeout)

    return LLMRuntimeConfig(
        primary=LLMRouteConfig(
            route_name="primary",
            provider_name=primary_provider,
            base_url=_normalize_base_url(primary_base_url),
            wire_api=primary_wire_api,
            model=primary_model,
            reasoning_effort=primary_effort,
            supports_reasoning_summaries=primary_supports_summary,
            disable_response_storage=disable_storage,
            timeout_seconds=primary_timeout,
            api_key=primary_api_key,
        ),
        review=LLMRouteConfig(
            route_name="review",
            provider_name=primary_provider,
            base_url=_normalize_base_url(review_base_url),
            wire_api=review_wire_api,
            model=review_model,
            reasoning_effort=review_effort,
            supports_reasoning_summaries=review_supports_summary,
            disable_response_storage=disable_storage,
            timeout_seconds=review_timeout,
            api_key=_require_secret(review_api_key, "MANIMIND_REVIEW_API_KEY"),
        ),
        worker=LLMRouteConfig(
            route_name="worker",
            provider_name=worker_provider,
            base_url=_normalize_base_url(worker_base_url),
            wire_api=worker_wire_api,
            model=worker_model,
            reasoning_effort=worker_effort,
            supports_reasoning_summaries=worker_supports_summary,
            disable_response_storage=disable_storage,
            timeout_seconds=worker_timeout,
            api_key=worker_api_key,
        ),
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
    retries_raw = os.environ.get("MANIMIND_LLM_RETRY_COUNT", "3").strip()
    try:
        retries = max(1, int(retries_raw))
    except ValueError:
        retries = 3

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with request.urlopen(req, timeout=timeout_seconds) as resp:
                content = resp.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                raise LLMRequestError(f"invalid_json_response:{content[:600]}") from exc
            if not isinstance(parsed, dict):
                raise LLMRequestError("invalid_response_shape")
            return parsed
        except error.HTTPError as exc:
            content = exc.read().decode("utf-8", errors="replace")
            last_error = LLMRequestError(f"http_{exc.code}:{content[:600]}")
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                time.sleep(min(8, 2 ** (attempt - 1)))
                continue
            raise last_error from exc
        except error.URLError as exc:
            last_error = LLMRequestError(f"url_error:{exc.reason}")
            if attempt < retries:
                time.sleep(min(8, 2 ** (attempt - 1)))
                continue
            raise last_error from exc
        except (TimeoutError, socket.timeout) as exc:
            last_error = LLMRequestError("timeout_error")
            if attempt < retries:
                time.sleep(min(8, 2 ** (attempt - 1)))
                continue
            raise last_error from exc
        except (http.client.RemoteDisconnected, ConnectionResetError) as exc:
            last_error = LLMRequestError("connection_reset")
            if attempt < retries:
                time.sleep(min(8, 2 ** (attempt - 1)))
                continue
            raise last_error from exc

    if last_error is not None:
        raise last_error
    raise LLMRequestError("request_failed_without_error")


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
    route: LLMRouteConfig,
    instructions: str,
    prompt: str,
    response_format: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": route.model,
        "instructions": instructions,
        "input": prompt,
        "store": not route.disable_response_storage,
    }
    if response_format == "json_object":
        payload["text"] = {"format": {"type": "json_object"}}
    if route.reasoning_effort:
        reasoning: dict[str, Any] = {"effort": route.reasoning_effort}
        if route.supports_reasoning_summaries:
            reasoning["summary"] = "auto"
        payload["reasoning"] = reasoning
    return _post_json(
        url=f"{route.base_url}/responses",
        api_key=route.api_key,
        payload=payload,
        timeout_seconds=route.timeout_seconds,
    )


def _extract_text_from_chat_completions(resp: dict[str, Any]) -> str:
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
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") not in {"text", "output_text"}:
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())
    return "\n".join(chunks).strip()


def _chat_completions_request(
    *,
    route: LLMRouteConfig,
    instructions: str,
    prompt: str,
    response_format: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": route.model,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt},
        ],
    }
    if response_format == "json_object":
        payload["response_format"] = {"type": "json_object"}
    return _post_json(
        url=f"{route.base_url}/chat/completions",
        api_key=route.api_key,
        payload=payload,
        timeout_seconds=route.timeout_seconds,
    )


def _call_role_route(
    *,
    cfg: LLMRuntimeConfig,
    role_id: str,
    instructions: str,
    prompt: str,
    response_format: str | None,
) -> tuple[str, dict[str, Any]]:
    route = cfg.route_for_role(role_id)
    if route.wire_api == "responses":
        resp = _responses_request(
            route=route,
            instructions=instructions,
            prompt=prompt,
            response_format=response_format,
        )
        text = _extract_text_from_responses(resp)
    elif route.wire_api == "chat_completions":
        resp = _chat_completions_request(
            route=route,
            instructions=instructions,
            prompt=prompt,
            response_format=response_format,
        )
        text = _extract_text_from_chat_completions(resp)
    else:
        raise LLMRequestError(f"unsupported_wire_api:{route.wire_api}")
    if not text:
        raise LLMRequestError("empty_output_text")
    return text, {
        "endpoint": route.wire_api,
        "role_id": role_id,
        "route": route.route_name,
        "provider": route.provider_name,
        "model": route.model,
    }


def generate_json_for_role(
    *,
    cfg: LLMRuntimeConfig,
    role_id: str,
    instructions: str,
    prompt: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    text, meta = _call_role_route(
        cfg=cfg,
        role_id=role_id,
        instructions=instructions,
        prompt=prompt,
        response_format="json_object",
    )
    return _extract_json_from_text(text), meta


def generate_text_for_role(
    *,
    cfg: LLMRuntimeConfig,
    role_id: str,
    instructions: str,
    prompt: str,
) -> tuple[str, dict[str, Any]]:
    return _call_role_route(
        cfg=cfg,
        role_id=role_id,
        instructions=instructions,
        prompt=prompt,
        response_format=None,
    )
