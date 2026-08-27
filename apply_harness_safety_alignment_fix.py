from pathlib import Path

ROOT = Path.cwd()
VERIFIER = ROOT / "ai/app/orchestration/harness/verifier.py"
TESTS = ROOT / "ai/tests/unit/harness/test_harness_runner.py"

for path in (VERIFIER, TESTS):
    if not path.exists():
        raise SystemExit(f"[ERROR] repo root에서 실행하세요. 파일 없음: {path}")

verifier = VERIFIER.read_text(encoding="utf-8")
tests = TESTS.read_text(encoding="utf-8")

if "SafetyRuleAlignmentValidator().validate(" in verifier:
    raise SystemExit("[INFO] Harness alignment fix가 이미 적용되어 있습니다.")

old_imports = '''from ...retrieval.models.retrieved_chunk import RetrievedChunk
from ...safety.rule_loader import SafetyRuleLoader
from ...schemas import RiskLevel, SafetyAssessment, UsageGuidance, UsageGuidanceStatus
'''
new_imports = '''from ...retrieval.models.retrieved_chunk import RetrievedChunk
from ...schemas import RiskLevel, SafetyAssessment, UsageGuidance
from ...validation.safety import SafetyRuleAlignmentValidator
'''
if old_imports not in verifier:
    raise SystemExit("[ERROR] verifier import block이 최신 main 예상 형태와 다릅니다.")
verifier = verifier.replace(old_imports, new_imports, 1)

old_safety_block = '''    @staticmethod
    def _safety_is_consistent(
        safety_assessment: SafetyAssessment | None,
        guidance: UsageGuidance | None,
    ) -> bool:
        if safety_assessment is None or guidance is None:
            return True
        if safety_assessment.risk_level == RiskLevel.DANGER:
            if guidance.guidance_status == UsageGuidanceStatus.NORMAL:
                return False
            if guidance.guidance_status in {
                UsageGuidanceStatus.TOTAL_STOP,
                UsageGuidanceStatus.PENDING_CONSULTATION,
            }:
                return True
            if guidance.guidance_status == UsageGuidanceStatus.PARTIAL_STOP:
                return HarnessVerifier._danger_partial_stop_is_approved(
                    safety_assessment
                )
            return False
        return True

    @staticmethod
    def _danger_partial_stop_is_approved(
        safety_assessment: SafetyAssessment,
    ) -> bool:
        if not safety_assessment.requires_consultation:
            return False

        matched_rule_ids = set(safety_assessment.matched_safety_rule_ids)
        if not matched_rule_ids:
            return False

        rules = SafetyRuleLoader().get_safety_rules().get("rules", {})
        # UsageGuidanceClassifier와 동일하게 safety_rules.yaml의 선언 순서에서
        # 첫 번째로 매칭되는 승인 Rule을 기준으로 Safety 정합성을 판정한다.
        for rule_def in rules.values():
            if rule_def.get("rule_id") not in matched_rule_ids:
                continue
            return (
                rule_def.get("risk_level") == RiskLevel.DANGER.value
                and rule_def.get("usage_guidance_status")
                == UsageGuidanceStatus.PARTIAL_STOP.value
                and rule_def.get("requires_consultation") is True
            )
        return False

'''
new_safety_block = '''    @staticmethod
    def _safety_is_consistent(
        safety_assessment: SafetyAssessment | None,
        guidance: UsageGuidance | None,
    ) -> bool:
        if safety_assessment is None or guidance is None:
            return True
        try:
            SafetyRuleAlignmentValidator().validate(
                safety_assessment,
                guidance,
            )
        except ValueError:
            return False
        return True

'''
if old_safety_block not in verifier:
    raise SystemExit("[ERROR] verifier safety block이 최신 main 예상 형태와 다릅니다.")
verifier = verifier.replace(old_safety_block, new_safety_block, 1)

if "import pytest\n" not in tests:
    tests = tests.replace(
        "from pydantic import BaseModel\n",
        "import pytest\n\nfrom pydantic import BaseModel\n",
        1,
    )

if "from ai.app.safety.rule_loader import SafetyRuleLoader\n" not in tests:
    tests = tests.replace(
        "from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk\n",
        "from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk\n"
        "from ai.app.safety.rule_loader import SafetyRuleLoader\n",
        1,
    )

