"""기사 작업 결과 요약 계약 Pydantic 모델."""

from typing import List, Optional

from pydantic import Field

from .common import AiExecutionStatus, AiStage, ContractModel


class TechnicianReportRequest(ContractModel):
    inquiry_id: str
    correlation_id: str
    ai_request_id: str
    state_version: int = Field(..., ge=1)
    visit_id: str
    symptom_notes: str = Field(..., min_length=1, max_length=8000)
    action_notes: str = Field(..., min_length=1, max_length=8000)


class TechnicianReportResult(ContractModel):
    inquiry_id: str
    correlation_id: str
    ai_request_id: str
    state_version: int = Field(..., ge=1)
    status: AiExecutionStatus = AiExecutionStatus.SUCCEEDED
    failure_stage: Optional[AiStage] = None
    retry_count: int = Field(0, ge=0, le=1)
    visit_id: str
    tech_summary: str = Field(..., min_length=1, max_length=4000)
    parts_replaced: List[str] = Field(default_factory=list)
    suggested_final_status: str = Field(..., description="Backend Guard 검토용 제안 상태")
