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
    if payload.get("version") != "1.0.0":
        raise SafetyRuleRegistryError("The safety rule registry version is unsupported.")
    if not isinstance(rules, list) or not rules:
        raise SafetyRuleRegistryError("The safety rule registry is empty.")

    registry: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            raise SafetyRuleRegistryError("Every safety rule must be an object.")
        rule_id = rule.get("rule_id")
        statuses = rule.get("allowed_guidance_statuses")
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
        registry[rule_id] = rule
    if not isinstance(codes, list) or codes != list(registry):
        raise SafetyRuleRegistryError(
            "Safety rule codes and rule definitions differ."
        )
    return registry


def danger_assessment_is_valid(payload: dict[str, Any]) -> bool:
    """Apply the shared registry and the stricter Backend DB safety invariant."""

    safety = payload.get("safety_assessment")
    guidance = payload.get("usage_guidance")
    if not isinstance(safety, dict) or not isinstance(guidance, dict):
        return False
    matched_ids = safety.get("matched_safety_rule_ids")
    guidance_status = guidance.get("guidance_status")
    if (
        safety.get("risk_level") != "danger"
        or safety.get("requires_consultation") is not True
        or guidance_status != "TOTAL_STOP"
        or not isinstance(matched_ids, list)
        or not matched_ids
        or len(set(matched_ids)) != len(matched_ids)
    ):
        return False
    try:
        registry = load_safety_rule_registry()
    except SafetyRuleRegistryError:
        return False
    for rule_id in matched_ids:
        rule = registry.get(rule_id)
        if (
            rule is None
            or rule.get("active") is not True
            or rule.get("danger_event_enabled") is not True
            or rule.get("risk_level") != "danger"
            or rule.get("requires_consultation") is not True
            or guidance_status not in rule.get("allowed_guidance_statuses", [])
        ):
            return False
    return True
