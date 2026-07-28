"""공개 Header·Metadata·로그를 잇는 추적 검증."""

import uuid
from unittest.mock import patch

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from common.middleware.correlation_id import CorrelationIdMiddleware
from common.middleware.request_context import get_correlation_id
from common.middleware.request_logging import RequestLoggingMiddleware


def test_correlation_id_is_available_inside_request_and_response():
    observed = {}

    def get_response(request):
        observed["correlation_id"] = request.correlation_id
        return HttpResponse(status=200)

    request = RequestFactory().get("/health")
    response = CorrelationIdMiddleware(get_response)(request)

    uuid.UUID(observed["correlation_id"])
    assert response["X-Correlation-ID"] == observed["correlation_id"]
    assert get_correlation_id() is None


def test_correlation_id_context_is_reset_when_request_raises():
    observed = {}

    def get_response(request):
        observed["correlation_id"] = request.correlation_id
        raise RuntimeError("request failed")

    request = RequestFactory().get("/api/v1/failure")

    with pytest.raises(RuntimeError, match="request failed"):
        CorrelationIdMiddleware(get_response)(request)

    uuid.UUID(observed["correlation_id"])
    assert get_correlation_id() is None


def test_consecutive_requests_receive_different_ids():
    observed = []

    def get_response(request):
        observed.append(request.correlation_id)
        return HttpResponse(status=200)

    middleware = CorrelationIdMiddleware(get_response)
    first_response = middleware(RequestFactory().get("/health"))
    second_response = middleware(RequestFactory().get("/health"))

    assert len(set(observed)) == 2
    for correlation_id in observed:
        uuid.UUID(correlation_id)
    assert first_response["X-Correlation-ID"] == observed[0]
    assert second_response["X-Correlation-ID"] == observed[1]
    assert get_correlation_id() is None


def test_valid_client_correlation_id_is_propagated():
    correlation_id = str(uuid.uuid4())
    request = RequestFactory().get(
        "/health",
        headers={"X-Correlation-ID": correlation_id},
    )

    response = CorrelationIdMiddleware(
        lambda request: HttpResponse(status=200)
    )(request)

    assert request.correlation_id == correlation_id
    assert response["X-Correlation-ID"] == correlation_id


def test_invalid_client_correlation_id_is_replaced():
    request = RequestFactory().get(
        "/health",
        headers={"X-Correlation-ID": "not-a-uuid"},
    )

    response = CorrelationIdMiddleware(
        lambda request: HttpResponse(status=200)
    )(request)

    uuid.UUID(request.correlation_id)
    assert request.correlation_id != "not-a-uuid"
    assert response["X-Correlation-ID"] == request.correlation_id


def test_request_logging_records_safe_http_metadata():
    middleware = RequestLoggingMiddleware(
        lambda request: HttpResponse(status=200)
    )
    request = RequestFactory().get("/health?token=must-not-be-logged")

    with patch(
        "common.middleware.request_logging.logger.info"
    ) as log_info:
        middleware(request)

    log_info.assert_called_once()
    _, kwargs = log_info.call_args
    assert kwargs["extra"]["http_method"] == "GET"
    assert kwargs["extra"]["request_route"] == "<unresolved>"
    assert kwargs["extra"]["status_code"] == 200
    assert "token" not in str(kwargs["extra"])
