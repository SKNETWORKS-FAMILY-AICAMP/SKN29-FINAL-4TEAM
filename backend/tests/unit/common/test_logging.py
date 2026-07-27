"""구조화 로그의 필드와 비노출 기준 검증."""

import json
import logging
import sys

from common.logging.formatter import JsonFormatter


def test_json_formatter_includes_trace_and_request_metadata():
    record = logging.LogRecord(
        name="watercare.request",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.correlation_id = "test-request-001"
    record.http_method = "GET"
    record.request_route = "/health"
    record.status_code = 200
    record.duration_ms = 1.25

    payload = json.loads(JsonFormatter().format(record))

    assert payload["utc_offset"]
    assert payload["correlation_id"] == "test-request-001"
    assert payload["request_route"] == "/health"
    assert payload["status_code"] == 200


def test_json_formatter_omits_exception_message_and_stack_trace():
    try:
        raise RuntimeError("sensitive-value-must-not-be-logged")
    except RuntimeError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="watercare.exception",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="unhandled_exception",
        args=(),
        exc_info=exc_info,
    )
    record.correlation_id = None

    rendered = JsonFormatter().format(record)
    payload = json.loads(rendered)

    assert payload["exception_type"] == "RuntimeError"
    assert "sensitive-value-must-not-be-logged" not in rendered


def test_json_formatter_uses_warn_level_name():
    record = logging.LogRecord(
        name="watercare.request",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="request_completed",
        args=(),
        exc_info=None,
    )
    record.correlation_id = "test-request-002"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "WARN"
