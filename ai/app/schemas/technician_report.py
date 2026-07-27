"""방문기사 사전 점검 리포트 Pydantic 데이터 모델."""

from typing import List
from pydantic import BaseModel, Field
from .common import RiskLevel
from .retrieval import EvidenceReference


class TechnicianReportResult(BaseModel):
    """방문기사 사전 점검 리포트 결과 모델"""
    inquiry_id: str = Field(..., description="공개 문의 식별자")
    product_info_summary: str = Field(..., description="제품 모델, 사용 연수, 케어 이력 요약")
    reported_symptom: str = Field(..., description="접수된 구조화 증상 및 발생 조건")
    risk_level: RiskLevel = Field(..., description="판정된 위험도")
    priority_check_items: List[str] = Field(default_factory=list, description="방문 시 우선 점검 항목 목록")
    suspected_causes: List[str] = Field(default_factory=list, description="추정 고장/점검 원인 후보")
    evidence_references: List[EvidenceReference] = Field(default_factory=list, description="참조 근거 목록")
