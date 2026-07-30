"""상담 요약 계약 Pydantic 모델."""

from typing import List, Optional

from pydantic import Field

from .common import AiExecutionStatus, AiStage, ContractModel


class ConsultationSummaryRequest(ContractModel):
    inquiry_id: str
    correlation_id: str
    ai_request_id: str
    state_version: int = Field(..., ge=1)
    customer_raw_text: str = Field(..., min_length=1, max_length=8000)
    agent_notes: Optional[str] = Field(None, max_length=8000)


class ConsultationSummaryResult(ContractModel):
    inquiry_id: str
    correlation_id: str
    ai_request_id: str
    state_version: int = Field(..., ge=1)
    status: AiExecutionStatus = AiExecutionStatus.SUCCEEDED
    failure_stage: Optional[AiStage] = None
    retry_count: int = Field(0, ge=0, le=1)
    summary_text: str = Field(..., min_length=1, max_length=4000)
    key_issues: List[str] = Field(default_factory=list)
    recommended_followup: str = Field(..., min_length=1, max_length=2000)
