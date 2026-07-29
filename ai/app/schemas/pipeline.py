"""AI 파이프라인 통합 응답 Pydantic 데이터 모델."""

from typing import List
from pydantic import BaseModel, Field
from .guidance import UsageGuidance
from .retrieval import EvidenceReference
from .safety import SafetyAssessment
from .symptom import FollowUpQuestion, MissingField, StructuredSymptom


class SymptomAnalysisResult(BaseModel):
    """증상 분석 통합 파이프라인 결과 모델"""
    inquiry_id: str = Field(..., description="Backend가 발급한 공개 문의 식별자")
    correlation_id: str = Field(..., description="요청 추적 식별자")
    structured_symptom: StructuredSymptom = Field(..., description="구조화 증상 결과")
    missing_fields: List[MissingField] = Field(default_factory=list, description="추가 파악이 필요한 누락 필드 목록")
    followup_questions: List[FollowUpQuestion] = Field(default_factory=list, description="생성된 추가 질문 목록")
    safety_assessment: SafetyAssessment = Field(..., description="위험도 및 안전 평가 결과")
    usage_guidance: UsageGuidance = Field(..., description="현재 정수기 사용 안내 상태 및 다음 행동")
    evidence_references: List[EvidenceReference] = Field(default_factory=list, description="공식 매뉴얼/FAQ 근거 참조 목록")
