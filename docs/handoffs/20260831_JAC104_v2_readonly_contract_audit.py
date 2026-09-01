"""Readonly metadata audit only; not candidate-image or retrieval evidence.

Run with Python 3.13.13 in the existing AI container, using its protected DSN.
No Provider import, embedding, schema change, database write, or file write.
The two local identity assets must match the exact candidate Git blobs.
"""

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform

import psycopg
from psycopg.rows import dict_row


ASSET_HASHES = {
    "ai/configs/index_manifest_3model.json":
        "3fa0f26c0c2c2628f9d4410c061ff17dd8d6ce9c6e0b76358cbb0bb0a9c28a1e",
    "ai/configs/canonical_evidence_identity_3model.json":
        "ab98aa6cfe839366cb13ecc3839d72ee0ae99419af85f702f0c2f1d05bdca169",
}
EXPECTED_COUNTS = {"WPUJAC104DWH": 15, "WPUIAC425SNW": 19, "WPUIAC606SNW": 19}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def main():
    stage = "ENVIRONMENT"
    try:
        require(platform.python_version() == "3.13.13", stage)
        require(os.environ.get("AI_VECTOR_TABLE_NAME") == "backend_ai_rag_chunks_v1", stage)
        stage = "CANDIDATE_ASSET_HASHES"
        assets = {}
        for relative, digest in ASSET_HASHES.items():
            content = Path(relative).read_bytes()
            require(hashlib.sha256(content).hexdigest() == digest, stage)
            assets[relative] = json.loads(content)
        manifest = assets["ai/configs/index_manifest_3model.json"]
        identity = assets["ai/configs/canonical_evidence_identity_3model.json"]
        canonical = {row["chunk_id"]: row for row in identity["chunks"]}
        require(len(canonical) == len(identity["chunks"]) == 53, stage)
        require(identity["model_chunk_counts"] == EXPECTED_COUNTS, stage)

        stage = "RDS_READONLY_QUERY"
        with psycopg.connect(os.environ["AI_VECTOR_DSN"], connect_timeout=5) as connection:
            connection.read_only = True
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SET LOCAL statement_timeout = '5s'")
                cursor.execute("SHOW default_transaction_read_only")
                require(cursor.fetchone() == {"default_transaction_read_only": "on"}, stage)
                cursor.execute("SHOW transaction_read_only")
                require(cursor.fetchone() == {"transaction_read_only": "on"}, stage)
                cursor.execute("""
                    SELECT chunk_id, model_code, product_generation,
                           verification_status, allowed_use, metadata,
                           vector_dims(embedding) AS dimension,
                           encode(sha256(convert_to(content, 'UTF8')), 'hex') AS content_sha256
                    FROM backend_ai_rag_chunks_v1
                    ORDER BY chunk_id
                    LIMIT 54
                """)
                rows = cursor.fetchall()

        stage = "CANONICAL_CHILD_SET"
        require(len(rows) == 53, stage)
        require({row["chunk_id"] for row in rows} == set(canonical), stage)
        counts = Counter(row["model_code"] for row in rows)
        require(dict(counts) == EXPECTED_COUNTS, stage)
        for row in rows:
            expected = canonical[row["chunk_id"]]
            metadata = row["metadata"]
            stage = "CANONICAL_IDENTITY_AND_HASH"
            require(all((
                row["model_code"] == expected["model_code"],
                row["product_generation"] == expected["product_generation"],
                metadata["model_code"] == row["model_code"],
                metadata["product_generation"] == row["product_generation"],
                metadata["document_id"] == expected["document_id"],
                metadata["page_refs"] == expected["page_refs"],
                metadata["source_hash"].casefold() == expected["source_file_sha256"].casefold(),
                row["content_sha256"].casefold() == expected["chunk_text_sha256"].casefold(),
                expected["source_file_sha256"].casefold()
                    == manifest["document_hashes"][expected["document_id"]].casefold(),
            )), stage)
            stage = "INDEX_IDENTITY"
            require(all((
                row["dimension"] == manifest["dimension"] == 1024,
                metadata["embedding_model"] == manifest["model_name"],
                metadata["embedding_model_revision"] == manifest["model_revision"],
                metadata["index_version"] == manifest["index_version"] == "2.0.0",
                metadata["chunk_set_sha256"].casefold() == manifest["chunk_set_sha256"].casefold(),
            )), stage)
            stage = "CHILD_ELIGIBILITY_AND_LINEAGE"
            require(all((
                expected["verification_status"] == "TEXT_AND_VISUAL_VERIFIED",
                row["verification_status"] == metadata["verification_status"] == "official_verified",
                row["allowed_use"] is True,
                metadata["allowed_use"] is True,
                metadata.get("runtime_eligible", True) is True,
                metadata.get("record_type") in ("child", "CHILD"),
                metadata["retrieval_role"] == "SEARCH_CANDIDATE",
                all(isinstance(metadata.get(key), str) and metadata[key].strip()
                    for key in ("evidence_group_id", "source_variant_id", "parent_id")),
            )), stage)
    except Exception as exc:
        print(json.dumps({"status": "BLOCKED", "stage": stage, "error_type": type(exc).__name__}))
        return 1
    print(json.dumps({
        "status": "PASS", "scope": "RDS_CANONICAL_METADATA_ONLY",
        "target_contract": "jac104_v2_recovery", "rows": len(rows),
        "model_counts": dict(counts), "record_type_child": len(rows),
        "canonical_identity_and_hash": "PASS", "jac104_eligible_rows": 15,
        "candidate_image_execution": False, "retrieval_probes_executed": False,
        "provider_calls": 0, "db_writes": 0,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
