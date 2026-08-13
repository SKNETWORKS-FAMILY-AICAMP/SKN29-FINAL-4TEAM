"""Canonical evidence verification used by inquiry state transitions.

This service is deliberately separate from the public EvidenceCard API. It
only answers whether every citation returned by the AI runtime belongs to the
checked-in baseline corpus for the inquiry's exact product model. It never
returns citation text to an external client.
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.inquiries.models import Inquiry


logger = logging.getLogger("watercare.ai")
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CANONICAL_IDENTITY_PATH = (
    REPOSITORY_ROOT / "ai" / "configs" / "canonical_evidence_identity.json"
)
BASELINE_CORPUS_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "structured"
    / "rag"
    / "mvp"
    / "rag_verified_sample.jsonl"
)


@lru_cache(maxsize=1)
def _canonical_rows() -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    """Load and cross-check the two immutable baseline identity sources."""

    identity = json.loads(CANONICAL_IDENTITY_PATH.read_text(encoding="utf-8"))
    manifest_rows = {
        row["chunk_id"]: row for row in identity.get("chunks", [])
    }
    corpus_rows: dict[str, dict[str, Any]] = {}
    with BASELINE_CORPUS_PATH.open(encoding="utf-8") as source:
        for line in source:
            if line.strip():
                row = json.loads(line)
                corpus_rows[row["chunk_id"]] = row

    if not manifest_rows or set(manifest_rows) != set(corpus_rows):
        raise ValueError("Canonical evidence identity and corpus are not aligned")

    verified: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for chunk_id, manifest in manifest_rows.items():
        corpus = corpus_rows[chunk_id]
        actual_chunk_hash = hashlib.sha256(
            corpus["chunk_text"].encode("utf-8")
        ).hexdigest()
        aligned = (
            manifest.get("document_id") == corpus.get("document_id")
            and manifest.get("page_refs") == corpus.get("page_refs")
            and manifest.get("model_code") == corpus.get("exact_sales_code")
            and manifest.get("product_generation")
            == corpus.get("product_generation")
            and str(manifest.get("source_file_sha256", "")).lower()
            == str(corpus.get("source_file_sha256", "")).lower()
            and str(manifest.get("chunk_text_sha256", "")).lower()
            == actual_chunk_hash
            and manifest.get("verification_status")
            == "TEXT_AND_VISUAL_VERIFIED"
            and corpus.get("verification_status")
            == "TEXT_AND_VISUAL_VERIFIED"
            and corpus.get("scope_role") == "mvp"
        )
        if not aligned:
            raise ValueError(f"Canonical evidence identity mismatch: {chunk_id}")
        verified[chunk_id] = (manifest, corpus)
    return verified


def verify_canonical_evidence(
    references: list[dict[str, Any]],
    inquiry: "Inquiry",
) -> list[str]:
    """Return canonical evidence IDs only when every citation verifies.

    A partial match is rejected because the state contract requires every
    cited item to be official, usable, and scoped to the exact product model.
    Configuration or data drift therefore holds the inquiry in its current
    state instead of exposing unverified guidance.
    """

    if not references or inquiry.subscription.product_model_id is None:
        return []
    try:
        canonical_rows = _canonical_rows()
    except (
        OSError,
        UnicodeError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ):
        logger.error(
            "canonical_evidence_registry_unavailable",
            extra={"trace_stage": "EVIDENCE_VERIFICATION_FAILED"},
        )
        return []

    product = inquiry.subscription.product_model
    verified_ids: list[str] = []
    seen_chunk_ids: set[str] = set()
    for reference in references:
        chunk_id = reference.get("chunk_id")
        if not isinstance(chunk_id, str) or chunk_id in seen_chunk_ids:
            return []
        seen_chunk_ids.add(chunk_id)
        pair = canonical_rows.get(chunk_id)
        if pair is None:
            return []
        manifest, corpus = pair

        reference_pages = reference.get("page_refs") or []
        expected_pages = manifest["page_refs"]
        reference_matches = (
            manifest["model_code"] == product.model_code
            and manifest["product_generation"] == product.generation_code
            and reference.get("verification_status") == "official_verified"
            and reference.get("document_title") == corpus.get("section_title")
            and reference.get("document_version") == corpus.get("version")
            and reference.get("page") == corpus.get("page_start")
            and reference_pages == expected_pages
            and reference.get("official_url") == corpus.get("source_url")
            and reference.get("summary") == corpus.get("chunk_text")
        )
        evidence_id = manifest.get("evidence_id")
        if not reference_matches or not isinstance(evidence_id, str):
            return []
        verified_ids.append(evidence_id)
    return verified_ids
