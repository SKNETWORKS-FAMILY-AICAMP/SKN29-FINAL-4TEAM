"""요청 로그 수준과 민감정보 비노출 기준 검증."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from common.middleware.request_logging import RequestLoggingMiddleware


@pytest.mark.parametrize(
    ("status_code", "log_method"),
    [
        (200, "info"),
        (404, "warning"),
        (500, "error"),
    ],
)
def test_request_logging_uses_level_for_response_status(
    status_code,
    log_method,
):
    request = RequestFactory().get("/api/v1/resources")
    middleware = RequestLoggingMiddleware(
        lambda request: HttpResponse(status=status_code)
    )

    with (
        patch(
            "common.middleware.request_logging.logger.info"
        ) as log_info,
        patch(
            "common.middleware.request_logging.logger.warning"
        ) as log_warning,
        patch(
            "common.middleware.request_logging.logger.error"
        ) as log_error,
    ):
        response = middleware(request)

    logs = {
        "info": log_info,
        "warning": log_warning,
        "error": log_error,
    }
    log = logs.pop(log_method)
    assert response.status_code == status_code
    log.assert_called_once()
    for unused_log in logs.values():
        unused_log.assert_not_called()

    message, = log.call_args.args
    extra = log.call_args.kwargs["extra"]
    assert message == "request_completed"
    assert extra["http_method"] == "GET"
    assert extra["status_code"] == status_code
    assert extra["duration_ms"] >= 0


def test_request_logging_records_route_without_sensitive_request_values():
    sensitive_values = [
        "query-secret",
        "bearer-secret",
        "cookie-secret",
        "body-secret",
    ]
    request = RequestFactory().post(
        "/api/v1/resources?token=query-secret",
        data='{"password":"body-secret"}',
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer bearer-secret",
        HTTP_COOKIE="session=cookie-secret",
    )
    request.resolver_match = SimpleNamespace(
        route="api/v1/resources/<str:resource_id>"
    )
    middleware = RequestLoggingMiddleware(
        lambda request: HttpResponse(status=200)
    )

    with patch(
        "common.middleware.request_logging.logger.info"
    ) as log_info:
        middleware(request)

    extra = log_info.call_args.kwargs["extra"]
    assert set(extra) == {
        "http_method",
        "request_route",
        "status_code",
        "duration_ms",
    }
    assert extra["request_route"] == (
        "/api/v1/resources/<str:resource_id>"
    )
    rendered_extra = str(extra)
    for sensitive_value in sensitive_values:
        assert sensitive_value not in rendered_extra


def test_request_logging_reraises_exception_with_safe_metadata():
    def raise_exception(request):
        raise RuntimeError("sensitive-exception-message")

    request = RequestFactory().get(
        "/api/v1/resources?token=query-secret",
        HTTP_AUTHORIZATION="Bearer bearer-secret",
    )
    middleware = RequestLoggingMiddleware(raise_exception)

    with patch(
        "common.middleware.request_logging.logger.exception"
    ) as log_exception:
        with pytest.raises(
            RuntimeError,
            match="sensitive-exception-message",
        ):
            middleware(request)

    log_exception.assert_called_once()
    message, = log_exception.call_args.args
    extra = log_exception.call_args.kwargs["extra"]
    assert message == "request_failed"
    assert set(extra) == {
        "http_method",
        "request_route",
        "duration_ms",
    }
    assert "query-secret" not in str(extra)
    assert "bearer-secret" not in str(extra)
    assert "sensitive-exception-message" not in str(extra)
