"""고객 원문·Prompt·Secret을 제외한 LLM 사용량 구조화 로그."""

import json
import logging
import os
from typing import Any


LOGGER = logging.getLogger("watercare.ai.llm")


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
    allowed = {
        "correlation_id",
        "ai_request_id",
        "model_name",
        "prompt_version",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "latency_ms",
        "retry_count",
    }
    allowed_events = {
        "llm_guidance_completed",
        "llm_symptom_structuring_completed",
        "llm_followup_wording_completed",
    }
    if event not in allowed_events:
        raise ValueError("허용되지 않은 LLM usage event입니다.")
    payload = {"event": event}
    payload.update({key: value for key, value in fields.items() if key in allowed})
    LOGGER.info(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))
