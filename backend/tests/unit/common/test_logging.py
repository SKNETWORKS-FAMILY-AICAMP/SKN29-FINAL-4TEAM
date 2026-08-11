"""구조화 로그의 필드와 비노출 기준 검증."""

import json
import logging
import sys
from unittest.mock import patch

from common.logging.formatter import JsonFormatter
from common.logging.filters import RequestContextFilter


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


def test_json_formatter_allows_safe_ai_lifecycle_fields_only():
    record = logging.LogRecord(
        name="watercare.ai",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="ai_analysis_terminal",
        args=(),
        exc_info=None,
    )
    record.correlation_id = "00000000-0000-0000-0000-000000000001"
    record.trace_stage = "ANALYSIS_TERMINAL"
    record.inquiry_id = "00000000-0000-0000-0000-000000000002"
    record.ai_request_id = "00000000-0000-0000-0000-000000000003"
    record.ai_run_id = "00000000-0000-0000-0000-000000000004"
    record.ai_status = "SUCCEEDED"
    record.pending_reason = "CANONICAL_EVIDENCE_VERIFICATION_REQUIRED"
    record.raw_text = "must-not-be-rendered"
    record.input_payload = {"symptom": "must-not-be-rendered"}

    rendered = JsonFormatter().format(record)
    payload = json.loads(rendered)

    assert payload["trace_stage"] == "ANALYSIS_TERMINAL"
    assert payload["ai_status"] == "SUCCEEDED"
    assert "raw_text" not in payload
    assert "input_payload" not in payload
    assert "must-not-be-rendered" not in rendered


def test_request_context_filter_preserves_explicit_callback_correlation():
    record = logging.LogRecord(
        name="watercare.ai",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="ai_callback_completed",
        args=(),
        exc_info=None,
    )
    explicit = "00000000-0000-0000-0000-000000000101"
    record.correlation_id = explicit

    with patch(
        "common.logging.filters.get_correlation_id",
        return_value="00000000-0000-0000-0000-000000000102",
    ):
        assert RequestContextFilter().filter(record) is True

    assert record.correlation_id == explicit


def test_request_context_filter_replaces_untrusted_explicit_value():
    record = logging.LogRecord(
        name="watercare.ai",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="ai_callback_completed",
        args=(),
        exc_info=None,
    )
    record.correlation_id = "customer-input-must-not-be-logged"
    contextual = "00000000-0000-0000-0000-000000000103"

    with patch(
        "common.logging.filters.get_correlation_id",
        return_value=contextual,
    ):
        assert RequestContextFilter().filter(record) is True

    assert record.correlation_id == contextual
