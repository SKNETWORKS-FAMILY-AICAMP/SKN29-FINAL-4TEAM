"""기사 작업 결과 요약 계약 Pydantic 모델."""

from typing import Annotated, List, Literal, Optional
from uuid import UUID

from pydantic import Field

from .common import AiExecutionStatus, AiStage, ContractModel


ReportFailureStage = Literal[
    AiStage.GENERATING,
    AiStage.VALIDATING,
    AiStage.FAILED,
    AiStage.CANCELLED,
]
PartName = Annotated[str, Field(min_length=1, max_length=500)]


class TechnicianReportRequest(ContractModel):
    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(..., min_length=1, max_length=100)
    state_version: int = Field(..., ge=1)
    visit_id: str = Field(..., min_length=1, max_length=100)
    symptom_notes: str = Field(..., min_length=1, max_length=8000)
    action_notes: str = Field(..., min_length=1, max_length=8000)


class TechnicianReportResult(ContractModel):
    inquiry_id: UUID
    correlation_id: UUID
    ai_request_id: str = Field(..., min_length=1, max_length=100)
    state_version: int = Field(..., ge=1)
    status: AiExecutionStatus = AiExecutionStatus.SUCCEEDED
    failure_stage: Optional[ReportFailureStage] = None
    retry_count: int = Field(0, ge=0, le=1)
    visit_id: str = Field(..., min_length=1, max_length=100)
    tech_summary: str = Field(..., min_length=1, max_length=4000)
    parts_replaced: List[PartName] = Field(default_factory=list)
    suggested_final_status: str = Field(..., min_length=1, max_length=100, description="Backend Guard 검토용 제안 상태")