old_exact_test = '''def test_approved_danger_partial_stop_rule_passes():
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=["SAFETY-HOT-WATER-HEATER-001"],
        detected_risks=["온수 히터·순간온수 모듈 고장 및 음용 제한"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.PARTIAL_STOP,
        message="위험 신호가 감지되어 온수 기능 사용 제한이 필요합니다.",
        restricted_functions=["온수 출수 및 음용 중지"],
        next_actions=["전문 상담 및 기사 점검을 요청하세요."],
    )

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert result.decision == HarnessDecision.PASS
    assert result.verification.passed is True
    assert result.verification.safety_valid is True
    assert not any(
        issue.code.value == "SAFETY_CONFLICT"
        for issue in result.verification.issues
    )


'''
new_tests = '''def test_approved_danger_partial_stop_rule_passes():
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=["SAFETY-HOT-WATER-HEATER-001"],
        detected_risks=["온수 히터·순간온수 모듈 고장 및 음용 제한"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.PARTIAL_STOP,
        message="위험 신호가 감지되어 온수 기능 사용 제한이 필요합니다.",
        restricted_functions=["온수 출수 및 음용 중지"],
        next_actions=[
            "온수 기능 사용과 온수 음용을 중단하세요.",
            "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
        ],
    )

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert result.decision == HarnessDecision.PASS
    assert result.verification.passed is True
    assert result.verification.safety_valid is True
    assert not any(
        issue.code.value == "SAFETY_CONFLICT"
        for issue in result.verification.issues
    )


@pytest.mark.parametrize(
    ("restricted_functions", "next_actions"),
    [
        (
            ["제품 전체 기능 사용 중지"],
            [
                "온수 기능 사용과 온수 음용을 중단하세요.",
                "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
            ],
        ),
        (
            ["온수 출수 및 음용 중지"],
            ["전문 상담 및 기사 점검을 요청하세요."],
        ),
    ],
)
def test_danger_partial_stop_with_wrong_rule_body_escalates(
    restricted_functions,
    next_actions,
):
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=["SAFETY-HOT-WATER-HEATER-001"],
        detected_risks=["온수 히터 이상"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.PARTIAL_STOP,
        message="안내",
        restricted_functions=restricted_functions,
        next_actions=next_actions,
    )

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert result.decision == HarnessDecision.ESCALATE
    assert result.verification.safety_valid is False
    assert any(
        issue.code.value == "SAFETY_CONFLICT"
        for issue in result.verification.issues
    )


@pytest.mark.parametrize(
    "rule_ids",
    [
        ["SAFETY-NOT-REGISTERED-999"],
        [],
    ],
)
def test_danger_with_unknown_or_empty_rule_escalates(rule_ids):
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=rule_ids,
        detected_risks=["위험"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.TOTAL_STOP,
        message="안내",
        restricted_functions=["제품 전체 기능 사용 중지"],
        next_actions=["전문 상담 및 기사 점검을 요청하세요."],
    )

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert result.decision == HarnessDecision.ESCALATE
    assert result.verification.safety_valid is False
    assert any(
        issue.code.value == "SAFETY_CONFLICT"
        for issue in result.verification.issues
    )


@pytest.mark.parametrize(
    "strong_rule_id",
    [
        "SAFETY-LEAK-001",
        "SAFETY-ELECTRICAL-001",
    ],
)
def test_heater_plus_total_stop_danger_rejects_partial_stop(strong_rule_id):
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=[
            "SAFETY-HOT-WATER-HEATER-001",
            strong_rule_id,
        ],
        detected_risks=["온수 히터 이상", "추가 중대 위험"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.PARTIAL_STOP,
        message="안내",
        restricted_functions=["온수 출수 및 음용 중지"],
        next_actions=[
            "온수 기능 사용과 온수 음용을 중단하세요.",
            "제품을 직접 분해하지 말고 전문 상담 및 기사 점검을 요청하세요.",
        ],
    )

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert result.decision == HarnessDecision.ESCALATE
    assert result.verification.safety_valid is False
    assert any(
        issue.code.value == "SAFETY_CONFLICT"
        for issue in result.verification.issues
    )


def test_heater_plus_leak_with_exact_total_stop_passes():
    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=[
            "SAFETY-HOT-WATER-HEATER-001",
            "SAFETY-LEAK-001",
        ],
        detected_risks=["온수 히터 이상", "누수"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.TOTAL_STOP,
        message="안내",
        restricted_functions=[
            "전체 출수 기능 중지",
            "제품 전원 차단 필요",
        ],
        next_actions=[
            "즉시 원수 공급 밸브(원수 밸브)를 잠그세요.",
            "젖은 손으로 전원 플러그를 만지지 마시고, 안전할 때 전원을 차단해 주세요.",
            "전문 기사 방문 점검을 요청하세요.",
        ],
    )

    result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert result.decision == HarnessDecision.PASS
    assert result.verification.passed is True
    assert result.verification.safety_valid is True


def test_danger_alignment_is_independent_of_yaml_rule_order(monkeypatch):
    original = SafetyRuleLoader().get_safety_rules()
    reordered = dict(original)
    reordered["rules"] = dict(
        reversed(list(original["rules"].items()))
    )

    safety = SafetyAssessment(
        risk_level=RiskLevel.DANGER,
        priority=SafetyPriority.PRIORITY_CONSULTATION,
        requires_consultation=True,
        matched_safety_rule_ids=[
            "SAFETY-HOT-WATER-HEATER-001",
            "SAFETY-LEAK-001",
        ],
        detected_risks=["온수 히터 이상", "누수"],
        safety_reason="test",
    )
    guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.TOTAL_STOP,
        message="안내",
        restricted_functions=[
            "전체 출수 기능 중지",
            "제품 전원 차단 필요",
        ],
        next_actions=[
            "즉시 원수 공급 밸브(원수 밸브)를 잠그세요.",
            "젖은 손으로 전원 플러그를 만지지 마시고, 안전할 때 전원을 차단해 주세요.",
            "전문 기사 방문 점검을 요청하세요.",
        ],
    )

    baseline = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )
    monkeypatch.setattr(
        SafetyRuleLoader,
        "get_safety_rules",
        lambda self: reordered,
    )
    reordered_result = HarnessRunner().run(
        product=_product(),
        evidence_chunks=[],
        safety_assessment=safety,
        guidance=guidance,
    )

    assert baseline.decision == HarnessDecision.PASS
    assert reordered_result.decision == baseline.decision
    assert reordered_result.verification.safety_valid is True


'''
if old_exact_test not in tests:
    raise SystemExit("[ERROR] 기존 heater PARTIAL_STOP 테스트가 최신 main 예상 형태와 다릅니다.")
tests = tests.replace(old_exact_test, new_tests, 1)

VERIFIER.write_text(verifier, encoding="utf-8")
TESTS.write_text(tests, encoding="utf-8")

print("[OK] modified:")
print(" - ai/app/orchestration/harness/verifier.py")
print(" - ai/tests/unit/harness/test_harness_runner.py")
print()
print("다음으로 git diff --check 및 Harness 표적 테스트를 실행하세요.")
