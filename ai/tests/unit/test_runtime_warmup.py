"""Local RAG Runtime의 공유 검색 서비스와 시작 Warmup 검증."""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from ai.app import bootstrap
from ai.app.orchestration import pipeline_router
from ai.app.retrieval.indexing.index_manifest import IndexManifest
from ai.app.retrieval.runtime_profile import resolve_rag_runtime_profile


def test_configured_search_service_is_reused_and_warmed_up(monkeypatch):
    dsn = "postgresql://test-only-secret@127.0.0.1:55432/test"
    revision = "5617a9f61b028005a4858fdac845db406aefb181"
    created_clients = []
    created_stores = []

    class FakeEmbeddingClient:
        model_name = "BAAI/bge-m3"
        dimension = 1024

        def __init__(self, *, model_revision):
            self.model_revision = model_revision
            self.warmup_calls = 0
            created_clients.append(self)

        def warmup(self):
            self.warmup_calls += 1

    monkeypatch.setenv("AI_VECTOR_DSN", dsn)
    monkeypatch.setenv("AI_EMBEDDING_REVISION", revision)
    monkeypatch.setenv("AI_VECTOR_TABLE_NAME", "backend_ai_rag_chunks_v1")
    monkeypatch.setattr(pipeline_router, "BgeM3EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(
        pipeline_router,
        "PgVectorStore",
        lambda configured_dsn, *, table_name: created_stores.append(
            (configured_dsn, table_name)
        ) or object(),
    )
    monkeypatch.setattr(pipeline_router, "_SEARCH_SERVICE_CACHE_KEY", None)
    monkeypatch.setattr(pipeline_router, "_SEARCH_SERVICE_CACHE", None)

    first = pipeline_router._configured_search_service()
    second = pipeline_router._configured_search_service()

    assert first is second
    assert len(created_clients) == 1
    assert pipeline_router.warmup_configured_search_service() is True
    assert created_clients[0].warmup_calls == 1
    assert dsn not in pipeline_router._SEARCH_SERVICE_CACHE_KEY
    assert created_stores == [(dsn, "backend_ai_rag_chunks_v1")]
    assert "backend_ai_rag_chunks_v1" in pipeline_router._SEARCH_SERVICE_CACHE_KEY


def test_app_startup_warms_local_rag_only_when_vector_dsn_exists(monkeypatch):
    warmup_calls = []

    monkeypatch.setenv("AI_VECTOR_DSN", "postgresql://configured-for-test")
    monkeypatch.setattr(
        bootstrap,
        "warmup_configured_search_service",
        lambda: warmup_calls.append("called") or True,
    )

    with TestClient(bootstrap.create_app()) as client:
        assert client.get("/health").status_code == 200

    assert warmup_calls == ["called"]


def test_app_startup_skips_local_rag_warmup_without_vector_dsn(monkeypatch):
    monkeypatch.delenv("AI_VECTOR_DSN", raising=False)

    def unexpected_warmup():
        raise AssertionError("Mock-only Runtime must not initialize the embedding model")

    monkeypatch.setattr(bootstrap, "warmup_configured_search_service", unexpected_warmup)

    with TestClient(bootstrap.create_app()) as client:
        assert client.get("/health").status_code == 200


def test_three_model_runtime_profile_selects_only_allowlisted_manifest_and_policy(
    monkeypatch,
    tmp_path,
):
    revision = "5617a9f61b028005a4858fdac845db406aefb181"

    class FakeEmbeddingClient:
        model_name = "BAAI/bge-m3"
        dimension = 1024

        def __init__(self, *, model_revision):
            self.model_revision = model_revision

    manifest = IndexManifest(
        model_name="BAAI/bge-m3",
        model_revision=revision,
        dimension=1024,
        index_type="exact_search",
        index_version="2.0.0",
        chunk_count=53,
        chunk_set_sha256=(
            "5B022EA8F00B22FE8CF9E386D2FFE91A1A136E2C6237ED4B64BA9EDCB181A304"
        ),
        document_hashes={
            "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00": "a" * 64,
            "MAN-SKMAGIC-WPU-IAC425-REV02": "b" * 64,
            "MAN-SKMAGIC-WPU-IAC606-REV00": "c" * 64,
        },
        indexed_at=datetime.now(timezone.utc),
    )
    manifest_path = tmp_path / "index_manifest_3model.json"
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    repository_root = Path(__file__).resolve().parents[3]
    test_profile = replace(
        resolve_rag_runtime_profile("three_model_integration"),
        manifest_relative_path=manifest_path.relative_to(repository_root).as_posix(),
    )

    monkeypatch.setenv("AI_VECTOR_DSN", "postgresql://test-only")
    monkeypatch.setenv("AI_EMBEDDING_REVISION", revision)
    monkeypatch.setenv("AI_VECTOR_TABLE_NAME", "backend_ai_rag_chunks_v1")
    monkeypatch.setenv("AI_RAG_RUNTIME_PROFILE", "three_model_integration")
    monkeypatch.setattr(pipeline_router, "BgeM3EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(pipeline_router, "PgVectorStore", lambda *args, **kwargs: object())
    monkeypatch.setattr(
        pipeline_router,
        "resolve_rag_runtime_profile",
        lambda: test_profile,
    )
    monkeypatch.setattr(pipeline_router, "_SEARCH_SERVICE_CACHE_KEY", None)
    monkeypatch.setattr(pipeline_router, "_SEARCH_SERVICE_CACHE", None)

    service = pipeline_router._configured_search_service()

    assert service.index_manifest == manifest
    assert service.product_filter.target_models == {
        "WPUJAC104DWH",
        "WPUIAC425SNW",
        "WPUIAC606SNW",
    }
    assert set(service.answerability_gate.definition["supported_model_codes"]) == (
        service.product_filter.target_models
    )
    assert "three_model_integration" in pipeline_router._SEARCH_SERVICE_CACHE_KEY


def test_app_startup_warms_persistent_mcp_runtime(monkeypatch):
    calls = []

    monkeypatch.setenv("AI_VECTOR_DSN", "postgresql://configured-for-test")
    monkeypatch.setenv("AI_RETRIEVAL_TRANSPORT", "mcp")
    monkeypatch.setattr(
        bootstrap,
        "warmup_shared_mcp_search_runtime",
        lambda: calls.append("mcp-warmup") or True,
    )
    monkeypatch.setattr(
        bootstrap,
        "warmup_configured_search_service",
        lambda: calls.append("local-warmup") or True,
    )
    monkeypatch.setattr(
        bootstrap,
        "close_shared_mcp_session_manager",
        lambda: calls.append("mcp-close"),
    )

    with TestClient(bootstrap.create_app()) as client:
        assert client.get("/health").status_code == 200

    assert calls == ["mcp-warmup", "mcp-close"]