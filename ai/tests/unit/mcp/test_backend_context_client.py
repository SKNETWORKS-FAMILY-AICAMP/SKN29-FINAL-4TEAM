"""Backend Context HTTP client contract and secret boundary."""

from __future__ import annotations

from uuid import uuid4

import httpx
import pytest

from ai.app.integrations.backend import (
    BackendContextClient,
    BackendContextClientError,
    BackendContextFailureKind,
)


def _payload(inquiry_id, correlation_id, *, model_code="WPUIAC425SNW"):
    return {
        "success": True,
        "data": {
            "inquiry_id": str(inquiry_id),
            "inquiry_code": "INQ-20260820-TEST",
            "status_code": "QUESTIONNAIRE_IN_PROGRESS",
            "state_version": 3,
            "correlation_id": str(correlation_id),
            "product_context": {
                "subscription_id": str(uuid4()),
                "subscription_status_code": "ACTIVE",
                "management_type_code": "SELF_MANAGED",
                "product_model_id": str(uuid4()),
                "model_code": model_code,
                "model_name": "테스트 정수기",
                "product_family": "ICE_WATER_PURIFIER",
                "generation_code": "ICE",
                "manufacturer": "SK매직",
                "features": {
                    "model_family": "WPU-IAC425",
                    "water_modes": ["COLD", "HOT"],
                    "supported_functions": ["HOT_WATER"],
                },
            },
            "inquiry_context": {
                "customer_query": "온수가 나오지 않아요.",
                "symptom_type": "HOT_WATER_STOPPED",
                "selected_symptoms": ["HOT_WATER_STOPPED"],
                "previous_answers": [
                    {
                        "question_id": "VALVE_OPEN",
                        "answer_text": "예",
                    }
                ],
            },
        },
        "error": None,
        "metadata": {"correlation_id": str(correlation_id)},
    }


def test_context_client_sends_protected_headers_and_validates_identity():
    inquiry_id = uuid4()
    correlation_id = uuid4()
    token = "protected-context-token"

    def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.path.endswith(f"/{inquiry_id}/context")
        assert request.headers["X-AI-Handoff-Token"] == token
        assert request.headers["X-Correlation-ID"] == str(correlation_id)
        return httpx.Response(
            200,
            json=_payload(inquiry_id, correlation_id),
            headers={"X-Correlation-ID": str(correlation_id)},
        )

    client = BackendContextClient(
        base_url="http://127.0.0.1:8000",
        handoff_token=token,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = client.get_context(
        inquiry_id=inquiry_id,
        correlation_id=correlation_id,
    )

    assert result.product_context.model_code == "WPUIAC425SNW"
    assert result.inquiry_context.customer_query == "온수가 나오지 않아요."
    assert token not in repr(result)


def test_context_client_timeout_is_sanitized_and_retryable():
    def handler(request: httpx.Request):
        raise httpx.ReadTimeout("sensitive upstream detail", request=request)

    client = BackendContextClient(
        base_url="http://127.0.0.1:8000",
        handoff_token="protected-context-token",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(BackendContextClientError) as exc_info:
        client.get_context(inquiry_id=uuid4(), correlation_id=uuid4())

    assert exc_info.value.kind == BackendContextFailureKind.TIMEOUT
    assert exc_info.value.retryable is True
    assert "sensitive" not in str(exc_info.value)


def test_context_client_fails_closed_on_correlation_mismatch():
    inquiry_id = uuid4()
    correlation_id = uuid4()

    client = BackendContextClient(
        base_url="http://127.0.0.1:8000",
        handoff_token="protected-context-token",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json=_payload(inquiry_id, correlation_id),
                    headers={"X-Correlation-ID": str(uuid4())},
                )
            )
        ),
    )

    with pytest.raises(BackendContextClientError) as exc_info:
        client.get_context(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
        )

    assert exc_info.value.kind == BackendContextFailureKind.INVALID_RESPONSE
    assert exc_info.value.retryable is False


@pytest.mark.parametrize(
    "base_url",
    [
        "",
        "ftp://127.0.0.1",
        "http://user:password@127.0.0.1:8000",
        "http://127.0.0.1:8000/api?token=value",
    ],
)
def test_context_client_rejects_unsafe_base_url(base_url):
    with pytest.raises(BackendContextClientError):
        BackendContextClient(
            base_url=base_url,
            handoff_token="protected-context-token",
        )
