"""팀 PostgreSQL/pgvector 읽기 전용 Runtime Gate."""

import os
from pathlib import Path

import psycopg
from psycopg import sql
import pytest

from ai.app.common.protected_database import run_protected_database_operation
from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.integrations.vector_store.vector_store import PgVectorStore
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.search.vector_search import VectorSearchService
from ai.app.retrieval.indexing.index_manifest import IndexManifest


REQUIRED_TEAM_TABLE = "backend_ai_rag_chunks_v1"
FORBIDDEN_BACKEND_TABLES = (
    "accounts_user",
    "knowledge_document_chunk",
    "knowledge_chunk_embedding",
    "knowledge_ai_chunk_crosswalk",
)


def _required_environment(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.fail(f"팀 pgvector Gate 필수 환경변수가 없습니다: {name}")
    return value


def test_actual_pgvector_rows_dimension_and_exact_search():
    dsn = _required_environment("AI_VECTOR_DSN")
    revision = _required_environment("AI_EMBEDDING_REVISION")
    table_name = _required_environment("AI_VECTOR_TABLE_NAME")
    assert table_name == REQUIRED_TEAM_TABLE
    store = PgVectorStore(dsn, table_name=table_name)
    def verify_database_permissions_and_shape() -> None:
        with (
            psycopg.connect(dsn, connect_timeout=5) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SHOW default_transaction_read_only")
            assert cursor.fetchone() == ("on",)
            cursor.execute(
                "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"
            )
            assert cursor.fetchone() == (False,)
            cursor.execute(
                """
                SELECT c.relkind,
                       has_table_privilege(current_user, c.oid, 'SELECT'),
                       has_table_privilege(current_user, c.oid, 'INSERT'),
                       has_table_privilege(current_user, c.oid, 'UPDATE'),
                       has_table_privilege(current_user, c.oid, 'DELETE'),
                       has_table_privilege(current_user, c.oid, 'TRUNCATE')
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = current_schema()
                  AND c.relname = %s
                """,
                (table_name,),
            )
            assert cursor.fetchone() == ("v", True, False, False, False, False)
            for backend_table in FORBIDDEN_BACKEND_TABLES:
                cursor.execute(
                    "SELECT to_regclass(%s)",
                    (f"public.{backend_table}",),
                )
                relation = cursor.fetchone()[0]
                assert relation is not None
                for privilege in (
                    "SELECT",
                    "INSERT",
                    "UPDATE",
                    "DELETE",
                    "TRUNCATE",
                ):
                    cursor.execute(
                        "SELECT has_table_privilege(current_user, %s, %s)",
                        (f"public.{backend_table}", privilege),
                    )
                    assert cursor.fetchone() == (False,)
            cursor.execute(
                sql.SQL("""
                SELECT COUNT(*), COUNT(DISTINCT chunk_id),
                       MIN(vector_dims(embedding)), MAX(vector_dims(embedding))
                FROM {}
                WHERE chunk_id LIKE 'RAG-WPUJAC104DWH-%'
                """).format(sql.Identifier(store.table_name))
            )
            assert cursor.fetchone() == (7, 7, 1024, 1024)

    run_protected_database_operation(
        verify_database_permissions_and_shape,
        public_message=(
            "팀 pgvector 연결·권한·Shape 검증에 실패했습니다. "
            "보호 DSN 원문은 출력하지 않습니다."
        ),
    )

    manifest = IndexManifest.load_manifest(str(
        Path(__file__).resolve().parents[2] / "configs" / "index_manifest.json"
    ))
    assert manifest is not None
    service = VectorSearchService(
        BgeM3EmbeddingClient(model_revision=revision),
        store,
        index_manifest=manifest,
    )
    results = run_protected_database_operation(
        lambda: service.search(RetrievalQuery(
            query_text="정수기에서 물이 나오지 않을 때 무엇을 확인해야 하나요?",
            model_code="WPUJAC104DWH",
            top_k=5,
        )),
        public_message=(
            "팀 pgvector 실제 검색에 실패했습니다. "
            "보호 DSN 원문은 출력하지 않습니다."
        ),
    )
    assert results
    assert results[0].chunk_id == "RAG-WPUJAC104DWH-NO-WATER-001"
    assert all(result.verification_status == "official_verified" for result in results)
    assert all(result.allowed_use for result in results)
    assert all(result.document_id == "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00" for result in results)
    assert all(result.page_refs for result in results)
    assert all(result.embedding_model_revision == revision for result in results)
    assert all(result.index_version == manifest.index_version for result in results)
    assert all(
        result.chunk_set_sha256.casefold() == manifest.chunk_set_sha256.casefold()
        for result in results
    )
