"""Contract tests for the AI-owned canonical embedding fixture exporter."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pytest

from ai.scripts import export_canonical_embedding_fixture as exporter


ROOT_FIELDS = {
    "schema_version",
    "status",
    "model_name",
    "model_revision",
    "dimension",
    "index_version",
    "chunk_set_sha256",
    "embedding_dtype",
    "rows",
}
ROW_FIELDS = {"chunk_id", "chunk_text_sha256", "embedding"}


class FakeEmbeddingClient:
    model_name = exporter.MODEL_NAME
    dimension = exporter.DIMENSION
    embedded_texts: list[str] = []

    def __init__(self, *, model_revision: str) -> None:
        assert model_revision == exporter.MODEL_REVISION
        self.model_revision = model_revision

    def embed_documents(self, texts):
        self.embedded_texts = list(texts)
        type(self).embedded_texts = self.embedded_texts
        return [
            [np.float64((row_index + 1) / 1000)] * self.dimension
            for row_index, _text in enumerate(self.embedded_texts)
        ]


def _runtime_output(name: str) -> Path:
    return exporter.REPOSITORY_ROOT / ".runtime" / "backend-ai" / name


def _source_rows() -> list[dict]:
    return exporter._load_jsonl_objects(exporter.SOURCE_DATASET_PATH)


def _identity_rows() -> list[dict]:
    return exporter._load_json_object(exporter.IDENTITY_PATH)["chunks"]


def test_exporter_writes_deterministic_canonical_seven_by_1024_fixture():
    first_path = _runtime_output("canonical_embedding_fixture_exporter_test_1.json")
    second_path = _runtime_output("canonical_embedding_fixture_exporter_test_2.json")

    first = exporter.export_fixture(
        output_path=first_path, client_factory=FakeEmbeddingClient
    )
    second = exporter.export_fixture(
        output_path=second_path, client_factory=FakeEmbeddingClient
    )

    fixture_bytes = first_path.read_bytes()
    payload = json.loads(fixture_bytes.decode("utf-8"))
    assert first_path.read_bytes() == second_path.read_bytes()
    assert (
        first["fixture_sha256"]
        == second["fixture_sha256"]
        == sha256(fixture_bytes).hexdigest()
    )
    assert set(payload) == ROOT_FIELDS
    assert all(set(row) == ROW_FIELDS for row in payload["rows"])
    assert payload["schema_version"] == "1.0.0"
    assert payload["status"] == "GENERATED_FROM_APPROVED_BASELINE_PENDING_DB_IMPORT"
    assert payload["model_name"] == "BAAI/bge-m3"
    assert payload["model_revision"] == exporter.MODEL_REVISION
    assert payload["dimension"] == 1024
    assert payload["index_version"] == "1.0.0"
    assert payload["chunk_set_sha256"] == exporter.CHUNK_SET_SHA256
    assert payload["embedding_dtype"] == "FLOAT32"
    assert len(payload["rows"]) == 7
    assert {len(row["embedding"]) for row in payload["rows"]} == {1024}
    assert all(
        value == float(np.float32(value))
        for row in payload["rows"]
        for value in row["embedding"]
    )
    assert [row["chunk_id"] for row in payload["rows"]] == sorted(
        row["chunk_id"] for row in payload["rows"]
    )
    source_by_id = {row["chunk_id"]: row for row in _source_rows()}
    assert FakeEmbeddingClient.embedded_texts == [
        source_by_id[row["chunk_id"]]["chunk_text"] for row in payload["rows"]
    ]
    assert all(
        row["chunk_text_sha256"]
        == sha256(
            source_by_id[row["chunk_id"]]["chunk_text"].encode("utf-8")
        ).hexdigest()
        for row in payload["rows"]
    )
    assert fixture_bytes == exporter._canonical_bytes(payload)
    assert not fixture_bytes.endswith(b"\n")
    assert first["nfc_validation"] == "7/7"
    assert first["rows_dimension"] == "7x1024"
    assert first["fixture_status"] == payload["status"]


def test_exporter_rejects_duplicate_chunk_ids():
    rows = _source_rows()
    rows[1]["chunk_id"] = rows[0]["chunk_id"]

    with pytest.raises(RuntimeError, match="chunk IDs must be unique"):
        exporter._validate_and_sort_chunks(rows, _identity_rows())


def test_exporter_rejects_non_nfc_without_mutating_source():
    rows = _source_rows()
    rows[0]["chunk_text"] = "e\u0301"
    original = deepcopy(rows)

    with pytest.raises(RuntimeError, match="already be NFC normalized"):
        exporter._validate_and_sort_chunks(rows, _identity_rows())

    assert rows == original
    assert rows[0]["chunk_text"] == "e\u0301"


@pytest.mark.parametrize("invalid_value", [True, "0.1", float("nan"), float("inf")])
def test_exporter_rejects_bool_string_nan_and_infinity(invalid_value):
    output_path = _runtime_output("canonical_embedding_fixture_exporter_invalid_test.json")

    class InvalidEmbeddingClient(FakeEmbeddingClient):
        def embed_documents(self, texts):
            vectors = super().embed_documents(texts)
            vectors[0][0] = invalid_value
            return vectors

    with pytest.raises(RuntimeError, match="non-numeric|NaN or Infinity"):
        exporter.export_fixture(
            output_path=output_path, client_factory=InvalidEmbeddingClient
        )


def test_exporter_casts_values_to_float32_without_manual_decimal_rounding():
    converted = exporter._to_float32_vectors(
        [[0.123456789] * exporter.DIMENSION for _ in range(exporter.ROW_COUNT)]
    )

    assert converted[0][0] == float(np.float32(0.123456789))


def test_exporter_rejects_output_outside_repository_runtime(tmp_path):
    with pytest.raises(RuntimeError, match="must stay under repository .runtime"):
        exporter.export_fixture(
            output_path=tmp_path / "fixture.json",
            client_factory=FakeEmbeddingClient,
        )


def test_exporter_resolves_relative_output_from_repository_root():
    output_path = Path(".runtime/backend-ai/canonical_embedding_fixture_relative_test.json")

    result = exporter.export_fixture(
        output_path=output_path,
        client_factory=FakeEmbeddingClient,
    )

    assert result["artifact_relative_path"] == output_path.as_posix()
    assert (exporter.REPOSITORY_ROOT / output_path).is_file()
