"""민감정보를 직접 기록하지 않는 JSON 로그 Formatter."""

import json
import logging
from datetime import datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        now = datetime.now().astimezone()
        offset = now.strftime("%z")
        formatted_offset = f"{offset[:3]}:{offset[3:]}" if offset else None
        level_name = "WARN" if record.levelname == "WARNING" else record.levelname
        payload = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "utc_offset": formatted_offset,
            "level": level_name,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
        }

        for field in (
            "http_method",
            "request_route",
            "status_code",
            "duration_ms",
            "trace_stage",
            "inquiry_id",
            "ai_request_id",
            "ai_run_id",
            "ai_status",
            "event_candidate",
            "event_applied",
            "pending_reason",
            "idempotent_replay",
            "stale",
            "failure_code",
            "latency_ms",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info and record.exc_info[0] is not None:
            payload["exception_type"] = record.exc_info[0].__name__

        return json.dumps(payload, ensure_ascii=False)
