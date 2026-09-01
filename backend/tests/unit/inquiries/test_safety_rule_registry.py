"""Fail-closed shared Safety Rule registry tests."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from apps.inquiries.services.safety_rule_registry import (
    danger_assessment_is_valid,
    load_safety_rule_registry,
)


AI_SAFETY_RULES_PATH = (
    Path(__file__).resolve().parents[4]
    / "ai"
    / "configs"
    / "safety_rules.yaml"
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
        "SAFETY-HOT-WATER-HEATER-001",
        "SAFETY-REFRIGERANT-001",
        "SAFETY-TEMP-ABNORMAL-001",
    }


def test_registered_total_stop_danger_assessment_is_valid():
    assert danger_assessment_is_valid(danger_payload()) is True


def test_registered_refrigerant_danger_assessment_is_valid():
    payload = danger_payload()
    payload["safety_assessment"]["matched_safety_rule_ids"] = [
        "SAFETY-REFRIGERANT-001"
    ]
    payload["usage_guidance"]["next_actions"] = [
        "제품이나 전원 코드를 만지지 마세요.",
        "불꽃이나 스파크를 일으킬 수 있는 행동을 피하세요.",
        "제품을 만지지 않고 가능한 경우 창문을 열어 충분히 환기하세요.",
        "안전한 장소로 이동한 뒤 전문 상담 및 기사 점검을 요청하세요.",
    ]

    assert danger_assessment_is_valid(payload) is True

    payload["usage_guidance"]["next_actions"] = ["플러그를 뽑으세요."]

    assert danger_assessment_is_valid(payload) is False


def test_approved_refrigerant_contract_matches_ai_rule():
    registry_rule = load_safety_rule_registry()["SAFETY-REFRIGERANT-001"]
    ai_payload = yaml.safe_load(
        AI_SAFETY_RULES_PATH.read_text(encoding="utf-8")
    )
    ai_rule = next(
        rule
        for rule in ai_payload["rules"].values()
        if rule.get("rule_id") == "SAFETY-REFRIGERANT-001"
    )

    assert ai_rule["risk_level"] == registry_rule["risk_level"] == "danger"
    assert ai_rule["usage_guidance_status"] == registry_rule[
        "default_guidance_status"
    ] == "TOTAL_STOP"
    assert ai_rule["requires_consultation"] is registry_rule[
        "requires_consultation"
    ] is True
    assert ai_rule["restricted_functions"] == registry_rule[
        "restricted_functions"
    ]
    assert ai_rule["next_actions"] == registry_rule["next_actions"]
    assert ai_rule["next_action_merge_policy"] == registry_rule[
        "next_action_merge_policy"
    ] == "EXCLUSIVE"


def test_unknown_or_mixed_rule_ids_fail_closed():
    payload = danger_payload()
    payload["safety_assessment"]["matched_safety_rule_ids"].append(
        "SAFETY-UNKNOWN-999"
    )

    assert danger_assessment_is_valid(payload) is False


def test_unapproved_generic_hot_water_partial_stop_remains_blocked():
    payload = danger_payload()
    payload["safety_assessment"]["matched_safety_rule_ids"] = [
        "SAFETY-HOT-WATER-001"
    ]
    payload["usage_guidance"]["guidance_status"] = "PARTIAL_STOP"

    assert danger_assessment_is_valid(payload) is False


def test_approved_hot_water_heater_partial_stop_is_valid():
    payload = danger_payload()
    payload["safety_assessment"]["matched_safety_rule_ids"] = [
        "SAFETY-HOT-WATER-HEATER-001"
    ]
    payload["usage_guidance"] = {
        "guidance_status": "PARTIAL_STOP",
        "restricted_functions": ["온수 출수 및 음용 중지"],
        "next_actions": [
            "온수 기능 사용과 온수 음용을 중단하세요.",
            "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
        ],
    }

    assert danger_assessment_is_valid(payload) is True


def test_approved_hot_water_heater_contract_matches_ai_rule():
    """Keep the approved Backend boundary aligned with the AI-owned rule."""

    registry_rule = load_safety_rule_registry()[
        "SAFETY-HOT-WATER-HEATER-001"
    ]
    ai_payload = yaml.safe_load(
        AI_SAFETY_RULES_PATH.read_text(encoding="utf-8")
    )
    ai_rule = next(
        rule
        for rule in ai_payload["rules"].values()
        if rule.get("rule_id") == "SAFETY-HOT-WATER-HEATER-001"
    )

    assert ai_rule["risk_level"] == registry_rule["risk_level"]
    assert (
        ai_rule["usage_guidance_status"]
        == registry_rule["default_guidance_status"]
    )
    assert (
        ai_rule["requires_consultation"]
        is registry_rule["requires_consultation"]
    )
    assert (
        ai_rule["restricted_functions"]
        == registry_rule["restricted_functions"]
    )
    assert ai_rule["next_actions"] == registry_rule["next_actions"]
    assert (
        ai_rule["applicability_policy"]
        == registry_rule["applicability_policy"]
        == "RUNTIME_APPROVED_PRODUCTS"
    )
    assert (
        ai_rule["negated_expressions"]
        == registry_rule["negated_expressions"]
    )


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("restricted_functions", []),
        ("next_actions", ["임의 조치"]),
    ],
)
def test_hot_water_heater_partial_stop_requires_exact_guidance(
    field,
    invalid_value,
):
    payload = danger_payload()
    payload["safety_assessment"]["matched_safety_rule_ids"] = [
        "SAFETY-HOT-WATER-HEATER-001"
    ]
    payload["usage_guidance"] = {
        "guidance_status": "PARTIAL_STOP",
        "restricted_functions": ["온수 출수 및 음용 중지"],
        "next_actions": [
            "온수 기능 사용과 온수 음용을 중단하세요.",
            "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
        ],
    }
    payload["usage_guidance"][field] = invalid_value

    assert danger_assessment_is_valid(payload) is False


def test_total_stop_rule_overrides_hot_water_heater_partial_stop():
    payload = danger_payload()
    payload["safety_assessment"]["matched_safety_rule_ids"] = [
        "SAFETY-HOT-WATER-HEATER-001",
        "SAFETY-LEAK-001",
    ]

    assert danger_assessment_is_valid(payload) is True

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
