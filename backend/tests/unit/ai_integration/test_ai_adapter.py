"""Backend↔AI request, response, HTTP contract tests."""

from __future__ import annotations

import json
from copy import deepcopy
from uuid import uuid4

import httpx
import pytest

from integrations.ai.client import AIClient
from integrations.ai.exceptions import (
    AIIdentifierMismatchError,
    AIRequestValidationError,
    AIServiceResponseError,
    AITimeoutError,
)
from integrations.ai.request_mapper import build_symptom_analysis_request
from integrations.ai.response_mapper import map_success_response
from integrations.ai.schema_validator import (
    AIContractValidator,
    DEFAULT_CONTRACT_ROOT,
)


def request_payload() -> dict:
    return build_symptom_analysis_request(
        inquiry_id=uuid4(),
        correlation_id=uuid4(),
        ai_request_id=uuid4(),
        state_version=2,
        raw_symptom="냉수가 미지근하게 나옵니다.",
        model_code="WPUJAC104DWH",
        selected_symptoms=["온도 이상"],
        previous_answers=[],
    )


def success_payload(request: dict) -> dict:
    example_path = (
        DEFAULT_CONTRACT_ROOT
        / "examples"
        / "symptom-analysis"
        / "general-guidance.json"
    )
    payload = json.loads(example_path.read_text(encoding="utf-8"))["response"]
    for field in (
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "state_version",
    ):
        payload[field] = request[field]
    return payload


def error_payload(request: dict) -> dict:
    return {
        "success": False,
        "inquiry_id": request["inquiry_id"],
        "correlation_id": request["correlation_id"],
        "ai_request_id": request["ai_request_id"],
        "state_version": request["state_version"],
        "error": {
            "code": "AI-FAILED-01",
            "message": "검색 구성이 준비되지 않았습니다.",
            "details": None,
            "retryable": False,
            "failure_stage": "RETRIEVING",
            "retry_count": 0,
        },
    }


def test_contract_validator_loads_relative_refs_and_uuid_format():
    payload = request_payload()
    AIContractValidator().validate_request(payload)

    with pytest.raises(AIRequestValidationError):
        build_symptom_analysis_request(
            inquiry_id=payload["inquiry_id"],
            correlation_id="not-a-uuid",
            ai_request_id=payload["ai_request_id"],
            state_version=2,
            raw_symptom="누수가 발생합니다.",
            model_code="WPUJAC104DWH",
        )


def test_mapper_rejects_duplicate_previous_question_ids():
    with pytest.raises(AIRequestValidationError) as exc_info:
        build_symptom_analysis_request(
            inquiry_id=uuid4(),
            correlation_id=uuid4(),
            ai_request_id=uuid4(),
            state_version=2,
            raw_symptom="누수가 발생합니다.",
            model_code="WPUJAC104DWH",
            previous_answers=[
                {"question_id": "Q1", "answer_text": "예"},
                {"question_id": "Q1", "answer_text": "아니오"},
            ],
        )
    assert "duplicate Q1" in exc_info.value.validation_errors[0]


def test_success_mapper_rejects_identifier_mismatch():
    request = request_payload()
    response = success_payload(request)
    response["ai_request_id"] = "other-request"

    with pytest.raises(AIIdentifierMismatchError):
        map_success_response(response, expected_request=request)


def test_success_mapper_rejects_model_code_mismatch():
    request = request_payload()
    response = success_payload(request)
    response["model_code"] = "WPUIAC606SNW"

    with pytest.raises(AIIdentifierMismatchError) as exc_info:
        map_success_response(response, expected_request=request)

    assert "identifier mismatch: model_code" in exc_info.value.validation_errors


def test_success_mapper_classifies_safe_and_no_evidence_results():
    request = request_payload()
    safe = map_success_response(
        success_payload(request),
        expected_request=request,
    )
    assert safe.event_candidate == "SAFE_GUIDANCE_READY"
    assert safe.is_no_evidence is False

    no_evidence_payload = success_payload(request)
    no_evidence_payload.update(
        {
            "status": "FALLBACK",
            "fallback_reason_code": "NO_EVIDENCE",
            "failure_stage": "RETRIEVING",
            "evidence_references": [],
        }
    )
    no_evidence_payload["safety_assessment"]["requires_consultation"] = True
    no_evidence_payload["usage_guidance"][
        "guidance_status"
    ] = "PENDING_CONSULTATION"
    no_evidence = map_success_response(
        no_evidence_payload,
        expected_request=request,
    )
    assert no_evidence.event_candidate == "NO_EVIDENCE"
    assert no_evidence.is_no_evidence is True

    product_hold_payload = success_payload(request)
    product_hold_payload.update(
        {
            "status": "FALLBACK",
            "fallback_reason_code": "RUNTIME_PRODUCT_NOT_APPROVED",
            "failure_stage": "RETRIEVING",
            "evidence_references": [],
        }
    )
    product_hold_payload["safety_assessment"]["requires_consultation"] = True
    product_hold_payload["usage_guidance"][
        "guidance_status"
    ] = "PENDING_CONSULTATION"
    product_hold = map_success_response(
        product_hold_payload,
        expected_request=request,
    )
    assert product_hold.event_candidate is None
    assert product_hold.is_no_evidence is False


def test_client_sends_matching_header_and_calls_once():
    request = request_payload()
    calls = []

    def handler(http_request: httpx.Request) -> httpx.Response:
        calls.append(http_request)
        body = json.loads(http_request.content.decode("utf-8"))
        assert http_request.headers["X-Correlation-ID"] == body[
            "correlation_id"
        ]
        assert http_request.url.params["mode"] == "local"
        return httpx.Response(200, json=success_payload(request))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    result = AIClient(
        base_url="http://ai.test",
        http_client=http_client,
    ).analyze(request)

    assert result.event_candidate == "SAFE_GUIDANCE_READY"
    assert len(calls) == 1
    http_client.close()


def test_client_validates_error_contract_without_retry():
    request = request_payload()
    calls = 0

    def handler(_http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json=error_payload(request))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(AIServiceResponseError) as exc_info:
        AIClient(
            base_url="http://ai.test",
            http_client=http_client,
        ).analyze(request)

    assert exc_info.value.http_status == 503
    assert exc_info.value.retryable is False
    assert calls == 1
    http_client.close()


def test_client_transport_timeout_is_not_retried():
    request = request_payload()
    calls = 0

    def handler(http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timeout", request=http_request)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(AITimeoutError):
        AIClient(
            base_url="http://ai.test",
            http_client=http_client,
        ).analyze(deepcopy(request))

    assert calls == 1
    http_client.close()
