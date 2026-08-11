"""공식 근거가 없을 때 판단 보류·상담 전환 정책 적용."""

from ..schemas import (
    RiskLevel,
    SafetyAssessment,
    SafetyPriority,
    UsageGuidance,
    UsageGuidanceStatus,
)
from .rule_loader import SafetyRuleLoader


class NoEvidencePolicy:
    """근거가 없으면 자가조치 생성을 막고 상담 필요 응답을 만든다."""

    def __init__(self, rule_loader: SafetyRuleLoader | None = None):
        rules = (rule_loader or SafetyRuleLoader()).get_safety_rules()
        self._config = rules["no_evidence_policy"]

    def apply(self) -> UsageGuidance:
        return UsageGuidance(
            guidance_status=UsageGuidanceStatus(
                self._config["default_usage_guidance_status"]
            ),
            message=self._config["message"],
            restricted_functions=["근거 없는 자가조치 안내"],
            next_actions=["전문 상담사 연결을 요청해 주세요."],
        )

    def apply_to_assessment(
        self,
        assessment: SafetyAssessment,
    ) -> SafetyAssessment:
        """근거 없음 결과를 Backend NO_EVIDENCE 불변식에 맞게 정규화한다."""

        if assessment.risk_level == RiskLevel.DANGER:
            return assessment
        return assessment.model_copy(
            update={
                "risk_level": RiskLevel(self._config["default_risk_level"]),
                "priority": SafetyPriority(self._config["default_priority"]),
                "requires_consultation": self._config["requires_consultation"],
                "safety_reason": self._config["safety_reason"],
            }
        )
