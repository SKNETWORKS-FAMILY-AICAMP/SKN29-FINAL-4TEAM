"""안전 분류기 및 가드레일 단위 테스트."""

from copy import deepcopy

import pytest
from ai.app.schemas import RiskLevel, SafetyPriority, UsageGuidanceStatus
from ai.app.safety import RiskClassifier, UsageGuidanceClassifier
from ai.app.safety import ProhibitedActionGuard
from ai.app.safety.rule_loader import SafetyRuleLoader
from ai.app.validation.safety import (
    ProhibitedPhraseValidator,
    SafetyRuleAlignmentValidator,
)


class StaticSafetyRuleLoader:
    def __init__(self, config):
        self._config = config

    def get_safety_rules(self):
        return self._config


@pytest.fixture
def risk_classifier():
    return RiskClassifier()


@pytest.fixture
def guidance_classifier():
    return UsageGuidanceClassifier()


@pytest.fixture
def phrase_validator():
    return ProhibitedPhraseValidator()


def test_leak_danger_classification(risk_classifier, guidance_classifier):
    """누수 위험 키워드 감지 및 사용 중지 안내 판정 테스트"""
    raw_text = "정수기 제품 밑에 물이 새고 전원선 근처에 누수가 생겼어요."
    assessment = risk_classifier.classify(raw_text)

    assert assessment.risk_level == RiskLevel.DANGER
    assert assessment.requires_consultation is True
    assert assessment.matched_safety_rule_ids == ["SAFETY-LEAK-001"]
    assert "제품 하부 및 전원부 주변 누수" in assessment.detected_risks

    guidance = guidance_classifier.determine_guidance(assessment, raw_text, has_evidence=True)
    assert guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP
    assert "전체 출수 기능 중지" in guidance.restricted_functions


def test_natural_leak_particle_expression_is_classified_as_danger(risk_classifier):
    assessment = risk_classifier.classify("제품 아래로 물이 새고 있습니다.")

    assert assessment.risk_level == RiskLevel.DANGER
    assert assessment.matched_safety_rule_ids == ["SAFETY-LEAK-001"]


@pytest.mark.parametrize(
    "selected_symptom",
    ["symptom_leak", "LEAK", "제품 누수"],
)
def test_leak_selected_symptom_aliases_apply_leak_rule(
    risk_classifier,
    guidance_classifier,
    selected_symptom,
):
    raw_text = "제품 밑으로 물이 번지고 있습니다."
    assessment = risk_classifier.classify(raw_text, [selected_symptom])
    guidance = guidance_classifier.determine_guidance(
        assessment,
        raw_text,
        has_evidence=False,
    )

    assert assessment.risk_level == RiskLevel.DANGER
    assert assessment.requires_consultation is True
    assert assessment.matched_safety_rule_ids == ["SAFETY-LEAK-001"]
    assert guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP
    assert any("젖은 손" in action for action in guidance.next_actions)


def test_electrical_danger_classification(risk_classifier, guidance_classifier):
    """전기 타는 냄새/스파크 위험 감지 테스트"""
    raw_text = "정수기 뒤에서 타는 냄새가 나고 스파크가 튑니다."
    assessment = risk_classifier.classify(raw_text)

    assert assessment.risk_level == RiskLevel.DANGER
    assert assessment.requires_consultation is True
    assert assessment.matched_safety_rule_ids == ["SAFETY-ELECTRICAL-001"]

    guidance = guidance_classifier.determine_guidance(assessment, raw_text, has_evidence=True)
    assert guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP


def test_caution_classification(risk_classifier, guidance_classifier):
    """출수량 저하 및 미지근한 물 일반 주의 단계 테스트"""
    raw_text = "냉수가 안 차갑고 물이 졸졸 나옵니다."
    assessment = risk_classifier.classify(raw_text)

    assert assessment.risk_level == RiskLevel.CAUTION
    assert assessment.matched_safety_rule_ids == ["SAFETY-TEMP-ABNORMAL-001"]

    guidance = guidance_classifier.determine_guidance(assessment, raw_text, has_evidence=True)
    assert guidance.guidance_status == UsageGuidanceStatus.PARTIAL_STOP


def test_general_normal_classification(risk_classifier, guidance_classifier):
    """일반 필터 문의 정상 케이스 테스트"""
    raw_text = "정기 필터 교체 주기 확인 부탁드립니다."
    assessment = risk_classifier.classify(raw_text)

    assert assessment.risk_level == RiskLevel.GENERAL
    assert assessment.requires_consultation is False
    assert assessment.matched_safety_rule_ids == []

    guidance = guidance_classifier.determine_guidance(assessment, raw_text, has_evidence=True)
    assert guidance.guidance_status == UsageGuidanceStatus.NORMAL


