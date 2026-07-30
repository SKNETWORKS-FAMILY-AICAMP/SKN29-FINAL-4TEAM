"""원문·Prompt·Secret을 기록하지 않는 AI HTTP 구조화 로그."""

import json
import logging
from typing import Any


LOGGER = logging.getLogger("watercare.ai.analysis")


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
