"""Local RAG Runtime의 공유 검색 서비스와 시작 Warmup 검증."""

from fastapi.testclient import TestClient

from ai.app import bootstrap
from ai.app.orchestration import pipeline_router


def test_configured_search_service_is_reused_and_warmed_up(monkeypatch):
    dsn = "postgresql://test-only-secret@127.0.0.1:55432/test"
    revision = "5617a9f61b028005a4858fdac845db406aefb181"
    created_clients = []

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
    monkeypatch.setattr(pipeline_router, "BgeM3EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(pipeline_router, "PgVectorStore", lambda configured_dsn: object())
    monkeypatch.setattr(pipeline_router, "_SEARCH_SERVICE_CACHE_KEY", None)
    monkeypatch.setattr(pipeline_router, "_SEARCH_SERVICE_CACHE", None)

    first = pipeline_router._configured_search_service()
    second = pipeline_router._configured_search_service()

    assert first is second
    assert len(created_clients) == 1
    assert pipeline_router.warmup_configured_search_service() is True
    assert created_clients[0].warmup_calls == 1
    assert dsn not in pipeline_router._SEARCH_SERVICE_CACHE_KEY


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
