"""증상 구조화 및 문진 관련 Pydantic 데이터 모델."""

from typing import List, Literal, Optional
from typing_extensions import Annotated
from pydantic import Field
from .common import ContractModel


class StructuredSymptom(ContractModel):
    """표준 구조화 증상 모델"""
    symptom_type: str = Field(..., description="증상 대표 유형 (출수량 저하, 물맛/냄새 이상, 누수, 온도 이상 등)")
    occurrence_time: Optional[str] = Field(None, description="증상 발생 시점")
    target_water_type: Optional[str] = Field(None, description="대상 출수 종류 (냉수, 온수, 정수, 전체)")
    occurrence_condition: Optional[str] = Field(None, description="발생 조건 및 특이사항")
    error_code: Optional[str] = Field(None, description="제품 디스플레이 오류 코드")
    accompanying_symptoms: List[str] = Field(default_factory=list, description="동반 증상 목록")
    actions_taken: List[str] = Field(default_factory=list, description="고객이 이미 수행한 조치 사항")


class MissingField(ContractModel):
    """누락 필드 정보"""
    field_name: str = Field(..., min_length=1, max_length=100, description="추가 확인이 필요한 누락 필드명")
    reason: str = Field(..., min_length=1, max_length=500, description="누락 판단 사유")
    importance: Literal["high", "medium", "low"] = Field(..., description="필드 중요도")


class FollowUpQuestion(ContractModel):
    """AI 추가 질문 모델"""
    question_id: str = Field(..., min_length=1, max_length=100, description="질문 식별자")
    question_text: str = Field(..., min_length=1, max_length=500, description="고객에게 제공할 추가 질문 문구")
    options: List[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list,
        max_length=10,
        description="선택지 답변 항목 (객관식 질문인 경우)",
    )
    target_field: str = Field(..., min_length=1, max_length=100, description="질문을 통해 확인하려는 목표 구조화 필드")
