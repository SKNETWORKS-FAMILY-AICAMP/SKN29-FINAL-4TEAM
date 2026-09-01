"""Readonly DB snapshots must match the selected profile, not just row counts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..indexing.index_manifest import IndexManifest
from ..runtime import RetrievalConfigurationError
from ..runtime_profile import RagRuntimeProfile, validate_runtime_manifest


class IndexReadinessError(RetrievalConfigurationError):
    """A fixed reason code, without protected DB values or source text."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class ReadonlyIndexRow:
    """Only identity metadata and a DB-computed content hash; no source text."""

    chunk_id: str
    model_code: str
    product_generation: str
    verification_status: str
    allowed_use: bool
    dimension: int
    content_sha256: str
    metadata: Mapping[str, Any]


def _require(condition: bool, reason_code: str) -> None:
    if not condition:
        raise IndexReadinessError(reason_code)


def _sha256(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.casefold()
    if len(normalized) != 64 or any(c not in "0123456789abcdef" for c in normalized):
        return None
    return normalized


def validate_readonly_index(
    profile: RagRuntimeProfile,
    manifest: IndexManifest,
    canonical_identity: Mapping[str, Any],
    rows: Sequence[ReadonlyIndexRow],
) -> dict[str, Any]:
    """Validate the whole index independently of the public product allowlist.

    For JAC104 recovery the index remains 53 rows, while only 15 rows belong to
    the permitted product. This check neither grants product approval nor
    replaces retrieval evaluation or the Backend role/privilege preflight.
    """

    validate_runtime_manifest(profile, manifest)
    _require(
        canonical_identity.get("chunk_count") == manifest.chunk_count
        and canonical_identity.get("index_version") == manifest.index_version
        and _sha256(canonical_identity.get("chunk_set_sha256"))
        == _sha256(manifest.chunk_set_sha256),
        "CANONICAL_MANIFEST_MISMATCH",
    )
    chunks = canonical_identity.get("chunks")
    _require(isinstance(chunks, list), "CANONICAL_IDENTITY_INVALID")
    _require(
        all(isinstance(item, dict) and isinstance(item.get("chunk_id"), str)
            for item in chunks),
        "CANONICAL_IDENTITY_INVALID",
    )
    expected = {item["chunk_id"]: item for item in chunks}
    _require(
        len(chunks) == len(expected) == manifest.chunk_count,
        "CANONICAL_IDENTITY_INVALID",
    )
    expected_counts = Counter(item.get("model_code") for item in chunks)
    _require(
        dict(expected_counts) == canonical_identity.get("model_chunk_counts")
        and profile.approved_model_codes.issubset(expected_counts),
        "CANONICAL_MODEL_SCOPE_MISMATCH",
    )
    _require(len(rows) == manifest.chunk_count, "VIEW_ROW_COUNT_MISMATCH")
    _require(
        len({row.chunk_id for row in rows}) == len(rows)
        and {row.chunk_id for row in rows} == set(expected),
        "VIEW_CANONICAL_CHILD_SET_MISMATCH",
    )
    model_counts = Counter(row.model_code for row in rows)
    _require(model_counts == expected_counts, "VIEW_MODEL_DISTRIBUTION_MISMATCH")

    for row in rows:
        canonical = expected[row.chunk_id]
        metadata = row.metadata
        _require(isinstance(metadata, Mapping), "VIEW_METADATA_INVALID")
        document_id = canonical.get("document_id")
        source_hash = _sha256(canonical.get("source_file_sha256"))
        text_hash = _sha256(canonical.get("chunk_text_sha256"))
        _require(
            canonical.get("verification_status") == "TEXT_AND_VISUAL_VERIFIED"
            and source_hash is not None
            and source_hash == _sha256(manifest.document_hashes.get(document_id))
            and text_hash is not None,
            "CANONICAL_IDENTITY_INVALID",
        )
        _require(
            row.model_code == canonical.get("model_code")
            and row.product_generation == canonical.get("product_generation")
            and metadata.get("model_code") == row.model_code
            and metadata.get("product_generation") == row.product_generation
            and metadata.get("document_id") == document_id
            and metadata.get("page_refs") == canonical.get("page_refs")
            and _sha256(metadata.get("source_hash")) == source_hash
            and _sha256(row.content_sha256) == text_hash,
            "VIEW_CANONICAL_IDENTITY_MISMATCH",
        )
        _require(
            row.dimension == manifest.dimension
            and metadata.get("embedding_model") == manifest.model_name
            and metadata.get("embedding_model_revision") == manifest.model_revision
            and metadata.get("index_version") == manifest.index_version
            and _sha256(metadata.get("chunk_set_sha256"))
            == _sha256(manifest.chunk_set_sha256),
            "VIEW_INDEX_IDENTITY_MISMATCH",
        )
        _require(
            row.verification_status == "official_verified"
            and row.allowed_use is True
            and metadata.get("verification_status") == "official_verified"
            and metadata.get("allowed_use") is True
            and metadata.get("runtime_eligible", True) is True
            # The approved Backend View currently omits record_type.
            and metadata.get("record_type") in (None, "child", "CHILD")
            and metadata.get("retrieval_role") == "SEARCH_CANDIDATE"
            and all(isinstance(metadata.get(key), str) and metadata[key].strip()
                    for key in ("evidence_group_id", "source_variant_id", "parent_id")),
            "VIEW_EVIDENCE_ELIGIBILITY_MISMATCH",
        )

    return {
        "index_version": manifest.index_version,
        "chunk_set_sha256": manifest.chunk_set_sha256,
        "index_row_count": len(rows),
        "model_row_counts": dict(sorted(model_counts.items())),
        "approved_model_codes": sorted(profile.approved_model_codes),
        "approved_model_row_count": sum(model_counts[code]
                                        for code in profile.approved_model_codes),
    }


__all__ = ["IndexReadinessError", "ReadonlyIndexRow", "validate_readonly_index"]
