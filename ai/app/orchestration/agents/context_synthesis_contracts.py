"""상담사 맥락 합성 Agent의 내부 입출력 계약.

공개 Backend 계약이나 현재 Multi-Agent Shared State에는 연결하지 않는다.
"""

from __future__ import annotations

from enum import Enum
import hashlib
import hmac
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...generation.consultation_summary.context_models import (
    CounselorContextBrief,
    EvidenceBriefFinding,
    SourcedBriefStatement,
)


BriefText = Annotated[str, Field(min_length=1, max_length=2000)]


class _ContextSynthesisContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        revalidate_instances="always",
        validate_assignment=True,
    )


class ContextRoutingReason(str, Enum):
    """합성 Agent 호출이 허용되는 최종 상담 분기."""

    PRE_SEND_HUMAN_REVIEW = "PRE_SEND_HUMAN_REVIEW"
    FAIL_CLOSED_CONSULTATION = "FAIL_CLOSED_CONSULTATION"
    DANGER_HANDOFF = "DANGER_HANDOFF"
    HARNESS_ESCALATE = "HARNESS_ESCALATE"


class ContextSynthesisStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FALLBACK = "FALLBACK"


class ContextSynthesisFallbackReason(str, Enum):
    CONFIGURATION = "CONFIGURATION"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    OUTPUT_INVALID = "OUTPUT_INVALID"
    REFUSED = "REFUSED"
    DANGER_BYPASS = "DANGER_BYPASS"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    INPUT_NOT_ELIGIBLE = "INPUT_NOT_ELIGIBLE"
    SAFETY_NOT_VERIFIED = "SAFETY_NOT_VERIFIED"
    RUNTIME_PRODUCT_NOT_APPROVED = "RUNTIME_PRODUCT_NOT_APPROVED"


class ContextSynthesisDiagnosticCode(str, Enum):
    """본문 없이 OUTPUT_INVALID의 고정된 실패 경계만 식별한다."""

    PROVIDER_OUTPUT_INVALID = "PROVIDER_OUTPUT_INVALID"
    PROVIDER_HTTP_REJECTED = "PROVIDER_HTTP_REJECTED"
    PROVIDER_RESPONSE_JSON_INVALID = "PROVIDER_RESPONSE_JSON_INVALID"
    PROVIDER_RESPONSE_INCOMPLETE = "PROVIDER_RESPONSE_INCOMPLETE"
    PROVIDER_OUTPUT_SHAPE_INVALID = "PROVIDER_OUTPUT_SHAPE_INVALID"
    PROVIDER_OUTPUT_COUNT_INVALID = "PROVIDER_OUTPUT_COUNT_INVALID"
    PROVIDER_SCHEMA_INVALID = "PROVIDER_SCHEMA_INVALID"
    INTERNAL_SOURCE_BINDING_INVALID = "INTERNAL_SOURCE_BINDING_INVALID"
    INTERNAL_OUTPUT_METADATA_INVALID = "INTERNAL_OUTPUT_METADATA_INVALID"


class ContextFact(_ContextSynthesisContract):
    field_name: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=1000)


class ContextQuestionnaireAnswer(_ContextSynthesisContract):
    field_name: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=1000)


class ContextSynthesisEvidence(_ContextSynthesisContract):
    chunk_id: str = Field(min_length=1, max_length=200)
    document_title: str = Field(min_length=1, max_length=500)
    page: int | None = Field(default=None, ge=1)
    summary: str = Field(min_length=1, max_length=4000)
    summary_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_summary_digest(self) -> "ContextSynthesisEvidence":
        expected = self.digest_summary(self.summary)
        if not hmac.compare_digest(self.summary_sha256, expected):
            raise ValueError("Evidence summary_sha256이 summary 본문과 일치하지 않습니다.")
        return self

    @classmethod
    def from_values(
        cls,
        *,
        chunk_id: str,
        document_title: str,
        page: int | None,
        summary: str,
    ) -> "ContextSynthesisEvidence":
        normalized_summary = summary.strip()
        return cls(
            chunk_id=chunk_id,
            document_title=document_title,
            page=page,
            summary=normalized_summary,
            summary_sha256=cls.digest_summary(normalized_summary),
        )

    @staticmethod
    def digest_summary(summary: str) -> str:
        return hashlib.sha256(summary.strip().encode("utf-8")).hexdigest()


