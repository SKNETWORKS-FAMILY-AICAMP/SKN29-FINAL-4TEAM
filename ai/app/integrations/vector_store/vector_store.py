"""pgvector 적재 및 Cosine Exact Search 저장소 어댑터."""

import json
import re
from typing import List, Protocol, Sequence

from ...retrieval.models.retrieved_chunk import RetrievedChunk


class VectorStore(Protocol):
    def search(
        self, vector: Sequence[float], *, model_code: str, product_generation: str, top_k: int
    ) -> List[RetrievedChunk]: ...


class PgVectorStore:
    """Cosine `<=>` 연산자를 이용하는 PostgreSQL/pgvector Exact Search 구현."""

    def __init__(
        self,
        dsn: str,
        *,
        table_name: str = "ai_rag_chunks",
        score_threshold: float = 0.4,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
            raise ValueError("허용되지 않은 Vector Table 이름입니다.")
        self.dsn = dsn
        self.table_name = table_name
        if not 0.0 <= score_threshold <= 1.0:
            raise ValueError("검색 점수 Threshold는 0.0~1.0이어야 합니다.")
        self.score_threshold = score_threshold

    @staticmethod
    def _vector_literal(vector: Sequence[float]) -> str:
        if len(vector) != 1024:
            raise ValueError("bge-m3 Vector는 1024차원이어야 합니다.")
        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    def search(
        self, vector: Sequence[float], *, model_code: str, product_generation: str, top_k: int
    ) -> List[RetrievedChunk]:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("pgvector 검색에는 psycopg가 필요합니다.") from exc

        sql = f"""
            SELECT chunk_id, metadata, content, similarity_score
            FROM (
                SELECT chunk_id, metadata, content,
                       1 - (embedding <=> %s::vector) AS similarity_score
                FROM {self.table_name}
                WHERE model_code = %s
                  AND product_generation = %s
                  AND verification_status = 'official_verified'
                  AND allowed_use = TRUE
            ) AS ranked
            WHERE similarity_score >= %s
            ORDER BY similarity_score DESC, chunk_id
            LIMIT %s
        """
        literal = self._vector_literal(vector)
        with psycopg.connect(self.dsn, connect_timeout=5) as connection, connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute(
                sql,
                (literal, model_code, product_generation, self.score_threshold, top_k),
            )
            rows = cursor.fetchall()

        chunks: List[RetrievedChunk] = []
        for chunk_id, metadata, content, score in rows:
            values = json.loads(metadata) if isinstance(metadata, str) else dict(metadata)
            values.update(chunk_id=chunk_id, content=content, similarity_score=float(score))
            chunks.append(RetrievedChunk.model_validate(values))
        return chunks

    def initialize_schema(self, *, disposable_confirm: bool = False) -> None:
        """격리 검증 DB에 vector 확장과 1024차원 청크 테이블을 생성한다."""
        if not disposable_confirm:
            raise RuntimeError("Schema 초기화는 명시적으로 확인된 Disposable DB에서만 허용됩니다.")
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("pgvector 적재에는 psycopg가 필요합니다.") from exc

        sql = f"""
            CREATE EXTENSION IF NOT EXISTS vector;
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                document_title TEXT NOT NULL,
                document_version TEXT,
                page INTEGER,
                manual_model TEXT NOT NULL,
                model_code TEXT NOT NULL,
                product_generation TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding vector(1024) NOT NULL,
                official_url TEXT,
                verification_status TEXT NOT NULL,
                allowed_use BOOLEAN NOT NULL,
                source_hash CHAR(64) NOT NULL,
                safe_actions JSONB NOT NULL DEFAULT '[]'::jsonb,
                metadata JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT {self.table_name}_source_hash_hex
                    CHECK (source_hash ~ '^[0-9A-Fa-f]{{64}}$'),
                CONSTRAINT {self.table_name}_embedding_dimension
                    CHECK (vector_dims(embedding) = 1024)
            );
        """
        with psycopg.connect(self.dsn, connect_timeout=5) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            database_name = str(cursor.fetchone()[0])
            if not re.search(r"(verify|test|tmp|disposable)", database_name, re.IGNORECASE):
                raise RuntimeError(
                    f"Disposable DB 식별 Guard를 통과하지 못했습니다: {database_name}"
                )
            cursor.execute(sql)

    def upsert(self, chunks: Sequence[RetrievedChunk], vectors: Sequence[Sequence[float]]) -> int:
        """청크 ID 기준 멱등 UPSERT를 수행하고 처리 행 수를 반환한다."""
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("pgvector 적재에는 psycopg가 필요합니다.") from exc
        if len(chunks) != len(vectors):
            raise ValueError("청크 수와 Vector 수가 일치해야 합니다.")

        sql = f"""
            INSERT INTO {self.table_name} (
                chunk_id, document_id, document_title, document_version, page,
                manual_model, model_code, product_generation, content, embedding,
                official_url, verification_status, allowed_use, source_hash,
                safe_actions, metadata
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s::vector,
                %s, %s, %s, %s,
                %s::jsonb, %s::jsonb
            )
            ON CONFLICT (chunk_id) DO UPDATE SET
                document_id = EXCLUDED.document_id,
                document_title = EXCLUDED.document_title,
                document_version = EXCLUDED.document_version,
                page = EXCLUDED.page,
                manual_model = EXCLUDED.manual_model,
                model_code = EXCLUDED.model_code,
                product_generation = EXCLUDED.product_generation,
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding,
                official_url = EXCLUDED.official_url,
                verification_status = EXCLUDED.verification_status,
                allowed_use = EXCLUDED.allowed_use,
                source_hash = EXCLUDED.source_hash,
                safe_actions = EXCLUDED.safe_actions,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
        """
        rows = []
        for chunk, vector in zip(chunks, vectors):
            if not chunk.source_hash:
                raise ValueError(f"원문 Hash가 없는 청크는 적재할 수 없습니다: {chunk.chunk_id}")
            metadata = chunk.model_dump(mode="json", exclude={"content", "similarity_score"})
            rows.append((
                chunk.chunk_id,
                chunk.document_id,
                chunk.document_title,
                chunk.document_version,
                chunk.page,
                chunk.manual_model,
                chunk.model_code,
                chunk.product_generation,
                chunk.content,
                self._vector_literal(vector),
                chunk.official_url,
                chunk.verification_status,
                chunk.allowed_use,
                chunk.source_hash,
                json.dumps(chunk.safe_actions, ensure_ascii=False),
                json.dumps(metadata, ensure_ascii=False),
            ))
        with psycopg.connect(self.dsn, connect_timeout=5) as connection, connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '10s'")
            cursor.executemany(sql, rows)
        return len(rows)

    def count(self, chunk_ids: Sequence[str] | None = None) -> int:
        """전체 또는 이번 배치 청크 범위의 적재 행 수를 반환한다."""
        import psycopg

        with psycopg.connect(self.dsn, connect_timeout=5) as connection, connection.cursor() as cursor:
            if chunk_ids is None:
                cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            elif not chunk_ids:
                return 0
            else:
                placeholders = ", ".join(["%s"] * len(chunk_ids))
                cursor.execute(
                    f"SELECT COUNT(*) FROM {self.table_name} WHERE chunk_id IN ({placeholders})",
                    tuple(chunk_ids),
                )
            return int(cursor.fetchone()[0])
