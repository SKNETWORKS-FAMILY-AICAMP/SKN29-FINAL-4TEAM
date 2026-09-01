"""Load the shared fail-closed safety rule identity contract."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


CONTRACT_PATH = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "codes"
    / "safety-rule-ids.yaml"
)
ALLOWED_GUIDANCE_STATUSES = {
    "NORMAL",
    "PARTIAL_STOP",
    "TOTAL_STOP",
    "PENDING_CONSULTATION",
}
ACTIVE_REGISTRY_STATUSES = {"OWNER_BASELINE", "TEAM_APPROVED"}
SUPPORTED_REGISTRY_VERSIONS = {"1.0.0", "1.1.0", "1.2.0", "1.3.0"}
DANGER_GUIDANCE_STATUSES = {"PARTIAL_STOP", "TOTAL_STOP"}
ALLOWED_APPLICABILITY_POLICIES = {"RUNTIME_APPROVED_PRODUCTS"}
ALLOWED_NEXT_ACTION_MERGE_POLICIES = {"EXCLUSIVE"}


class SafetyRuleRegistryError(RuntimeError):
    """Raised when the shared safety rule contract is missing or invalid."""


@lru_cache(maxsize=1)
def load_safety_rule_registry() -> dict[str, dict[str, Any]]:
    """Return validated safety rules keyed by their canonical ID."""

    try:
        payload = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SafetyRuleRegistryError(
            "The canonical safety rule registry could not be loaded."
        ) from exc
    rules = payload.get("rules") if isinstance(payload, dict) else None
    codes = payload.get("codes") if isinstance(payload, dict) else None
    if payload.get("status") not in ACTIVE_REGISTRY_STATUSES:
        raise SafetyRuleRegistryError("The safety rule registry is not active.")
    if payload.get("version") not in SUPPORTED_REGISTRY_VERSIONS:
        raise SafetyRuleRegistryError("The safety rule registry version is unsupported.")
    if not isinstance(rules, list) or not rules:
        raise SafetyRuleRegistryError("The safety rule registry is empty.")

    registry: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            raise SafetyRuleRegistryError("Every safety rule must be an object.")
        rule_id = rule.get("rule_id")
        statuses = rule.get("allowed_guidance_statuses")
        default_status = rule.get("default_guidance_status")
        if (
            not isinstance(rule_id, str)
            or not rule_id.startswith("SAFETY-")
            or rule_id in registry
        ):
            raise SafetyRuleRegistryError("Safety rule IDs must be unique SAFETY-* values.")
        if (
            not isinstance(statuses, list)
            or not statuses
            or any(status not in ALLOWED_GUIDANCE_STATUSES for status in statuses)
        ):
            raise SafetyRuleRegistryError(
                f"{rule_id}: allowed guidance statuses are invalid."
            )
        if default_status is not None and default_status not in statuses:
            raise SafetyRuleRegistryError(
                f"{rule_id}: the default guidance status is not allowed."
            )
        if rule.get("risk_level") == "danger" and (
            default_status not in DANGER_GUIDANCE_STATUSES
        ):
            raise SafetyRuleRegistryError(
                f"{rule_id}: danger rules require a default stop status."
            )
        if (
            rule.get("danger_event_enabled") is True
            and default_status == "PARTIAL_STOP"
            and (
                not _is_non_empty_string_list(rule.get("restricted_functions"))
                or not _is_non_empty_string_list(rule.get("next_actions"))
            )
        ):
            raise SafetyRuleRegistryError(
                f"{rule_id}: approved partial-stop rules require exact guidance."
            )
        applicability_policy = rule.get("applicability_policy")
        if applicability_policy is not None and (
            applicability_policy not in ALLOWED_APPLICABILITY_POLICIES
        ):
            raise SafetyRuleRegistryError(
                f"{rule_id}: the applicability policy is invalid."
            )
        next_action_merge_policy = rule.get("next_action_merge_policy")
        if next_action_merge_policy is not None and (
            next_action_merge_policy not in ALLOWED_NEXT_ACTION_MERGE_POLICIES
        ):
            raise SafetyRuleRegistryError(
                f"{rule_id}: the next-action merge policy is invalid."
            )
        if next_action_merge_policy == "EXCLUSIVE" and (
            default_status != "TOTAL_STOP"
            or not _is_non_empty_string_list(rule.get("restricted_functions"))
            or not _is_non_empty_string_list(rule.get("next_actions"))
        ):
            raise SafetyRuleRegistryError(
                f"{rule_id}: exclusive actions require exact total-stop guidance."
            )
        if rule_id == "SAFETY-HOT-WATER-HEATER-001" and (
            applicability_policy != "RUNTIME_APPROVED_PRODUCTS"
            or not _is_non_empty_string_list(
                rule.get("negated_expressions")
            )
        ):
            raise SafetyRuleRegistryError(
                f"{rule_id}: product applicability and negation rules are required."
            )
        registry[rule_id] = rule
    if not isinstance(codes, list) or codes != list(registry):
        raise SafetyRuleRegistryError(
            "Safety rule codes and rule definitions differ."
        )
    return registry


def danger_assessment_validation_errors(
    payload: dict[str, Any],
    *,
    require_guidance_details: bool = True,
) -> list[str]:
    """Return fail-closed errors for one danger assessment and guidance pair."""

    safety = payload.get("safety_assessment")
    guidance = payload.get("usage_guidance")
    if not isinstance(safety, dict) or not isinstance(guidance, dict):
        return ["danger safety_assessment and usage_guidance are required"]
    matched_ids = safety.get("matched_safety_rule_ids")
    guidance_status = guidance.get("guidance_status")
    if (
        safety.get("risk_level") != "danger"
        or safety.get("requires_consultation") is not True
        or not isinstance(matched_ids, list)
        or not matched_ids
        or len(set(matched_ids)) != len(matched_ids)
    ):
        return [
            "danger requires consultation and unique approved Safety Rule IDs"
        ]
    try:
        registry = load_safety_rule_registry()
    except SafetyRuleRegistryError:
        return ["the canonical Safety Rule registry is unavailable"]

    matched_rules = []
    for rule_id in matched_ids:
        rule = registry.get(rule_id)
        if (
            rule is None
            or rule.get("active") is not True
            or rule.get("danger_event_enabled") is not True
            or rule.get("risk_level") != "danger"
            or rule.get("requires_consultation") is not True
        ):
            return [f"{rule_id}: the danger rule is not enabled"]
        matched_rules.append(rule)

    expected_status = (
        "TOTAL_STOP"
        if any(
            rule.get("default_guidance_status") == "TOTAL_STOP"
            for rule in matched_rules
        )
        else "PARTIAL_STOP"
    )
    if guidance_status != expected_status:
        return [
            "danger guidance must follow the strictest matched Safety Rule"
        ]
    if any(
        guidance_status not in rule.get("allowed_guidance_statuses", [])
        for rule in matched_rules
    ):
        return [
            "danger guidance is not allowed by every matched Safety Rule"
        ]

    exclusive_rules = [
        rule
        for rule in matched_rules
        if rule.get("next_action_merge_policy") == "EXCLUSIVE"
    ]
    if exclusive_rules and require_guidance_details:
        expected_actions = list(
            dict.fromkeys(
                action
                for rule in exclusive_rules
                for action in rule.get("next_actions", [])
            )
        )
        if guidance.get("next_actions") != expected_actions:
            return [
                "danger next_actions differ from the exclusive approved rule"
            ]

    if expected_status == "PARTIAL_STOP" and require_guidance_details:
        if len(matched_rules) != 1:
            return [
                "partial-stop danger requires one unambiguous approved rule"
            ]
        approved_rule = matched_rules[0]
        if guidance.get("restricted_functions") != approved_rule.get(
            "restricted_functions"
        ):
            return [
                "partial-stop restricted_functions differ from the approved rule"
            ]
        if guidance.get("next_actions") != approved_rule.get("next_actions"):
            return [
                "partial-stop next_actions differ from the approved rule"
            ]
    return []


def danger_assessment_is_valid(
    payload: dict[str, Any],
    *,
    require_guidance_details: bool = True,
) -> bool:
    """Validate Rule-specific danger restrictions with TOTAL_STOP precedence."""

    return not danger_assessment_validation_errors(
        payload,
        require_guidance_details=require_guidance_details,
    )


def _is_non_empty_string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )
