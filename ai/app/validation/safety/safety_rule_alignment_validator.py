"""Danger 출력과 승인 Safety Rule 본문 정합성을 검증한다."""

from ...safety.rule_loader import SafetyRuleLoader
from ...safety.rule_precedence import (
    merge_rule_list_field,
    select_effective_safety_rules,
)
from ...schemas import (
    RiskLevel,
    SafetyAssessment,
    SafetyPriority,
    UsageGuidance,
    UsageGuidanceStatus,
)


class SafetyRuleAlignmentValidator:
    """Rule ID뿐 아니라 사용 제한·다음 행동까지 승인 설정과 대조한다."""

    def __init__(self, rule_loader: SafetyRuleLoader | None = None) -> None:
        self._loader = rule_loader or SafetyRuleLoader()

    def validate(
        self,
        safety: SafetyAssessment,
        guidance: UsageGuidance,
    ) -> None:
        if safety.risk_level != RiskLevel.DANGER:
            return
        if not safety.requires_consultation:
            raise ValueError("danger 결과에는 즉시 상담 연결 판정이 필요합니다.")
        if not safety.matched_safety_rule_ids:
            raise ValueError("danger 결과에는 승인 Safety Rule ID가 필요합니다.")

        matched_rule_ids = set(safety.matched_safety_rule_ids)
        configured_rules = list(
            self._loader.get_safety_rules()["rules"].values()
        )
        configured_rule_ids = {
            rule.get("rule_id") for rule in configured_rules
        }
        unknown_rule_ids = matched_rule_ids.difference(configured_rule_ids)
        if unknown_rule_ids:
            raise ValueError("danger 결과에 승인되지 않은 Safety Rule ID가 있습니다.")
        matched_rules = select_effective_safety_rules(
            self._loader.get_safety_rules()["rules"],
            safety.matched_safety_rule_ids,
            risk_level=RiskLevel.DANGER,
        )
        if not matched_rules:
            raise ValueError("danger 결과의 Safety Rule ID가 승인 설정에 없습니다.")
        if any(
            rule.get("requires_consultation") is not True
            for rule in matched_rules
        ):
            raise ValueError("danger Safety Rule은 상담 연결을 요구해야 합니다.")

        expected_priority = SafetyPriority(matched_rules[0]["priority"])
        expected_status = UsageGuidanceStatus(
            matched_rules[0]["usage_guidance_status"]
        )
        expected_restrictions = merge_rule_list_field(
            matched_rules,
            "restricted_functions",
        )
        expected_actions = merge_rule_list_field(
            matched_rules,
            "next_actions",
        )
        if safety.priority != expected_priority:
            raise ValueError("danger 우선순위가 승인 Safety Rule과 다릅니다.")
        if guidance.guidance_status != expected_status:
            raise ValueError("danger 안내 상태가 승인 Safety Rule과 다릅니다.")
        if guidance.restricted_functions != expected_restrictions:
            raise ValueError("danger 제한 기능이 승인 Safety Rule과 다릅니다.")
        if guidance.next_actions != expected_actions:
            raise ValueError("danger 다음 행동이 승인 Safety Rule과 다릅니다.")
