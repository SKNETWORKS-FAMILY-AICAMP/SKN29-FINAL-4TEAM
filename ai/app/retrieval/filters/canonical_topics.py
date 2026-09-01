"""Restore omitted View topic metadata from verified Child identities."""

from functools import lru_cache
from hashlib import sha256
import json

from ..runtime import RetrievalConfigurationError
from ..runtime_profile import REPOSITORY_ROOT, resolve_rag_runtime_profile


@lru_cache(maxsize=1)
def _topics():
    identity_path = REPOSITORY_ROOT / "ai/configs/canonical_evidence_identity_3model.json"
    topic_path = REPOSITORY_ROOT / "ai/configs/canonical_evidence_topics_3model.json"
    try:
        raw_identity = identity_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        identity = json.loads(raw_identity)
        topics = json.loads(topic_path.read_bytes())
        rows = {row["chunk_id"]: row for row in topics["chunks"]}
        originals = {row["chunk_id"]: row for row in identity["chunks"]}
        profile = resolve_rag_runtime_profile("three_model_integration")
        valid = (
            topics["canonical_identity_sha256"] == sha256(raw_identity).hexdigest()
            and topics["index_version"] == profile.expected_index_version
            and topics["chunk_set_sha256"].casefold() == profile.expected_chunk_set_sha256.casefold()
            and len(rows) == len(topics["chunks"]) == profile.expected_chunk_count
            and rows.keys() == originals.keys()
            and all(all(row.get(key) == value for key, value in originals[cid].items())
                    for cid, row in rows.items())
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise RetrievalConfigurationError("Canonical Topic metadata identity mismatch")
    return rows


def canonical_v2_topic(chunk):
    if chunk.index_version != "2.0.0":
        return None
    row = _topics().get(chunk.chunk_id)
    profile = resolve_rag_runtime_profile("three_model_integration")
    if row is None or not all((
        chunk.model_code == row["model_code"],
        chunk.document_id == row["document_id"],
        chunk.product_generation == row["product_generation"],
        chunk.page_refs == row["page_refs"],
        (chunk.chunk_set_sha256 or "").casefold() == profile.expected_chunk_set_sha256.casefold(),
        sha256(chunk.content.encode("utf-8")).hexdigest().upper() == row["chunk_text_sha256"],
        (chunk.source_hash or "").upper() == row["source_file_sha256"],
        chunk.verification_status == "official_verified", chunk.allowed_use, chunk.runtime_eligible,
        chunk.record_type in (None, "child", "CHILD"),
        chunk.retrieval_role == "SEARCH_CANDIDATE",
        chunk.evidence_group_id == row["evidence_group_id"],
    )):
        return None
    return row["topic_code"]
