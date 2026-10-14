"""Central cloud LLM client with bounded retries and redacted usage telemetry."""
from __future__ import annotations

import asyncio
import re
import time
import uuid

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.modal_client import WorkerUnavailable

logger = get_logger(__name__)


def _scope_ids() -> tuple[str | None, str | None]:
    try:
        from app.core.tenant import current_scope
        value = current_scope.get()
        return (value.tenant_id, value.user_id) if value else (None, None)
    except Exception:
        return None, None


def _header_int(headers, name: str) -> int | None:
    try:
        return int(headers[name])
    except (KeyError, TypeError, ValueError):
        return None


def _reset_seconds(value: str | None) -> int | None:
    """Parse Groq's duration headers such as 1m23.4s without guessing."""
    if not value:
        return None
    try:
        return max(1, int(float(value)))
    except ValueError:
        pass
    parts = re.findall(r"(\d+(?:\.\d+)?)(h|m|s)", value.lower())
    if not parts:
        return None
    scale = {"h": 3600, "m": 60, "s": 1}
    return max(1, int(sum(float(amount) * scale[unit] for amount, unit in parts)))


def _event(event: dict) -> None:
    """Best-effort telemetry; persistence faults must not leak provider output."""
    try:
        from app.services import cloud_db
        cloud_db.record_llm_attempt(event)
    except Exception as exc:  # analytics are not allowed to break user actions
        logger.warning("LLM usage event persistence failed (%s)", type(exc).__name__)


