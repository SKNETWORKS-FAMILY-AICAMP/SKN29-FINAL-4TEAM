"""Build the transient 53-row embedding fixture and actual index manifest."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any
import unicodedata

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "structured"
    / "rag"
    / "expansion"
    / "rag_child_chunks_3model_v1.jsonl"
)
DEFAULT_IDENTITY_PATH = (
    REPOSITORY_ROOT / "ai" / "configs" / "canonical_evidence_identity_3model.json"
)
DEFAULT_FIXTURE_OUTPUT = (
    REPOSITORY_ROOT
    / ".runtime"
    / "backend-ai"
    / "three_model_embedding_fixture_v2.json"
)
DEFAULT_INDEX_OUTPUT = (
    REPOSITORY_ROOT
    / ".runtime"
    / "backend-ai"
    / "index_manifest_3model.json"
)
EXPECTED_MODEL_COUNTS = {
    "WPUJAC104DWH": 15,
    "WPUIAC425SNW": 19,
    "WPUIAC606SNW": 19,
}
EXPECTED_CHUNK_COUNT = sum(EXPECTED_MODEL_COUNTS.values())
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
EMBEDDING_DIMENSION = 1024
INDEX_VERSION = "2.0.0"
IDENTITY_STATUS = "AI_SOURCE_IDENTITY_FIXED_BACKEND_MAPPING_PENDING"
FIXTURE_STATUS = "GENERATED_FROM_APPROVED_BASELINE_PENDING_DB_IMPORT"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot load JSON input: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return payload


def _load_source_rows(path: Path = SOURCE_PATH) -> list[dict[str, Any]]:
    try:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot load three-model source: {path}") from exc
    if len(rows) != EXPECTED_CHUNK_COUNT or any(
        not isinstance(row, dict) for row in rows
    ):
        raise RuntimeError("Three-model source must contain exactly 53 object rows.")
    ids = [row.get("child_id") for row in rows]
    if any(not isinstance(value, str) or not value for value in ids):
        raise RuntimeError("Every three-model source row requires child_id.")
    if len(set(ids)) != EXPECTED_CHUNK_COUNT:
        raise RuntimeError("Three-model source child IDs must be unique.")
    counts = Counter(str(row.get("exact_sales_code")) for row in rows)
    if dict(counts) != EXPECTED_MODEL_COUNTS:
        raise RuntimeError("Three-model source model distribution differs.")
    for row in rows:
        chunk_id = str(row["child_id"])
        chunk_text = row.get("child_text")
        if not isinstance(chunk_text, str) or not chunk_text:
            raise RuntimeError(f"{chunk_id}: child_text must be non-empty.")
        if unicodedata.normalize("NFC", chunk_text) != chunk_text:
            raise RuntimeError(f"{chunk_id}: child_text must already be NFC normalized.")
        expected_hash = sha256(chunk_text.encode("utf-8")).hexdigest().upper()
        if row.get("child_text_sha256") != expected_hash:
            raise RuntimeError(f"{chunk_id}: child_text_sha256 differs.")
    return sorted(rows, key=lambda row: str(row["child_id"]))


def _chunk_set_sha256(rows: list[dict[str, Any]]) -> str:
    canonical = [
        {
            "chunk_id": row["child_id"],
            "source_hash": str(row["source_file_sha256"]).upper(),
            "content": row["child_text"],
        }
        for row in rows
    ]
    serialized = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(serialized).hexdigest().upper()


def _validate_identity(
    identity: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    if identity.get("schema_version") != "1.0.0":
        raise RuntimeError("Canonical identity schema version is unsupported.")
    if identity.get("status") != IDENTITY_STATUS:
        raise RuntimeError("Canonical identity status is not mapping-ready.")
    if identity.get("index_version") != INDEX_VERSION:
        raise RuntimeError("Canonical identity index version differs.")
    if identity.get("chunk_count") != EXPECTED_CHUNK_COUNT:
        raise RuntimeError("Canonical identity chunk_count must be 53.")
    if identity.get("model_chunk_counts") != EXPECTED_MODEL_COUNTS:
        raise RuntimeError("Canonical identity model distribution differs.")
    chunk_set_hash = _chunk_set_sha256(rows)
    if identity.get("chunk_set_sha256") != chunk_set_hash:
        raise RuntimeError("Canonical identity chunk-set hash differs.")
    identity_rows = identity.get("chunks")
    if not isinstance(identity_rows, list) or len(identity_rows) != EXPECTED_CHUNK_COUNT:
        raise RuntimeError("Canonical identity must contain exactly 53 rows.")
    identity_by_id = {item.get("chunk_id"): item for item in identity_rows}
    if len(identity_by_id) != EXPECTED_CHUNK_COUNT:
        raise RuntimeError("Canonical identity chunk IDs must be unique.")
    for row in rows:
        chunk_id = str(row["child_id"])
        identity_row = identity_by_id.get(chunk_id)
        if not isinstance(identity_row, dict):
            raise RuntimeError(f"{chunk_id}: Canonical identity row is missing.")
        expected = {
            "document_id": row["document_id"],
            "page_refs": row["page_refs"],
            "model_code": row["exact_sales_code"],
            "product_generation": row["product_generation"],
            "verification_status": row["verification_status"],
            "source_file_sha256": row["source_file_sha256"],
            "chunk_text_sha256": row["child_text_sha256"],
        }
        if any(identity_row.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"{chunk_id}: Canonical identity metadata differs.")


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _validated_runtime_output(path: Path) -> Path:
    resolved = path.resolve()
    runtime_root = (REPOSITORY_ROOT / ".runtime").resolve()
    try:
        resolved.relative_to(runtime_root)
    except ValueError as exc:
        raise RuntimeError("Generated outputs must stay under .runtime/.") from exc
    return resolved


def _atomic_write(path: Path, payload: dict[str, Any]) -> bytes:
    serialized = _canonical_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(serialized)
    temporary.replace(path)
    return serialized


def build_artifacts(
    *,
    identity_path: Path,
    fixture_output: Path,
    index_output: Path,
    indexed_at: datetime | None = None,
) -> dict[str, Any]:
    rows = _load_source_rows()
    identity = _load_json(identity_path)
    _validate_identity(identity, rows)
    fixture_output = _validated_runtime_output(fixture_output)
    index_output = _validated_runtime_output(index_output)

    client = BgeM3EmbeddingClient(model_revision=EMBEDDING_REVISION)
    if client.model_name != EMBEDDING_MODEL or client.dimension != EMBEDDING_DIMENSION:
        raise RuntimeError("Embedding client does not match the approved BGE-M3 baseline.")
    vectors = client.embed_documents(str(row["child_text"]) for row in rows)
    if len(vectors) != EXPECTED_CHUNK_COUNT or any(
        len(vector) != EMBEDDING_DIMENSION for vector in vectors
    ):
        raise RuntimeError("Generated embedding fixture must be 53 x 1024.")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for vector in vectors
        for value in vector
    ):
        raise RuntimeError("Generated embedding fixture contains invalid values.")

    chunk_set_hash = _chunk_set_sha256(rows)
    fixture = {
        "schema_version": "1.0.0",
        "status": FIXTURE_STATUS,
        "model_name": EMBEDDING_MODEL,
        "model_revision": EMBEDDING_REVISION,
        "dimension": EMBEDDING_DIMENSION,
        "embedding_dtype": "FLOAT32",
        "index_version": INDEX_VERSION,
        "chunk_set_sha256": chunk_set_hash,
        "rows": [
            {
                "chunk_id": row["child_id"],
                "chunk_text_sha256": str(row["child_text_sha256"]).lower(),
                "embedding": vector,
            }
            for row, vector in zip(rows, vectors, strict=True)
        ],
    }
    timestamp = indexed_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise RuntimeError("indexed_at must include timezone information.")
    document_hashes = {
        str(row["document_id"]): str(row["source_file_sha256"]).upper()
        for row in rows
    }
    index = {
        "model_name": EMBEDDING_MODEL,
        "model_revision": EMBEDDING_REVISION,
        "dimension": EMBEDDING_DIMENSION,
        "index_type": "exact_search",
        "index_version": INDEX_VERSION,
        "chunk_count": EXPECTED_CHUNK_COUNT,
        "chunk_set_sha256": chunk_set_hash,
        "document_hashes": dict(sorted(document_hashes.items())),
        "indexed_at": timestamp.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
    }
    fixture_bytes = _atomic_write(fixture_output, fixture)
    index_bytes = _atomic_write(index_output, index)
    return {
        "status": "THREE_MODEL_ARTIFACTS_READY",
        "row_count": EXPECTED_CHUNK_COUNT,
        "model_counts": EXPECTED_MODEL_COUNTS,
        "dimension": EMBEDDING_DIMENSION,
        "fixture_sha256": sha256(fixture_bytes).hexdigest(),
        "index_manifest_sha256": sha256(index_bytes).hexdigest(),
        "chunk_set_sha256": chunk_set_hash,
        "fixture_output": fixture_output.relative_to(REPOSITORY_ROOT).as_posix(),
        "index_output": index_output.relative_to(REPOSITORY_ROOT).as_posix(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity-manifest", type=Path, default=DEFAULT_IDENTITY_PATH)
    parser.add_argument("--fixture-output", type=Path, default=DEFAULT_FIXTURE_OUTPUT)
    parser.add_argument("--index-output", type=Path, default=DEFAULT_INDEX_OUTPUT)
    options = parser.parse_args()
    print(
        json.dumps(
            build_artifacts(
                identity_path=options.identity_manifest,
                fixture_output=options.fixture_output,
                index_output=options.index_output,
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
