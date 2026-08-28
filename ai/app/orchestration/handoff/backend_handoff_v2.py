"""Strict external AI -> Backend Consultation Handoff 2.0 DTO mapping."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...generation.consultation_summary.context_models import (
    CounselorContextBrief,
    EvidenceBriefFinding,
    SourcedBriefStatement,
)
from .handoff_result import ConsultationHandoffResult, HandoffContextSynthesis


ExternalRoutingReason = Literal[
    "DANGER_HANDOFF",
    "FAIL_CLOSED_CONSULTATION",
    "HARNESS_ESCALATE",
]
ExternalSafetyLevel = Literal["general", "caution", "danger", "unknown"]
ExternalContextStatus = Literal["SUCCEEDED", "FALLBACK"]
ExternalFallbackReason = Literal[
    "CONFIGURATION",
    "PROVIDER_TIMEOUT",
    "PROVIDER_UNAVAILABLE",
    "OUTPUT_INVALID",
    "REFUSED",
    "DANGER_BYPASS",
    "INPUT_TOO_LARGE",
    "INPUT_NOT_ELIGIBLE",
    "SAFETY_NOT_VERIFIED",
    "RUNTIME_PRODUCT_NOT_APPROVED",
]


class _ExternalHandoffModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        revalidate_instances="always",
    )


class BackendHandoffQuestionnaireAnswer(_ExternalHandoffModel):
    field_name: str = Field(min_length=1, max_length=100)
    answer: str = Field(min_length=1, max_length=500)


class BackendHandoffEvidence(_ExternalHandoffModel):
    chunk_id: str = Field(min_length=1, max_length=200)
    document_title: str = Field(min_length=1, max_length=500)
    page: int | None = Field(ge=1)
    summary: str = Field(min_length=1, max_length=2000)


class BackendHandoffBriefStatement(_ExternalHandoffModel):
    text: str = Field(min_length=1, max_length=2000)


class BackendHandoffEvidenceFinding(BackendHandoffBriefStatement):
    source_chunk_ids: list[
        Annotated[str, Field(min_length=1, max_length=200)]
    ] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_unique_chunk_ids(self) -> "BackendHandoffEvidenceFinding":
        if len(self.source_chunk_ids) != len(set(self.source_chunk_ids)):
            raise ValueError("Evidence finding의 source_chunk_ids는 중복될 수 없습니다.")
        return self


class BackendHandoffContextBrief(_ExternalHandoffModel):
    safety_constraints: list[BackendHandoffBriefStatement] = Field(max_length=70)
    issue_summary: BackendHandoffBriefStatement
    customer_reported_facts: list[BackendHandoffBriefStatement] = Field(
        max_length=60
    )
    attempted_actions_and_outcomes: list[BackendHandoffBriefStatement] = Field(
        max_length=20
    )
    unresolved_questions: list[BackendHandoffBriefStatement] = Field(max_length=30)
    evidence_based_findings: list[BackendHandoffEvidenceFinding] = Field(
        max_length=10
    )
    consultant_priority_checks: list[BackendHandoffBriefStatement] = Field(
        max_length=30
    )
    uncertainty_notes: list[BackendHandoffBriefStatement] = Field(max_length=80)


class BackendHandoffContextSynthesis(_ExternalHandoffModel):
    status: ExternalContextStatus
    fallback_reason: ExternalFallbackReason | None
    brief: BackendHandoffContextBrief

    @model_validator(mode="after")
    def validate_status_and_fallback(self) -> "BackendHandoffContextSynthesis":
        if self.status == "SUCCEEDED" and self.fallback_reason is not None:
            raise ValueError("성공한 Context Synthesis에는 fallback_reason이 없습니다.")
        if self.status == "FALLBACK" and self.fallback_reason is None:
            raise ValueError("Fallback Context Synthesis에는 fallback_reason이 필요합니다.")
        return self


class ConsultationHandoffV2Request(_ExternalHandoffModel):
    """Public-safe 2.0 envelope built from the internal Handoff result."""

    schema_version: Literal["2.0.0"]
    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(min_length=1, max_length=100)
    state_version: int = Field(ge=1)
    model_code: str = Field(min_length=1, max_length=100)
    product_family: str = Field(min_length=1, max_length=100)
    routing_reason: ExternalRoutingReason
    customer_symptom_summary: str = Field(min_length=1, max_length=2000)
    questionnaire_answers: list[BackendHandoffQuestionnaireAnswer] = Field(
        max_length=30
    )
    self_help_actions: list[Annotated[str, Field(min_length=1, max_length=1000)]] = (
        Field(max_length=20)
    )
    evidence: list[BackendHandoffEvidence] = Field(max_length=10)
    safety_level: ExternalSafetyLevel
    safety_requires_consultation: bool
    safety_notes: list[Annotated[str, Field(min_length=1, max_length=1000)]] = (
        Field(max_length=20)
    )
    escalation_reason: str = Field(min_length=1, max_length=500)
    consultant_priority_checks: list[
        Annotated[str, Field(min_length=1, max_length=1000)]
    ] = Field(max_length=30)
    source_chunk_ids: list[
        Annotated[str, Field(min_length=1, max_length=200)]
    ] = Field(max_length=10)
    context_synthesis: BackendHandoffContextSynthesis | None

    @model_validator(mode="after")
    def validate_contract_invariants(self) -> "ConsultationHandoffV2Request":
        evidence_ids = [item.chunk_id for item in self.evidence]
        if self.source_chunk_ids != evidence_ids:
            raise ValueError(
                "source_chunk_ids는 evidence[].chunk_id와 같은 순서로 일치해야 합니다."
            )
        if len(self.source_chunk_ids) != len(set(self.source_chunk_ids)):
            raise ValueError("source_chunk_ids는 중복될 수 없습니다.")

        context = self.context_synthesis
        if context is None:
            return self

        if self.routing_reason == "DANGER_HANDOFF":
            if not (
                context.status == "FALLBACK"
                and context.fallback_reason == "DANGER_BYPASS"
            ):
                raise ValueError(
                    "Danger Handoff Context는 DANGER_BYPASS Fallback이어야 합니다."
                )
        elif context.fallback_reason == "DANGER_BYPASS":
            raise ValueError(
                "DANGER_BYPASS는 DANGER_HANDOFF에서만 사용할 수 있습니다."
            )

        nested_ids = {
            chunk_id
            for finding in context.brief.evidence_based_findings
            for chunk_id in finding.source_chunk_ids
        }
        if not nested_ids.issubset(set(self.source_chunk_ids)):
            raise ValueError(
                "Context Evidence ID는 최상위 source_chunk_ids의 부분집합이어야 합니다."
            )
        return self

    @classmethod
    def from_internal(
        cls,
        handoff: ConsultationHandoffResult,
    ) -> "ConsultationHandoffV2Request":
        if handoff.state_version is None:
            raise ValueError("Handoff 2.0에는 원래 요청의 state_version이 필요합니다.")
        if handoff.routing_reason is None:
            raise ValueError("Handoff 2.0에는 실제 routing_reason이 필요합니다.")

        context_synthesis = cls._map_optional_context(
            handoff.context_synthesis,
            routing_reason=handoff.routing_reason,
        )
        return cls(
            schema_version="2.0.0",
            inquiry_id=handoff.inquiry_id,
            correlation_id=handoff.correlation_id,
            ai_request_id=handoff.ai_request_id,
            state_version=handoff.state_version,
            model_code=handoff.model_code,
            product_family=handoff.product_family,
            routing_reason=handoff.routing_reason,
            customer_symptom_summary=handoff.customer_symptom_summary,
            questionnaire_answers=[
                BackendHandoffQuestionnaireAnswer(
                    field_name=item.field_name,
                    answer=item.answer,
                )
                for item in handoff.questionnaire_answers
            ],
            self_help_actions=list(handoff.self_help_actions),
            evidence=[
                BackendHandoffEvidence(
                    chunk_id=item.chunk_id,
                    document_title=item.document_title,
                    page=item.page,
                    summary=item.summary,
                )
                for item in handoff.evidence
            ],
            safety_level=handoff.safety_level,
            safety_requires_consultation=handoff.safety_requires_consultation,
            safety_notes=list(handoff.safety_notes),
            escalation_reason=handoff.escalation_reason,
            consultant_priority_checks=list(handoff.consultant_priority_checks),
            source_chunk_ids=list(handoff.source_chunk_ids),
            context_synthesis=context_synthesis,
        )

    @classmethod
    def _map_optional_context(
        cls,
        synthesis: HandoffContextSynthesis | None,
        *,
        routing_reason: str,
    ) -> BackendHandoffContextSynthesis | None:
        if synthesis is None:
            return None
        try:
            if synthesis.routing_reason != routing_reason:
                raise ValueError(
                    "Context routing_reason이 최상위 Handoff 분기와 다릅니다."
                )
            brief = CounselorContextBrief.model_validate(synthesis.brief)
            return BackendHandoffContextSynthesis(
                status=synthesis.status,
                fallback_reason=synthesis.fallback_reason,
                brief=BackendHandoffContextBrief(
                    safety_constraints=cls._map_statements(
                        brief.safety_constraints
                    ),
                    issue_summary=cls._map_statement(brief.issue_summary),
                    customer_reported_facts=cls._map_statements(
                        brief.customer_reported_facts
                    ),
                    attempted_actions_and_outcomes=cls._map_statements(
                        brief.attempted_actions_and_outcomes
                    ),
                    unresolved_questions=cls._map_statements(
                        brief.unresolved_questions
                    ),
                    evidence_based_findings=[
                        cls._map_evidence_finding(item)
                        for item in brief.evidence_based_findings
                    ],
                    consultant_priority_checks=cls._map_statements(
                        brief.consultant_priority_checks
                    ),
                    uncertainty_notes=cls._map_statements(
                        brief.uncertainty_notes
                    ),
                ),
            )
        except Exception:
            # The context is supplementary. Preserve the valid base Handoff and
            # expose no partially mapped or internal-only context fields.
            return None

    @staticmethod
    def _map_statement(
        statement: SourcedBriefStatement,
    ) -> BackendHandoffBriefStatement:
        return BackendHandoffBriefStatement(text=statement.text)

    @classmethod
    def _map_statements(
        cls,
        statements: list[SourcedBriefStatement],
    ) -> list[BackendHandoffBriefStatement]:
        return [cls._map_statement(item) for item in statements]

    @staticmethod
    def _map_evidence_finding(
        finding: EvidenceBriefFinding,
    ) -> BackendHandoffEvidenceFinding:
        return BackendHandoffEvidenceFinding(
            text=finding.text,
            source_chunk_ids=list(finding.source_chunk_ids),
        )
