"""원문·Prompt·Secret을 기록하지 않는 AI HTTP 구조화 로그."""

import json
import logging
import os
from typing import Any


LOGGER = logging.getLogger("watercare.ai.analysis")


def configure_structured_logging() -> None:
    """AI_LOG_LEVEL을 실제 Runtime Logger에 적용한다."""
    level_name = os.getenv("AI_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        raise RuntimeError(f"지원하지 않는 AI_LOG_LEVEL입니다: {level_name}")
    LOGGER.setLevel(level)
    if not any(getattr(handler, "_watercare_ai_handler", False) for handler in LOGGER.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._watercare_ai_handler = True  # type: ignore[attr-defined]
        LOGGER.addHandler(handler)


def log_analysis_event(event: str, **fields: Any) -> None:
    """허용된 추적·실행 메타데이터만 JSON 한 줄로 기록한다."""
    allowed = {
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "state_version",
        "stage",
        "status",
        "retry_count",
        "latency_ms",
        "error_code",
    }
    payload = {"event": event}
    payload.update({key: value for key, value in fields.items() if key in allowed})
    LOGGER.info(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))
