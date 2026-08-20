import pytest

from ai.app.integrations.mcp.errors import MCPContextMismatchError

from ai.app.integrations.mcp.tools.lookup_product_context import (
    BackendProductContext,
    LookupProductContextAdapter,
    LookupProductContextInput,
)
from ai.app.orchestration.harness.product_match import ProductFamily


class FakeProductContextReader:
    """
    실제 Backend API 대신 사용하는 테스트용 가짜 Reader.
    """

    def __init__(
        self,
        product: BackendProductContext,
    ) -> None:
        self.product = product
        self.called_model_code: str | None = None

    def get_product_context(
        self,
        model_code: str,
    ) -> BackendProductContext:
        self.called_model_code = model_code
        return self.product


def test_lookup_jac104_product_context():
    """
    JAC104 제품 정보를 정상적으로 MCP Output으로 변환한다.
    """

    reader = FakeProductContextReader(
        BackendProductContext(
            model_code="WPUJAC104DWH",
            product_family=(
                ProductFamily.DIRECT_WATER_PURIFIER
            ),
            supported_functions={
                "hot_water",
                "cold_water",
            },
        )
    )

    adapter = LookupProductContextAdapter(reader)

    result = adapter.execute(
        LookupProductContextInput(
            model_code="WPUJAC104DWH",
        )
    )

    assert reader.called_model_code == "WPUJAC104DWH"

    assert result.model_code == "WPUJAC104DWH"

    assert (
        result.product_family
        == ProductFamily.DIRECT_WATER_PURIFIER
    )

    assert result.supported_functions == [
        "cold_water",
        "hot_water",
    ]

    assert result.runtime_approved is True


def test_lookup_iac425_is_runtime_hold():
    """
    제품은 존재하지만 현재 AI Runtime에서는
    HOLD 상태인 경우를 구분한다.
    """

    reader = FakeProductContextReader(
        BackendProductContext(
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

    adapter = LookupProductContextAdapter(reader)

    result = adapter.execute(
        LookupProductContextInput(
            model_code="WPUIAC425SNW",
        )
    )

    assert result.model_code == "WPUIAC425SNW"

    assert (
        result.product_family
        == ProductFamily.ICE_WATER_PURIFIER
    )

    assert result.runtime_approved is False


def test_model_code_is_normalized_before_backend_lookup():
    """
    앞뒤 공백이나 소문자가 들어와도
    Backend에는 정확한 대문자 판매코드를 전달한다.
    """

    reader = FakeProductContextReader(
        BackendProductContext(
            model_code="WPUJAC104DWH",
            product_family=(
                ProductFamily.DIRECT_WATER_PURIFIER
            ),
            supported_functions=set(),
        )
    )

    adapter = LookupProductContextAdapter(reader)

    result = adapter.execute(
        LookupProductContextInput(
            model_code="  wpujac104dwh  ",
        )
    )

    assert reader.called_model_code == "WPUJAC104DWH"
    assert result.model_code == "WPUJAC104DWH"


def test_backend_wrong_model_code_fails_closed():
    """
    IAC425를 요청했는데 Backend가 IAC606을 반환하면
    잘못된 제품 정보를 사용하지 않고 즉시 차단한다.
    """

    reader = FakeProductContextReader(
        BackendProductContext(
            model_code="WPUIAC606SNW",
            product_family=(
                ProductFamily.ICE_WATER_PURIFIER
            ),
            supported_functions={"ice"},
        )
    )

    adapter = LookupProductContextAdapter(reader)

    with pytest.raises(
        MCPContextMismatchError,
        match="model_code",
    ):
        adapter.execute(
            LookupProductContextInput(
                model_code="WPUIAC425SNW",
            )
        )