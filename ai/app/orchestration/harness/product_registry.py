"""Fail-closed ProductContext resolution for the current three-product RAG contract."""

from __future__ import annotations

from .product_match import ProductContext, ProductFamily


SUPPORTED_EXACT_MODEL_CODES: dict[str, ProductFamily] = {
    "WPUJAC104DWH": ProductFamily.DIRECT_WATER_PURIFIER,
    "WPUIAC425SNW": ProductFamily.ICE_WATER_PURIFIER,
    "WPUIAC606SNW": ProductFamily.ICE_WATER_PURIFIER,
}

PRODUCT_GENERATION_BY_MODEL_CODE: dict[str, str] = {
    "WPUJAC104DWH": "D",
    "WPUIAC425SNW": "IAC425",
    "WPUIAC606SNW": "IAC606",
}


def resolve_product_context(
    model_code: str,
    *,
    supported_functions: set[str] | None = None,
) -> ProductContext:
    """Resolve a verified exact sales code, or return UNKNOWN so runtime fails closed."""

    exact_code = model_code.strip().upper()
    product_family = SUPPORTED_EXACT_MODEL_CODES.get(
        exact_code,
        ProductFamily.UNKNOWN,
    )
    return ProductContext(
        model_code=exact_code,
        product_family=product_family,
        supported_functions=supported_functions or set(),
    )


def resolve_product_generation(model_code: str) -> str | None:
    return PRODUCT_GENERATION_BY_MODEL_CODE.get(model_code.strip().upper())
