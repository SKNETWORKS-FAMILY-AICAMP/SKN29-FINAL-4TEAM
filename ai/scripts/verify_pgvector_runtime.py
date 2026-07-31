"""실제 pgvector 적재·검색·필터·평가 계약을 검증하고 증거 JSON을 저장한다."""

import json
import os
import platform
import re
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from ai.app.integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ai.app.integrations.vector_store.vector_store import PgVectorStore
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.search.vector_search import VectorSearchService
from ai.app.retrieval.indexing.index_manifest import IndexManifest
from ai.evaluation.metrics import calculate_mrr, calculate_recall_at_k


def _database_facts(dsn: str) -> dict:
    with psycopg.connect(dsn, connect_timeout=5) as connection, connection.cursor() as cursor:
        cursor.execute("SHOW server_version")
        postgres_version = cursor.fetchone()[0]
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        vector_version = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT chunk_id),
                   MIN(vector_dims(embedding)), MAX(vector_dims(embedding)),
                   COUNT(DISTINCT source_hash),
                   ARRAY_AGG(DISTINCT metadata->>'embedding_model_revision'),
                   ARRAY_AGG(DISTINCT metadata->>'index_version'),
                   ARRAY_AGG(DISTINCT metadata->>'chunk_set_sha256')
            FROM ai_rag_chunks
            """
        )
        (
            row_count, distinct_ids, min_dimension, max_dimension, source_hash_count,
            embedding_revisions, index_versions, chunk_set_hashes,
        ) = cursor.fetchone()
        cursor.execute(
            """
            SELECT document_id, ARRAY_AGG(DISTINCT source_hash)
            FROM ai_rag_chunks
            GROUP BY document_id
            ORDER BY document_id
            """
        )
        document_source_hashes = {
            document_id: hashes[0] if len(hashes) == 1 else hashes
            for document_id, hashes in cursor.fetchall()
        }
    return {
        "postgres_version": postgres_version,
        "pgvector_version": vector_version,
        "row_count": row_count,
        "distinct_chunk_ids": distinct_ids,
        "min_dimension": min_dimension,
        "max_dimension": max_dimension,
        "source_hash_count": source_hash_count,
        "embedding_model_revisions": embedding_revisions,
        "index_versions": index_versions,
        "chunk_set_sha256_values": chunk_set_hashes,
        "document_source_hashes": document_source_hashes,
    }


def _assert_disposable_database(dsn: str) -> str:
    if os.getenv("AI_VECTOR_DISPOSABLE_CONFIRM") != "DISPOSABLE_ONLY":
        raise RuntimeError(
            "검증 Fixture는 AI_VECTOR_DISPOSABLE_CONFIRM=DISPOSABLE_ONLY인 DB에서만 허용됩니다."
        )
    with psycopg.connect(dsn, connect_timeout=5) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        database_name = str(cursor.fetchone()[0])
    if not re.search(r"(verify|test|tmp|disposable)", database_name, re.IGNORECASE):
        raise RuntimeError(f"공유 DB 검증을 거부했습니다: {database_name}")
    return database_name


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
        execution_path = search_service.execution_path(query)
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
        expected_document = case["expected_document_id"]
        expected_pages = set(case["expected_page_numbers"])
        expected_chunks = [chunk for chunk in chunks if chunk.chunk_id in expected_ids]
        document_match = not expected_document or all(
            chunk.document_id == expected_document for chunk in expected_chunks
        )
        page_match = not expected_pages or all(
            expected_pages.issubset(set(chunk.page_refs or ([chunk.page] if chunk.page else [])))
            for chunk in expected_chunks
        )
        model_generation_match = all(
            chunk.model_code == case["product_model_code"] and chunk.product_generation == "D"
            for chunk in chunks
        )
        provenance_match = all(
            chunk.embedding_model
            and chunk.embedding_model_revision
            and chunk.index_version
            and chunk.chunk_set_sha256
            and chunk.source_hash
            and chunk.document_version
            for chunk in chunks
        )
        recall = calculate_recall_at_k(ranked_ids, expected_ids, k=case["top_k"]) if expected_ids else 1.0
        mrr = calculate_mrr(ranked_ids, expected_ids) if expected_ids else 1.0
        no_evidence_pass = not case["expected_no_evidence"] or not ranked_ids
        passed = (
            recall >= (1.0 if expected_ids else 0.0)
            and not forbidden_hits
            and no_evidence_pass
            and document_match
            and page_match
            and model_generation_match
            and provenance_match
        )
        results.append({
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "ranked_chunk_ids": ranked_ids,
            "ranked_document_ids": ranked_documents,
            "ranked_page_refs": [chunk.page_refs for chunk in chunks],
            "ranked_model_codes": [chunk.model_code for chunk in chunks],
            "ranked_product_generations": [chunk.product_generation for chunk in chunks],
            "ranked_document_versions": [chunk.document_version for chunk in chunks],
            "ranked_embedding_revisions": [chunk.embedding_model_revision for chunk in chunks],
            "ranked_index_versions": [chunk.index_version for chunk in chunks],
            "ranked_chunk_set_sha256": [chunk.chunk_set_sha256 for chunk in chunks],
            "execution_path": execution_path,
            "scores": [round(chunk.similarity_score, 6) for chunk in chunks],
            "recall_at_5": recall,
            "mrr": mrr,
            "forbidden_hits": forbidden_hits,
            "expected_no_evidence": case["expected_no_evidence"],
            "document_metadata_passed": document_match,
            "page_metadata_passed": page_match,
            "model_generation_passed": model_generation_match,
            "provenance_passed": provenance_match,
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
    connection = psycopg.connect(dsn, connect_timeout=5)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '10s'")
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
            cursor.execute(
                """
                SELECT chunk_id
                FROM ai_rag_chunks
                WHERE model_code = %s
                  AND product_generation = %s
                  AND verification_status = 'official_verified'
                  AND allowed_use = TRUE
                  AND 1 - (embedding <=> %s::vector) >= %s
                ORDER BY 1 - (embedding <=> %s::vector) DESC, chunk_id
                LIMIT 20
                """,
                ("WPUJAC104DWH", "D", literal, store.score_threshold, literal),
            )
            ranked_ids = [row[0] for row in cursor.fetchall()]
        fixture_ids = {item[0] for item in fixtures}
        leaked_ids = sorted(chunk_id for chunk_id in ranked_ids if chunk_id in fixture_ids)

        dimension_rejected = False
        with connection.cursor() as cursor:
            cursor.execute("SAVEPOINT invalid_dimension_check")
            try:
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
                cursor.execute("ROLLBACK TO SAVEPOINT invalid_dimension_check")
            finally:
                cursor.execute("RELEASE SAVEPOINT invalid_dimension_check")
    finally:
        connection.rollback()
        connection.close()

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
    database_name = _assert_disposable_database(dsn)

    repository_root = Path(__file__).resolve().parents[2]
    config_path = repository_root / "data" / "config" / "rag" / "jac104_retrieval_cases.json"
    report_path = repository_root / "ai" / "evaluation" / "reports" / "pgvector_verification.json"
    manifest_path = repository_root / "ai" / "configs" / "index_manifest.json"

    embedding_client = BgeM3EmbeddingClient(model_revision=model_revision)
    store = PgVectorStore(dsn)
    manifest = IndexManifest.load_manifest(str(manifest_path))
    if manifest is None:
        raise RuntimeError("pgvector 검증에는 Index Manifest가 필요합니다.")
    search_service = VectorSearchService(embedding_client, store, index_manifest=manifest)
    sql_filter_verification = _verify_sql_filters(dsn, store, embedding_client)
    facts = _database_facts(dsn)
    database_provenance_passed = all((
        set(facts["embedding_model_revisions"]) == {manifest.model_revision},
        set(facts["index_versions"]) == {manifest.index_version},
        set(facts["chunk_set_sha256_values"]) == {manifest.chunk_set_sha256},
        facts["document_source_hashes"] == manifest.document_hashes,
    ))
    cases = _evaluate(search_service, config_path)
    positive = [case for case in cases if case["case_type"] == "POSITIVE"]
    forbidden_hit_count = sum(len(case["forbidden_hits"]) for case in cases)
    report = {
        "verification_status": "PASS" if (
            all(case["passed"] for case in cases)
            and sql_filter_verification["metadata_filter_passed"]
            and sql_filter_verification["invalid_dimension_rejected"]
            and database_provenance_passed
        ) else "PARTIAL",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python_version": platform.python_version(),
            "os": platform.system(),
            "machine": platform.machine(),
        },
        "embedding_model": embedding_client.model_name,
        "embedding_model_version": model_revision,
        "index_version": manifest.index_version,
        "chunk_set_sha256": manifest.chunk_set_sha256,
        "dimension": embedding_client.dimension,
        "search_type": "cosine_exact_search",
        "top_k": 5,
        "score_threshold": store.score_threshold,
        "ann_used": False,
        "database": facts,
        "database_provenance_passed": database_provenance_passed,
        "database_guard": {
            "mode": "DISPOSABLE_ONLY",
            "database_name": database_name,
            "fixture_transaction_rolled_back": True,
        },
        "sql_filter_verification": sql_filter_verification,
        "summary": {
            "case_count": len(cases),
            "passed_count": sum(case["passed"] for case in cases),
            "failed_count": sum(not case["passed"] for case in cases),
            "mean_positive_recall_at_5": sum(case["recall_at_5"] for case in positive) / len(positive),
            "mean_positive_mrr": sum(case["mrr"] for case in positive) / len(positive),
            "forbidden_hit_count": forbidden_hit_count,
            "pgvector_query_case_count": sum(
                case["execution_path"] == "PGVECTOR_QUERY" for case in cases
            ),
            "policy_block_case_count": sum(
                case["execution_path"] != "PGVECTOR_QUERY" for case in cases
            ),
        },
        "cases": cases,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "verification_status": report["verification_status"],
        "report_path": str(report_path.relative_to(repository_root)),
        **report["summary"],
        "database": facts,
        "database_provenance_passed": database_provenance_passed,
        "sql_filter_verification": sql_filter_verification,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
