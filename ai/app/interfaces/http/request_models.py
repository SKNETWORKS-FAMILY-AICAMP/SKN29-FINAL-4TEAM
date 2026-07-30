"""FastAPI HTTP 요청 DTO 모델."""

from typing import Annotated, List
from uuid import UUID
from pydantic import Field
from ...schemas.common import ContractModel


SelectedSymptom = Annotated[str, Field(min_length=1, max_length=200)]


class PreviousAnswerItem(ContractModel):
    """이전 문진 답변 항목"""
    question_id: str = Field(..., min_length=1, max_length=100, description="질문 식별자")
    answer_text: str = Field(..., min_length=1, max_length=1000, description="고객 답변 문구")


class SymptomAnalysisApiRequest(ContractModel):
    """증상 분석 요청 HTTP DTO (Backend -> AI)"""
    inquiry_id: UUID = Field(..., description="Backend가 발급한 Public UUID")
    correlation_id: str = Field(..., min_length=1, max_length=100, description="전체 요청 추적 식별자")
    ai_request_id: str = Field(..., min_length=1, max_length=100, description="AI 호출 멱등 식별자")
    state_version: int = Field(..., ge=1, description="AI 호출 시작 시점 문의 상태 버전")
    raw_symptom: str = Field(..., min_length=1, max_length=4000, description="고객 최초 자연어 입력 증상")
    model_code: str = Field(..., min_length=1, max_length=100, description="문의 정수기 모델 코드 (예: WPUJAC104DWH)")
    selected_symptoms: List[SelectedSymptom] = Field(default_factory=list, max_length=30, description="고객 선택 대표 증상 유형")
    previous_answers: List[PreviousAnswerItem] = Field(default_factory=list, max_length=50, description="이전 문진 답변 목록")
