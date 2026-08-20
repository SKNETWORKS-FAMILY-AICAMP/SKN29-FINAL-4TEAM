"""Unit tests for sanitized AI -> Backend handoff delivery."""

from __future__ import annotations

import json
from uuid import UUID

import httpx

from ai.app.integrations.backend.handoff_client import (
    BACKEND_BASE_URL_ENV,
    HANDOFF_ENABLED_ENV,
    HANDOFF_TOKEN_ENV,
    HandoffPublishFailureKind,
    HandoffPublishStatus,
    INITIAL_DELAY_SECONDS,
    RETRY_DELAY_SECONDS,
    publish_consultation_handoff,
)
from ai.app.orchestration.handoff import ConsultationHandoffResult


TOKEN = "unit-test-handoff-secret"


def _handoff(
    *,
    symptom_summary: str = "출수량 저하가 확인되어 상담이 필요합니다.",
) -> ConsultationHandoffResult:
    return ConsultationHandoffResult(
        inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b201"),
        correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e001"),
        ai_request_id="ai-handoff-unit-001",
        model_code="WPUJAC104DWH",
        product_family="DIRECT_WATER_PURIFIER",
        customer_symptom_summary=symptom_summary,
        questionnaire_answers=[],
        self_help_actions=["상담 연결 요청"],
        evidence=[],
        safety_level="unknown",
        safety_requires_consultation=False,
        safety_notes=[],
        escalation_reason="NO_EVIDENCE",
        consultant_priority_checks=["출수 환경 확인"],
        source_chunk_ids=[],
    )


def _enable(monkeypatch, base_url: str = "http://backend.test"):
    monkeypatch.setenv(HANDOFF_ENABLED_ENV, "true")
    monkeypatch.setenv(BACKEND_BASE_URL_ENV, base_url)
    monkeypatch.setenv(HANDOFF_TOKEN_ENV, TOKEN)


def test_publish_sends_backend_contract_headers_and_payload(monkeypatch):
    _enable(monkeypatch)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["headers"] = request.headers
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(201)

    sleeps = []
    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = publish_consultation_handoff(
            _handoff(),
            http_client=client,
            sleep_fn=sleeps.append,
        )

    assert result.status == HandoffPublishStatus.DELIVERED
    assert result.attempts == 1
    assert result.status_code == 201
    assert seen["path"].endswith(
        "/api/v1/internal/ai/inquiries/"
        "018f2f9b-7c30-7981-b541-1a987c88b201/"
        "consultation-handoffs"
    )
    assert seen["headers"]["X-AI-Handoff-Token"] == TOKEN
    assert seen["headers"]["Idempotency-Key"] == "ai-handoff-unit-001"
    assert (
        seen["headers"]["X-Correlation-ID"]
        == "018f2f9b-7c30-7981-b541-1a987c88e001"
    )
    assert seen["payload"]["model_code"] == "WPUJAC104DWH"
    assert "system_prompt" not in seen["payload"]
    assert "raw_output_text" not in seen["payload"]
    assert sleeps == [INITIAL_DELAY_SECONDS]
    assert TOKEN not in repr(result)


def test_publish_retries_once_for_airun_finalization_conflict(monkeypatch):
    _enable(monkeypatch)
    statuses = iter([409, 201])
    calls = []
    sleeps = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(next(statuses))

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = publish_consultation_handoff(
            _handoff(),
            http_client=client,
            sleep_fn=sleeps.append,
        )

    assert result.status == HandoffPublishStatus.DELIVERED
    assert result.attempts == 2
    assert result.status_code == 201
    assert len(calls) == 2
    assert sleeps == [INITIAL_DELAY_SECONDS, RETRY_DELAY_SECONDS]


def test_publish_does_not_retry_permanent_backend_rejection(monkeypatch):
    _enable(monkeypatch)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(403)

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = publish_consultation_handoff(
            _handoff(),
            http_client=client,
            sleep_fn=lambda _seconds: None,
        )

    assert result.status == HandoffPublishStatus.FAILED
    assert result.attempts == 1
    assert result.status_code == 403
    assert result.failure_kind == (
        HandoffPublishFailureKind.BACKEND_REJECTED
    )
    assert calls == 1


def test_publish_fails_closed_before_network_when_pii_remains(monkeypatch):
    _enable(monkeypatch)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(201)

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = publish_consultation_handoff(
            _handoff(
                symptom_summary="연락처 010-1234-5678로 연락해 주세요."
            ),
            http_client=client,
            sleep_fn=lambda _seconds: None,
        )

    assert result.status == HandoffPublishStatus.FAILED
    assert result.attempts == 0
    assert result.failure_kind == HandoffPublishFailureKind.PII_DETECTED
    assert calls == 0


def test_publish_missing_configuration_preserves_caller(monkeypatch):
    monkeypatch.setenv(HANDOFF_ENABLED_ENV, "true")
    monkeypatch.delenv(BACKEND_BASE_URL_ENV, raising=False)
    monkeypatch.delenv(HANDOFF_TOKEN_ENV, raising=False)

    result = publish_consultation_handoff(
        _handoff(),
        sleep_fn=lambda _seconds: None,
    )

    assert result.status == HandoffPublishStatus.FAILED
    assert result.attempts == 0
    assert result.failure_kind == (
        HandoffPublishFailureKind.CONFIGURATION
    )


def test_publish_disabled_is_noop(monkeypatch):
    monkeypatch.setenv(HANDOFF_ENABLED_ENV, "false")

    result = publish_consultation_handoff(
        _handoff(),
        sleep_fn=lambda _seconds: None,
    )

    assert result.status == HandoffPublishStatus.DISABLED
    assert result.attempts == 0
