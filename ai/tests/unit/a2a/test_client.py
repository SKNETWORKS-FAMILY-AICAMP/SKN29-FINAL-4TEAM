"""A2A Safety Client와 Local fallback 테스트."""

import asyncio
from uuid import UUID

from ai.app.integrations.a2a.client import (
    A2ASafetyFailureKind,
    WaterBridgeA2ASafetyClient,
)
from ai.app.integrations.a2a.safety_adapter import (
    SafetyA2AAdapter,
    SafetyA2ARequest,
    SafetyA2AResponse,
)
from ai.app.schemas.common import (
    RiskLevel,
    SafetyPriority,
)
from ai.app.schemas.safety import SafetyAssessment


INQUIRY_ID = UUID(
    "11111111-1111-4111-8111-111111111111"
)
CORRELATION_ID = UUID(
    "22222222-2222-4222-8222-222222222222"
)


def _request() -> SafetyA2ARequest:
    return SafetyA2ARequest(
        inquiry_id=INQUIRY_ID,
        correlation_id=CORRELATION_ID,
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


def _assessment(
    reason: str,
) -> SafetyAssessment:
    return SafetyAssessment(
        risk_level=RiskLevel.GENERAL,
        priority=SafetyPriority.GENERAL_GUIDANCE,
        requires_consultation=False,
        matched_safety_rule_ids=[],
        detected_risks=[],
        safety_reason=reason,
    )


class FakeLocalClassifier:
    def __init__(self) -> None:
        self.calls = 0

    def classify(
        self,
        raw_text: str,
        selected_symptoms: list[str] | None = None,
    ) -> SafetyAssessment:
        self.calls += 1
        return _assessment("LOCAL")


class SuccessfulRemote:
    async def execute(
        self,
        request: SafetyA2ARequest,
    ) -> SafetyA2AResponse:
        return SafetyA2AResponse(
            inquiry_id=request.inquiry_id,
            correlation_id=request.correlation_id,
            model_code=request.model_code,
            product_family=request.product_family,
            assessment=_assessment("REMOTE"),
        )


class TimeoutRemote:
    async def execute(
        self,
        request: SafetyA2ARequest,
    ) -> SafetyA2AResponse:
        await asyncio.sleep(0.2)
        raise AssertionError(
            "timeout 뒤에는 여기까지 도달하면 안 됩니다."
        )


class WrongModelRemote:
    async def execute(
        self,
        request: SafetyA2ARequest,
    ) -> SafetyA2AResponse:
        return SafetyA2AResponse(
            inquiry_id=request.inquiry_id,
            correlation_id=request.correlation_id,
            model_code="WPUIAC606SNW",
            product_family=request.product_family,
            assessment=_assessment("WRONG REMOTE"),
        )


def test_remote_success_does_not_use_local_fallback():
    local_classifier = FakeLocalClassifier()

    client = WaterBridgeA2ASafetyClient(
        remote_transport=SuccessfulRemote(),
        local_adapter=SafetyA2AAdapter(
            classifier=local_classifier,
        ),
        timeout_seconds=1,
    )

    result = asyncio.run(
        client.assess(_request())
    )

    assert result.used_local_fallback is False
    assert result.failure_kind is None
    assert result.response.model_code == (
        "WPUJAC104DWH"
    )
    assert result.response.assessment.safety_reason == (
        "REMOTE"
    )

    # Remote 성공 시 Local RiskClassifier는 호출하지 않아야 함
    assert local_classifier.calls == 0


def test_remote_timeout_uses_existing_local_safety():
    local_classifier = FakeLocalClassifier()

    client = WaterBridgeA2ASafetyClient(
        remote_transport=TimeoutRemote(),
        local_adapter=SafetyA2AAdapter(
            classifier=local_classifier,
        ),
        timeout_seconds=0.01,
    )

    result = asyncio.run(
        client.assess(_request())
    )

    assert result.used_local_fallback is True
    assert result.failure_kind == (
        A2ASafetyFailureKind.TIMEOUT
    )

    assert result.response.model_code == (
        "WPUJAC104DWH"
    )

    assert result.response.assessment.safety_reason == (
        "LOCAL"
    )

    assert local_classifier.calls == 1


def test_wrong_model_remote_response_falls_back_locally():
    local_classifier = FakeLocalClassifier()

    client = WaterBridgeA2ASafetyClient(
        remote_transport=WrongModelRemote(),
        local_adapter=SafetyA2AAdapter(
            classifier=local_classifier,
        ),
        timeout_seconds=1,
    )

    result = asyncio.run(
        client.assess(_request())
    )

    # 다른 제품의 Remote Safety 결과를 사용하면 안 됨
    assert result.used_local_fallback is True

    assert result.failure_kind == (
        A2ASafetyFailureKind.INVALID_RESPONSE
    )

    # 최종 결과는 원래 Backend Context 제품을 유지
    assert result.response.model_code == (
        "WPUJAC104DWH"
    )

    assert result.response.assessment.safety_reason == (
        "LOCAL"
    )

    assert local_classifier.calls == 1


def test_missing_remote_configuration_uses_local_safety():
    local_classifier = FakeLocalClassifier()

    client = WaterBridgeA2ASafetyClient(
        remote_transport=None,
        local_adapter=SafetyA2AAdapter(
            classifier=local_classifier,
        ),
    )

    result = asyncio.run(
        client.assess(_request())
    )

    assert result.used_local_fallback is True
    assert result.failure_kind == (
        A2ASafetyFailureKind.CONFIGURATION
    )

    assert local_classifier.calls == 1
