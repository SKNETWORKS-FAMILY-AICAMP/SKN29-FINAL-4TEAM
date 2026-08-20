from __future__ import annotations

# Protocol은
# "이 기능을 사용하려면 최소한 이런 함수가 있어야 한다"
# 라는 규칙을 만들 때 사용합니다.
from typing import Protocol

# inquiry_id와 correlation_id는 UUID 형식이므로 가져옵니다.
from uuid import UUID

# Pydantic은 들어오는 데이터가 우리가 정한 형식에 맞는지 검사합니다.
from pydantic import BaseModel, ConfigDict, Field

# 요청한 문의와 Backend가 반환한 문의가 다른 경우 사용하는 오류입니다.
from app.integrations.mcp.errors import MCPContextMismatchError

# 제품 종류를 나타내는 공통 Enum입니다.
#
# 예:
# DIRECT_WATER_PURIFIER
# ICE_WATER_PURIFIER
from app.orchestration.harness.product_match import ProductFamily

# 해당 제품이 현재 AI Runtime 검색 대상으로 승인되어 있는지
# 확인하는 기존 함수를 재사용합니다.
from app.orchestration.harness.product_registry import (
    is_runtime_approved_model_code,
)


# -------------------------------------------------------------------
# 1. 고객이 이전 문진에서 입력한 답변 하나의 형태
# -------------------------------------------------------------------


class InquiryAnswer(BaseModel):
    # 정의하지 않은 이상한 필드가 들어오면 거부합니다.
    #
    # 예:
    # {"question_id": "...", "answer_text": "...", "unknown": "..."}
    #                                              ↑
    #                                     이런 값은 허용하지 않음
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # 어떤 질문에 대한 답변인지 구분하는 ID
    question_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    # 고객이 실제로 입력하거나 선택한 답변
    answer_text: str = Field(
        ...,
        min_length=1,
        max_length=1000,
    )


# -------------------------------------------------------------------
# 2. Backend 내부 API에서 받아올 문의 Context 형태
# -------------------------------------------------------------------


class BackendInquiryContext(BaseModel):
    # Backend에서 예상하지 못한 필드가 들어오는 것을 막습니다.
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # 현재 문의를 구분하는 고유 ID
    inquiry_id: UUID

    # Mobile → Backend → AI 전체 요청을 추적할 때 사용하는 ID
    #
    # 장애가 발생했을 때
    # "이 요청이 어디까지 처리됐는가?"
    # 를 추적하는 데 사용됩니다.
    correlation_id: UUID

    # 고객이 사용 중인 정확한 제품 판매 코드
    #
    # 예:
    # WPUJAC104DWH
    model_code: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    # 제품 종류
    #
    # 예:
    # DIRECT_WATER_PURIFIER
    product_family: ProductFamily

    # 해당 제품에서 지원하는 기능
    #
    # 예:
    # {"cold_water", "hot_water"}
    supported_functions: set[str] = Field(
        default_factory=set,
    )

    # 이전에 고객이 답변한 문진 정보
    previous_answers: list[InquiryAnswer] = Field(
        default_factory=list,
    )

    # 아래 값들은 현재 Backend→AI 계약에는 존재하지만,
    # 아직 새 내부 MCP Context API의 최종 응답 계약이
    # 확정되지 않았으므로 Optional로 둡니다.

    # 문의 상태의 버전 번호
    #
    # 동시에 여러 요청이 처리될 때
    # 오래된 상태를 잘못 사용하는 것을 방지하는 데 사용할 수 있습니다.
    state_version: int | None = Field(
        default=None,
        ge=1,
    )

    # 고객이 처음 작성한 증상 문장
    #
    # 예:
    # "정수기 물에서 이상한 냄새가 나요."
    raw_symptom: str | None = Field(
        default=None,
        max_length=4000,
    )

    # 이미 분류된 대표 증상
    #
    # 예:
    # ["물맛/냄새 이상"]
    selected_symptoms: list[str] = Field(
        default_factory=list,
    )


# -------------------------------------------------------------------
# 3. 문의 정보를 읽어오는 객체가 지켜야 할 규칙
# -------------------------------------------------------------------


