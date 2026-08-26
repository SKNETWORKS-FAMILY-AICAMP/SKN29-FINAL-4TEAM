"""PM 승인 위험도별 응답 Routing과 Safety Rule 정합성 검증."""

import json
from pathlib import Path

import pytest

from ai.app.schemas import (
    SafetyAssessment,
    SymptomAnalysisResult,
    UsageGuidance,
)
from ai.app.validation.routing import (
    ResponseRoutingDisposition,
    ResponseRoutingPolicy,
)
from ai.app.validation.safety import SafetyRuleAlignmentValidator


CONTRACT_ROOT = Path("contracts/ai")


def _response(example_name: str) -> SymptomAnalysisResult:
    document = json.loads(
        (CONTRACT_ROOT / "examples/symptom-analysis" / example_name).read_text(
            encoding="utf-8"
        )
    )
    return SymptomAnalysisResult.model_validate(document["response"])


def test_existing_contract_fields_distinguish_four_terminal_routes():
    policy = ResponseRoutingPolicy()

    danger, danger_route = policy.apply(_response("danger-detected.json"))
    caution, caution_route = policy.apply(
        _response("caution-pre-send-human-review.json")
    )
    general, general_route = policy.apply(_response("general-guidance.json"))
    no_evidence, fallback_route = policy.apply(_response("no-evidence.json"))

    assert danger_route == ResponseRoutingDisposition.DANGER_HANDOFF
    assert caution_route == ResponseRoutingDisposition.PRE_SEND_HUMAN_REVIEW
    assert general_route == ResponseRoutingDisposition.AUTO_GUIDANCE
    assert fallback_route == ResponseRoutingDisposition.FAIL_CLOSED_CONSULTATION
    assert caution.status.value == "SUCCEEDED"
    assert general.status.value == "SUCCEEDED"
    assert no_evidence.status.value == "FALLBACK"


def test_invalid_general_success_is_downgraded_to_fail_closed():
    policy = ResponseRoutingPolicy()
    response = _response("general-guidance.json").model_copy(
        update={"evidence_references": []}
    )

    normalized, route = policy.apply(response)

    assert route == ResponseRoutingDisposition.FAIL_CLOSED_CONSULTATION
    assert normalized.status.value == "FALLBACK"
    assert normalized.fallback_reason_code.value == "OUTPUT_SCHEMA_INVALID"
    assert normalized.failure_stage.value == "VALIDATING"
    assert normalized.safety_assessment.requires_consultation is True
    assert normalized.usage_guidance.guidance_status.value == (
        "PENDING_CONSULTATION"
    )
    assert normalized.evidence_references == []


def test_public_evidence_ids_must_match_harness_accepted_set():
    response = _response("caution-pre-send-human-review.json")

    normalized, route = ResponseRoutingPolicy().apply(
        response,
        accepted_evidence_chunk_ids=["RAG-OTHER-MODEL-CHUNK"],
    )

    assert route == ResponseRoutingDisposition.FAIL_CLOSED_CONSULTATION
    assert normalized.status.value == "FALLBACK"
    assert normalized.fallback_reason_code.value == "OUTPUT_SCHEMA_INVALID"
    assert normalized.evidence_references == []


def test_hot_water_heater_rule_requires_exact_restrictions_and_actions():
    validator = SafetyRuleAlignmentValidator()
    safety = SafetyAssessment.model_validate(
        {
            "risk_level": "danger",
            "priority": "priority_consultation",
            "requires_consultation": True,
            "matched_safety_rule_ids": ["SAFETY-HOT-WATER-HEATER-001"],
            "detected_risks": ["온수 히터 이상"],
            "safety_reason": "승인 Safety Rule이 감지되었습니다.",
        }
    )
    guidance = UsageGuidance.model_validate(
        {
            "guidance_status": "PARTIAL_STOP",
            "message": "위험 신호가 감지되어 정수기 사용 제한 및 안전 조치가 필요합니다.",
            "restricted_functions": ["온수 출수 및 음용 중지"],
            "next_actions": [
                "온수 기능 사용과 온수 음용을 중단하세요.",
                "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
            ],
        }
    )

    validator.validate(safety, guidance)

    with pytest.raises(ValueError, match="제한 기능"):
        validator.validate(
            safety,
            guidance.model_copy(update={"restricted_functions": []}),
        )
    with pytest.raises(ValueError, match="다음 행동"):
        validator.validate(
            safety,
            guidance.model_copy(update={"next_actions": ["임의 조치"]}),
        )
    with pytest.raises(ValueError, match="승인되지 않은"):
        validator.validate(
            safety.model_copy(
                update={
                    "matched_safety_rule_ids": [
                        "SAFETY-HOT-WATER-HEATER-001",
                        "SAFETY-UNKNOWN-999",
                    ]
                }
            ),
            guidance,
        )
