"""Fail-closed ProductContext resolution for the current three-product RAG contract."""

from __future__ import annotations

from .product_match import ProductContext, ProductFamily


KNOWN_EXACT_MODEL_CODES: dict[str, ProductFamily] = {
    "WPUJAC104DWH": ProductFamily.DIRECT_WATER_PURIFIER,
    "WPUIAC425SNW": ProductFamily.ICE_WATER_PURIFIER,
    "WPUIAC606SNW": ProductFamily.ICE_WATER_PURIFIER,
}

# Data/RAG evaluation knows all three exact sales codes, but the current runtime
# contract approves only the indexed MVP product. IAC425/IAC606 remain fail-closed
# until Backend/Public API runtime activation is explicitly approved.
RUNTIME_APPROVED_EXACT_MODEL_CODES = frozenset({"WPUJAC104DWH"})

# Backward-compatible name for callers that only need the known three-product set.
# Runtime authorization must use ``is_runtime_approved_model_code`` instead.
SUPPORTED_EXACT_MODEL_CODES = KNOWN_EXACT_MODEL_CODES

PRODUCT_GENERATION_BY_MODEL_CODE: dict[str, str] = {
    "WPUJAC104DWH": "D",
    "WPUIAC425SNW": "IAC425",
    "WPUIAC606SNW": "IAC606",
}


def is_runtime_approved_model_code(model_code: str) -> bool:
    return model_code.strip().upper() in RUNTIME_APPROVED_EXACT_MODEL_CODES


def resolve_product_context(
    model_code: str,
    *,
    supported_functions: set[str] | None = None,
) -> ProductContext:
    """Resolve exact product identity separately from current runtime approval."""

    exact_code = model_code.strip().upper()
    product_family = KNOWN_EXACT_MODEL_CODES.get(
        exact_code,
        ProductFamily.UNKNOWN,
    )
    return ProductContext(
        model_code=exact_code,
        product_family=product_family,
        runtime_approved=is_runtime_approved_model_code(exact_code),
        supported_functions=supported_functions or set(),
    )


def resolve_product_generation(model_code: str) -> str | None:
    return PRODUCT_GENERATION_BY_MODEL_CODE.get(model_code.strip().upper())
