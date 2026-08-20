from uuid import UUID

import pytest

from app.integrations.mcp.errors import MCPContextMismatchError

from app.integrations.mcp.tools.get_inquiry_context import (
    BackendInquiryContext,
    GetInquiryContextAdapter,
    GetInquiryContextInput,
    InquiryAnswer,
)
from app.orchestration.harness.product_match import ProductFamily


# -------------------------------------------------------------------
# 실제 Backend 대신 사용하는 테스트용 가짜 Reader
# -------------------------------------------------------------------


class FakeInquiryContextReader:
    # 실제 HTTP 요청을 하지 않고
    # 미리 준비해둔 데이터를 반환합니다.
    #
    # 따라서 Backend가 아직 완성되지 않아도
    # MCP Adapter만 독립적으로 테스트할 수 있습니다.

    def __init__(
        self,
        context: BackendInquiryContext,
    ) -> None:
        self.context = context

        # Adapter가 실제로 어떤 inquiry_id를 전달했는지
        # 확인하기 위해 저장합니다.
        self.called_inquiry_id: UUID | None = None

    def get_inquiry_context(
        self,
        inquiry_id: UUID,
    ) -> BackendInquiryContext:
        self.called_inquiry_id = inquiry_id
        return self.context


def test_get_inquiry_context_success():
    # 정상 문의 Context를 준비합니다.

    inquiry_id = UUID(
        "11111111-1111-1111-1111-111111111111"
    )

    correlation_id = UUID(
        "22222222-2222-2222-2222-222222222222"
    )

    reader = FakeInquiryContextReader(
        BackendInquiryContext(
            inquiry_id=inquiry_id,
            correlation_id=correlation_id,
            model_code="WPUJAC104DWH",
            product_family=(
                ProductFamily.DIRECT_WATER_PURIFIER
            ),
            supported_functions={
                "hot_water",
                "cold_water",
            },
            previous_answers=[
                InquiryAnswer(
                    question_id="followup-001",
                    answer_text="10일 이내 부재 후",
                )
            ],
            state_version=3,
            raw_symptom="물에서 냄새가 나요.",
            selected_symptoms=[
                "물맛/냄새 이상",
            ],
        )
    )

    adapter = GetInquiryContextAdapter(reader)

    result = adapter.execute(
        GetInquiryContextInput(
            inquiry_id=inquiry_id,
        )
    )

    # Adapter가 요청한 inquiry_id를
    # Reader에게 정확히 전달했는지 확인합니다.
    assert reader.called_inquiry_id == inquiry_id

    # 반환된 문의 ID 확인
    assert result.inquiry_id == inquiry_id

    # 추적 ID 확인
    assert result.correlation_id == correlation_id

    # 제품 코드 확인
    assert result.model_code == "WPUJAC104DWH"

    # 지원 기능은 정렬되어 반환되어야 합니다.
    assert result.supported_functions == [
        "cold_water",
        "hot_water",
    ]

    # JAC104는 현재 AI Runtime 승인 모델입니다.
    assert result.runtime_approved is True

    # 이전 문진 답변도 유지되어야 합니다.
    assert len(result.previous_answers) == 1

    assert (
        result.previous_answers[0].question_id
        == "followup-001"
    )


def test_iac425_context_is_runtime_hold():
    # 제품 정보 자체는 존재하지만
    # AI Runtime 검색에서는 HOLD인 경우를 확인합니다.

    inquiry_id = UUID(
        "33333333-3333-3333-3333-333333333333"
    )

    reader = FakeInquiryContextReader(
        BackendInquiryContext(
            inquiry_id=inquiry_id,
            correlation_id=UUID(
                "44444444-4444-4444-4444-444444444444"
            ),
            model_code="WPUIAC425SNW",
            product_family=(
                ProductFamily.ICE_WATER_PURIFIER
            ),
            supported_functions={
                "ice",
                "cold_water",
            },
        )
    )

    adapter = GetInquiryContextAdapter(reader)

    result = adapter.execute(
        GetInquiryContextInput(
            inquiry_id=inquiry_id,
        )
    )

    # 제품 Context 조회 성공과
    # AI 검색 허용 여부는 서로 다른 문제입니다.
    assert result.model_code == "WPUIAC425SNW"

    assert result.runtime_approved is False


def test_model_code_is_normalized():
    # Backend가 모델 코드를 소문자나 공백 포함 형태로 보내더라도
    # MCP Output에서는 정확한 형태로 정규화하는지 확인합니다.

    inquiry_id = UUID(
        "55555555-5555-5555-5555-555555555555"
    )

    reader = FakeInquiryContextReader(
        BackendInquiryContext(
            inquiry_id=inquiry_id,
            correlation_id=UUID(
                "66666666-6666-6666-6666-666666666666"
            ),
            model_code="  wpujac104dwh  ",
            product_family=(
                ProductFamily.DIRECT_WATER_PURIFIER
            ),
        )
    )

    adapter = GetInquiryContextAdapter(reader)

    result = adapter.execute(
        GetInquiryContextInput(
            inquiry_id=inquiry_id,
        )
    )

    assert result.model_code == "WPUJAC104DWH"

    assert result.runtime_approved is True


def test_wrong_inquiry_id_fails_closed():
    # inquiry-A를 요청했는데
    # Backend가 inquiry-B 데이터를 반환하는 상황입니다.
    #
    # 다른 고객/문의 Context가 섞일 수 있으므로
    # 반드시 실패해야 합니다.

    requested_inquiry_id = UUID(
        "77777777-7777-7777-7777-777777777777"
    )

    wrong_inquiry_id = UUID(
        "88888888-8888-8888-8888-888888888888"
    )

    reader = FakeInquiryContextReader(
        BackendInquiryContext(
            inquiry_id=wrong_inquiry_id,
            correlation_id=UUID(
                "99999999-9999-9999-9999-999999999999"
            ),
            model_code="WPUJAC104DWH",
            product_family=(
                ProductFamily.DIRECT_WATER_PURIFIER
            ),
        )
    )

    adapter = GetInquiryContextAdapter(reader)

    with pytest.raises(
        MCPContextMismatchError,
        match="inquiry_id",
    ):
        adapter.execute(
            GetInquiryContextInput(
                inquiry_id=requested_inquiry_id,
            )
        )