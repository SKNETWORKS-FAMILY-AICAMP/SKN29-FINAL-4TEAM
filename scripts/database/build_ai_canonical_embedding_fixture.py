"""Generate the transient approved seven-row BGE-M3 embedding fixture."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_MANIFEST = (
    REPOSITORY_ROOT
    / "data"
    / "config"
    / "evidence"
    / "backend_ai_canonical_import_v1.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / ".runtime"
    / "backend-ai"
    / "canonical_embedding_fixture_v1.json"
)


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return payload


def _file_digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest().upper()


def build_fixture(*, output_path: Path) -> dict:
    manifest = _load_json(PACKAGE_MANIFEST)
    source = manifest["source"]
    index = manifest["index"]
    chunks_path = (REPOSITORY_ROOT / source["rag_chunks_path"]).resolve()
    if _file_digest(chunks_path) != source["rag_chunks_sha256"]:
        raise RuntimeError("Approved RAG source SHA-256 differs.")
    chunks = [
        json.loads(line)
        for line in chunks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(chunks) != 7:
        raise RuntimeError("Approved RAG source must contain exactly seven rows.")

    client = BgeM3EmbeddingClient(model_revision=index["model_revision"])
    if client.model_name != index["model_name"] or client.dimension != 1024:
        raise RuntimeError("Embedding client does not match the approved baseline.")
    vectors = client.embed_documents(row["chunk_text"] for row in chunks)
    if len(vectors) != 7 or any(len(vector) != 1024 for vector in vectors):
        raise RuntimeError("Generated embedding fixture must be 7 x 1024.")
    if any(
        not math.isfinite(float(value))
        for vector in vectors
        for value in vector
    ):
        raise RuntimeError("Generated embedding fixture contains invalid values.")

    payload = {
        "schema_version": "1.0.0",
        "status": "GENERATED_FROM_APPROVED_BASELINE_PENDING_DB_IMPORT",
        "model_name": index["model_name"],
        "model_revision": index["model_revision"],
        "dimension": index["dimension"],
        "index_version": index["index_version"],
        "chunk_set_sha256": index["chunk_set_sha256"],
        "rows": [
            {
                "chunk_id": row["chunk_id"],
                "chunk_text_sha256": sha256(
                    row["chunk_text"].encode("utf-8")
                ).hexdigest(),
                "embedding": vector,
            }
            for row, vector in zip(chunks, vectors, strict=True)
        ],
    }
    runtime_root = (REPOSITORY_ROOT / ".runtime").resolve()
    resolved_output = output_path.resolve()
    try:
        resolved_output.relative_to(runtime_root)
    except ValueError as exc:
        raise RuntimeError("Embedding fixture output must stay under .runtime/.") from exc
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    temporary_path = resolved_output.with_suffix(resolved_output.suffix + ".tmp")
    temporary_path.write_bytes(serialized)
    temporary_path.replace(resolved_output)
    return {
        "status": "FIXTURE_READY",
        "output": str(resolved_output.relative_to(REPOSITORY_ROOT)),
        "fixture_sha256": sha256(serialized).hexdigest(),
        "row_count": len(vectors),
        "dimension": client.dimension,
        "model_name": client.model_name,
        "model_revision": index["model_revision"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    options = parser.parse_args()
    print(
        json.dumps(
            build_fixture(output_path=options.output),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
