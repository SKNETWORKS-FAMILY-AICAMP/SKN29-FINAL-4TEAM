"""Shared MCP transport models without orchestration imports."""

from pydantic import Field

from ...schemas import EvidenceReference


class SearchOfficialEvidenceReference(EvidenceReference):
    """Internal evidence identity retained for downstream safety filters."""

    model_code: str = Field(..., min_length=1, max_length=100)
    product_generation: str = Field(..., min_length=1, max_length=100)
    allowed_use: bool
    runtime_eligible: bool
    document_id: str | None = None
    source_hash: str | None = None
    index_version: str | None = None
    chunk_set_sha256: str | None = None
    topic_code: str | None = None
    evidence_group_id: str | None = None
    record_type: str | None = None
    retrieval_role: str | None = None
