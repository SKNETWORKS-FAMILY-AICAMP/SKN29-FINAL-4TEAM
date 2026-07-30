"""pgvector Exact Search 저장소 어댑터."""

import json
import re
from typing import Iterable, List, Protocol, Sequence

from ...retrieval.models.retrieved_chunk import RetrievedChunk


class VectorStore(Protocol):
    def search(
        self, vector: Sequence[float], *, model_code: str, product_generation: str, top_k: int
    ) -> List[RetrievedChunk]: ...


class PgVectorStore:
    """Cosine `<=>` 연산자를 이용하는 PostgreSQL/pgvector Exact Search 구현."""

    def __init__(self, dsn: str, *, table_name: str = "ai_rag_chunks") -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
            raise ValueError("허용되지 않은 Vector Table 이름입니다.")
        self.dsn = dsn
        self.table_name = table_name

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
            SELECT chunk_id, metadata, content, 1 - (embedding <=> %s::vector) AS similarity_score
            FROM {self.table_name}
            WHERE model_code = %s
              AND product_generation = %s
              AND verification_status = 'official_verified'
              AND allowed_use = TRUE
            ORDER BY embedding <=> %s::vector, chunk_id
            LIMIT %s
        """
        literal = self._vector_literal(vector)
        with psycopg.connect(self.dsn) as connection, connection.cursor() as cursor:
            cursor.execute(sql, (literal, model_code, product_generation, literal, top_k))
            rows = cursor.fetchall()

        chunks: List[RetrievedChunk] = []
        for chunk_id, metadata, content, score in rows:
            values = json.loads(metadata) if isinstance(metadata, str) else dict(metadata)
            values.update(chunk_id=chunk_id, content=content, similarity_score=float(score))
            chunks.append(RetrievedChunk.model_validate(values))
        return chunks
