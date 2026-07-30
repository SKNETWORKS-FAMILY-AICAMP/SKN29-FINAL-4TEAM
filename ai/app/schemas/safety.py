"""안전 평가 및 위험도 관련 Pydantic 데이터 모델."""

from typing import List
from pydantic import Field
from .common import ContractModel, RiskLevel


class SafetyAssessment(ContractModel):
    """위험도 및 안전 규칙 평가 모델"""
    risk_level: RiskLevel = Field(..., description="위험도 분류 (general, caution, danger)")
    priority: str = Field(..., description="문의 처리 우선순위 (general_guidance, consultation_recommended, priority_consultation)")
    requires_consultation: bool = Field(..., description="상담 연결 필요 여부")
    detected_risks: List[str] = Field(default_factory=list, description="감지된 위험 항목 목록 (누수, 감전, 화상 등)")
    safety_reason: str = Field(..., description="위험도 판정 사유 및 안전 규칙 적용 설명")
