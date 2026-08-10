"""상담 요약 계약 Pydantic 모델."""

from typing import Annotated, List, Literal, Optional
from uuid import UUID

from pydantic import Field

from .common import AiExecutionStatus, AiStage, ContractModel


SummaryFailureStage = Literal[
    AiStage.GENERATING,
    AiStage.VALIDATING,
    AiStage.FAILED,
    AiStage.CANCELLED,
]
KeyIssue = Annotated[str, Field(min_length=1, max_length=500)]


class ConsultationSummaryRequest(ContractModel):
    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(..., min_length=1, max_length=100)
    state_version: int = Field(..., ge=1)
    customer_raw_text: str = Field(..., min_length=1, max_length=8000)
    agent_notes: Optional[str] = Field(None, max_length=8000)


class ConsultationSummaryResult(ContractModel):
    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(..., min_length=1, max_length=100)
    state_version: int = Field(..., ge=1)
    status: AiExecutionStatus = AiExecutionStatus.SUCCEEDED
    failure_stage: Optional[SummaryFailureStage] = None
    retry_count: int = Field(0, ge=0, le=1)
    summary_text: str = Field(..., min_length=1, max_length=4000)
    key_issues: List[KeyIssue] = Field(default_factory=list)
    recommended_followup: str = Field(..., min_length=1, max_length=2000)
