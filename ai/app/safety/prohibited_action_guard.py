"""분해·직접 수리 등 금지된 자가조치 차단."""

from typing import Iterable, List

from .rule_loader import SafetyRuleLoader


class ProhibitedActionGuard:
    """고객 행동 목록에서 설정으로 금지한 직접 수리 문구를 차단한다."""

    def __init__(self, rule_loader: SafetyRuleLoader | None = None):
        config = (rule_loader or SafetyRuleLoader()).get_prohibited_expressions()
        self._phrases = tuple(config.get("prohibited_repair_action_phrases", []))

    def validate(self, actions: Iterable[str]) -> List[str]:
        blocked = [action for action in actions if any(phrase in action for phrase in self._phrases)]
        if blocked:
            raise ValueError("직접 분해·수리를 유도하는 행동은 안내할 수 없습니다.")
        return list(actions)
