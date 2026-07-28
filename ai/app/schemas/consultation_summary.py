"""상담용 AI 요약 Pydantic 데이터 모델."""

from typing import List
from pydantic import BaseModel, Field
from .common import RiskLevel
from .retrieval import EvidenceReference


class ConsultationSummaryResult(BaseModel):
    """상담사용 문의 요약 결과 모델"""
    inquiry_id: str = Field(..., description="공개 문의 식별자")
    symptom_summary: str = Field(..., description="고객 자연어 및 문진 답변 바탕의 증상 요약")
    customer_actions_taken: List[str] = Field(default_factory=list, description="고객이 이미 시도한 자가조치")
    risk_level: RiskLevel = Field(..., description="판정된 위험도")
    key_findings: List[str] = Field(default_factory=list, description="주요 점검 필요 항목 및 이상 소유 파악")
    recommended_consultant_actions: List[str] = Field(default_factory=list, description="상담사 권장 안내/행동")
    evidence_references: List[EvidenceReference] = Field(default_factory=list, description="참조 근거 목록")
