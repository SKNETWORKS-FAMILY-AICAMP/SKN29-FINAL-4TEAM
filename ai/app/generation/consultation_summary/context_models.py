"""상담 맥락 합성 Provider에 허용되는 최소 데이터 계약."""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


ProviderSourceId = Annotated[
    str,
    Field(pattern=r"^[a-z][a-z0-9_]*-\d{3}$"),
]


class _ContextProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        revalidate_instances="always",
    )


class ContextSourceKind(str, Enum):
    CUSTOMER_REPORTED = "CUSTOMER_REPORTED"
    QUESTIONNAIRE = "QUESTIONNAIRE"
    ATTEMPTED_ACTION = "ATTEMPTED_ACTION"
    EVIDENCE = "EVIDENCE"
    SAFETY = "SAFETY"
    UNRESOLVED = "UNRESOLVED"
    PRIORITY = "PRIORITY"
    ESCALATION = "ESCALATION"


class ContextSource(_ContextProviderModel):
    """실제 Runtime 식별자를 제거한 Provider용 출처."""

    source_id: ProviderSourceId
    kind: ContextSourceKind
    label: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=2000)


class ConsultationContextSynthesisRequest(_ContextProviderModel):
    """추적 ID·청크 ID·검색 점수·고객 원문을 포함하지 않는다."""

    model_code: str = Field(min_length=1, max_length=100)
    product_family: str = Field(min_length=1, max_length=100)
    safety_level: str = Field(pattern=r"^(general|caution)$")
    sources: list[ContextSource] = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> "ConsultationContextSynthesisRequest":
        source_ids = [source.source_id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Provider source_id는 중복될 수 없습니다.")
        return self


class ContextSourceGroup(_ContextProviderModel):
    """LLM은 새 문장 대신 함께 묶을 Source ID만 선택한다."""

    source_ids: list[ProviderSourceId] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> "ContextSourceGroup":
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("Source Group의 source_ids는 중복될 수 없습니다.")
        return self


class ConsultationContextSynthesisCandidate(_ContextProviderModel):
    """LLM이 선택·정렬·그룹화할 수 있는 Source ID 전용 후보."""

    issue_summary_source_ids: list[ProviderSourceId] = Field(min_length=1, max_length=20)
    customer_reported_fact_ids: list[ProviderSourceId] = Field(max_length=60)
    attempted_action_ids: list[ProviderSourceId] = Field(max_length=20)
    unresolved_question_ids: list[ProviderSourceId] = Field(max_length=30)
    safety_constraint_ids: list[ProviderSourceId] = Field(max_length=70)
    evidence_finding_source_groups: list[ContextSourceGroup] = Field(max_length=10)
    consultant_priority_check_ids: list[ProviderSourceId] = Field(max_length=30)
    uncertainty_source_groups: list[ContextSourceGroup] = Field(max_length=20)


class SourcedBriefStatement(_ContextProviderModel):
    """상담 브리프에 보존되는 출처 추적 문장."""

    text: str = Field(min_length=1, max_length=2000)
    source_ids: list[ProviderSourceId] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> "SourcedBriefStatement":
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("Brief source_ids는 중복될 수 없습니다.")
        return self


class EvidenceBriefFinding(SourcedBriefStatement):
    source_chunk_ids: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        min_length=1,
        max_length=10,
    )


class CounselorContextBrief(_ContextProviderModel):
    """상담사의 확인을 돕는 내부 초안이며 진단·상태 전환 권한이 없다."""

    safety_constraints: list[SourcedBriefStatement] = Field(
        default_factory=list,
        max_length=70,
    )
    issue_summary: SourcedBriefStatement
    customer_reported_facts: list[SourcedBriefStatement] = Field(
        default_factory=list,
        max_length=60,
    )
    attempted_actions_and_outcomes: list[SourcedBriefStatement] = Field(
        default_factory=list,
        max_length=20,
    )
    unresolved_questions: list[SourcedBriefStatement] = Field(
        default_factory=list,
        max_length=30,
    )
    evidence_based_findings: list[EvidenceBriefFinding] = Field(
        default_factory=list,
        max_length=10,
    )
    consultant_priority_checks: list[SourcedBriefStatement] = Field(
        default_factory=list,
        max_length=30,
    )
    uncertainty_notes: list[SourcedBriefStatement] = Field(
        default_factory=list,
        max_length=80,
    )