class AcceptedEvidenceBinding(_ContextSynthesisContract):
    chunk_id: str = Field(min_length=1, max_length=200)
    summary_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ConsultationContextSynthesisInput(_ContextSynthesisContract):
    """고객 원문·Prompt·검색 점수 없이 합성에 필요한 구조화 사실만 보유한다."""

    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(min_length=1, max_length=100)
    state_version: int = Field(ge=1)
    model_code: str = Field(pattern=r"^[A-Z0-9-]{1,100}$")
    runtime_product_approved: bool
    product_family: Literal[
        "DIRECT_WATER_PURIFIER",
        "ICE_WATER_PURIFIER",
        "UNKNOWN",
    ]
    routing_reason: ContextRoutingReason
    symptom_facts: list[ContextFact] = Field(default_factory=list, max_length=30)
    questionnaire_answers: list[ContextQuestionnaireAnswer] = Field(
        default_factory=list,
        max_length=30,
    )
    attempted_actions: list[BriefText] = Field(default_factory=list, max_length=20)
    evidence: list[ContextSynthesisEvidence] = Field(default_factory=list, max_length=10)
    accepted_evidence_bindings: list[AcceptedEvidenceBinding] = Field(
        default_factory=list,
        max_length=10,
    )
    safety_level: Literal["general", "caution", "danger", "unknown"]
    safety_requires_consultation: bool
    matched_safety_rule_ids: list[
        Annotated[
            str,
            Field(pattern=r"^SAFETY-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}$"),
        ]
    ] = Field(
        default_factory=list,
        max_length=20,
    )
    safety_notes: list[BriefText] = Field(default_factory=list, max_length=20)
    safety_constraints: list[BriefText] = Field(default_factory=list, max_length=20)
    escalation_reason: str = Field(min_length=1, max_length=1000)
    unresolved_questions: list[BriefText] = Field(default_factory=list, max_length=30)
    consultant_priority_checks: list[BriefText] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_cross_field_invariants(self) -> "ConsultationContextSynthesisInput":
        chunk_ids = [item.chunk_id for item in self.evidence]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("합성 입력 Evidence chunk_id는 중복될 수 없습니다.")
        accepted_chunk_ids = [
            item.chunk_id for item in self.accepted_evidence_bindings
        ]
        if len(accepted_chunk_ids) != len(set(accepted_chunk_ids)):
            raise ValueError("승인 Evidence Binding의 chunk_id는 중복될 수 없습니다.")
        evidence_bindings = {
            item.chunk_id: item.summary_sha256 for item in self.evidence
        }
        accepted_bindings = {
            item.chunk_id: item.summary_sha256
            for item in self.accepted_evidence_bindings
        }
        if evidence_bindings != accepted_bindings:
            raise ValueError(
                "합성 Evidence 본문은 Harness 승인 chunk_id·summary_sha256과 정확히 일치해야 합니다."
            )
        if len(self.matched_safety_rule_ids) != len(
            set(self.matched_safety_rule_ids)
        ):
            raise ValueError("matched_safety_rule_ids는 중복될 수 없습니다.")
        is_danger = self.safety_level == "danger"
        is_danger_route = self.routing_reason == ContextRoutingReason.DANGER_HANDOFF
        if is_danger != is_danger_route:
            raise ValueError("danger Safety와 DANGER_HANDOFF 분기는 서로 일치해야 합니다.")
        if is_danger and not self.safety_requires_consultation:
            raise ValueError(
                "danger 상담 이관에는 Safety 상담 필요 true가 필요합니다."
            )
        if is_danger and not self.matched_safety_rule_ids:
            raise ValueError("danger 상담 이관에는 승인된 Safety Rule ID가 필요합니다.")
        return self

    @classmethod
    def from_pipeline_context(
        cls,
        *,
        ctx: Any,
        product_family: str,
        runtime_product_approved: bool,
        routing_reason: ContextRoutingReason,
        escalation_reason: str,
        accepted_evidence: list[Any],
    ) -> "ConsultationContextSynthesisInput":
        """호출자가 선별한 Evidence와 기존 Context로 독립 후보 입력을 만든다.

        이 factory의 digest는 본문 변조만 탐지한다. ``accepted_evidence``가 같은
        실행의 Harness 승인 산출물인지 확인하는 책임은 아직 연결되지 않은
        Harness 호출 경계에 있다.
        """

        symptom = getattr(ctx, "structured_symptom", None)
        symptom_facts: list[ContextFact] = []
        if symptom is not None:
            for field_name in (
                "symptom_type",
                "occurrence_time",
                "target_water_type",
                "occurrence_condition",
                "error_code",
            ):
                value = getattr(symptom, field_name, None)
                if value:
                    symptom_facts.append(
                        ContextFact(field_name=field_name, value=str(value))
                    )
            for value in getattr(symptom, "accompanying_symptoms", []) or []:
                symptom_facts.append(
                    ContextFact(field_name="accompanying_symptom", value=str(value))
                )
        if not symptom_facts:
            for value in getattr(ctx, "selected_symptoms", []) or []:
                symptom_facts.append(
                    ContextFact(field_name="selected_symptom", value=str(value))
                )

        answers: list[ContextQuestionnaireAnswer] = []
        for item in getattr(ctx, "previous_answers", []) or []:
            if not isinstance(item, dict):
                continue
            field_name = str(
                item.get("field_name")
                or item.get("target_field")
                or item.get("question_id")
                or "answer"
            )
            value = (
                item.get("answer_text")
                or item.get("answer")
                or item.get("value")
                or item.get("selected_option")
            )
            if value is not None and str(value).strip():
                answers.append(
                    ContextQuestionnaireAnswer(
                        field_name=field_name,
                        answer=str(value),
                    )
                )

        attempted_actions = list(
            getattr(symptom, "actions_taken", []) or []
        )
        evidence = [
            ContextSynthesisEvidence.from_values(
                chunk_id=item.chunk_id,
                document_title=item.document_title,
                page=item.page,
                summary=item.summary,
            )
            for item in accepted_evidence
        ]

        safety = getattr(ctx, "safety_assessment", None)
        safety_level = (
            getattr(getattr(safety, "risk_level", None), "value", None)
            or "unknown"
        )
        safety_notes = list(getattr(safety, "detected_risks", []) or [])
        safety_reason = getattr(safety, "safety_reason", None)
        if safety_reason:
            safety_notes.append(str(safety_reason))

        guidance = getattr(ctx, "usage_guidance", None)
        safety_constraints = list(
            getattr(guidance, "restricted_functions", []) or []
        )

        unresolved_questions: list[str] = []
        for item in getattr(ctx, "followup_questions", []) or []:
            question = getattr(item, "question_text", None)
            if question:
                unresolved_questions.append(str(question))
        priority_checks: list[str] = []
        for item in getattr(ctx, "missing_fields", []) or []:
            reason = getattr(item, "reason", None)
            if reason:
                priority_checks.append(str(reason))

        trace = ctx.trace_context
        return cls(
            inquiry_id=trace.inquiry_id,
            correlation_id=trace.correlation_id,
            ai_request_id=trace.ai_request_id,
            state_version=trace.state_version,
            model_code=ctx.model_code,
            runtime_product_approved=runtime_product_approved,
            product_family=product_family,
            routing_reason=routing_reason,
            symptom_facts=symptom_facts,
            questionnaire_answers=answers,
            attempted_actions=attempted_actions,
            evidence=evidence,
            accepted_evidence_bindings=[
                AcceptedEvidenceBinding(
                    chunk_id=item.chunk_id,
                    summary_sha256=item.summary_sha256,
                )
                for item in evidence
            ],
            safety_level=str(safety_level),
            safety_requires_consultation=bool(
                getattr(safety, "requires_consultation", False)
            ),
            matched_safety_rule_ids=list(
                getattr(safety, "matched_safety_rule_ids", []) or []
            ),
            safety_notes=safety_notes,
            safety_constraints=safety_constraints,
            escalation_reason=escalation_reason,
            unresolved_questions=unresolved_questions,
            consultant_priority_checks=priority_checks,
        )


