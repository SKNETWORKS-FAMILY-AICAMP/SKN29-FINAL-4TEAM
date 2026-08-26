"""위험도와 제품 사용 안내 상태의 일관성 검사."""

from ...schemas import RiskLevel, SafetyAssessment, UsageGuidance, UsageGuidanceStatus
from ...safety.prohibited_action_guard import ProhibitedActionGuard
from .guidance_message_guard import GuidanceMessageGuard
from .prohibited_phrase_validator import ProhibitedPhraseValidator
from .safety_rule_alignment_validator import SafetyRuleAlignmentValidator


class UsageGuidanceValidator:
    """안전 평가·근거·안내 결과를 최종적으로 함께 검사한다."""

    def __init__(self) -> None:
        self._phrase_validator = ProhibitedPhraseValidator()
        self._action_guard = ProhibitedActionGuard()
        self._message_guard = GuidanceMessageGuard()
        self._rule_alignment_validator = SafetyRuleAlignmentValidator()

    def validate(
        self,
        safety: SafetyAssessment,
        guidance: UsageGuidance,
        *,
        has_evidence: bool,
    ) -> UsageGuidance:
        if safety.risk_level == RiskLevel.DANGER and guidance.guidance_status == UsageGuidanceStatus.NORMAL:
            raise ValueError("danger 결과에는 NORMAL 안내를 반환할 수 없습니다.")
        if not has_evidence and safety.risk_level != RiskLevel.DANGER:
            if guidance.guidance_status != UsageGuidanceStatus.PENDING_CONSULTATION:
                raise ValueError("근거가 없으면 PENDING_CONSULTATION이어야 합니다.")
        self._rule_alignment_validator.validate(safety, guidance)
        self._message_guard.validate_safety_semantics(
            guidance.message,
            guidance.guidance_status,
        )
        self._action_guard.validate(guidance.next_actions)
        valid, _, detected = self._phrase_validator.validate(guidance.message)
        if not valid:
            raise ValueError(f"금지 표현이 포함되어 있습니다: {', '.join(detected)}")
        return guidance