async def generate(prompt: str, system: str | None = None, task_type: str = "other") -> str:
    cfg = get_settings()
    if cfg.llm_provider == "xai":
        base, model, keys = "https://api.x.ai/v1", cfg.xai_model, [("xai_primary", cfg.xai_api_key)]
    elif cfg.llm_provider == "groq":
        base, model = "https://api.groq.com/openai/v1", cfg.groq_model
        keys = [("groq_primary", cfg.groq_api_key)]
        if cfg.groq_api_key_secondary:
            keys.append(("groq_secondary", cfg.groq_api_key_secondary))
    else:
        raise WorkerUnavailable("LLM provider is not configured")

    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    request_id = uuid.uuid4().hex
    tenant_id, user_id = _scope_ids()
    auth_failover_used = False
    for key_index, (alias, key) in enumerate(keys):
        if not key:
            continue
        retry_count = 0
        while True:
            reserved_tokens = (len(prompt) + len(system or "") + 3) // 4 + (512 if task_type == "ingestion_summary" else 1024)
            if cfg.llm_provider == "groq":
                try:
                    from app.core.ratelimit import (RateLimitUnavailable, provider_circuit_remaining,
                                                    provider_cooldown_remaining, reserve_provider_budget)
                    if provider_circuit_remaining(model, cfg):
                        raise WorkerUnavailable("LLM temporarily unavailable")
                    if provider_cooldown_remaining(model, cfg):
                        raise WorkerUnavailable("LLM temporarily unavailable")
                    allowed, _retry = reserve_provider_budget(model, reserved_tokens, cfg)
                    if not allowed:
                        raise WorkerUnavailable("LLM temporarily unavailable")
                except RateLimitUnavailable:
                    raise WorkerUnavailable("LLM temporarily unavailable") from None
            started = time.perf_counter()
            response = None
            status, code = "unknown", None
            headers = {}
            usage = {}
            try:
                async with httpx.AsyncClient(timeout=90) as client:
                    response = await client.post(
                        base + "/chat/completions",
                        headers={"Authorization": "Bearer " + key, "X-Request-ID": request_id},
                        json={"model": model, "messages": messages, "stream": False,
                              "max_completion_tokens": 2048},
                    )
                headers = response.headers
                code = response.status_code
                if code == 401:
                    status, code_class = "auth_error", "credential_rejected"
                    if cfg.llm_provider == "groq" and key_index == 0 and len(keys) > 1:
                        auth_failover_used = True
                elif code == 429:
                    status, code_class = "rate_limited", "provider_rate_limited"
                elif code >= 500:
                    status, code_class = "upstream_error", "provider_5xx"
                elif code >= 400:
                    status, code_class = "invalid_request", "provider_rejected_request"
                else:
                    response.raise_for_status()
                    body = response.json()
                    answer = body["choices"][0]["message"]["content"]
                    if not isinstance(answer, str) or not answer.strip():
                        raise ValueError("empty_completion")
                    usage = body.get("usage") or {}
                    status, code_class = "success", None
                input_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
                output_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
                total_tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
                if status == "success" and isinstance(total_tokens, int) and cfg.llm_provider == "groq":
                    try:
                        from app.core.ratelimit import reconcile_provider_tokens
                        reconcile_provider_tokens(model, reserved_tokens, total_tokens, cfg)
                    except Exception:
                        pass
                await asyncio.to_thread(_event, {
                    "request_id": request_id, "tenant_id": tenant_id, "user_id": user_id,
                    "task_type": task_type if task_type in {"ask_ai", "ingestion_summary", "other"} else "other",
                    "provider": cfg.llm_provider, "model": model, "key_alias": alias,
                    "quota_scope": "organization/model" if cfg.llm_provider == "groq" else "provider/model",
                    "status": status, "http_status": code,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "input_tokens": input_tokens, "output_tokens": output_tokens,
                    "total_tokens": total_tokens, "retry_count": retry_count,
                    "fallback_used": auth_failover_used,
                    "fallback_reason": "credential_rejected" if auth_failover_used else None,
                    "error_code": code_class,
                    "rpd_limit": _header_int(headers, "x-ratelimit-limit-requests"),
                    "rpd_remaining": _header_int(headers, "x-ratelimit-remaining-requests"),
                    "rpd_reset": headers.get("x-ratelimit-reset-requests"),
                    "tpm_limit": _header_int(headers, "x-ratelimit-limit-tokens"),
                    "tpm_remaining": _header_int(headers, "x-ratelimit-remaining-tokens"),
                    "tpm_reset": headers.get("x-ratelimit-reset-tokens"),
                })
                if status == "success":
                    if cfg.llm_provider == "groq":
                        try:
                            from app.core.ratelimit import provider_success
                            provider_success(model, cfg)
                        except Exception:
                            pass
                    return answer.strip()
                if status == "auth_error":
                    break
                if status == "upstream_error" and cfg.llm_provider == "groq":
                    try:
                        from app.core.ratelimit import provider_failure
                        provider_failure(model, cfg)
                    except Exception:
                        pass
                if status == "upstream_error" and retry_count < 2:
                    retry_count += 1
                    await asyncio.sleep(min(0.15 * (2 ** retry_count), 0.6))
                    continue
                if status == "rate_limited":
                    retry_after = headers.get("retry-after")
                    wait_seconds = _reset_seconds(retry_after)
                    if wait_seconds is None:
                        reset_candidates = []
                        if _header_int(headers, "x-ratelimit-remaining-requests") == 0:
                            reset_candidates.append(_reset_seconds(headers.get("x-ratelimit-reset-requests")))
                        if _header_int(headers, "x-ratelimit-remaining-tokens") == 0:
                            reset_candidates.append(_reset_seconds(headers.get("x-ratelimit-reset-tokens")))
                        wait_seconds = next((value for value in reset_candidates if value is not None), 60)
                    try:
                        from app.core.ratelimit import provider_cooldown
                        provider_cooldown(model, wait_seconds, cfg)
                    except Exception:
                        # The provider event is still logged; avoid leaking or
                        # retrying when its shared cooldown store is unavailable.
                        pass
                    logger.warning("LLM provider rate limited model=%s retry_after=%s", model, retry_after)
                raise WorkerUnavailable("LLM temporarily unavailable")
            except WorkerUnavailable:
                raise
            except httpx.HTTPError:
                await asyncio.to_thread(_event, {
                    "request_id": request_id, "tenant_id": tenant_id, "user_id": user_id,
                    "task_type": task_type if task_type in {"ask_ai", "ingestion_summary", "other"} else "other",
                    "provider": cfg.llm_provider, "model": model, "key_alias": alias,
                    "quota_scope": "organization/model" if cfg.llm_provider == "groq" else "provider/model",
                    "status": "timeout",
                    "http_status": code, "latency_ms": int((time.perf_counter() - started) * 1000),
                    "retry_count": retry_count, "error_code": "network_or_response_error",
                })
                if cfg.llm_provider == "groq":
                    try:
                        from app.core.ratelimit import provider_failure
                        provider_failure(model, cfg)
                    except Exception:
                        pass
                if retry_count < 1:
                    retry_count += 1
                    await asyncio.sleep(0.2)
                    continue
                raise WorkerUnavailable("LLM temporarily unavailable") from None
            except (ValueError, KeyError, IndexError, TypeError):
                await asyncio.to_thread(_event, {
                    "request_id": request_id, "tenant_id": tenant_id, "user_id": user_id,
                    "task_type": task_type if task_type in {"ask_ai", "ingestion_summary", "other"} else "other",
                    "provider": cfg.llm_provider, "model": model, "key_alias": alias,
                    "quota_scope": "organization/model" if cfg.llm_provider == "groq" else "provider/model",
                    "status": "invalid_request", "http_status": code,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "retry_count": retry_count, "error_code": "invalid_provider_response",
                })
                raise WorkerUnavailable("LLM temporarily unavailable") from None
        # Only a credential-specific 401 reaches this point. Never rotate on 429.
    raise WorkerUnavailable("LLM temporarily unavailable")
