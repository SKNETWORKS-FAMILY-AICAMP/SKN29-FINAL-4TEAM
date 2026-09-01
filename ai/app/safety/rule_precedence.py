"""설정 선언 순서와 무관한 Safety Rule 우선순위 선택."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ..schemas import RiskLevel, UsageGuidanceStatus


_GUIDANCE_STATUS_PRECEDENCE = {
    UsageGuidanceStatus.NORMAL: 0,
    UsageGuidanceStatus.PENDING_CONSULTATION: 1,
    UsageGuidanceStatus.PARTIAL_STOP: 2,
    UsageGuidanceStatus.TOTAL_STOP: 3,
}


def select_effective_safety_rule(
    rules_config: Mapping[str, Mapping[str, Any]],
    matched_rule_ids: Iterable[str],
    *,
    risk_level: RiskLevel,
) -> Mapping[str, Any] | None:
    """동일 위험도에서 가장 제한적인 안내 상태의 대표 Rule을 선택한다."""

    effective_rules = select_effective_safety_rules(
        rules_config,
        matched_rule_ids,
        risk_level=risk_level,
    )
    return effective_rules[0] if effective_rules else None


def select_effective_safety_rules(
    rules_config: Mapping[str, Mapping[str, Any]],
    matched_rule_ids: Iterable[str],
    *,
    risk_level: RiskLevel,
) -> list[Mapping[str, Any]]:
    """가장 제한적인 상태를 가진 모든 Rule을 안정적인 순서로 반환한다.

    최고 상태가 같은 복합 위험은 모두 보존해 한 Rule의 제한 기능이나 다음
    행동이 유실되지 않게 한다. 반환 순서는 ``rule_id``로 고정한다.
    """

    matched_ids = set(matched_rule_ids)
    candidates = [
        rule
        for rule in rules_config.values()
        if rule.get("rule_id") in matched_ids
        and rule.get("risk_level") == risk_level.value
    ]
    if not candidates:
        return []

    highest_precedence = max(
        _GUIDANCE_STATUS_PRECEDENCE[
            UsageGuidanceStatus(rule["usage_guidance_status"])
        ]
        for rule in candidates
    )
    return sorted(
        (
            rule
            for rule in candidates
            if _GUIDANCE_STATUS_PRECEDENCE[
                UsageGuidanceStatus(rule["usage_guidance_status"])
            ]
            == highest_precedence
        ),
        key=lambda rule: str(rule["rule_id"]),
    )


def merge_rule_list_field(
    rules: Iterable[Mapping[str, Any]],
    field_name: str,
) -> list[str]:
    """여러 Rule의 문자열 목록 필드를 중복 없이 안정적으로 합친다."""

    selected_rules = list(rules)
    if field_name == "next_actions":
        exclusive_rules = [
            rule
            for rule in selected_rules
            if rule.get("next_action_merge_policy") == "EXCLUSIVE"
        ]
        if exclusive_rules:
            selected_rules = exclusive_rules

    merged: list[str] = []
    for rule in selected_rules:
        for item in rule.get(field_name, []):
            if item not in merged:
                merged.append(item)
    return merged
