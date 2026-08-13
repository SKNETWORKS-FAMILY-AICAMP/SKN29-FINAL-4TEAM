"""AI Runtime Smoke가 성공 HTTP와 실제 결과 Gate를 구분하는지 검증한다."""

import pytest

from ai.scripts import smoke_test


def _analysis_body(*, status="SUCCEEDED", failure_stage=None, evidence=None):
    return {
        "inquiry_id": smoke_test.INQUIRY_ID,
        "correlation_id": smoke_test.CORRELATION_ID,
        "ai_request_id": smoke_test.AI_REQUEST_ID,
        "state_version": 1,
        "status": status,
        "failure_stage": failure_stage,
        "retry_count": 0,
        "structured_symptom": {
            "symptom_type": "출수량 저하",
            "occurrence_time": None,
            "target_water_type": "냉수",
            "occurrence_condition": None,
            "error_code": None,
            "accompanying_symptoms": [],
            "actions_taken": [],
        },
        "missing_fields": [],
        "followup_questions": [],
        "safety_assessment": {
            "risk_level": "caution",
            "priority": "consultation_recommended",
            "requires_consultation": False,
            "matched_safety_rule_ids": [],
            "detected_risks": [],
            "safety_reason": "점검 필요",
        },
        "evidence_references": evidence or [],
        "usage_guidance": {
            "guidance_status": "PARTIAL_STOP",
            "message": "출수량이 적으면 조리수 사용을 멈춘 뒤 출수합니다.",
            "restricted_functions": ["냉수 출수 확인 필요"],
            "next_actions": ["안내된 자가조치 단계별 점검 수행"],
        },
    }


def _verified_evidence():
    return {
        "chunk_id": "RAG-WPUJAC104DWH-LOW-FLOW-001",
        "document_title": "WPU-JAC104D 사용설명서",
        "page": 38,
        "page_refs": [38],
        "official_url": "https://example.invalid/manual",
        "verification_status": "official_verified",
        "summary": "공식 출수량 점검 근거",
    }


def _install_fake_http(monkeypatch, analysis_body):
    def fake_json_request(url, *, method="GET", payload=None):
        if url.endswith("/health"):
            return 200, {"status": "ok"}, {}
        return (
            200,
            analysis_body,
            {"X-Correlation-ID": smoke_test.CORRELATION_ID},
        )

    monkeypatch.setattr(smoke_test, "_json_request", fake_json_request)


def test_strict_local_smoke_requires_succeeded_and_verified_evidence(monkeypatch):
    _install_fake_http(
        monkeypatch,
        _analysis_body(evidence=[_verified_evidence()]),
    )

    result = smoke_test.run_smoke(
        "http://127.0.0.1:8001",
        "local",
        200,
        expected_result_status="SUCCEEDED",
        expected_failure_stage="NONE",
        expected_evidence_id="RAG-WPUJAC104DWH-LOW-FLOW-001",
        minimum_evidence_count=1,
        require_verified_evidence=True,
        expected_guidance_message=(
            "출수량이 적으면 조리수 사용을 멈춘 뒤 출수합니다."
        ),
    )

    assert result["analysis_result_status"] == "SUCCEEDED"
    assert result["analysis_failure_stage"] is None
    assert result["evidence_count"] == 1
    assert result["guidance_message_match"] == "PASS"


def test_strict_local_smoke_does_not_treat_fallback_200_as_pass(monkeypatch):
    _install_fake_http(
        monkeypatch,
        _analysis_body(status="FALLBACK", failure_stage="RETRIEVING"),
    )

    with pytest.raises(smoke_test.SmokeFailure, match="실행 상태 불일치"):
        smoke_test.run_smoke(
            "http://127.0.0.1:8001",
            "local",
            200,
            expected_result_status="SUCCEEDED",
        )


def test_strict_local_smoke_rejects_unverified_evidence(monkeypatch):
    evidence = _verified_evidence()
    evidence["verification_status"] = "unverified"
    _install_fake_http(monkeypatch, _analysis_body(evidence=[evidence]))

    with pytest.raises(smoke_test.SmokeFailure, match="계약 3.0.0 검증 실패"):
        smoke_test.run_smoke(
            "http://127.0.0.1:8001",
            "local",
            200,
            expected_result_status="SUCCEEDED",
            require_verified_evidence=True,
        )


def test_strict_local_smoke_requires_at_least_one_verified_evidence(monkeypatch):
    _install_fake_http(monkeypatch, _analysis_body())

    with pytest.raises(smoke_test.SmokeFailure, match="Evidence가 없습니다"):
        smoke_test.run_smoke(
            "http://127.0.0.1:8001",
            "local",
            200,
            expected_result_status="SUCCEEDED",
            require_verified_evidence=True,
        )


def test_strict_local_smoke_rejects_deterministic_or_stale_guidance(monkeypatch):
    _install_fake_http(
        monkeypatch,
        _analysis_body(evidence=[_verified_evidence()]),
    )

    with pytest.raises(smoke_test.SmokeFailure, match="LLM Guidance 문구 불일치"):
        smoke_test.run_smoke(
            "http://127.0.0.1:8001",
            "local",
            200,
            expected_result_status="SUCCEEDED",
            expected_guidance_message="실제 승인 Evidence 전체 원문",
        )


def test_strict_local_smoke_rejects_wrong_inquiry_echo(monkeypatch):
    body = _analysis_body(evidence=[_verified_evidence()])
    body["inquiry_id"] = "018f2f9b-7c30-7981-b541-1a987c88ffff"
    _install_fake_http(monkeypatch, body)

    with pytest.raises(smoke_test.SmokeFailure, match="inquiry_id Echo"):
        smoke_test.run_smoke(
            "http://127.0.0.1:8001",
            "local",
            200,
            expected_result_status="SUCCEEDED",
        )


def test_strict_local_smoke_rejects_schema_invalid_success_response(monkeypatch):
    body = _analysis_body(evidence=[_verified_evidence()])
    del body["retry_count"]
    _install_fake_http(monkeypatch, body)

    with pytest.raises(smoke_test.SmokeFailure, match="계약 3.0.0 검증 실패"):
        smoke_test.run_smoke(
            "http://127.0.0.1:8001",
            "local",
            200,
            expected_result_status="SUCCEEDED",
        )
