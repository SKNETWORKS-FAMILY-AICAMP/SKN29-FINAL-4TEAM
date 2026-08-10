"""T-024 trace continuity and sensitive-log regression tests.

Only the existing middleware, formatter, and exception handler are exercised.
No public runtime route or response contract is introduced by this module.
"""

from __future__ import annotations

from contextlib import contextmanager
from io import StringIO
import json
import logging
from uuid import UUID, uuid4

from django.test import override_settings
from django.urls import path
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from common.logging.filters import RequestContextFilter
from common.logging.formatter import JsonFormatter
from config.urls import urlpatterns as project_urlpatterns


class TraceFailureView(APIView):
    """Test-only exception source used to inspect safe failure logs."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        raise RuntimeError("private-exception-secret")


urlpatterns = [
    path(
        "api/v1/_test/t024-trace-failure",
        TraceFailureView.as_view(),
        name="t024-trace-failure",
    ),
    *project_urlpatterns,
]


@contextmanager
def captured_json_logs(*logger_names: str):
    """Capture application JSON logs while restoring global logger state."""

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RequestContextFilter())
    handler.setFormatter(JsonFormatter())
    originals = []

    try:
        for logger_name in logger_names:
            logger = logging.getLogger(logger_name)
            originals.append(
                (logger, list(logger.handlers), logger.level, logger.propagate)
            )
            logger.handlers = [handler]
            logger.setLevel(logging.INFO)
            logger.propagate = False
        yield stream
    finally:
        for logger, handlers, level, propagate in originals:
            logger.handlers = handlers
            logger.setLevel(level)
            logger.propagate = propagate


def parsed_lines(stream: StringIO) -> list[dict]:
    return [
        json.loads(line)
        for line in stream.getvalue().splitlines()
        if line.strip()
    ]


def test_404_log_uses_route_template_and_response_trace_without_secrets(
    client,
):
    correlation_id = str(uuid4())
    secrets = (
        "query-secret",
        "bearer-secret",
        "cookie-secret",
    )

    with captured_json_logs("watercare.request") as stream:
        response = client.get(
            "/api/v1/not-a-real-route?token=query-secret",
            HTTP_AUTHORIZATION="Bearer bearer-secret",
            HTTP_COOKIE="session=cookie-secret",
            HTTP_X_CORRELATION_ID=correlation_id,
        )

    assert response.status_code == 404
    assert response["X-Correlation-ID"] == correlation_id
    assert response.json()["metadata"]["correlation_id"] == correlation_id

    logs = parsed_lines(stream)
    assert len(logs) == 1
    log = logs[0]
    assert log["message"] == "request_completed"
    assert log["request_route"] == "/api/v1/<path:unmatched_path>"
    assert log["status_code"] == 404
    assert log["correlation_id"] == correlation_id
    UUID(log["correlation_id"])

    rendered = stream.getvalue()
    for secret in secrets:
        assert secret not in rendered


@override_settings(ROOT_URLCONF=__name__)
def test_500_logs_and_response_share_trace_and_redact_private_values(client):
    client.raise_request_exception = False
    correlation_id = str(uuid4())
    secrets = (
        "query-secret",
        "bearer-secret",
        "cookie-secret",
        "customer-private-raw-text",
        "ai-private-prompt",
        "private-exception-secret",
    )

    with captured_json_logs(
        "watercare.request",
        "watercare.exception",
    ) as stream:
        response = client.post(
            "/api/v1/_test/t024-trace-failure?token=query-secret",
            data=json.dumps(
                {
                    "raw_text": "customer-private-raw-text",
                    "prompt": "ai-private-prompt",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer bearer-secret",
            HTTP_COOKIE="session=cookie-secret",
            HTTP_X_CORRELATION_ID=correlation_id,
        )

    assert response.status_code == 500
    payload = response.json()
    assert response["X-Correlation-ID"] == correlation_id
    assert payload["metadata"]["correlation_id"] == correlation_id
    assert payload["error"]["code"] == "INTERNAL_ERROR"

    logs = parsed_lines(stream)
    assert {log["logger"] for log in logs} == {
        "watercare.request",
        "watercare.exception",
    }
    assert all(log["correlation_id"] == correlation_id for log in logs)
    request_log = next(
        log for log in logs if log["logger"] == "watercare.request"
    )
    exception_log = next(
        log for log in logs if log["logger"] == "watercare.exception"
    )
    assert request_log["request_route"] == (
        "/api/v1/_test/t024-trace-failure"
    )
    assert request_log["status_code"] == 500
    assert exception_log["message"] == "unhandled_exception"
    assert exception_log["exception_type"] == "RuntimeError"

    rendered = stream.getvalue() + response.content.decode("utf-8")
    for secret in secrets:
        assert secret not in rendered