class InquiryContextReader(Protocol):
    # 쉽게 말하면:
    #
    # "누가 실제 Backend와 연결되든 상관없지만
    # get_inquiry_context() 함수는 반드시 가지고 있어야 한다."
    #
    # 라는 규칙입니다.
    #
    # 현재 테스트:
    # FakeInquiryContextReader
    #
    # 나중 실제 환경:
    # BackendContextClient
    def get_inquiry_context(
        self,
        inquiry_id: UUID,
    ) -> BackendInquiryContext:
        ...


# -------------------------------------------------------------------
# 4. MCP get_inquiry_context가 받는 입력
# -------------------------------------------------------------------


class GetInquiryContextInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    # MCP에서는 문의 ID 하나를 받아
    # 해당 문의의 Context 전체를 조회합니다.
    inquiry_id: UUID


# -------------------------------------------------------------------
# 5. MCP가 최종적으로 반환하는 데이터
# -------------------------------------------------------------------


class GetInquiryContextOutput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    inquiry_id: UUID

    correlation_id: UUID

    model_code: str

    product_family: ProductFamily

    # MCP 결과에서는 JSON으로 전달하기 편하게
    # set이 아니라 정렬된 list로 반환합니다.
    supported_functions: list[str] = Field(
        default_factory=list,
    )

    previous_answers: list[InquiryAnswer] = Field(
        default_factory=list,
    )

    state_version: int | None = None

    raw_symptom: str | None = None

    selected_symptoms: list[str] = Field(
        default_factory=list,
    )

    # Backend가 결정하는 값이 아닙니다.
    #
    # "현재 이 제품을 AI 검색 Runtime에서 사용할 수 있는가?"
    # 는 AI 정책이 결정합니다.
    runtime_approved: bool


# -------------------------------------------------------------------
# 6. Backend 데이터를 MCP 결과로 바꾸는 Adapter
# -------------------------------------------------------------------


class GetInquiryContextAdapter:
    # Adapter는 쉽게 말하면 "번역기"입니다.
    #
    # Backend에서 받은 데이터
    # ↓
    # Adapter
    # ↓
    # MCP가 사용하는 데이터
    #
    # 로 변환합니다.

    def __init__(
        self,
        context_reader: InquiryContextReader,
    ) -> None:
        self.context_reader = context_reader

    def execute(
        self,
        request: GetInquiryContextInput,
    ) -> GetInquiryContextOutput:

        # Reader에게 실제 문의 정보를 요청합니다.
        context = self.context_reader.get_inquiry_context(
            request.inquiry_id
        )

        # -----------------------------------------------------------
        # 중요한 Fail-closed 검사
        # -----------------------------------------------------------
        #
        # 예를 들어:
        #
        # 요청한 문의
        # inquiry-A
        #
        # Backend가 반환한 문의
        # inquiry-B
        #
        # 라면 잘못된 고객 문의 정보를 사용하는 것이므로
        # 즉시 중단해야 합니다.
        if context.inquiry_id != request.inquiry_id:
        # inquiry_id가 다르면 다른 문의 정보가 섞였을 가능성이 있으므로
        # 해당 Context를 절대 사용하지 않습니다.
            raise MCPContextMismatchError(
                "Backend Inquiry Context의 inquiry_id가 "
                "요청한 inquiry_id와 일치하지 않습니다."
            )

        # 모델 코드는 앞뒤 공백을 제거하고
        # 대문자로 통일합니다.
        #
        # wpujac104dwh
        # ↓
        # WPUJAC104DWH
        model_code = context.model_code.strip().upper()

        # Backend Context를 MCP Output 형식으로 변환합니다.
        return GetInquiryContextOutput(
            inquiry_id=context.inquiry_id,
            correlation_id=context.correlation_id,
            model_code=model_code,
            product_family=context.product_family,

            # set은 순서가 일정하지 않을 수 있으므로
            # MCP에서는 정렬된 list로 반환합니다.
            supported_functions=sorted(
                context.supported_functions
            ),

            previous_answers=context.previous_answers,
            state_version=context.state_version,
            raw_symptom=context.raw_symptom,
            selected_symptoms=context.selected_symptoms,

            # Runtime 사용 가능 여부는
            # Backend가 아니라 기존 AI 정책을 이용해서 판단합니다.
            runtime_approved=(
                is_runtime_approved_model_code(
                    model_code
                )
            ),
        )