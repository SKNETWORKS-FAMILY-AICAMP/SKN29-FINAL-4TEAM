"""안전 평가 및 위험도 관련 Pydantic 데이터 모델."""

from typing import Annotated, List
from pydantic import Field, field_validator
from .common import ContractModel, RiskLevel, SafetyPriority


SafetyRuleId = Annotated[
    str,
    Field(pattern=r"^SAFETY-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}$"),
]


class SafetyAssessment(ContractModel):
    """위험도 및 안전 규칙 평가 모델"""
    risk_level: RiskLevel = Field(..., description="위험도 분류 (general, caution, danger)")
    priority: SafetyPriority = Field(..., description="문의 처리 우선순위")
    requires_consultation: bool = Field(..., description="상담 연결 필요 여부")
    matched_safety_rule_ids: List[SafetyRuleId] = Field(
        ...,
        description="명시적으로 일치한 안정 안전 규칙 ID 목록",
    )
    detected_risks: List[str] = Field(default_factory=list, description="감지된 위험 항목 목록 (누수, 감전, 화상 등)")
    safety_reason: str = Field(..., description="위험도 판정 사유 및 안전 규칙 적용 설명")

    @field_validator("matched_safety_rule_ids")
    @classmethod
    def validate_unique_rule_ids(cls, value: List[str]) -> List[str]:
        if len(value) != len(set(value)):
            raise ValueError("matched_safety_rule_ids는 중복될 수 없습니다.")
        return value
