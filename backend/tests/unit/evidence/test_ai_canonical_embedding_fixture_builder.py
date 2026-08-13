"""Transient canonical embedding fixture builder tests."""

from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def test_builder_writes_seven_by_1024_fixture_under_runtime(monkeypatch):
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

    class FakeEmbeddingClient:
        model_name = "BAAI/bge-m3"
        dimension = 1024

        def __init__(self, *, model_revision):
            self.model_revision = model_revision

        def embed_documents(self, texts):
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

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["status"] == "FIXTURE_READY"
    assert result["row_count"] == 7
    assert result["dimension"] == 1024
    assert result["fixture_sha256"] == sha256(output_path.read_bytes()).hexdigest()
    assert len(payload["rows"]) == 7
    assert {len(row["embedding"]) for row in payload["rows"]} == {1024}
    assert payload["model_revision"] == (
        "5617a9f61b028005a4858fdac845db406aefb181"
    )
