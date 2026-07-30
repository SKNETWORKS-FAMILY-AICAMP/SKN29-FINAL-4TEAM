"""FastAPI HTTP 요청 DTO 모델."""

from typing import List
from pydantic import Field
from ...schemas.common import ContractModel


class PreviousAnswerItem(ContractModel):
    """이전 문진 답변 항목"""
    question_id: str = Field(..., description="질문 식별자")
    answer_text: str = Field(..., description="고객 답변 문구")


class SymptomAnalysisApiRequest(ContractModel):
    """증상 분석 요청 HTTP DTO (Backend -> AI)"""
    inquiry_id: str = Field(..., min_length=1, max_length=100, pattern=r".*[^0-9].*", description="공개 문의 식별자 (예: DEMO-INQ-002)")
    correlation_id: str = Field(..., min_length=1, max_length=100, description="전체 요청 추적 식별자")
    ai_request_id: str = Field(..., min_length=1, max_length=100, description="AI 호출 멱등 식별자")
    state_version: int = Field(..., ge=1, description="AI 호출 시작 시점 문의 상태 버전")
    raw_symptom: str = Field(..., min_length=1, max_length=4000, description="고객 최초 자연어 입력 증상")
    model_code: str = Field(..., min_length=1, max_length=100, description="문의 정수기 모델 코드 (예: WPUJAC104DWH)")
    selected_symptoms: List[str] = Field(default_factory=list, description="고객 선택 대표 증상 유형")
    previous_answers: List[PreviousAnswerItem] = Field(default_factory=list, description="이전 문진 답변 목록")
