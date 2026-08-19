"""Three-model transient embedding fixture builder tests."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def _load_builder():
    script_path = (
        REPOSITORY_ROOT
        / "scripts"
        / "database"
        / "build_ai_three_model_embedding_fixture.py"
    )
    spec = importlib.util.spec_from_file_location(
        "build_ai_three_model_embedding_fixture",
        script_path,
    )
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))
    return module


def _identity(builder, rows):
    chunks = [
        {
            "chunk_id": row["child_id"],
            "document_id": row["document_id"],
            "page_refs": row["page_refs"],
            "model_code": row["exact_sales_code"],
            "product_generation": row["product_generation"],
            "verification_status": row["verification_status"],
            "source_file_sha256": row["source_file_sha256"],
            "chunk_text_sha256": row["child_text_sha256"],
        }
        for row in rows
    ]
    return {
        "schema_version": "1.0.0",
        "status": builder.IDENTITY_STATUS,
        "index_version": builder.INDEX_VERSION,
        "chunk_count": 53,
        "model_chunk_counts": builder.EXPECTED_MODEL_COUNTS,
        "chunk_set_sha256": builder._chunk_set_sha256(rows),
        "chunks": chunks,
    }


def test_builder_writes_53_by_1024_fixture_and_actual_index(monkeypatch):
    builder = _load_builder()
    rows = builder._load_source_rows()
    identity_path = REPOSITORY_ROOT / ".runtime" / "backend-ai" / "test-identity.json"
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    identity_path.write_text(
        json.dumps(_identity(builder, rows), ensure_ascii=False),
        encoding="utf-8",
    )
    embedded_texts = []

    class FakeEmbeddingClient:
        model_name = builder.EMBEDDING_MODEL
        dimension = builder.EMBEDDING_DIMENSION

        def __init__(self, *, model_revision):
            assert model_revision == builder.EMBEDDING_REVISION

        def embed_documents(self, texts):
            values = list(texts)
            embedded_texts.extend(values)
            return [
                [float(index + 1) / 1000.0] * self.dimension
                for index, _value in enumerate(values)
            ]

    monkeypatch.setattr(builder, "BgeM3EmbeddingClient", FakeEmbeddingClient)
    fixture_path = (
        REPOSITORY_ROOT / ".runtime" / "backend-ai" / "three-model-test-fixture.json"
    )
    index_path = (
        REPOSITORY_ROOT / ".runtime" / "backend-ai" / "three-model-test-index.json"
    )

    result = builder.build_artifacts(
        identity_path=identity_path,
        fixture_output=fixture_path,
        index_output=index_path,
        indexed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
    )

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert result["status"] == "THREE_MODEL_ARTIFACTS_READY"
    assert result["row_count"] == 53
    assert result["model_counts"] == {
        "WPUJAC104DWH": 15,
        "WPUIAC425SNW": 19,
        "WPUIAC606SNW": 19,
    }
    assert len(fixture["rows"]) == 53
    assert {len(row["embedding"]) for row in fixture["rows"]} == {1024}
    assert [row["chunk_id"] for row in fixture["rows"]] == sorted(
        row["chunk_id"] for row in fixture["rows"]
    )
    assert embedded_texts == [str(row["child_text"]) for row in rows]
    assert index["chunk_count"] == 53
    assert index["index_version"] == "2.0.0"
    assert index["indexed_at"] == "2026-08-19T00:00:00Z"
    assert set(index["document_hashes"]) == {
        "MAN-SKMAGIC-WPU-IAC425-REV02",
        "MAN-SKMAGIC-WPU-IAC606-REV00",
        "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00",
    }
    assert not fixture_path.read_bytes().endswith(b"\n")
    assert not index_path.read_bytes().endswith(b"\n")


def test_builder_rejects_identity_model_distribution_drift():
    builder = _load_builder()
    rows = builder._load_source_rows()
    identity = _identity(builder, rows)
    identity["model_chunk_counts"] = {"WPUJAC104DWH": 53}

    with pytest.raises(RuntimeError, match="model distribution"):
        builder._validate_identity(identity, rows)


def test_builder_rejects_output_outside_runtime(monkeypatch):
    builder = _load_builder()
    rows = builder._load_source_rows()
    identity_path = REPOSITORY_ROOT / ".runtime" / "backend-ai" / "test-identity.json"
    identity_path.parent.mkdir(parents=True, exist_ok=True)
    identity_path.write_text(
        json.dumps(_identity(builder, rows), ensure_ascii=False),
        encoding="utf-8",
    )

    class FakeEmbeddingClient:
        model_name = builder.EMBEDDING_MODEL
        dimension = builder.EMBEDDING_DIMENSION

        def __init__(self, *, model_revision):
            del model_revision

        def embed_documents(self, texts):
            return [[0.0] * self.dimension for _value in texts]

    monkeypatch.setattr(builder, "BgeM3EmbeddingClient", FakeEmbeddingClient)

    with pytest.raises(RuntimeError, match="must stay under .runtime"):
        builder.build_artifacts(
            identity_path=identity_path,
            fixture_output=REPOSITORY_ROOT / "fixture-outside-runtime.json",
            index_output=REPOSITORY_ROOT / ".runtime" / "backend-ai" / "index.json",
        )
