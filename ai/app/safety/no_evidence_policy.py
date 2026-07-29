"""공식 근거가 없을 때 판단 보류·상담 전환 정책 적용."""

from ..schemas import UsageGuidance, UsageGuidanceStatus
from .rule_loader import SafetyRuleLoader


class NoEvidencePolicy:
    """근거가 없으면 자가조치 생성을 막고 상담 필요 응답을 만든다."""

    def __init__(self, rule_loader: SafetyRuleLoader | None = None):
        rules = (rule_loader or SafetyRuleLoader()).get_safety_rules()
        self._config = rules["no_evidence_policy"]

    def apply(self) -> UsageGuidance:
        return UsageGuidance(
            guidance_status=UsageGuidanceStatus.PENDING_CONSULTATION,
            message=self._config["message"],
            restricted_functions=["근거 없는 자가조치 안내"],
            next_actions=["전문 상담사 연결을 요청해 주세요."],
        )
