from types import SimpleNamespace
from uuid import UUID

from ai.app.orchestration.handoff import (
    ConsultationHandoffAgent,
    ConsultationHandoffInput,
    HandoffContextSynthesis,
    HandoffEvidence,
    HandoffQuestionnaireAnswer,
)


def _input() -> ConsultationHandoffInput:
    return ConsultationHandoffInput(
        inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b201"),
        correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e001"),
        ai_request_id="ai-req-handoff-001",
        model_code="WPU-IAC425",
        product_family="ICE_WATER_PURIFIER",
        symptom_summary="얼음이 나오지 않음",
        questionnaire_answers=[
            HandoffQuestionnaireAnswer(field_name="contact", answer="010-1234-5678")
        ],
        proposed_self_help_actions=["아이스룸 상태 확인"],
        evidence=[
            HandoffEvidence(
                chunk_id="iac425-ice-001",
                document_title="WPU-IAC425 공식 매뉴얼",
                page=31,
                summary="아이스룸 관련 공식 근거",
            )
        ],
        safety_level="general",
        safety_requires_consultation=False,
        safety_notes=[],
        escalation_reason="NO_EVIDENCE after retry",
        consultant_priority_checks=["얼음 토출 상태 확인"],
    )


def test_handoff_preserves_exact_model_and_source_coverage():
    result = ConsultationHandoffAgent().run(_input())
    assert result.model_code == "WPU-IAC425"
    assert result.source_chunk_ids == ["iac425-ice-001"]
    assert result.customer_symptom_summary == "얼음이 나오지 않음"
    assert result.evidence[0].summary == "아이스룸 관련 공식 근거"


def test_handoff_redacts_contact_information_without_generating_new_fact():
    source = _input()
    result = ConsultationHandoffAgent().run(source)
    assert result.questionnaire_answers[0].answer == "[REDACTED_PHONE]"
    assert "진단" not in result.customer_symptom_summary
    assert result.consultant_priority_checks == source.consultant_priority_checks


def test_handoff_attaches_internal_context_synthesis():
    synthesis = HandoffContextSynthesis(
        status="FALLBACK",
        routing_reason="HARNESS_ESCALATE",
        brief={"summary": "상담사 내부 맥락"},
        fallback_reason="CONFIGURATION",
        should_use_deterministic_handoff=True,
        provider_called=False,
        model_name=None,
        prompt_version="consultation_summary/v1",
        tokens_used=None,
        latency_ms=None,
    )

    result = ConsultationHandoffAgent().run(
        _input(),
        context_synthesis=synthesis,
    )

    assert result.context_synthesis == synthesis
    assert result.customer_symptom_summary == "얼음이 나오지 않음"


def test_handoff_input_reads_answer_text_and_actual_actions_not_future_guidance():
    ctx = SimpleNamespace(
        trace_context=SimpleNamespace(
            inquiry_id=UUID("018f2f9b-7c30-7981-b541-1a987c88b201"),
            correlation_id=UUID("018f2f9b-7c30-7981-b541-1a987c88e001"),
            ai_request_id="ai-req-handoff-context-001",
        ),
        model_code="WPU-IAC425",
        structured_symptom=SimpleNamespace(
            symptom_type="얼음이 나오지 않음",
            occurrence_time=None,
            target_water_type=None,
            occurrence_condition=None,
            error_code=None,
            accompanying_symptoms=[],
            actions_taken=["고객이 이미 전원을 재부팅함"],
        ),
        previous_answers=[
            {
                "question_id": "followup-time",
                "answer_text": "오늘 아침부터",
            }
        ],
        evidence_references=[],
        safety_assessment=None,
        usage_guidance=SimpleNamespace(
            next_actions=["아직 수행하지 않은 필터 교체"]
        ),
        missing_fields=[],
    )

    result = ConsultationHandoffInput.from_pipeline_context(
        ctx=ctx,
        product_family="ICE_WATER_PURIFIER",
        escalation_reason="AI_PROCESSING_TIMEOUT",
        accepted_evidence_chunk_ids=[],
    )

    assert result.questionnaire_answers[0].answer == "오늘 아침부터"
    assert result.proposed_self_help_actions == ["고객이 이미 전원을 재부팅함"]
    assert "아직 수행하지 않은 필터 교체" not in result.model_dump_json()
    assert result.safety_level == "unknown"
    assert result.safety_requires_consultation is False
