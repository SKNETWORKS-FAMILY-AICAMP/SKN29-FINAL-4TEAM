"""Shared MCP transport models without orchestration imports."""

from pydantic import Field

from ...schemas import EvidenceReference


class SearchOfficialEvidenceReference(EvidenceReference):
    """Internal evidence identity retained for the outer product guard."""

    model_code: str = Field(..., min_length=1, max_length=100)
    product_generation: str = Field(..., min_length=1, max_length=100)
    allowed_use: bool
    runtime_eligible: bool
