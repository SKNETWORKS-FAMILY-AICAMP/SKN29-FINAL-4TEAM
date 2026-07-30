"""bge-m3 임베딩 기반 pgvector Exact Search 서비스 모듈."""

from typing import List

from ...integrations.embedding.embedding_client import EmbeddingProvider
from ...integrations.vector_store.vector_store import VectorStore
from ..models.retrieval_query import RetrievalQuery
from ..models.retrieved_chunk import RetrievedChunk
from ..verification.faq_usage_validator import FaqUsageValidator
from ...common.timeout import CancellationToken


class VectorSearchService:
    """BAAI/bge-m3 1024차원 Exact Search 기반 Vector Store 검색기"""

    def __init__(
        self,
        embedding_client: EmbeddingProvider,
        vector_store: VectorStore,
    ):
        self.embedding_client = embedding_client
        self.vector_store = vector_store

    def search(
        self,
        query: RetrievalQuery,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> List[RetrievedChunk]:
        """질의를 bge-m3로 임베딩하고 DB 필터가 적용된 Exact Search를 수행한다."""
        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()
        if not query.model_code:
            raise ValueError("검색에는 공개 제품 모델 코드가 필요합니다.")
        if query.model_code not in self.SUPPORTED_MODEL_CODES:
            return []
        if (query.product_generation or "D") not in self.SUPPORTED_GENERATIONS:
            return []
        if not FaqUsageValidator().allows_query(query.query_text):
            return []
        vector = self.embedding_client.embed_query(query.query_text)
        token.raise_if_cancelled()
        chunks = self.vector_store.search(
            vector,
            model_code=query.model_code,
            product_generation=query.product_generation or "D",
            top_k=query.top_k,
        )
        token.raise_if_cancelled()
        return chunks

    @classmethod
    def execution_path(cls, query: RetrievalQuery) -> str:
        """평가 보고서에서 DB Query와 검색 전 정책 차단을 구분한다."""
        if query.model_code not in cls.SUPPORTED_MODEL_CODES:
            return "POLICY_BLOCK_UNSUPPORTED_MODEL"
        if (query.product_generation or "D") not in cls.SUPPORTED_GENERATIONS:
            return "POLICY_BLOCK_UNSUPPORTED_GENERATION"
        if not FaqUsageValidator().allows_query(query.query_text):
            return "POLICY_BLOCK_UNVERIFIED_SOURCE"
        return "PGVECTOR_QUERY"
    SUPPORTED_MODEL_CODES = frozenset({"WPUJAC104DWH"})
    SUPPORTED_GENERATIONS = frozenset({"D"})
