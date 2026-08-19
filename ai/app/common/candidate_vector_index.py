"""Runtime 비활성 RAG Candidate 인덱스의 DB 경계."""

from __future__ import annotations

import os
import re

from .protected_database import run_protected_database_operation


RAG_EXPANSION_PROFILE = "rag-expansion"
RAG_EXPANSION_TABLE = "ai_rag_chunks_expansion_candidate"


def assert_rag_expansion_candidate_target(dsn: str, table_name: str) -> str:
    """확장 Candidate가 운영 테이블이나 공유 DB에 적재되는 것을 차단한다."""

    if table_name != RAG_EXPANSION_TABLE:
        raise RuntimeError(
            f"rag-expansion은 {RAG_EXPANSION_TABLE} 전용 Table만 사용할 수 있습니다."
        )
    if os.getenv("AI_VECTOR_DISPOSABLE_CONFIRM") != "DISPOSABLE_ONLY":
        raise RuntimeError(
            "rag-expansion 적재·평가는 AI_VECTOR_DISPOSABLE_CONFIRM=DISPOSABLE_ONLY가 필요합니다."
        )
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Candidate DB 확인에는 psycopg가 필요합니다.") from exc

    def read_database_name() -> str:
        with (
            psycopg.connect(dsn, connect_timeout=5) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT current_database()")
            return str(cursor.fetchone()[0])

    database_name = run_protected_database_operation(
        read_database_name,
        public_message="RAG Candidate DB 경계 확인에 실패했습니다.",
    )
    if not re.search(r"(verify|test|tmp|disposable)", database_name, re.IGNORECASE):
        raise RuntimeError("rag-expansion은 식별 가능한 Disposable DB에서만 실행할 수 있습니다.")
    return database_name
