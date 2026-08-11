"""결정론적 상담 요약 Fallback 기준선 테스트."""

import json
from pathlib import Path

from ai.app.generation.consultation_summary import ConsultationSummaryGenerator
from ai.app.schemas import ConsultationSummaryRequest
from jsonschema import Draft202012Validator, FormatChecker


def _request(**overrides) -> ConsultationSummaryRequest:
    payload = {
        "inquiry_id": "018f2f9b-7c30-7981-b541-1a987c88b201",
        "correlation_id": "018f2f9b-7c30-7981-b541-1a987c88e001",
        "ai_request_id": "ai-req-summary-001",
        "state_version": 5,
        "customer_raw_text": "냉수가 2일 전부터 미지근하게 나옵니다.",
        "agent_notes": "전원 상태를 확인했고 고객은 방문 여부를 검토 중입니다.",
    }
    payload.update(overrides)
    return ConsultationSummaryRequest.model_validate(payload)


def test_summary_preserves_trace_and_only_uses_supplied_content():
    result = ConsultationSummaryGenerator().generate(_request())

    assert str(result.inquiry_id) == "018f2f9b-7c30-7981-b541-1a987c88b201"
    assert str(result.correlation_id) == "018f2f9b-7c30-7981-b541-1a987c88e001"
    assert result.ai_request_id == "ai-req-summary-001"
    assert result.state_version == 5
    assert result.status == "SUCCEEDED"
    assert result.failure_stage is None
    assert result.retry_count == 0
    assert "냉수가 2일 전부터 미지근하게 나옵니다." in result.summary_text
    assert "전원 상태를 확인했고 고객은 방문 여부를 검토 중입니다." in result.summary_text
    assert result.key_issues[0] == "온도 이상"
    schema = json.loads(
        Path("contracts/ai/responses/ConsultationSummaryResponse.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(
        result.model_dump(mode="json")
    )


def test_summary_prioritizes_danger_without_diagnosis_or_state_change():
    result = ConsultationSummaryGenerator().generate(
        _request(
            customer_raw_text="제품 아래로 물이 새고 전선 근처에서 타는 냄새가 납니다.",
            agent_notes=None,
        )
    )

    assert "안전 위험 신호" in result.summary_text
    assert "제품 하부 및 전원부 주변 누수" in result.key_issues
    assert "전기 냄새·연기·스파크·감전 위험" in result.key_issues
    assert result.recommended_followup.startswith("사용 제한 상태")
    assert "고장으로 확정" not in result.summary_text


def test_negated_danger_is_not_promoted_to_danger_summary():
    result = ConsultationSummaryGenerator().generate(
        _request(
            customer_raw_text="누수는 없고 냉수가 미지근합니다.",
            agent_notes=None,
        )
    )

    assert "안전 위험 신호" not in result.summary_text
    assert "제품 하부 및 전원부 주변 누수" not in result.key_issues
    assert result.key_issues[0] == "온도 이상"


def test_summary_output_respects_public_contract_lengths():
    raw_text = ("출수량이 줄었습니다. " * 350).strip()
    notes = ("상담사가 현상을 확인했습니다. " * 250).strip()
    result = ConsultationSummaryGenerator().generate(
        _request(customer_raw_text=raw_text, agent_notes=notes)
    )

    assert 1 <= len(result.summary_text) <= 4000
    assert result.summary_text.endswith("…")
    assert result.key_issues
    assert all(1 <= len(issue) <= 500 for issue in result.key_issues)
    assert 1 <= len(result.recommended_followup) <= 2000
