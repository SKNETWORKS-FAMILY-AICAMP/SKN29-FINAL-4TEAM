"""3-Agent 내부 책임·Handoff 계약."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ...retrieval import RetrievalOutcome
from ...schemas import (
    EvidenceReference,
    FollowUpQuestion,
    MissingField,
    SafetyAssessment,
    StructuredSymptom,
    UsageGuidance,
)


class AgentRole(str, Enum):
    """Supervisor가 호출할 수 있는 고정 역할."""

    SUPERVISOR = "SUPERVISOR"
    SYMPTOM_ANALYSIS = "SYMPTOM_ANALYSIS"
    EVIDENCE_ANALYSIS = "EVIDENCE_ANALYSIS"
    CARE_DECISION = "CARE_DECISION"


class HandoffReason(str, Enum):
    """고객 원문 없이 역할 전환 이유만 남기는 코드."""

    START_ANALYSIS = "START_ANALYSIS"
    DANGER_PRIORITY = "DANGER_PRIORITY"
    RETRIEVAL_REQUIRED = "RETRIEVAL_REQUIRED"
    EVIDENCE_READY = "EVIDENCE_READY"
    MORE_INFORMATION_REQUIRED = "MORE_INFORMATION_REQUIRED"
    CUSTOMER_INPUT_PENDING = "CUSTOMER_INPUT_PENDING"
    NO_EVIDENCE = "NO_EVIDENCE"
    CARE_DECISION_READY = "CARE_DECISION_READY"


class _AgentContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentHandoff(_AgentContract):
    """내부 감사용 최소 Handoff 레코드."""

    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(min_length=1, max_length=100)
    state_version: int = Field(ge=1)
    from_agent: AgentRole
    to_agent: AgentRole
    reason_code: HandoffReason
    hop_count: int = Field(ge=1, le=8)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    latency_ms: float = Field(default=0.0, ge=0)
    status: Literal["SUCCEEDED"] = "SUCCEEDED"
    retry_count: int = Field(default=0, ge=0, le=1)


class SymptomAgentOutput(_AgentContract):
    """Symptom Analysis Agent가 소유하는 출력."""

    structured_symptom: StructuredSymptom
    safety_assessment: SafetyAssessment
    missing_fields: list[MissingField] = Field(default_factory=list)
    followup_questions: list[FollowUpQuestion] = Field(default_factory=list)
    clarification_needed: bool


class EvidenceAgentOutput(_AgentContract):
    """Evidence Analysis Agent가 소유하는 출력."""

    retrieval_outcome: RetrievalOutcome
    evidence_references: list[EvidenceReference] = Field(default_factory=list)
    evidence_sufficient: bool
    request_more_information: bool


class CareDecisionAgentOutput(_AgentContract):
    """Care Decision Agent가 소유하는 출력."""

    usage_guidance: UsageGuidance
    requires_consultation: bool
    awaiting_customer_input: bool


class MultiAgentRunMetadata(_AgentContract):
    """공개 응답에 포함하지 않는 Supervisor 실행 증거."""

    runtime_name: Literal["multi_agent"] = "multi_agent"
    hop_count: int = Field(ge=0, le=8)
    awaiting_customer_input: bool = False
    handoffs: list[AgentHandoff] = Field(default_factory=list)
