"""Export the approved eight-row BGE-M3 fixture for Backend import."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable, Sequence
from hashlib import sha256
import json
import math
from numbers import Real
from pathlib import Path
import unicodedata

import numpy as np

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_PATH = REPOSITORY_ROOT / "ai" / "configs" / "canonical_evidence_identity.json"
INDEX_MANIFEST_PATH = REPOSITORY_ROOT / "ai" / "configs" / "index_manifest.json"
SOURCE_DATASET_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "processed"
    / "structured"
    / "rag"
    / "mvp"
    / "rag_verified_sample.jsonl"
)
DEFAULT_OUTPUT_PATH = (
    REPOSITORY_ROOT
    / ".runtime"
    / "backend-ai"
    / "canonical_embedding_fixture_v1.json"
)

SCHEMA_VERSION = "1.0.0"
FIXTURE_STATUS = "GENERATED_FROM_APPROVED_BASELINE_PENDING_DB_IMPORT"
MODEL_NAME = "BAAI/bge-m3"
MODEL_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
DIMENSION = 1024
INDEX_VERSION = "1.0.0"
CHUNK_SET_SHA256 = "D523833B06C2F88C7C028F845D4782B1C1E66F3F5D567F4F3FF40C9DC8B114FB"
EMBEDDING_DTYPE = "FLOAT32"
ROW_COUNT = 8

EmbeddingClientFactory = Callable[..., BgeM3EmbeddingClient]


def _load_json_object(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return payload


def _load_jsonl_objects(path: Path) -> list[dict]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("Approved source rows must be JSON objects.")
    return rows


def _require_nfc(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{label} must be a non-empty string.")
    if unicodedata.normalize("NFC", value) != value:
        raise RuntimeError(f"{label} must already be NFC normalized.")
    return value


def _canonical_chunk_set_sha256(rows: Iterable[dict]) -> str:
    canonical = [
        {
            "chunk_id": row["chunk_id"],
            "source_hash": row["source_file_sha256"],
            "content": row["chunk_text"],
        }
        for row in sorted(rows, key=lambda item: item["chunk_id"])
    ]
    serialized = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(serialized.encode("utf-8")).hexdigest().upper()


def _validate_and_sort_chunks(
    rows: Sequence[dict], identity_rows: Sequence[dict]
) -> list[dict]:
    if len(rows) != ROW_COUNT or len(identity_rows) != ROW_COUNT:
        raise RuntimeError("Approved source and identity must each contain exactly eight rows.")

    validated: list[dict] = []
    for row in rows:
        chunk_id = _require_nfc(row.get("chunk_id"), label="chunk_id")
        chunk_text = _require_nfc(row.get("chunk_text"), label=f"{chunk_id}: chunk_text")
        validated.append({**row, "chunk_id": chunk_id, "chunk_text": chunk_text})

    chunk_ids = [row["chunk_id"] for row in validated]
    if len(set(chunk_ids)) != ROW_COUNT:
        raise RuntimeError("Approved source chunk IDs must be unique.")

    identity_by_id: dict[str, dict] = {}
    for identity in identity_rows:
        chunk_id = _require_nfc(identity.get("chunk_id"), label="identity chunk_id")
        if chunk_id in identity_by_id:
            raise RuntimeError("Canonical identity chunk IDs must be unique.")
        identity_by_id[chunk_id] = identity
    if set(chunk_ids) != set(identity_by_id):
        raise RuntimeError("Approved source and canonical identity chunk sets differ.")

    for row in validated:
        expected_text_hash = identity_by_id[row["chunk_id"]].get("chunk_text_sha256")
        actual_text_hash = sha256(row["chunk_text"].encode("utf-8")).hexdigest()
        if actual_text_hash != expected_text_hash:
            raise RuntimeError(f"Canonical chunk text hash differs: {row['chunk_id']}")

    if _canonical_chunk_set_sha256(validated) != CHUNK_SET_SHA256:
        raise RuntimeError("Approved source chunk-set SHA-256 differs.")
    return sorted(validated, key=lambda row: row["chunk_id"])


def _load_approved_chunks() -> list[dict]:
    identity = _load_json_object(IDENTITY_PATH)
    index = _load_json_object(INDEX_MANIFEST_PATH)
    expected_index = {
        "model_name": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "dimension": DIMENSION,
        "index_version": INDEX_VERSION,
        "chunk_count": ROW_COUNT,
        "chunk_set_sha256": CHUNK_SET_SHA256,
    }
    if any(index.get(key) != value for key, value in expected_index.items()):
        raise RuntimeError("AI index manifest differs from the fixed fixture contract.")
    expected_source_dataset = str(
        SOURCE_DATASET_PATH.relative_to(REPOSITORY_ROOT)
    ).replace("\\", "/")
    if identity.get("source_dataset") != expected_source_dataset:
        raise RuntimeError("Canonical identity source dataset differs.")
    if identity.get("chunk_set_sha256") != CHUNK_SET_SHA256:
        raise RuntimeError("Canonical identity chunk-set SHA-256 differs.")
    identity_rows = identity.get("chunks")
    if not isinstance(identity_rows, list):
        raise RuntimeError("Canonical identity chunks must be an array.")
    return _validate_and_sort_chunks(_load_jsonl_objects(SOURCE_DATASET_PATH), identity_rows)


def _to_float32_vectors(vectors: Sequence[Sequence[object]]) -> list[list[float]]:
    if len(vectors) != ROW_COUNT or any(len(vector) != DIMENSION for vector in vectors):
        raise RuntimeError("Generated embedding fixture must be 8 x 1024.")

    converted: list[list[float]] = []
    for vector in vectors:
        float32_vector: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, Real):
                raise RuntimeError("Generated embedding fixture contains non-numeric values.")
            numeric = float(value)
            if not math.isfinite(numeric):
                raise RuntimeError("Generated embedding fixture contains NaN or Infinity.")
            with np.errstate(over="ignore", invalid="ignore"):
                float32_value = np.float32(numeric)
            if not np.isfinite(float32_value):
                raise RuntimeError("Generated embedding fixture is not finite as FLOAT32.")
            float32_vector.append(float(float32_value))
        converted.append(float32_vector)
    return converted


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _resolve_output_path(output_path: Path) -> Path:
    if not output_path.is_absolute():
        output_path = REPOSITORY_ROOT / output_path
    runtime_root = (REPOSITORY_ROOT / ".runtime").resolve()
    resolved_output = output_path.resolve()
    try:
        resolved_output.relative_to(runtime_root)
    except ValueError as exc:
        raise RuntimeError("Fixture output must stay under repository .runtime/.") from exc
    return resolved_output


def _write_runtime_artifact(output_path: Path, serialized: bytes) -> None:
    resolved_output = output_path.resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = resolved_output.with_suffix(resolved_output.suffix + ".tmp")
    temporary_path.write_bytes(serialized)
    temporary_path.replace(resolved_output)


def export_fixture(
    *,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    client_factory: EmbeddingClientFactory = BgeM3EmbeddingClient,
) -> dict:
    """Generate the transient fixture and return a vector-free audit summary."""

    chunks = _load_approved_chunks()
    client = client_factory(model_revision=MODEL_REVISION)
    if (
        client.model_name != MODEL_NAME
        or getattr(client, "model_revision", None) != MODEL_REVISION
        or client.dimension != DIMENSION
    ):
        raise RuntimeError("Embedding client differs from the fixed fixture contract.")

    vectors = _to_float32_vectors(
        client.embed_documents(row["chunk_text"] for row in chunks)
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": FIXTURE_STATUS,
        "model_name": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "dimension": DIMENSION,
        "index_version": INDEX_VERSION,
        "chunk_set_sha256": CHUNK_SET_SHA256,
        "embedding_dtype": EMBEDDING_DTYPE,
        "rows": [
            {
                "chunk_id": row["chunk_id"],
                "chunk_text_sha256": sha256(row["chunk_text"].encode("utf-8")).hexdigest(),
                "embedding": vector,
            }
            for row, vector in zip(chunks, vectors, strict=True)
        ],
    }
    serialized = _canonical_bytes(payload)
    resolved_output = _resolve_output_path(output_path)
    _write_runtime_artifact(resolved_output, serialized)
    return {
        "status": "FIXTURE_READY",
        "fixture_status": FIXTURE_STATUS,
        "artifact_relative_path": str(
            resolved_output.relative_to(REPOSITORY_ROOT)
        ).replace("\\", "/"),
        "fixture_sha256": sha256(serialized).hexdigest(),
        "schema_version": SCHEMA_VERSION,
        "model_revision": MODEL_REVISION,
        "embedding_dtype": EMBEDDING_DTYPE,
        "rows_dimension": f"{ROW_COUNT}x{DIMENSION}",
        "row_order": "chunk_id_ASC",
        "nfc_validation": f"{ROW_COUNT}/{ROW_COUNT}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    options = parser.parse_args()
    print(json.dumps(export_fixture(output_path=options.output), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
