from __future__ import annotations


from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

# MCP Context에서 발생하는 제품 불일치 오류를 사용합니다.
from ..errors import MCPContextMismatchError

from ....orchestration.harness.product_match import ProductFamily
from ....orchestration.harness.product_registry import (
    is_runtime_approved_model_code,
)


class BackendProductContext(BaseModel):
    """
    Backend에서 조회한 제품 정보.

    아직 실제 Backend API 계약이 확정되지 않았기 때문에
    MCP Adapter가 필요로 하는 최소 필드만 정의한다.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    model_code: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    product_family: ProductFamily

    supported_functions: set[str] = Field(
        default_factory=set,
    )


class ProductContextReader(Protocol): # 나는 제품 정보를 어디서 가져오는지 모르겠고, get_product_context()라는 기능만 있으면 됨
    """
    제품 Context를 제공하는 객체가 따라야 하는 계약.

    실제 BackendContextClient가 완성되면
    이 인터페이스를 만족하도록 연결한다.
    """

    def get_product_context(
        self,
        model_code: str,
    ) -> BackendProductContext:
        ...


class LookupProductContextInput(BaseModel):
    """MCP lookup_product_context Tool 입력."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    model_code: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="고객 구독에서 확인한 정확한 판매 모델 코드",
    )


class LookupProductContextOutput(BaseModel):
    """MCP lookup_product_context Tool 출력."""

    model_code: str

    product_family: ProductFamily

    supported_functions: list[str] = Field(
        default_factory=list,
    )

    runtime_approved: bool


class LookupProductContextAdapter:
    """
    Backend Product Context를
    MCP Tool 출력 계약으로 변환한다.
    """

    def __init__(
        self,
        context_reader: ProductContextReader,
    ) -> None:
        self.context_reader = context_reader

    def execute(
        self,
        request: LookupProductContextInput,
    ) -> LookupProductContextOutput:
        requested_model_code = ( # 요청을 실수로 보내도 소문자로 보내도 정규화 되게 함
            request.model_code.strip().upper()
        )

        product = self.context_reader.get_product_context(
            requested_model_code
        )

        backend_model_code = (
            product.model_code.strip().upper()
        )

        if backend_model_code != requested_model_code:
         # 요청 제품과 Backend가 돌려준 제품이 다르면
         # 다른 제품의 정보를 AI가 사용하지 못하도록 즉시 차단합니다.
            raise MCPContextMismatchError(
                "Backend Product Context의 model_code가 "
                "요청한 model_code와 일치하지 않습니다."
            )

        return LookupProductContextOutput(
            model_code=backend_model_code,
            product_family=product.product_family,
            supported_functions=sorted(
                product.supported_functions
            ),
            runtime_approved=( # AI가 집적 판단함
                is_runtime_approved_model_code(
                    backend_model_code
                )
            ),
        )