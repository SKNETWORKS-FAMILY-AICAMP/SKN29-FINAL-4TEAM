"""Transient canonical embedding fixture builder tests."""

from __future__ import annotations

from hashlib import sha256
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
        / "build_ai_canonical_embedding_fixture.py"
    )
    spec = importlib.util.spec_from_file_location(
        "build_ai_canonical_embedding_fixture",
        script_path,
    )
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))
    return builder


def test_builder_writes_deterministic_seven_by_1024_fixture(monkeypatch):
    builder = _load_builder()
    embedded_texts = []

    class FakeEmbeddingClient:
        model_name = "BAAI/bge-m3"
        dimension = 1024

        def __init__(self, *, model_revision):
            self.model_revision = model_revision

        def embed_documents(self, texts):
            texts = list(texts)
            embedded_texts.extend(texts)
            return [
                [float(index + 1) / 1000.0] * self.dimension
                for index, _text in enumerate(texts)
            ]

    monkeypatch.setattr(builder, "BgeM3EmbeddingClient", FakeEmbeddingClient)
    output_path = (
        REPOSITORY_ROOT
        / ".runtime"
        / "backend-ai"
        / "canonical_embedding_fixture_test.json"
    )

    result = builder.build_fixture(output_path=output_path)

    fixture_bytes = output_path.read_bytes()
    payload = json.loads(fixture_bytes.decode("utf-8"))
    assert result["status"] == "FIXTURE_READY"
    assert result["row_count"] == 7
    assert result["dimension"] == 1024
    assert result["embedding_dtype"] == "FLOAT32"
    assert result["row_order"] == "chunk_id_ASC"
    assert result["nfc_validation"] == "7/7"
    assert result["fixture_sha256"] == sha256(fixture_bytes).hexdigest()
    assert payload["schema_version"] == "1.0.0"
    assert payload["status"] == "GENERATED_FROM_APPROVED_BASELINE_PENDING_DB_IMPORT"
    assert payload["embedding_dtype"] == "FLOAT32"
    assert len(payload["rows"]) == 7
    assert {len(row["embedding"]) for row in payload["rows"]} == {1024}
    row_ids = [row["chunk_id"] for row in payload["rows"]]
    assert row_ids == sorted(row_ids)
    source_rows = [
        json.loads(line)
        for line in (
            REPOSITORY_ROOT
            / "data"
            / "processed"
            / "structured"
            / "rag"
            / "mvp"
            / "rag_verified_sample.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    source_by_id = {row["chunk_id"]: row for row in source_rows}
    assert embedded_texts == [
        source_by_id[chunk_id]["chunk_text"] for chunk_id in row_ids
    ]
    assert fixture_bytes == json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert not fixture_bytes.endswith(b"\n")
    assert payload["model_revision"] == (
        "5617a9f61b028005a4858fdac845db406aefb181"
    )


@pytest.mark.parametrize("invalid_value", [True, "0.1", float("nan"), float("inf")])
def test_builder_rejects_non_finite_or_non_numeric_vectors(monkeypatch, invalid_value):
    builder = _load_builder()

    class InvalidEmbeddingClient:
        model_name = "BAAI/bge-m3"
        dimension = 1024

        def __init__(self, *, model_revision):
            self.model_revision = model_revision

        def embed_documents(self, texts):
            vectors = [[0.0] * self.dimension for _ in texts]
            vectors[0][0] = invalid_value
            return vectors

    monkeypatch.setattr(builder, "BgeM3EmbeddingClient", InvalidEmbeddingClient)
    output_path = (
        REPOSITORY_ROOT
        / ".runtime"
        / "backend-ai"
        / "canonical_embedding_fixture_invalid_test.json"
    )

    with pytest.raises(RuntimeError, match="contains invalid values"):
        builder.build_fixture(output_path=output_path)


def test_builder_nfc_policy_validates_without_mutating_text():
    builder = _load_builder()

    assert builder._require_nfc("정수기", label="chunk_text") == "정수기"
    with pytest.raises(RuntimeError, match="already be NFC normalized"):
        builder._require_nfc("e\u0301", label="chunk_text")
