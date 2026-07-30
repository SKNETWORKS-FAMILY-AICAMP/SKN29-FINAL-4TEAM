"""실제 pgvector 적재·검색·필터·평가 계약을 검증하고 증거 JSON을 저장한다."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.integrations.vector_store.vector_store import PgVectorStore
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.search.vector_search import VectorSearchService
from ai.evaluation.metrics import calculate_mrr, calculate_recall_at_k


def _database_facts(dsn: str) -> dict:
    with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute("SHOW server_version")
        postgres_version = cursor.fetchone()[0]
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        vector_version = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT chunk_id),
                   MIN(vector_dims(embedding)), MAX(vector_dims(embedding)),
                   COUNT(DISTINCT source_hash)
            FROM ai_rag_chunks
            """
        )
        row_count, distinct_ids, min_dimension, max_dimension, source_hash_count = cursor.fetchone()
    return {
        "postgres_version": postgres_version,
        "pgvector_version": vector_version,
        "row_count": row_count,
        "distinct_chunk_ids": distinct_ids,
        "min_dimension": min_dimension,
        "max_dimension": max_dimension,
        "source_hash_count": source_hash_count,
    }


def _evaluate(search_service: VectorSearchService, config_path: Path) -> list[dict]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    results = []
    for case in config["cases"]:
        query = RetrievalQuery(
            query_text=case["query"],
            model_code=case["product_model_code"],
            product_generation="D",
            top_k=case["top_k"],
        )
        chunks = search_service.search(query)
        ranked_ids = [chunk.chunk_id for chunk in chunks]
        ranked_documents = [chunk.document_id for chunk in chunks]
        forbidden_hits = sorted(
            {
                chunk.chunk_id
                for chunk in chunks
                if chunk.model_code in case["forbidden_model_codes"]
                or chunk.document_id in case["forbidden_document_ids"]
            }
        )
        expected_ids = case["expected_chunk_ids"]
        recall = calculate_recall_at_k(ranked_ids, expected_ids, k=case["top_k"]) if expected_ids else 1.0
        mrr = calculate_mrr(ranked_ids, expected_ids) if expected_ids else 1.0
        no_evidence_pass = not case["expected_no_evidence"] or not ranked_ids
        passed = recall >= (1.0 if expected_ids else 0.0) and not forbidden_hits and no_evidence_pass
        results.append({
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "ranked_chunk_ids": ranked_ids,
            "ranked_document_ids": ranked_documents,
            "scores": [round(chunk.similarity_score, 6) for chunk in chunks],
            "recall_at_5": recall,
            "mrr": mrr,
            "forbidden_hits": forbidden_hits,
            "expected_no_evidence": case["expected_no_evidence"],
            "passed": passed,
        })
    return results


