"""bge-m3 임베딩 기반 pgvector Exact Search 서비스 모듈."""

from typing import List

from ...integrations.embedding.embedding_client import EmbeddingProvider
from ...integrations.vector_store.vector_store import VectorStore
from ..models.retrieval_query import RetrievalQuery
from ..models.retrieved_chunk import RetrievedChunk
from ..verification.faq_usage_validator import FaqUsageValidator


class VectorSearchService:
    """BAAI/bge-m3 1024차원 Exact Search 기반 Vector Store 검색기"""

    def __init__(
        self,
        embedding_client: EmbeddingProvider,
        vector_store: VectorStore,
    ):
        self.embedding_client = embedding_client
        self.vector_store = vector_store

    def search(self, query: RetrievalQuery) -> List[RetrievedChunk]:
        """질의를 bge-m3로 임베딩하고 DB 필터가 적용된 Exact Search를 수행한다."""
        if not query.model_code:
            raise ValueError("검색에는 공개 제품 모델 코드가 필요합니다.")
        if not FaqUsageValidator().allows_query(query.query_text):
            return []
        vector = self.embedding_client.embed_query(query.query_text)
        return self.vector_store.search(
            vector,
            model_code=query.model_code,
            product_generation=query.product_generation or "D",
            top_k=query.top_k,
        )
