"""bge-m3 임베딩 기반 pgvector Exact Search 서비스 모듈."""

from typing import List

from ...integrations.embedding.embedding_client import EmbeddingProvider
from ...integrations.vector_store.vector_store import VectorStore
from ..models.retrieval_query import RetrievalQuery
from ..models.retrieved_chunk import RetrievedChunk
from ..filters.document_policy_filter import DocumentPolicyFilter
from ..filters.product_filter import ProductFilter
from ..indexing.index_manifest import IndexManifest
from ..verification.faq_usage_validator import FaqUsageValidator
from ...common.timeout import CancellationToken


class VectorSearchService:
    """BAAI/bge-m3 1024차원 Exact Search 기반 Vector Store 검색기"""

    def __init__(
        self,
        embedding_client: EmbeddingProvider,
        vector_store: VectorStore,
        index_manifest: IndexManifest | None = None,
    ):
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.index_manifest = index_manifest
        if index_manifest is not None:
            if getattr(embedding_client, "model_name", None) != index_manifest.model_name:
                raise RuntimeError("Embedding 모델과 Index Manifest 모델이 일치하지 않습니다.")
            if getattr(embedding_client, "model_revision", None) != index_manifest.model_revision:
                raise RuntimeError("Embedding Revision과 Index Manifest Revision이 일치하지 않습니다.")
            if embedding_client.dimension != index_manifest.dimension:
                raise RuntimeError("Embedding 차원과 Index Manifest 차원이 일치하지 않습니다.")

    def _is_valid_result(self, chunk: RetrievedChunk, requested_model: str) -> bool:
        if not ProductFilter().is_valid_chunk(chunk, requested_model=requested_model):
            return False
        if not DocumentPolicyFilter().is_valid_chunk(chunk):
            return False
        if self.index_manifest is None:
            return True
        expected_hash = self.index_manifest.document_hashes.get(chunk.document_id or "")
        return all((
            chunk.embedding_model == self.index_manifest.model_name,
            chunk.embedding_model_revision == self.index_manifest.model_revision,
            chunk.index_version == self.index_manifest.index_version,
            chunk.chunk_set_sha256 == self.index_manifest.chunk_set_sha256,
            expected_hash is not None,
            chunk.source_hash == expected_hash,
        ))

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
        return [
            chunk
            for chunk in chunks
            if self._is_valid_result(chunk, requested_model=query.model_code)
        ]

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
