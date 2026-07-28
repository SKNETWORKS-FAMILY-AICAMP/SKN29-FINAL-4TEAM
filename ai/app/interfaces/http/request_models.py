"""FastAPI HTTP 요청 DTO 모델."""

from typing import List, Optional
from pydantic import BaseModel, Field


class PreviousAnswerItem(BaseModel):
    """이전 문진 답변 항목"""
    question_id: str = Field(..., description="질문 식별자")
    answer_text: str = Field(..., description="고객 답변 문구")


class SymptomAnalysisApiRequest(BaseModel):
    """증상 분석 요청 HTTP DTO (Backend -> AI)"""
    inquiry_id: str = Field(..., description="공개 문의 식별자 (예: DEMO-INQ-002)")
    correlation_id: str = Field(..., description="전체 요청 추적 식별자")
    raw_symptom: str = Field(..., description="고객 최초 자연어 입력 증상")
    model_code: str = Field(..., description="문의 정수기 모델 코드 (예: WPUJAC104DWH)")
    selected_symptoms: List[str] = Field(default_factory=list, description="고객 선택 대표 증상 유형")
    previous_answers: List[PreviousAnswerItem] = Field(default_factory=list, description="이전 문진 답변 목록")
