"""고객 원문·Prompt·Secret을 제외한 LLM 사용량 구조화 로그."""

import json
import logging
import os
from typing import Any


LOGGER = logging.getLogger("watercare.ai.llm")

_ALLOWED_FIELDS = {
    "correlation_id",
    "ai_request_id",
    "inquiry_id",
    "model_code",
    "task",
    "model_name",
    "prompt_version",
    "reason",
    "validation_result",
    "validation_reason",
    "fallback_fields",
    "target_field",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "latency_ms",
    "retry_count",
}
_USAGE_EVENTS = {
    "llm_guidance_completed",
    "llm_symptom_structuring_completed",
    "llm_followup_wording_completed",
}
_FALLBACK_EVENTS = {
    "llm_symptom_structuring_fallback",
    "llm_followup_wording_fallback",
    "llm_followup_wording_field_fallback",
    "llm_client_configuration_fallback",
}


def configure_llm_usage_logging() -> None:
    level_name = os.getenv("AI_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        raise RuntimeError(f"지원하지 않는 AI_LOG_LEVEL입니다: {level_name}")
    LOGGER.setLevel(level)
    if not any(getattr(handler, "_watercare_llm_handler", False) for handler in LOGGER.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._watercare_llm_handler = True  # type: ignore[attr-defined]
        LOGGER.addHandler(handler)


def log_llm_usage(*, event: str = "llm_guidance_completed", **fields: Any) -> None:
    if event not in _USAGE_EVENTS:
        raise ValueError("허용되지 않은 LLM usage event입니다.")
    _log_event(logging.INFO, event, fields)


def log_llm_fallback(*, event: str, **fields: Any) -> None:
    """고객 원문이나 Provider 오류 본문 없이 fallback 사유만 경고한다."""

    if event not in _FALLBACK_EVENTS:
        raise ValueError("허용되지 않은 LLM fallback event입니다.")
    _log_event(logging.WARNING, event, fields)


def _log_event(level: int, event: str, fields: dict[str, Any]) -> None:
    payload = {"event": event}
    payload.update(
        {
            key: value
            for key, value in fields.items()
            if key in _ALLOWED_FIELDS and value is not None
        }
    )
    LOGGER.log(
        level,
        json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True),
    )