def _verify_sql_filters(
    dsn: str,
    store: PgVectorStore,
    embedding_client: BgeM3EmbeddingClient,
) -> dict:
    """유사도 1.0의 금지 Fixture가 실제 WHERE 조건에서 빠지는지 검증한다."""
    vector = embedding_client.embed_query("정수기 누수 안전 조치")
    literal = store._vector_literal(vector)
    fixtures = [
        ("VERIFY-UNVERIFIED", "WPUJAC104DWH", "D", "unverified", True),
        ("VERIFY-DISALLOWED", "WPUJAC104DWH", "D", "official_verified", False),
        ("VERIFY-WRONG-GENERATION", "WPUJAC104DWH", "S", "official_verified", True),
        ("VERIFY-WRONG-MODEL", "WATERCARE-X999", "D", "official_verified", True),
    ]
    insert_sql = """
        INSERT INTO ai_rag_chunks (
            chunk_id, document_id, document_title, document_version, page,
            manual_model, model_code, product_generation, content, embedding,
            official_url, verification_status, allowed_use, source_hash,
            safe_actions, metadata
        ) VALUES (
            %s, 'VERIFY-DOC', '검증용 금지 문서', 'VERIFY', 1,
            %s, %s, %s, '검증용 금지 청크', %s::vector,
            NULL, %s, %s, %s, '[]'::jsonb, %s::jsonb
        )
    """
    source_hash = "F" * 64
    try:
        with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
            for chunk_id, model_code, generation, verification, allowed in fixtures:
                metadata = {
                    "document_id": "VERIFY-DOC",
                    "document_title": "검증용 금지 문서",
                    "document_version": "VERIFY",
                    "page": 1,
                    "manual_model": model_code,
                    "model_code": model_code,
                    "product_generation": generation,
                    "official_url": None,
                    "verification_status": verification,
                    "allowed_use": allowed,
                    "source_hash": source_hash,
                    "safe_actions": [],
                }
                cursor.execute(
                    insert_sql,
                    (
                        chunk_id,
                        model_code,
                        model_code,
                        generation,
                        literal,
                        verification,
                        allowed,
                        source_hash,
                        json.dumps(metadata, ensure_ascii=False),
                    ),
                )
        results = store.search(
            vector,
            model_code="WPUJAC104DWH",
            product_generation="D",
            top_k=20,
        )
        fixture_ids = {item[0] for item in fixtures}
        leaked_ids = sorted(chunk.chunk_id for chunk in results if chunk.chunk_id in fixture_ids)
    finally:
        with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM ai_rag_chunks WHERE chunk_id LIKE 'VERIFY-%'")

    dimension_rejected = False
    try:
        with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ai_rag_chunks (
                    chunk_id, document_id, document_title, manual_model, model_code,
                    product_generation, content, embedding, verification_status,
                    allowed_use, source_hash, metadata
                ) VALUES (
                    'VERIFY-BAD-DIMENSION', 'VERIFY-DOC', '검증용', 'WPUJAC104DWH',
                    'WPUJAC104DWH', 'D', '검증용', '[0,0,0]'::vector,
                    'official_verified', TRUE, %s, '{}'::jsonb
                )
                """,
                (source_hash,),
            )
    except psycopg.Error:
        dimension_rejected = True
    finally:
        with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
            cursor.execute("DELETE FROM ai_rag_chunks WHERE chunk_id = 'VERIFY-BAD-DIMENSION'")

    return {
        "fixture_count": len(fixtures),
        "leaked_fixture_ids": leaked_ids,
        "metadata_filter_passed": not leaked_ids,
        "invalid_dimension_rejected": dimension_rejected,
    }


def main() -> None:
    dsn = os.getenv("AI_VECTOR_DSN")
    model_revision = os.getenv("AI_EMBEDDING_REVISION")
    if not dsn or not model_revision:
        raise RuntimeError("AI_VECTOR_DSN과 AI_EMBEDDING_REVISION이 필요합니다.")

    repository_root = Path(__file__).resolve().parents[2]
    config_path = repository_root / "data" / "config" / "rag" / "jac104_retrieval_cases.json"
    report_path = repository_root / "ai" / "evaluation" / "reports" / "pgvector_verification.json"

    embedding_client = BgeM3EmbeddingClient(model_revision=model_revision)
    store = PgVectorStore(dsn)
    search_service = VectorSearchService(embedding_client, store)
    sql_filter_verification = _verify_sql_filters(dsn, store, embedding_client)
    facts = _database_facts(dsn)
    cases = _evaluate(search_service, config_path)
    positive = [case for case in cases if case["case_type"] == "POSITIVE"]
    forbidden_hit_count = sum(len(case["forbidden_hits"]) for case in cases)
    report = {
        "verification_status": "PASS" if (
            all(case["passed"] for case in cases)
            and sql_filter_verification["metadata_filter_passed"]
            and sql_filter_verification["invalid_dimension_rejected"]
        ) else "PARTIAL",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": embedding_client.model_name,
        "embedding_model_version": model_revision,
        "dimension": embedding_client.dimension,
        "search_type": "cosine_exact_search",
        "top_k": 5,
        "score_threshold": store.score_threshold,
        "ann_used": False,
        "database": facts,
        "sql_filter_verification": sql_filter_verification,
        "summary": {
            "case_count": len(cases),
            "passed_count": sum(case["passed"] for case in cases),
            "failed_count": sum(not case["passed"] for case in cases),
            "mean_positive_recall_at_5": sum(case["recall_at_5"] for case in positive) / len(positive),
            "mean_positive_mrr": sum(case["mrr"] for case in positive) / len(positive),
            "forbidden_hit_count": forbidden_hit_count,
        },
        "cases": cases,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "verification_status": report["verification_status"],
        "report_path": str(report_path.relative_to(repository_root)),
        **report["summary"],
        "database": facts,
        "sql_filter_verification": sql_filter_verification,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
