"""안전 분류기 및 가드레일 단위 테스트."""

import pytest
from ai.app.schemas import RiskLevel, UsageGuidanceStatus
from ai.app.safety import RiskClassifier, UsageGuidanceClassifier
from ai.app.safety import ProhibitedActionGuard
from ai.app.validation.safety import ProhibitedPhraseValidator


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


def test_no_evidence_fallback(risk_classifier, guidance_classifier):
    """공식 매뉴얼 근거 부족 시 PENDING_CONSULTATION 판정 테스트"""
    raw_text = "특이한 사용법을 알려주세요."
    assessment = risk_classifier.classify(raw_text)

    # 근거가 없는 경우 (has_evidence=False)
    guidance = guidance_classifier.determine_guidance(assessment, raw_text, has_evidence=False)
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


def test_prohibited_action_guard_blocks_disassembly():
    with pytest.raises(ValueError, match="직접 분해"):
        ProhibitedActionGuard().validate(["정수기 커버를 분해하세요."])
