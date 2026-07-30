"""실제 PostgreSQL/pgvector 연결이 제공될 때만 실행하는 통합 검증."""

import os

import psycopg
import pytest

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.integrations.vector_store.vector_store import PgVectorStore
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.search.vector_search import VectorSearchService


pytestmark = pytest.mark.skipif(
    not os.getenv("AI_VECTOR_DSN") or not os.getenv("AI_EMBEDDING_REVISION"),
    reason="실제 pgvector 통합 검증 환경이 설정되지 않았습니다.",
)


def test_actual_pgvector_rows_dimension_and_exact_search():
    dsn = os.environ["AI_VECTOR_DSN"]
    revision = os.environ["AI_EMBEDDING_REVISION"]
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT chunk_id),
                   MIN(vector_dims(embedding)), MAX(vector_dims(embedding))
            FROM ai_rag_chunks
            """
        )
        assert cursor.fetchone() == (7, 7, 1024, 1024)

    service = VectorSearchService(
        BgeM3EmbeddingClient(model_revision=revision),
        PgVectorStore(dsn),
    )
    results = service.search(RetrievalQuery(
        query_text="정수기에서 물이 나오지 않을 때 무엇을 확인해야 하나요?",
        model_code="WPUJAC104DWH",
        top_k=5,
    ))
    assert results
    assert results[0].chunk_id == "RAG-WPUJAC104DWH-NO-WATER-001"
    assert all(result.verification_status == "official_verified" for result in results)
    assert all(result.allowed_use for result in results)
