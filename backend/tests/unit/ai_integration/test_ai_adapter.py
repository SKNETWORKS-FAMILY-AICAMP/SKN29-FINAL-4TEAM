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
    AIResponseValidationError,
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
    if "model_code" in payload:
        payload["model_code"] = request["model_code"]
    return payload


def danger_payload(request: dict) -> dict:
    example_path = (
        DEFAULT_CONTRACT_ROOT
        / "examples"
        / "symptom-analysis"
        / "danger-detected.json"
    )
    payload = json.loads(example_path.read_text(encoding="utf-8"))["response"]
    for field in (
        "inquiry_id",
        "correlation_id",
        "ai_request_id",
        "state_version",
    ):
        payload[field] = request[field]
    if "model_code" in payload:
        payload["model_code"] = request["model_code"]
    return payload


class ContractV4ResponseValidator:
    """Narrow validator used until the owner Contract 4.0 commit is merged."""

    allowed_fallback_reasons = {
        "RUNTIME_PRODUCT_NOT_APPROVED",
        "NO_EVIDENCE",
        "MCP_TOOL_FAILURE",
        "OUTPUT_SCHEMA_INVALID",
        "UNSPECIFIED_FALLBACK",
    }

    def validate_success_response(self, payload: dict) -> None:
        assert isinstance(payload.get("model_code"), str)
        reason = payload.get("fallback_reason_code")
        if payload["status"] == "FALLBACK":
            assert reason in self.allowed_fallback_reasons
        else:
            assert reason is None


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


def test_success_mapper_rejects_contract_v4_model_code_mismatch():
    request = request_payload()
    response = success_payload(request)
    response.update(
        {
            "model_code": "WPUIAC606SNW",
            "fallback_reason_code": None,
        }
    )

    with pytest.raises(AIIdentifierMismatchError) as exc_info:
        map_success_response(
            response,
            expected_request=request,
            validator=ContractV4ResponseValidator(),
        )

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
            "failure_stage": "RETRIEVING",
            "evidence_references": [],
        }
    )
    if "fallback_reason_code" in no_evidence_payload:
        no_evidence_payload["fallback_reason_code"] = "NO_EVIDENCE"
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


def test_success_mapper_allows_missing_fields_when_no_followup_is_needed():
    request = request_payload()
    response = success_payload(request)
    response["missing_fields"] = [
        {
            "field_name": "occurrence_time",
            "importance": "medium",
            "reason": "증상이 시작된 시점을 확인하면 도움이 됩니다.",
        }
    ]
    response["followup_questions"] = []

    result = map_success_response(response, expected_request=request)

    assert result.event_candidate == "SAFE_GUIDANCE_READY"


def test_success_mapper_accepts_approved_hot_water_heater_partial_stop():
    request = request_payload()
    response = danger_payload(request)
    response["safety_assessment"]["matched_safety_rule_ids"] = [
        "SAFETY-HOT-WATER-HEATER-001"
    ]
    response["usage_guidance"] = {
        "guidance_status": "PARTIAL_STOP",
        "message": "온수 기능 사용을 중단하고 상담을 연결합니다.",
        "restricted_functions": ["온수 출수 및 음용 중지"],
        "next_actions": [
            "온수 기능 사용과 온수 음용을 중단하세요.",
            "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
        ],
    }

    result = map_success_response(response, expected_request=request)

    assert result.event_candidate == "DANGER_DETECTED"
    assert result.usage_guidance_status == "PARTIAL_STOP"


def test_success_mapper_rejects_unapproved_partial_stop_guidance_content():
    request = request_payload()
    response = danger_payload(request)
    response["safety_assessment"]["matched_safety_rule_ids"] = [
        "SAFETY-HOT-WATER-HEATER-001"
    ]
    response["usage_guidance"] = {
        "guidance_status": "PARTIAL_STOP",
        "message": "온수 기능 사용을 중단하고 상담을 연결합니다.",
        "restricted_functions": [],
        "next_actions": ["임의 조치"],
    }

    with pytest.raises(AIResponseValidationError):
        map_success_response(response, expected_request=request)


def test_success_mapper_requires_total_stop_for_mixed_danger_rules():
    request = request_payload()
    response = danger_payload(request)
    response["safety_assessment"]["matched_safety_rule_ids"].append(
        "SAFETY-HOT-WATER-HEATER-001"
    )

    result = map_success_response(response, expected_request=request)

    assert result.event_candidate == "DANGER_DETECTED"
    assert result.usage_guidance_status == "TOTAL_STOP"

    response["usage_guidance"]["guidance_status"] = "PARTIAL_STOP"
    with pytest.raises(AIResponseValidationError):
        map_success_response(response, expected_request=request)


def test_success_mapper_uses_reason_not_stage_for_product_validation_event():
    request = request_payload()
    response = success_payload(request)
    response.update(
        {
            "model_code": request["model_code"],
            "status": "FALLBACK",
            "fallback_reason_code": "RUNTIME_PRODUCT_NOT_APPROVED",
            "failure_stage": "VALIDATING",
            "evidence_references": [],
        }
    )
    response["safety_assessment"]["requires_consultation"] = True
    response["usage_guidance"][
        "guidance_status"
    ] = "PENDING_CONSULTATION"

    result = map_success_response(
        response,
        expected_request=request,
        validator=ContractV4ResponseValidator(),
    )

    assert result.event_candidate == "PRODUCT_VALIDATION_FAILED"
    assert result.is_product_validation_failed is True
    assert result.is_no_evidence is False


def test_success_mapper_routes_output_schema_fallback_to_consultation():
    request = request_payload()
    response = success_payload(request)
    response.update(
        {
            "model_code": request["model_code"],
            "status": "FALLBACK",
            "fallback_reason_code": "OUTPUT_SCHEMA_INVALID",
            "failure_stage": "VALIDATING",
            "evidence_references": [],
        }
    )
    response["safety_assessment"]["requires_consultation"] = True
    response["usage_guidance"][
        "guidance_status"
    ] = "PENDING_CONSULTATION"

    result = map_success_response(
        response,
        expected_request=request,
        validator=ContractV4ResponseValidator(),
    )

    assert result.event_candidate == "AI_CONSULTATION_REQUIRED"
    assert result.is_product_validation_failed is False


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
