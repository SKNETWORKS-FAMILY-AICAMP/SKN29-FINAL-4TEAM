"""5주차 위험·근거 없음 시나리오가 Data와 AI 계약에서 같은 안전 경계를 갖는지 검증한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load(relative_path: str) -> Any:
    return json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


def _expected_safety_by_scenario() -> dict[str, dict[str, Any]]:
    return {
        item["scenario_id"]: item
        for item in _load("data/synthetic/expected/safety_assessments.json")
    }


def test_danger_scenarios_require_consultation_and_never_return_normal_guidance() -> None:
    expected = _expected_safety_by_scenario()
    scenarios = _load("data/synthetic/scenarios/danger_escalation.json")

    assert scenarios
    for scenario in scenarios:
        safety = expected[scenario["scenario_id"]]
        assert safety["risk_level"] == "danger"
        assert safety["consultation_required"] is True
        assert safety["usage_guidance_status"] in {"TOTAL_STOP", "PENDING_CONSULTATION"}
        assert safety["usage_guidance_status"] != "NORMAL"
        assert safety["prohibited_actions"]


def test_no_evidence_scenarios_converge_to_consultation_without_guidance_claims() -> None:
    expected = _expected_safety_by_scenario()
    scenarios = _load("data/synthetic/scenarios/no_evidence_fallback.json")

    assert scenarios
    for scenario in scenarios:
        safety = expected[scenario["scenario_id"]]
        assert scenario["workflow_kind"] == "NO_EVIDENCE_FALLBACK"
        assert safety["consultation_required"] is True
        assert safety["usage_guidance_status"] == "PENDING_CONSULTATION"


def test_ai_danger_example_uses_safety_path_without_vector_evidence() -> None:
    document = _load("contracts/ai/examples/symptom-analysis/danger-detected.json")
    response = document["response"]

    assert response["safety_assessment"]["risk_level"] == "danger"
    assert response["safety_assessment"]["requires_consultation"] is True
    assert response["usage_guidance"]["guidance_status"] == "TOTAL_STOP"
    assert response["evidence_references"] == []


def test_ai_no_evidence_example_falls_back_without_fabricated_evidence() -> None:
    document = _load("contracts/ai/examples/symptom-analysis/no-evidence.json")
    response = document["response"]

    assert response["status"] == "FALLBACK"
    assert response["failure_stage"] == "RETRIEVING"
    assert response["safety_assessment"]["requires_consultation"] is True
    assert response["usage_guidance"]["guidance_status"] == "PENDING_CONSULTATION"
    assert response["evidence_references"] == []
