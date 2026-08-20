"""A2A Safety Agent와 기존 RiskClassifier 사이의 Adapter."""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ...safety.risk_classifier import RiskClassifier
from ...schemas.safety import SafetyAssessment


# -------------------------------------------------------------------
# 1. 기존 Safety 구현이 지켜야 하는 최소 규칙
# -------------------------------------------------------------------
#
# A2A Adapter는 Safety 판정 규칙을 새로 만들지 않습니다.
#
# 현재 프로젝트에서 실제 Safety 판단은:
#
# RiskClassifier.classify(...)
#
# 가 담당합니다.
#
# 이 Protocol은 테스트에서 Fake Classifier를 넣을 수 있도록
# "classify 함수가 있어야 한다"는 최소 규칙만 정의합니다.
class SafetyClassifier(Protocol):
    def classify(
        self,
        raw_text: str,
        selected_symptoms: list[str] | None = None,
    ) -> SafetyAssessment:
        ...


# -------------------------------------------------------------------
# 2. A2A Safety Agent가 받을 요청 데이터
# -------------------------------------------------------------------
class SafetyA2ARequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # 하나의 고객 문의를 식별하는 ID
    inquiry_id: UUID

    # Backend → AI → Agent 사이에서 같은 요청인지 추적하는 ID
    correlation_id: UUID

    # 고객이 실제로 입력한 증상 문장
    raw_text: str = Field(
        ...,
        min_length=1,
        max_length=4000,
    )

    # 이미 구조화된 대표 증상
    selected_symptoms: list[str] = Field(
        default_factory=list,
        max_length=30,
    )

    # Backend Context에서 받은 정확한 판매 모델 코드
    #
    # 중요:
    # A2A에서 임의로 대문자 변환이나 다른 모델로 치환하지 않습니다.
    model_code: str = Field(
        ...,
        min_length=1,
        max_length=60,
    )

    # 현재 고객 제품군
    product_family: Literal[
        "DIRECT_WATER_PURIFIER",
        "ICE_WATER_PURIFIER",
        "UNKNOWN",
    ]

    # 제품이 실제로 지원하는 기능 목록
    #
    # 현재 RiskClassifier는 이 값을 직접 사용하지 않습니다.
    # 하지만 Safety Agent 간 계약에서 Product Context가
    # 유실되지 않도록 함께 전달합니다.
    supported_functions: list[str] = Field(
        default_factory=list,
        max_length=40,
    )


# -------------------------------------------------------------------
# 3. A2A Safety Agent가 반환할 데이터
# -------------------------------------------------------------------
class SafetyA2AResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    inquiry_id: UUID
    correlation_id: UUID

    # 요청에서 받은 정확한 제품 Context를 그대로 돌려줍니다.
    # 이를 통해 Orchestrator가 다른 문의/제품 응답이 섞이지 않았는지
    # 이후 단계에서 검증할 수 있습니다.
    model_code: str
    product_family: Literal[
        "DIRECT_WATER_PURIFIER",
        "ICE_WATER_PURIFIER",
        "UNKNOWN",
    ]

    # 실제 Safety 결과.
    #
    # 새 A2A 전용 Safety 결과를 만드는 것이 아니라
    # 기존 프로젝트의 SafetyAssessment를 그대로 재사용합니다.
    assessment: SafetyAssessment


# -------------------------------------------------------------------
# 4. 기존 RiskClassifier를 A2A 형태로 연결하는 Adapter
# -------------------------------------------------------------------
class SafetyA2AAdapter:
    """기존 RiskClassifier를 A2A Safety 계약으로 감싸는 Adapter."""

    def __init__(
        self,
        classifier: SafetyClassifier | None = None,
    ) -> None:
        # 실제 Runtime에서는 기존 RiskClassifier 사용
        #
        # 단위 테스트에서는 Fake Classifier를 주입할 수 있습니다.
        self.classifier = classifier or RiskClassifier()

    def execute(
        self,
        request: SafetyA2ARequest,
    ) -> SafetyA2AResponse:
        # Safety 판정은 기존 RiskClassifier에 그대로 위임합니다.
        #
        # A2A Adapter 내부에서:
        # - 위험 키워드 추가
        # - 위험도 재판정
        # - 임의 규칙 추가
        #
        # 를 하지 않습니다.
        assessment = self.classifier.classify(
            raw_text=request.raw_text,
            selected_symptoms=request.selected_symptoms,
        )

        return SafetyA2AResponse(
            inquiry_id=request.inquiry_id,
            correlation_id=request.correlation_id,

            # Backend Context에서 받은 model_code를 변경하지 않습니다.
            model_code=request.model_code,

            product_family=request.product_family,
            assessment=assessment,
        )
