"""A2A Safety Adapter 단위 테스트."""

from uuid import UUID

from ai.app.integrations.a2a.safety_adapter import (
    SafetyA2AAdapter,
    SafetyA2ARequest,
)
from ai.app.schemas.common import RiskLevel, SafetyPriority
from ai.app.schemas.safety import SafetyAssessment


class FakeSafetyClassifier:
    """
    실제 Safety 규칙 대신 테스트에서 사용하는 가짜 Classifier.

    Adapter가 기존 Classifier에 어떤 데이터를 넘겼는지 확인하기 위한 용도입니다.
    """

    def __init__(self) -> None:
        self.called_raw_text: str | None = None
        self.called_selected_symptoms: list[str] | None = None

    def classify(
        self,
        raw_text: str,
        selected_symptoms: list[str] | None = None,
    ) -> SafetyAssessment:
        self.called_raw_text = raw_text
        self.called_selected_symptoms = selected_symptoms

        return SafetyAssessment(
            risk_level=RiskLevel.GENERAL,
            priority=SafetyPriority.GENERAL_GUIDANCE,
            requires_consultation=False,
            matched_safety_rule_ids=[],
            detected_risks=[],
            safety_reason="테스트용 일반 Safety 결과",
        )


def test_safety_adapter_reuses_existing_classifier_and_preserves_context():
    inquiry_id = UUID(
        "11111111-1111-4111-8111-111111111111"
    )
    correlation_id = UUID(
        "22222222-2222-4222-8222-222222222222"
    )

    classifier = FakeSafetyClassifier()
    adapter = SafetyA2AAdapter(
        classifier=classifier,
    )

    result = adapter.execute(
        SafetyA2ARequest(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
            raw_text="정수기 냉수가 미지근합니다.",
            selected_symptoms=[
                "COLD_WATER_TEMPERATURE",
            ],
            model_code="WPUJAC104DWH",
            product_family="DIRECT_WATER_PURIFIER",
            supported_functions=[
                "COLD_WATER",
            ],
        )
    )

    # ---------------------------------------------------------------
    # 기존 Safety Classifier 호출 여부
    # ---------------------------------------------------------------
    assert classifier.called_raw_text == (
        "정수기 냉수가 미지근합니다."
    )

    assert classifier.called_selected_symptoms == [
        "COLD_WATER_TEMPERATURE",
    ]

    # ---------------------------------------------------------------
    # Inquiry / Correlation Identity 보존
    # ---------------------------------------------------------------
    assert result.inquiry_id == inquiry_id
    assert result.correlation_id == correlation_id

    # ---------------------------------------------------------------
    # Backend에서 받은 model_code를 임의로 변경하지 않아야 함
    # ---------------------------------------------------------------
    assert result.model_code == "WPUJAC104DWH"

    assert (
        result.product_family
        == "DIRECT_WATER_PURIFIER"
    )

    # ---------------------------------------------------------------
    # 기존 SafetyAssessment를 그대로 반환
    # ---------------------------------------------------------------
    assert (
        result.assessment.risk_level
        == RiskLevel.GENERAL
    )

    assert result.assessment.requires_consultation is False


def test_safety_adapter_uses_real_risk_classifier():
    """
    Adapter가 실제 RiskClassifier와도 연결되는지 확인합니다.

    구체적인 위험 키워드 정책 자체는 기존 Safety 테스트의 책임이고,
    여기서는 A2A Adapter가 실제 Classifier를 실행할 수 있는지만 봅니다.
    """

    adapter = SafetyA2AAdapter()

    result = adapter.execute(
        SafetyA2ARequest(
            inquiry_id=UUID(
                "33333333-3333-4333-8333-333333333333"
            ),
            correlation_id=UUID(
                "44444444-4444-4444-8444-444444444444"
            ),
            raw_text="정수기 물이 잘 나오지 않습니다.",
            selected_symptoms=[
                "LOW_FLOW",
            ],
            model_code="WPUJAC104DWH",
            product_family="DIRECT_WATER_PURIFIER",
            supported_functions=[
                "COLD_WATER",
            ],
        )
    )

    assert isinstance(
        result.assessment,
        SafetyAssessment,
    )

    assert result.model_code == "WPUJAC104DWH"