def test_explicitly_negated_leak_does_not_override_detected_temperature_caution(risk_classifier):
    assessment = risk_classifier.classify("누수는 아니고 어제부터 냉수가 미지근합니다.")

    assert assessment.risk_level == RiskLevel.CAUTION
    assert "제품 하부 및 전원부 주변 누수" not in assessment.detected_risks


@pytest.mark.parametrize(
    "raw_text",
    [
        "누수는 아니고 필터 교체 주기를 확인하고 싶습니다.",
        "물이 새지 않는다. 정기 관리 일정만 확인하고 싶습니다.",
    ],
)
def test_explicitly_negated_leak_ignores_selected_leak_alias(
    risk_classifier,
    raw_text,
):
    assessment = risk_classifier.classify(raw_text, ["symptom_leak"])

    assert assessment.risk_level != RiskLevel.DANGER
    assert "SAFETY-LEAK-001" not in assessment.matched_safety_rule_ids


def test_no_evidence_fallback(risk_classifier, guidance_classifier):
    """공식 매뉴얼 근거 부족 시 PENDING_CONSULTATION 판정 테스트"""
    raw_text = "특이한 사용법을 알려주세요."
    assessment = risk_classifier.classify(raw_text)

    # 근거가 없는 경우 (has_evidence=False)
    assessment, guidance = guidance_classifier.determine_assessment_and_guidance(
        assessment,
        raw_text,
        has_evidence=False,
    )
    assert assessment.risk_level == RiskLevel.CAUTION
    assert assessment.priority == SafetyPriority.CONSULTATION_RECOMMENDED
    assert assessment.requires_consultation is True
    assert guidance.guidance_status == UsageGuidanceStatus.PENDING_CONSULTATION
    assert "전문 상담사 연결" in guidance.next_actions[0]


def test_prohibited_phrase_validation(phrase_validator):
    """금지 표현(확정 진단, 안전 보증, 분해 유도) 감지 테스트"""
    # 1. 정상 문구
    valid, msg, detected = phrase_validator.validate("필터 수명이 다했는지 점검해 보세요.")
    assert valid is True
    assert detected == []

    # 2. 확정 진단 포함 문구
    valid, msg, detected = phrase_validator.validate("이 증상은 모터 고장이 확실합니다.")
    assert valid is False
    assert len(detected) > 0
    assert "[확정진단 금지]" in detected[0]

    # 3. 위험 분해 유도 포함 문구
    valid, msg, detected = phrase_validator.validate("정수기 커버를 분해하세요.")
    assert valid is False
    assert len(detected) > 0
    assert "[직접수리유도 금지]" in detected[0]


def test_hot_water_burn_risk_never_returns_normal(risk_classifier, guidance_classifier):
    raw_text = "온수가 계속 나오고 멈추지 않아 화상 위험이 있습니다."
    assessment = risk_classifier.classify(raw_text)
    guidance = guidance_classifier.determine_guidance(assessment, raw_text, has_evidence=True)
    assert assessment.risk_level == RiskLevel.DANGER
    assert assessment.matched_safety_rule_ids == ["SAFETY-HOT-WATER-001"]
    assert guidance.guidance_status in {UsageGuidanceStatus.PARTIAL_STOP, UsageGuidanceStatus.TOTAL_STOP}


@pytest.mark.parametrize(
    ("case_id", "raw_text"),
    [
        ("SYN-IAC606-108", "온수 히터 고장으로 기사 점검이 필요합니다."),
        ("SYN-IAC425-109", "순간온수 모듈 점검이 필요하다는 안내를 받았습니다."),
        ("SYN-JAC104-031", "온수 음용 금지 안내를 받았습니다."),
    ],
)
def test_hot_water_heater_danger_cases_require_partial_stop_and_consultation(
    risk_classifier,
    guidance_classifier,
    case_id,
    raw_text,
):
    assessment = risk_classifier.classify(raw_text)
    guidance = guidance_classifier.determine_guidance(
        assessment,
        raw_text,
        has_evidence=False,
    )

    assert case_id.startswith("SYN-")
    assert assessment.risk_level == RiskLevel.DANGER
    assert assessment.requires_consultation is True
    assert "SAFETY-HOT-WATER-HEATER-001" in assessment.matched_safety_rule_ids
    assert "SAFETY-LEAK-001" not in assessment.matched_safety_rule_ids
    assert "SAFETY-ELECTRICAL-001" not in assessment.matched_safety_rule_ids
    assert guidance.guidance_status == UsageGuidanceStatus.PARTIAL_STOP
    assert guidance.restricted_functions == ["온수 출수 및 음용 중지"]
    assert guidance.next_actions == [
        "온수 기능 사용과 온수 음용을 중단하세요.",
        "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
    ]