class ConsultationContextSynthesisAgentOutput(_ContextSynthesisContract):
    """식별자와 분기 사유를 보존하는 Agent 내부 실행 결과."""

    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(min_length=1, max_length=100)
    state_version: int = Field(ge=1)
    model_code: str = Field(min_length=1, max_length=100)
    routing_reason: ContextRoutingReason
    status: ContextSynthesisStatus
    brief: CounselorContextBrief
    fallback_reason: ContextSynthesisFallbackReason | None = None
    diagnostic_code: ContextSynthesisDiagnosticCode | None = None
    should_use_deterministic_handoff: bool
    provider_called: bool
    retry_count: Literal[0] = 0
    model_name: str | None = Field(default=None, min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=100)
    tokens_used: int | None = Field(default=None, ge=0)
    latency_ms: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_status_boundary(self) -> "ConsultationContextSynthesisAgentOutput":
        if self.status == ContextSynthesisStatus.SUCCEEDED:
            if (
                self.fallback_reason is not None
                or self.diagnostic_code is not None
                or self.should_use_deterministic_handoff
            ):
                raise ValueError("합성 성공 결과에는 Fallback 표시를 둘 수 없습니다.")
            if not self.provider_called or self.model_name is None:
                raise ValueError("합성 성공 결과에는 Provider 실행 메타데이터가 필요합니다.")
        else:
            if self.fallback_reason is None or not self.should_use_deterministic_handoff:
                raise ValueError("합성 Fallback 결과에는 사유와 결정론적 이관 표시가 필요합니다.")
            if (
                self.fallback_reason == ContextSynthesisFallbackReason.OUTPUT_INVALID
                and self.diagnostic_code is None
            ):
                raise ValueError("OUTPUT_INVALID에는 비식별 세부 진단 코드가 필요합니다.")
            if (
                self.fallback_reason != ContextSynthesisFallbackReason.OUTPUT_INVALID
                and self.diagnostic_code is not None
            ):
                raise ValueError("OUTPUT_INVALID 이외의 Fallback에는 세부 진단 코드를 둘 수 없습니다.")
        return self
