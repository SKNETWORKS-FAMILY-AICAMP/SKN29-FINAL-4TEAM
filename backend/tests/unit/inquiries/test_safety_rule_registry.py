"""Fail-closed shared Safety Rule registry tests."""

from __future__ import annotations

from copy import deepcopy

from apps.inquiries.services.safety_rule_registry import (
    danger_assessment_is_valid,
    load_safety_rule_registry,
)


def danger_payload() -> dict:
    return {
        "safety_assessment": {
            "risk_level": "danger",
            "requires_consultation": True,
            "matched_safety_rule_ids": [
                "SAFETY-LEAK-001",
                "SAFETY-ELECTRICAL-001",
            ],
        },
        "usage_guidance": {"guidance_status": "TOTAL_STOP"},
    }


def test_shared_registry_loads_unique_known_rules():
    load_safety_rule_registry.cache_clear()
    registry = load_safety_rule_registry()

    assert set(registry) == {
        "SAFETY-LEAK-001",
        "SAFETY-ELECTRICAL-001",
        "SAFETY-HOT-WATER-001",
        "SAFETY-TEMP-ABNORMAL-001",
    }


def test_registered_total_stop_danger_assessment_is_valid():
    assert danger_assessment_is_valid(danger_payload()) is True


def test_unknown_or_mixed_rule_ids_fail_closed():
    payload = danger_payload()
    payload["safety_assessment"]["matched_safety_rule_ids"].append(
        "SAFETY-UNKNOWN-999"
    )

    assert danger_assessment_is_valid(payload) is False


def test_hot_water_partial_stop_policy_conflict_remains_blocked():
    payload = danger_payload()
    payload["safety_assessment"]["matched_safety_rule_ids"] = [
        "SAFETY-HOT-WATER-001"
    ]
    payload["usage_guidance"]["guidance_status"] = "PARTIAL_STOP"

    assert danger_assessment_is_valid(payload) is False


def test_empty_duplicate_and_non_consultation_danger_fail_closed():
    empty = danger_payload()
    empty["safety_assessment"]["matched_safety_rule_ids"] = []
    duplicate = danger_payload()
    duplicate["safety_assessment"]["matched_safety_rule_ids"] = [
        "SAFETY-LEAK-001",
        "SAFETY-LEAK-001",
    ]
    no_consultation = deepcopy(danger_payload())
    no_consultation["safety_assessment"]["requires_consultation"] = False

    assert danger_assessment_is_valid(empty) is False
    assert danger_assessment_is_valid(duplicate) is False
    assert danger_assessment_is_valid(no_consultation) is False