@pytest.mark.parametrize(
    ("case_id", "raw_text", "expected_total_stop_rule_id"),
    [
        (
            "HOT-WATER-HEATER-WITH-LEAK",
            "온수 히터 고장과 누수가 함께 발생했습니다.",
            "SAFETY-LEAK-001",
        ),
        (
            "HOT-WATER-HEATER-WITH-ELECTRICAL-RISK",
            "온수 히터 고장 중에 스파크가 발생했습니다.",
            "SAFETY-ELECTRICAL-001",
        ),
        (
            "HOT-WATER-HEATER-WITH-FIRE-RISK",
            "온수 히터 고장과 화재 위험이 함께 있습니다.",
            "SAFETY-ELECTRICAL-001",
        ),
    ],
)
def test_hot_water_heater_with_more_restrictive_danger_uses_total_stop(
    risk_classifier,
    guidance_classifier,
    case_id,
    raw_text,
    expected_total_stop_rule_id,
):
    assessment = risk_classifier.classify(raw_text)
    guidance = guidance_classifier.determine_guidance(
        assessment,
        raw_text,
        has_evidence=False,
    )

    assert case_id.startswith("HOT-WATER-HEATER-WITH-")
    assert assessment.risk_level == RiskLevel.DANGER
    assert assessment.requires_consultation is True
    assert "SAFETY-HOT-WATER-HEATER-001" in assessment.matched_safety_rule_ids
    assert expected_total_stop_rule_id in assessment.matched_safety_rule_ids
    assert guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP
    SafetyRuleAlignmentValidator().validate(assessment, guidance)


def test_total_stop_precedence_does_not_depend_on_rule_declaration_order():
    config = deepcopy(SafetyRuleLoader().get_safety_rules())
    rules = config["rules"]
    config["rules"] = {
        "hot_water_heater_danger": rules["hot_water_heater_danger"],
        "leak_danger": rules["leak_danger"],
    }
    loader = StaticSafetyRuleLoader(config)
    risk_classifier = RiskClassifier(loader)
    guidance_classifier = UsageGuidanceClassifier(loader)
    raw_text = "온수 히터 고장과 누수가 함께 발생했습니다."

    assessment = risk_classifier.classify(raw_text)
    guidance = guidance_classifier.determine_guidance(
        assessment,
        raw_text,
        has_evidence=False,
    )

    assert assessment.matched_safety_rule_ids == [
        "SAFETY-HOT-WATER-HEATER-001",
        "SAFETY-LEAK-001",
    ]
    assert assessment.requires_consultation is True
    assert guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP
    assert guidance.restricted_functions == rules["leak_danger"][
        "restricted_functions"
    ]
    SafetyRuleAlignmentValidator(loader).validate(assessment, guidance)


def test_explicitly_negated_fire_risk_keeps_hot_water_heater_partial_stop(
    risk_classifier,
    guidance_classifier,
):
    raw_text = "온수 히터 고장이지만 화재 위험은 없습니다."

    assessment = risk_classifier.classify(raw_text)
    guidance = guidance_classifier.determine_guidance(
        assessment,
        raw_text,
        has_evidence=False,
    )

    assert assessment.matched_safety_rule_ids == [
        "SAFETY-HOT-WATER-HEATER-001"
    ]
    assert assessment.requires_consultation is True
    assert guidance.guidance_status == UsageGuidanceStatus.PARTIAL_STOP


@pytest.mark.parametrize(
    "raw_text",
    [
        "온수 히터 고장은 아닙니다. 냉수가 약하게 나옵니다.",
        "온수 히터 이상은 없습니다. 출수량만 줄었습니다.",
        "온수 히터는 정상입니다. 필터를 확인하고 싶습니다.",
        "순간온수 모듈은 정상입니다. 소음만 확인해 주세요.",
    ],
)
def test_explicitly_negated_hot_water_heater_is_not_danger(
    risk_classifier,
    raw_text,
):
    assessment = risk_classifier.classify(raw_text)

    assert "SAFETY-HOT-WATER-HEATER-001" not in (
        assessment.matched_safety_rule_ids
    )
    assert assessment.risk_level != RiskLevel.DANGER


def test_prohibited_action_guard_blocks_disassembly():
    with pytest.raises(ValueError, match="직접 분해"):
        ProhibitedActionGuard().validate(["정수기 커버를 분해하세요."])
