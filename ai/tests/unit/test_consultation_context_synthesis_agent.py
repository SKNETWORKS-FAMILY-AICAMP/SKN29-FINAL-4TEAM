"""독립 상담 맥락 합성 Agent의 계약·출처·안전·Provider 경계 테스트."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from ai.app.generation.consultation_summary.context_models import (
    ConsultationContextSynthesisCandidate,
    ContextSourceGroup,
    ContextSourceKind,
)
from ai.app.generation.consultation_summary.context_synthesizer import (
    ConsultationContextSynthesizer,
)
from ai.app.integrations.llm import (
    ConsultationContextLLMResponse,
    LLMConfigurationError,
    LLMOutputValidationError,
    LLMProviderConnectionError,
    LLMProviderTimeoutError,
    LLMRefusalError,
    LLMUsage,
    OpenAIResponsesConsultationContextClient,
)
from ai.app.orchestration.agents import (
    AcceptedEvidenceBinding,
    ConsultationContextSynthesisAgent,
    ConsultationContextSynthesisInput,
    ContextFact,
    ContextQuestionnaireAnswer,
    ContextRoutingReason,
    ContextSynthesisEvidence,
    ContextSynthesisFallbackReason,
    ContextSynthesisStatus,
)
from ai.app.schemas import (
    EvidenceReference,
    FollowUpQuestion,
    MissingField,
    RiskLevel,
    SafetyAssessment,
    SafetyPriority,
    StructuredSymptom,
    TraceContext,
    UsageGuidance,
    UsageGuidanceStatus,
)


INQUIRY_ID = "018f2f9b-7c30-7981-b541-1a987c88b321"
CORRELATION_ID = "018f2f9b-7c30-7981-b541-1a987c88b421"


def synthesis_input(
    *,
    safety_level: str = "caution",
    include_evidence: bool = True,
    runtime_product_approved: bool = True,
    questionnaire_answers: list[ContextQuestionnaireAnswer] | None = None,
) -> ConsultationContextSynthesisInput:
    evidence = (
        [
            ContextSynthesisEvidence.from_values(
                chunk_id="RAG-WPUJAC104DWH-LOW-FLOW-001",
                document_title="WPU-JAC104D 사용설명서",
                page=38,
                summary="출수량 저하 시 원수 공급 상태 확인 항목이 있습니다.",
            )
        ]
        if include_evidence
        else []
    )
    return ConsultationContextSynthesisInput(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        ai_request_id="ai-context-synthesis-001",
        state_version=7,
        model_code="WPUJAC104DWH",
        runtime_product_approved=runtime_product_approved,
        product_family="DIRECT_WATER_PURIFIER",
        routing_reason=(
            ContextRoutingReason.DANGER_HANDOFF
            if safety_level == "danger"
            else ContextRoutingReason.FAIL_CLOSED_CONSULTATION
        ),
        symptom_facts=[
            ContextFact(field_name="symptom_type", value="출수량 저하"),
            ContextFact(field_name="target_water_type", value="냉수"),
        ],
        questionnaire_answers=questionnaire_answers
        or [
            ContextQuestionnaireAnswer(
                field_name="occurrence_time",
                answer="오늘부터",
            )
        ],
        attempted_actions=["원수 밸브 상태를 확인했으나 변화 없음"],
        evidence=evidence,
        accepted_evidence_bindings=[
            AcceptedEvidenceBinding(
                chunk_id=item.chunk_id,
                summary_sha256=item.summary_sha256,
            )
            for item in evidence
        ],
        safety_level=safety_level,
        safety_requires_consultation=True,
        matched_safety_rule_ids=(
            ["SAFETY-LEAK-ELECTRIC-001"] if safety_level == "danger" else []
        ),
        safety_notes=["상담 전 사용 상태 확인 필요"],
        safety_constraints=["냉수 기능 사용 보류"],
        escalation_reason="자동 안내 검증을 통과하지 못해 상담 검토가 필요함",
        unresolved_questions=["필터 교체 시점을 확인해 주세요"],
        consultant_priority_checks=["원수 공급 상태와 필터 이력을 확인"],
    )


def valid_candidate(request):
    by_kind = {
        kind: [source.source_id for source in request.sources if source.kind == kind]
        for kind in ContextSourceKind
    }
    issue_source_ids = (
        by_kind[ContextSourceKind.CUSTOMER_REPORTED]
        + by_kind[ContextSourceKind.QUESTIONNAIRE]
    )[:2] or by_kind[ContextSourceKind.ESCALATION][:1]
    return ConsultationContextSynthesisCandidate(
        issue_summary_source_ids=issue_source_ids,
        customer_reported_fact_ids=(
            by_kind[ContextSourceKind.CUSTOMER_REPORTED]
            + by_kind[ContextSourceKind.QUESTIONNAIRE]
        ),
        attempted_action_ids=by_kind[ContextSourceKind.ATTEMPTED_ACTION],
        unresolved_question_ids=by_kind[ContextSourceKind.UNRESOLVED],
        safety_constraint_ids=by_kind[ContextSourceKind.SAFETY],
        evidence_finding_source_groups=[
            ContextSourceGroup(source_ids=[source_id])
            for source_id in by_kind[ContextSourceKind.EVIDENCE]
        ],
        consultant_priority_check_ids=by_kind[ContextSourceKind.PRIORITY],
        uncertainty_source_groups=[
            ContextSourceGroup(source_ids=[source_id])
            for source_id in by_kind[ContextSourceKind.UNRESOLVED]
        ],
    )


class DynamicClient:
    def __init__(self, *, candidate_factory=valid_candidate, error=None):
        self.candidate_factory = candidate_factory
        self.error = error
        self.calls = 0
        self.requests = []
        self.timeouts = []

    def synthesize_context(self, request, *, timeout_seconds):
        self.calls += 1
        self.requests.append(request)
        self.timeouts.append(timeout_seconds)
        if self.error is not None:
            raise self.error
        return ConsultationContextLLMResponse(
            output=self.candidate_factory(request),
            model_name="gpt-4o-mini-2024-07-18",
            usage=LLMUsage(input_tokens=40, output_tokens=30, total_tokens=70),
            latency_ms=18.5,
        )


def test_context_synthesis_returns_explicit_sourced_brief_contract():
    client = DynamicClient()
    source = synthesis_input()

    result = ConsultationContextSynthesisAgent(llm_client=client).run(
        source,
        timeout_seconds=1.5,
    )

    assert result.status == ContextSynthesisStatus.SUCCEEDED
    assert result.fallback_reason is None
    assert result.should_use_deterministic_handoff is False
    assert result.provider_called is True
    assert result.retry_count == 0
    assert result.model_name == "gpt-4o-mini-2024-07-18"
    assert result.prompt_version == "consultation_summary/v2"
    assert result.tokens_used == 70
    assert result.inquiry_id == source.inquiry_id
    assert result.correlation_id == source.correlation_id
    assert result.ai_request_id == source.ai_request_id
    assert result.state_version == source.state_version
    assert result.model_code == source.model_code
    assert result.routing_reason == source.routing_reason
    assert result.brief.customer_reported_facts
    assert result.brief.attempted_actions_and_outcomes[0].text.endswith("변화 없음")
    assert result.brief.evidence_based_findings[0].source_chunk_ids == [
        "RAG-WPUJAC104DWH-LOW-FLOW-001"
    ]


def test_pipeline_context_reads_answer_text_and_actual_actions_not_future_guidance():
    trace = TraceContext(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
        ai_request_id="ai-context-from-pipeline",
        state_version=4,
    )
    ctx = SimpleNamespace(
        trace_context=trace,
        model_code="WPUJAC104DWH",
        selected_symptoms=[],
        structured_symptom=StructuredSymptom(
            symptom_type="출수량 저하",
            actions_taken=["고객이 이미 원수 밸브를 확인함"],
        ),
        previous_answers=[
            {
                "question_id": "followup-occurrence-time",
                "answer_text": "오늘 아침부터",
            }
        ],
        evidence_references=[],
        safety_assessment=SafetyAssessment(
            risk_level=RiskLevel.CAUTION,
            priority=SafetyPriority.CONSULTATION_RECOMMENDED,
            requires_consultation=True,
            matched_safety_rule_ids=[],
            detected_risks=[],
            safety_reason="상담 확인 필요",
        ),
        usage_guidance=UsageGuidance(
            guidance_status=UsageGuidanceStatus.PENDING_CONSULTATION,
            message="상담 연결",
            restricted_functions=["냉수 사용 보류"],
            next_actions=["아직 수행하지 않은 미래 행동"],
        ),
        followup_questions=[
            FollowUpQuestion(
                question_id="followup-filter",
                question_text="필터 교체 시점은 언제인가요?",
                target_field="filter_date",
            )
        ],
        missing_fields=[
            MissingField(
                field_name="filter_date",
                reason="필터 이력 확인 필요",
                importance="medium",
            )
        ],
    )

    result = ConsultationContextSynthesisInput.from_pipeline_context(
        ctx=ctx,
        product_family="DIRECT_WATER_PURIFIER",
        runtime_product_approved=True,
        routing_reason=ContextRoutingReason.FAIL_CLOSED_CONSULTATION,
        escalation_reason="안내 검증 실패",
        accepted_evidence=[],
    )

    assert result.questionnaire_answers[0].answer == "오늘 아침부터"
    assert result.attempted_actions == ["고객이 이미 원수 밸브를 확인함"]
    assert "아직 수행하지 않은 미래 행동" not in result.model_dump_json()
    assert result.safety_constraints == ["냉수 사용 보류"]
    assert result.unresolved_questions == ["필터 교체 시점은 언제인가요?"]


def test_phone_email_id_url_address_and_internal_fields_are_redacted():
    client = DynamicClient()
    source = synthesis_input(
        questionnaire_answers=[
            ContextQuestionnaireAnswer(
                field_name="occurrence_condition",
                answer=(
                    "010-1234-5678 customer@example.com 900101-1234567 "
                    "https://example.com 홍길동이 서울특별시 강남구 테헤란로 123 "
                    "AI_VECTOR_DSN postgresql://user:super-secret@10.0.0.1:5432/db"
                ),
            ),
            ContextQuestionnaireAnswer(
                field_name="other_condition",
                answer="홍길동",
            ),
            ContextQuestionnaireAnswer(
                field_name="other_condition_english",
                answer="John Doe",
            ),
            ContextQuestionnaireAnswer(
                field_name="other_condition_short_name",
                answer="이준",
            ),
            ContextQuestionnaireAnswer(
                field_name="customer_name",
                answer="홍길동",
            ),
        ]
    ).model_copy(
        update={
            "symptom_facts": [
                ContextFact(field_name="symptom_type", value="출수량 저하"),
                ContextFact(
                    field_name="symptom_type",
                    value="John Doe customer reported low flow",
                ),
            ],
            "safety_notes": [
                "홍길동 고객이 연락함",
                "AWS_SECRET_ACCESS_KEY opaque-credential-value",
            ],
            "safety_constraints": [
                "sk-proj-example-secret-value",
                "Bearer opaque-credential-value",
            ],
        }
    )

    result = ConsultationContextSynthesisAgent(llm_client=client).run(source)

    provider_json = client.requests[0].model_dump_json()
    output_json = result.brief.model_dump_json()
    for secret in (
        "010-1234-5678",
        "customer@example.com",
        "900101-1234567",
        "https://example.com",
        "서울특별시 강남구 테헤란로 123",
        "AI_VECTOR_DSN",
        "postgresql://user:super-secret@10.0.0.1:5432/db",
        "super-secret",
        "10.0.0.1",
        "sk-proj-example-secret-value",
        "John Doe",
        "opaque-credential-value",
        "AWS_SECRET_ACCESS_KEY",
        "Bearer",
        "홍길동",
        "이준",
    ):
        assert secret not in provider_json
        assert secret not in output_json
    assert "[REDACTED_PHONE]" in output_json
    assert "[REDACTED_SENSITIVE]" in output_json
    assert all(
        item.kind
        not in {ContextSourceKind.QUESTIONNAIRE, ContextSourceKind.ATTEMPTED_ACTION}
        for item in client.requests[0].sources
    )
    assert "inquiry_id" not in provider_json
    assert "RAG-WPUJAC104DWH-LOW-FLOW-001" not in provider_json


def test_unknown_source_id_falls_back_without_second_call():
    def unknown_source_candidate(request):
        candidate = valid_candidate(request)
        return candidate.model_copy(
            update={
                "issue_summary_source_ids": ["unknown-999"]
            }
        )

    client = DynamicClient(candidate_factory=unknown_source_candidate)
    result = ConsultationContextSynthesisAgent(llm_client=client).run(
        synthesis_input()
    )

    assert client.calls == 1
    assert result.status == ContextSynthesisStatus.FALLBACK
    assert result.fallback_reason == ContextSynthesisFallbackReason.OUTPUT_INVALID
    assert result.should_use_deterministic_handoff is True
    assert result.retry_count == 0
    assert result.brief.customer_reported_facts


def test_candidate_contract_rejects_free_generated_diagnosis_or_action_text():
    prepared = ConsultationContextSynthesizer().prepare(synthesis_input())
    assert prepared.request is not None
    payload = valid_candidate(prepared.request).model_dump(mode="json")
    payload["issue_summary"] = {
        "text": "고장이 확실하므로 필터를 직접 교체하세요",
        "source_ids": ["symptom-001"],
    }

    with pytest.raises(ValidationError):
        ConsultationContextSynthesisCandidate.model_validate(payload)


def test_non_evidence_source_cannot_be_grouped_as_evidence_finding():
    def invalid_group_candidate(request):
        candidate = valid_candidate(request)
        return candidate.model_copy(
            update={
                "evidence_finding_source_groups": [
                    ContextSourceGroup(source_ids=["symptom-001"])
                ]
            }
        )

    client = DynamicClient(candidate_factory=invalid_group_candidate)

    result = ConsultationContextSynthesisAgent(llm_client=client).run(
        synthesis_input()
    )

    assert result.status == ContextSynthesisStatus.FALLBACK
    assert result.fallback_reason == ContextSynthesisFallbackReason.OUTPUT_INVALID
    assert client.calls == 1


@pytest.mark.parametrize(
    ("error", "expected_reason"),
    [
        (
            LLMProviderTimeoutError("timeout"),
            ContextSynthesisFallbackReason.PROVIDER_TIMEOUT,
        ),
        (
            LLMProviderConnectionError("temporary"),
            ContextSynthesisFallbackReason.PROVIDER_UNAVAILABLE,
        ),
        (
            LLMConfigurationError("configuration"),
            ContextSynthesisFallbackReason.CONFIGURATION,
        ),
        (
            LLMOutputValidationError("schema"),
            ContextSynthesisFallbackReason.OUTPUT_INVALID,
        ),
        (
            LLMRefusalError("refused"),
            ContextSynthesisFallbackReason.REFUSED,
        ),
    ],
)
def test_provider_failure_is_explicit_and_never_retried(error, expected_reason):
    client = DynamicClient(error=error)

    result = ConsultationContextSynthesisAgent(llm_client=client).run(
        synthesis_input()
    )

    assert client.calls == 1
    assert result.status == ContextSynthesisStatus.FALLBACK
    assert result.fallback_reason == expected_reason
    assert result.provider_called is True
    assert result.retry_count == 0


def test_invalid_provider_response_metadata_uses_fallback():
    class InvalidMetadataClient(DynamicClient):
        def synthesize_context(self, request, *, timeout_seconds):
            self.calls += 1
            return ConsultationContextLLMResponse(
                output=valid_candidate(request),
                model_name="",
                usage=LLMUsage(total_tokens=1),
                latency_ms=1.0,
            )

    client = InvalidMetadataClient()
    result = ConsultationContextSynthesisAgent(llm_client=client).run(
        synthesis_input()
    )

    assert client.calls == 1
    assert result.status == ContextSynthesisStatus.FALLBACK
    assert result.fallback_reason == ContextSynthesisFallbackReason.OUTPUT_INVALID


def test_missing_client_returns_configuration_fallback():
    result = ConsultationContextSynthesisAgent().run(synthesis_input())

    assert result.status == ContextSynthesisStatus.FALLBACK
    assert result.fallback_reason == ContextSynthesisFallbackReason.CONFIGURATION
    assert result.provider_called is False
    assert result.brief.customer_reported_facts


def test_danger_bypasses_provider_and_preserves_safety_first():
    client = DynamicClient()

    result = ConsultationContextSynthesisAgent(llm_client=client).run(
        synthesis_input(safety_level="danger")
    )

    assert client.calls == 0
    assert result.status == ContextSynthesisStatus.FALLBACK
    assert result.fallback_reason == ContextSynthesisFallbackReason.DANGER_BYPASS
    assert result.provider_called is False
    assert result.routing_reason == ContextRoutingReason.DANGER_HANDOFF
    assert result.brief.safety_constraints[0].text == "위험도: danger"
    assert any(
        item.text == "SAFETY-LEAK-ELECTRIC-001"
        for item in result.brief.safety_constraints
    )
    assert next(iter(result.brief.model_dump())) == "safety_constraints"


def test_runtime_unapproved_product_bypasses_provider_and_keeps_handoff_brief():
    client = DynamicClient()

    result = ConsultationContextSynthesisAgent(llm_client=client).run(
        synthesis_input(runtime_product_approved=False)
    )

    assert client.calls == 0
    assert result.status == ContextSynthesisStatus.FALLBACK
    assert (
        result.fallback_reason
        == ContextSynthesisFallbackReason.RUNTIME_PRODUCT_NOT_APPROVED
    )
    assert result.provider_called is False
    assert result.should_use_deterministic_handoff is True
    assert result.brief.customer_reported_facts


@pytest.mark.parametrize(
    "updates",
    [
        {
            "routing_reason": ContextRoutingReason.DANGER_HANDOFF,
            "safety_level": "caution",
        },
        {
            "routing_reason": ContextRoutingReason.FAIL_CLOSED_CONSULTATION,
            "safety_level": "danger",
            "matched_safety_rule_ids": ["SAFETY-LEAK-ELECTRIC-001"],
        },
        {
            "routing_reason": ContextRoutingReason.DANGER_HANDOFF,
            "safety_level": "danger",
            "matched_safety_rule_ids": [],
        },
        {
            "routing_reason": ContextRoutingReason.DANGER_HANDOFF,
            "safety_level": "danger",
            "safety_requires_consultation": False,
            "matched_safety_rule_ids": ["SAFETY-LEAK-ELECTRIC-001"],
        },
    ],
)
def test_routing_and_safety_cross_field_mismatch_is_rejected(updates):
    payload = synthesis_input().model_dump(mode="python")
    payload.update(updates)

    with pytest.raises(ValidationError):
        ConsultationContextSynthesisInput.model_validate(payload)


def test_unknown_safety_bypasses_provider_without_coercion_to_caution():
    payload = synthesis_input(include_evidence=False).model_dump(mode="python")
    payload.update(
        {
            "routing_reason": ContextRoutingReason.HARNESS_ESCALATE,
            "safety_level": "unknown",
            "safety_requires_consultation": False,
        }
    )
    source = ConsultationContextSynthesisInput.model_validate(payload)
    client = DynamicClient()

    result = ConsultationContextSynthesisAgent(llm_client=client).run(source)

    assert client.calls == 0
    assert result.status == ContextSynthesisStatus.FALLBACK
    assert (
        result.fallback_reason
        == ContextSynthesisFallbackReason.SAFETY_NOT_VERIFIED
    )


def test_fail_closed_allows_safety_consultation_false():
    payload = synthesis_input().model_dump(mode="python")
    payload.update(
        {
            "routing_reason": ContextRoutingReason.FAIL_CLOSED_CONSULTATION,
            "safety_level": "general",
            "safety_requires_consultation": False,
            "matched_safety_rule_ids": [],
        }
    )

    source = ConsultationContextSynthesisInput.model_validate(payload)

    assert source.safety_requires_consultation is False
    assert source.routing_reason == ContextRoutingReason.FAIL_CLOSED_CONSULTATION


def test_pre_send_human_review_allows_safety_consultation_false():
    payload = synthesis_input().model_dump(mode="python")
    payload.update(
        {
            "routing_reason": ContextRoutingReason.PRE_SEND_HUMAN_REVIEW,
            "safety_requires_consultation": False,
        }
    )
    source = ConsultationContextSynthesisInput.model_validate(payload)
    client = DynamicClient()

    result = ConsultationContextSynthesisAgent(llm_client=client).run(source)

    assert client.calls == 1
    assert result.status == ContextSynthesisStatus.SUCCEEDED
    assert result.routing_reason == ContextRoutingReason.PRE_SEND_HUMAN_REVIEW


def test_no_evidence_produces_empty_findings_and_explicit_uncertainty():
    result = ConsultationContextSynthesisAgent().run(
        synthesis_input(include_evidence=False)
    )

    assert result.status == ContextSynthesisStatus.FALLBACK
    assert result.brief.evidence_based_findings == []
    assert any(
        "공식 근거가 없어" in note.text
        for note in result.brief.uncertainty_notes
    )


def test_maximum_valid_input_bypasses_provider_and_preserves_all_categories():
    source = synthesis_input(include_evidence=False).model_copy(
        update={
            "symptom_facts": [
                ContextFact(field_name=f"symptom_{index}", value=f"증상 {index}")
                for index in range(30)
            ],
            "questionnaire_answers": [
                ContextQuestionnaireAnswer(
                    field_name=f"answer_{index}",
                    answer=f"답변 {index}",
                )
                for index in range(30)
            ],
            "attempted_actions": [f"수행 조치 {index}" for index in range(20)],
            "matched_safety_rule_ids": [
                f"SAFETY-TEST-{index:03d}" for index in range(20)
            ],
            "safety_notes": [f"안전 참고 {index}" for index in range(20)],
            "safety_constraints": [f"사용 제한 {index}" for index in range(20)],
            "unresolved_questions": [
                f"미확인 질문 {index}" for index in range(30)
            ],
            "consultant_priority_checks": [
                f"우선 확인 {index}" for index in range(30)
            ],
        }
    )
    client = DynamicClient()

    result = ConsultationContextSynthesisAgent(llm_client=client).run(source)

    assert client.calls == 0
    assert result.status == ContextSynthesisStatus.FALLBACK
    assert result.fallback_reason == ContextSynthesisFallbackReason.INPUT_TOO_LARGE
    assert len(result.brief.customer_reported_facts) == 60
    assert len(result.brief.attempted_actions_and_outcomes) == 20
    assert len(result.brief.safety_constraints) == 62
    assert len(result.brief.unresolved_questions) == 30
    assert len(result.brief.consultant_priority_checks) == 30


def test_two_max_length_facts_fit_deterministic_issue_summary():
    payload = synthesis_input(include_evidence=False).model_dump(mode="python")
    payload["symptom_facts"] = [
        {"field_name": "fact_a", "value": "가" * 1000},
        {"field_name": "fact_b", "value": "나" * 1000},
    ]
    source = ConsultationContextSynthesisInput.model_validate(payload)

    result = ConsultationContextSynthesisAgent().run(source)

    assert result.status == ContextSynthesisStatus.FALLBACK
    assert len(result.brief.issue_summary.text) <= 2000
    assert result.brief.issue_summary.source_ids[:2] == [
        "symptom-001",
        "symptom-002",
    ]


def test_sixty_two_safety_sources_fit_success_contract_when_total_is_bounded():
    payload = synthesis_input(include_evidence=False).model_dump(mode="python")
    payload.update(
        {
            "matched_safety_rule_ids": [
                f"SAFETY-TEST-{index:03d}" for index in range(20)
            ],
            "safety_notes": [f"안전 참고 {index}" for index in range(20)],
            "safety_constraints": [f"사용 제한 {index}" for index in range(20)],
        }
    )
    source = ConsultationContextSynthesisInput.model_validate(payload)
    client = DynamicClient()

    result = ConsultationContextSynthesisAgent(llm_client=client).run(source)

    assert client.calls == 1
    assert result.status == ContextSynthesisStatus.SUCCEEDED
    assert len(result.brief.safety_constraints) == 62


def test_duplicate_evidence_ids_are_rejected_before_provider():
    first = ContextSynthesisEvidence.from_values(
        chunk_id="duplicate-chunk",
        document_title="설명서",
        page=None,
        summary="근거 A",
    )
    mutated = synthesis_input().model_copy(
        update={
            "evidence": [first, first],
            "accepted_evidence_bindings": [
                AcceptedEvidenceBinding(
                    chunk_id="duplicate-chunk",
                    summary_sha256=first.summary_sha256,
                )
            ],
        }
    )

    with pytest.raises(ValidationError, match="중복"):
        ConsultationContextSynthesisAgent(
            llm_client=DynamicClient()
        ).run(mutated)


def test_rejected_evidence_cannot_enter_direct_input_contract():
    payload = synthesis_input().model_dump(mode="json")
    payload["accepted_evidence_bindings"] = []

    with pytest.raises(ValidationError, match="Harness"):
        ConsultationContextSynthesisInput.model_validate(payload)


def test_accepted_evidence_binding_rejects_summary_body_tamper():
    payload = synthesis_input().model_dump(mode="json")
    payload["evidence"][0]["summary"] = "승인 후 바뀐 근거 본문"

    with pytest.raises(ValidationError, match="summary_sha256"):
        ConsultationContextSynthesisInput.model_validate(payload)


def test_ambiguous_official_evidence_term_is_preserved_but_never_sent_to_provider():
    evidence = ContextSynthesisEvidence.from_values(
        chunk_id="RAG-DOMAIN-TEST-001",
        document_title="승인 근거",
        page=1,
        summary="정수기",
    )
    payload = synthesis_input().model_dump(mode="python")
    payload["evidence"] = [evidence.model_dump(mode="python")]
    payload["accepted_evidence_bindings"] = [
        {
            "chunk_id": evidence.chunk_id,
            "summary_sha256": evidence.summary_sha256,
        }
    ]
    source = ConsultationContextSynthesisInput.model_validate(payload)
    client = DynamicClient()

    result = ConsultationContextSynthesisAgent(llm_client=client).run(source)

    assert result.status == ContextSynthesisStatus.SUCCEEDED
    provider_json = client.requests[0].model_dump_json()
    output_json = result.brief.model_dump_json()
    assert "정수기" not in provider_json
    assert "정수기" in output_json
    assert all(
        item.kind != ContextSourceKind.EVIDENCE
        for item in client.requests[0].sources
    )


def test_ambiguous_domain_terms_are_not_removed_from_safety_or_evidence():
    evidence = [
        ContextSynthesisEvidence.from_values(
            chunk_id=f"RAG-DOMAIN-TERM-{index:03d}",
            document_title="공식 근거",
            page=index,
            summary=value,
        )
        for index, value in enumerate(
            ["정수기", "안전성", "이상함", "Cold Water"],
            start=1,
        )
    ]
    payload = synthesis_input().model_dump(mode="python")
    payload["evidence"] = [item.model_dump(mode="python") for item in evidence]
    payload["accepted_evidence_bindings"] = [
        {
            "chunk_id": item.chunk_id,
            "summary_sha256": item.summary_sha256,
        }
        for item in evidence
    ]
    payload["safety_notes"] = [
        "고장",
        "이상",
        "정상",
        "안전",
        "정수기",
        "안전성",
        "이상함",
        "Cold Water",
    ]
    source = ConsultationContextSynthesisInput.model_validate(payload)

    prepared = ConsultationContextSynthesizer().prepare(source)
    safety_texts = [
        item.text for item in prepared.deterministic_brief.safety_constraints
    ]

    expected_terms = [
        "고장",
        "이상",
        "정상",
        "안전",
        "정수기",
        "안전성",
        "이상함",
        "Cold Water",
    ]
    assert all(value in safety_texts for value in expected_terms)
    assert [
        item.text for item in prepared.deterministic_brief.evidence_based_findings
    ] == ["정수기", "안전성", "이상함", "Cold Water"]


def test_product_family_is_closed_to_current_service_scope():
    payload = synthesis_input().model_dump(mode="json")
    payload["product_family"] = "홍길동"

    with pytest.raises(ValidationError):
        ConsultationContextSynthesisInput.model_validate(payload)


@pytest.mark.parametrize(
    "product_family",
    ["DIRECT_WATER_PURIFIER", "ICE_WATER_PURIFIER", "UNKNOWN"],
)
def test_product_family_accepts_existing_harness_enum_values(product_family):
    payload = synthesis_input().model_dump(mode="json")
    payload["product_family"] = product_family

    result = ConsultationContextSynthesisInput.model_validate(payload)

    assert result.product_family == product_family


def test_from_pipeline_context_copies_only_caller_selected_evidence():
    source = synthesis_input()
    accepted = source.evidence[0]
    rejected = EvidenceReference(
        chunk_id="REJECTED-WRONG-PRODUCT",
        document_title="다른 제품 설명서",
        summary="다른 제품 근거",
    )
    ctx = SimpleNamespace(
        trace_context=TraceContext(
            inquiry_id=source.inquiry_id,
            correlation_id=source.correlation_id,
            ai_request_id=source.ai_request_id,
            state_version=source.state_version,
        ),
        model_code=source.model_code,
        selected_symptoms=[],
        structured_symptom=StructuredSymptom(symptom_type="출수량 저하"),
        previous_answers=[],
        evidence_references=[
            EvidenceReference(
                **accepted.model_dump(exclude={"summary_sha256"})
            ),
            rejected,
        ],
        safety_assessment=SafetyAssessment(
            risk_level=RiskLevel.CAUTION,
            priority=SafetyPriority.CONSULTATION_RECOMMENDED,
            requires_consultation=True,
            matched_safety_rule_ids=[],
            detected_risks=[],
            safety_reason="상담 확인 필요",
        ),
        usage_guidance=UsageGuidance(
            guidance_status=UsageGuidanceStatus.PENDING_CONSULTATION,
            message="상담 연결",
        ),
        followup_questions=[],
        missing_fields=[],
    )

    result = ConsultationContextSynthesisInput.from_pipeline_context(
        ctx=ctx,
        product_family="DIRECT_WATER_PURIFIER",
        runtime_product_approved=True,
        routing_reason=ContextRoutingReason.FAIL_CLOSED_CONSULTATION,
        escalation_reason="안내 검증 실패",
        accepted_evidence=[EvidenceReference(**accepted.model_dump(exclude={"summary_sha256"}))],
    )

    assert [item.chunk_id for item in result.evidence] == [accepted.chunk_id]
    assert rejected.chunk_id not in result.model_dump_json()


def test_auto_guidance_is_not_an_allowed_synthesis_routing_reason():
    payload = synthesis_input().model_dump(mode="json")
    payload["routing_reason"] = "AUTO_GUIDANCE"

    with pytest.raises(ValidationError):
        ConsultationContextSynthesisInput.model_validate(payload)


def test_output_contract_rejects_unknown_authority_fields():
    result = ConsultationContextSynthesisAgent().run(synthesis_input())
    payload = result.model_dump(mode="json")
    payload["diagnosis"] = "임의 진단"
    payload["target_state"] = "CONSULTATION_REQUIRED"

    with pytest.raises(ValidationError):
        type(result).model_validate(payload)


def test_llm_candidate_must_preserve_every_input_source_category():
    def dropped_fact_candidate(request):
        candidate = valid_candidate(request)
        return candidate.model_copy(update={"customer_reported_fact_ids": []})

    result = ConsultationContextSynthesisAgent(
        llm_client=DynamicClient(candidate_factory=dropped_fact_candidate)
    ).run(synthesis_input())

    assert result.status == ContextSynthesisStatus.FALLBACK
    assert result.fallback_reason == ContextSynthesisFallbackReason.OUTPUT_INVALID
    assert len(result.brief.customer_reported_facts) == 3


def test_conflicting_facts_and_missing_action_outcome_remain_uncertain():
    payload = synthesis_input().model_dump(mode="python")
    payload["symptom_facts"] = [
        {"field_name": "symptom_type", "value": "출수량 저하"},
        {"field_name": "symptom_type", "value": "온도 이상"},
    ]
    payload["attempted_actions"] = ["원수 밸브 확인"]
    source = ConsultationContextSynthesisInput.model_validate(payload)

    result = ConsultationContextSynthesisAgent(
        llm_client=DynamicClient()
    ).run(source)

    assert result.status == ContextSynthesisStatus.SUCCEEDED
    assert any("상충 정보" in note.text for note in result.brief.uncertainty_notes)
    assert any(
        "조치 결과 미확인" in note.text
        for note in result.brief.uncertainty_notes
    )


def test_openai_adapter_sends_only_redacted_sources_and_strict_schema():
    prepared = ConsultationContextSynthesizer().prepare(synthesis_input())
    assert prepared.request is not None
    output = valid_candidate(prepared.request)
    captured = {}

    def handler(request: httpx.Request):
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "model": "gpt-4o-mini-2024-07-18",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": output.model_dump_json(),
                            }
                        ],
                    }
                ],
                "usage": {
                    "input_tokens": 21,
                    "output_tokens": 17,
                    "total_tokens": 38,
                },
            },
        )

    client = OpenAIResponsesConsultationContextClient(
        api_key="test-only-key",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    response = client.synthesize_context(prepared.request, timeout_seconds=1.0)

    payload = captured["payload"]
    request_text = payload["input"][1]["content"]
    schema = payload["text"]["format"]["schema"]
    assert captured["authorization"] == "Bearer test-only-key"
    assert payload["store"] is False
    assert payload["temperature"] == 0.2
    assert payload["max_output_tokens"] == 800
    assert payload["text"]["format"]["strict"] is True
    assert set(schema["properties"]) == {
        "issue_summary_source_ids",
        "customer_reported_fact_ids",
        "attempted_action_ids",
        "unresolved_question_ids",
        "safety_constraint_ids",
        "evidence_finding_source_groups",
        "consultant_priority_check_ids",
        "uncertainty_source_groups",
    }
    assert "inquiry_id" not in request_text
    assert "correlation_id" not in request_text
    assert "ai_request_id" not in request_text
    assert "RAG-WPUJAC104DWH-LOW-FLOW-001" not in request_text
    assert response.output.issue_summary_source_ids
    assert response.usage.total_tokens == 38


def test_openai_adapter_rejects_refusal_and_invalid_schema():
    prepared = ConsultationContextSynthesizer().prepare(synthesis_input())
    assert prepared.request is not None

    refusal_client = OpenAIResponsesConsultationContextClient(
        api_key="test-only-key",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "status": "completed",
                        "output": [
                            {
                                "type": "message",
                                "content": [
                                    {"type": "refusal", "refusal": "cannot comply"}
                                ],
                            }
                        ],
                    },
                )
            )
        ),
    )
    with pytest.raises(LLMRefusalError):
        refusal_client.synthesize_context(prepared.request, timeout_seconds=1.0)

    invalid_client = OpenAIResponsesConsultationContextClient(
        api_key="test-only-key",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "status": "completed",
                        "output": [
                            {
                                "type": "message",
                                "content": [
                                    {"type": "output_text", "text": "{}"}
                                ],
                            }
                        ],
                    },
                )
            )
        ),
    )
    with pytest.raises(LLMOutputValidationError):
        invalid_client.synthesize_context(prepared.request, timeout_seconds=1.0)


def test_openai_adapter_classifies_authentication_failure_as_configuration():
    prepared = ConsultationContextSynthesizer().prepare(synthesis_input())
    assert prepared.request is not None
    client = OpenAIResponsesConsultationContextClient(
        api_key="test-only-key",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(401, json={"error": {}})
            )
        ),
    )

    with pytest.raises(LLMConfigurationError):
        client.synthesize_context(prepared.request, timeout_seconds=1.0)
