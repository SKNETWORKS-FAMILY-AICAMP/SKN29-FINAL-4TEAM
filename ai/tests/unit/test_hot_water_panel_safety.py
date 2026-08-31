"""Manual-derived alert paraphrases, independent of the 45-case Oracle."""

from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.safety import RiskClassifier, UsageGuidanceClassifier
from ai.app.schemas import RiskLevel, UsageGuidanceStatus


ALERTS = (
    "냉수, 온수, 정수 버튼이 전부 깜빡이고 화면이 붉은색이에요.",
    "[온수], [정수], [냉수] 버튼이 동시에 점멸합니다. LED 표시창이 빨간색으로 변했어요.",
    "디스플레이가 적색이고 정수와 냉수와 온수 버튼이 모두 깜박여요.",
    "온수·냉수·정수 버튼들이 모두 깜빡이고 표시창에 빨간 불이 들어왔어요.",
)


@pytest.mark.parametrize("raw", ALERTS)
def test_combined_panel_alert_uses_existing_approved_heater_guidance(raw):
    assessment = RiskClassifier().classify(raw)
    guidance = UsageGuidanceClassifier().determine_guidance(assessment, raw, has_evidence=False)

    assert assessment.risk_level == RiskLevel.DANGER
    assert assessment.requires_consultation is True
    assert assessment.matched_safety_rule_ids == ["SAFETY-HOT-WATER-HEATER-001"]
    assert guidance.guidance_status == UsageGuidanceStatus.PARTIAL_STOP
    assert guidance.restricted_functions == ["온수 출수 및 음용 중지"]
    assert guidance.next_actions == [
        "온수 기능 사용과 온수 음용을 중단하세요.",
        "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
    ]


@pytest.mark.parametrize("raw", (
    "냉수 버튼이 깜박이고 잠금 표시등이 빨간색이에요.",
    "온수와 정수 버튼이 모두 깜박이고 표시창이 빨간색이에요.",
    "온수, 냉수, 정수 버튼이 모두 깜박이는데 표시창은 파란색이에요.",
    "온수, 냉수, 정수 버튼이 모두 깜박이지만 표시창은 빨간색이 아니에요.",
    "온수, 냉수, 정수 버튼이 모두 깜박이지 않아요. 표시창은 빨간색이에요.",
    "온수, 냉수, 정수 버튼이 모두 깜박이고 표시창이 빨갛게 켜지지 않아요.",
    "온수, 냉수, 정수 버튼이 모두 깜박이는데 표시창은 빨갛게 안 켜져요.",
    "온수, 냉수, 정수 버튼이 모두 깜박이고 표시창에 빨간 불이 안 들어와요.",
    "온수, 냉수, 정수 버튼이 모두 깜박이면 표시창이 빨간색으로 켜지나요?",
    "온수, 냉수, 정수 버튼이 모두 깜박이고 표시창이 빨간색일 경우 어떻게 하죠?",
    "온수, 냉수, 정수 버튼이 모두 깜박이고 표시창이 빨간색이면 어떻게 하죠?",
    "온수, 냉수, 정수 버튼 중 냉수만 깜박이고 표시창이 빨간색이에요.",
    "온수, 냉수, 정수 버튼에서 온수 제외하고 모두 깜박여요. 표시창은 빨간색이에요.",
))
def test_incomplete_negated_or_hypothetical_panel_alert_is_not_heater_danger(raw):
    assessment = RiskClassifier().classify(raw)
    assert "SAFETY-HOT-WATER-HEATER-001" not in assessment.matched_safety_rule_ids


@pytest.mark.parametrize("runtime", ("single_rag", "multi_agent"))
@pytest.mark.parametrize("raw", ALERTS)
def test_panel_alert_stops_before_any_provider_or_search(runtime, raw):
    dependency = Mock()
    for name in ("search", "structure_symptom", "generate_followup_wording", "generate_guidance"):
        getattr(dependency, name).side_effect = AssertionError("EXTERNAL_CALL_FORBIDDEN")
    dependency.prompt_version = "test-prompt"
    result = PipelineRouter(
        search_service=dependency, symptom_llm_client=dependency,
        followup_llm_client=dependency, llm_client=dependency, mcp_context_service=None,
    ).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b801",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88b802",
        ai_request_id="panel-alert-safety-regression", state_version=3,
        raw_symptom=raw, runtime_name=runtime,
    ).to_analysis_result()

    assert dependency.mock_calls == []
    assert result.safety_assessment.risk_level == RiskLevel.DANGER
    assert result.safety_assessment.matched_safety_rule_ids == ["SAFETY-HOT-WATER-HEATER-001"]
    assert result.usage_guidance.guidance_status == UsageGuidanceStatus.PARTIAL_STOP
    assert result.followup_questions == []
    assert result.evidence_references == []


def test_panel_alert_with_observed_electrical_danger_preserves_total_stop():
    raw = ALERTS[0] + " 전원 코드에서 불꽃이 튑니다."
    assessment = RiskClassifier().classify(raw)
    guidance = UsageGuidanceClassifier().determine_guidance(assessment, raw, has_evidence=False)
    assert set(assessment.matched_safety_rule_ids) == {
        "SAFETY-HOT-WATER-HEATER-001", "SAFETY-ELECTRICAL-001",
    }
    assert guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP


def test_panel_alert_output_matches_backend_approved_registry_without_policy_change():
    root = Path(__file__).resolve().parents[3]
    registry = yaml.safe_load((root / "contracts/codes/safety-rule-ids.yaml").read_text(encoding="utf-8"))
    rule = next(item for item in registry["rules"] if item["rule_id"] == "SAFETY-HOT-WATER-HEATER-001")
    assessment = RiskClassifier().classify(ALERTS[0])
    guidance = UsageGuidanceClassifier().determine_guidance(assessment, ALERTS[0], has_evidence=False)

    assert registry["status"] == "TEAM_APPROVED"
    assert rule["active"] and rule["danger_event_enabled"]
    assert rule["risk_level"] == assessment.risk_level.value
    assert rule["requires_consultation"] == assessment.requires_consultation
    assert rule["default_guidance_status"] == guidance.guidance_status.value
    assert guidance.guidance_status.value in rule["allowed_guidance_statuses"]
    assert rule["restricted_functions"] == guidance.restricted_functions
    assert rule["next_actions"] == guidance.next_actions
