"""bge-m3 임베딩 기반 pgvector Exact Search 서비스 모듈."""

from typing import List

from ...integrations.embedding.embedding_client import EmbeddingProvider
from ...integrations.vector_store.vector_store import VectorStore
from ..models.retrieval_query import RetrievalQuery
from ..models.retrieved_chunk import RetrievedChunk
from ..filters.document_policy_filter import DocumentPolicyFilter
from ..filters.product_filter import ProductFilter
from ..filters.scope_filter import SearchCandidateFilter
from ..indexing.index_manifest import IndexManifest
from ..query.query_expander import QueryExpansionDecision, RetrievalQueryExpander
from ..verification.faq_usage_validator import FaqUsageValidator
from ..verification.answerability_capability_gate import (
    AnswerabilityCapabilityGate,
    AnswerabilityDecision,
)
from ..verification.model_capability_gate import (
    ModelCapabilityDecision,
    ModelCapabilityGate,
)
from ...common.timeout import CancellationToken


class VectorSearchService:
    """BAAI/bge-m3 1024차원 Exact Search 기반 Vector Store 검색기"""

    def __init__(
        self,
        embedding_client: EmbeddingProvider,
        vector_store: VectorStore,
        index_manifest: IndexManifest | None = None,
        answerability_gate: AnswerabilityCapabilityGate | None = None,
        model_capability_gate: ModelCapabilityGate | None = None,
        product_filter: ProductFilter | None = None,
        query_expander: RetrievalQueryExpander | None = None,
    ):
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.index_manifest = index_manifest
        self.answerability_gate = answerability_gate or AnswerabilityCapabilityGate()
        self.model_capability_gate = model_capability_gate or ModelCapabilityGate()
        self.product_filter = product_filter or ProductFilter()
        self.query_expander = query_expander or RetrievalQueryExpander()
        if index_manifest is not None:
            if getattr(embedding_client, "model_name", None) != index_manifest.model_name:
                raise RuntimeError("Embedding 모델과 Index Manifest 모델이 일치하지 않습니다.")
            if getattr(embedding_client, "model_revision", None) != index_manifest.model_revision:
                raise RuntimeError("Embedding Revision과 Index Manifest Revision이 일치하지 않습니다.")
            if embedding_client.dimension != index_manifest.dimension:
                raise RuntimeError("Embedding 차원과 Index Manifest 차원이 일치하지 않습니다.")

    def _is_valid_result(self, chunk: RetrievedChunk, requested_model: str) -> bool:
        if not SearchCandidateFilter().is_valid_chunk(chunk):
            return False
        if not self.product_filter.is_valid_chunk(
            chunk,
            requested_model=requested_model,
        ):
            return False
        if not DocumentPolicyFilter().is_valid_chunk(chunk):
            return False
        if self.index_manifest is None:
            return True
        expected_hash = self.index_manifest.document_hashes.get(chunk.document_id or "")
        normalized_chunk_set = self._normalized_sha256(chunk.chunk_set_sha256)
        normalized_source_hash = self._normalized_sha256(chunk.source_hash)
        expected_chunk_set = self._normalized_sha256(
            self.index_manifest.chunk_set_sha256
        )
        normalized_expected_hash = self._normalized_sha256(expected_hash)
        return all((
            chunk.embedding_model == self.index_manifest.model_name,
            chunk.embedding_model_revision == self.index_manifest.model_revision,
            chunk.index_version == self.index_manifest.index_version,
            normalized_chunk_set is not None,
            expected_chunk_set is not None,
            normalized_chunk_set == expected_chunk_set,
            normalized_source_hash is not None,
            normalized_expected_hash is not None,
            normalized_source_hash == normalized_expected_hash,
        ))

    @staticmethod
    def _normalized_sha256(value: str | None) -> str | None:
        """SHA-256의 의미는 대소문자와 무관하되 다른 Metadata는 엄격 비교한다."""

        if value is None:
            return None
        normalized = value.casefold()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            return None
        return normalized

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
        decision = self.evaluate_pre_search_gate(query)
        if decision.blocked:
            return []
        if not FaqUsageValidator().allows_query(query.query_text):
            return []
        expansion = self.expand_query(query)
        vector = self.embedding_client.embed_query(expansion.expanded_query)
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

    def expand_query(self, query: RetrievalQuery) -> QueryExpansionDecision:
        """Policy 판정에 사용한 원문은 유지하고 Embedding 입력만 확장한다."""

        return self.query_expander.expand(
            query.query_text,
            model_code=query.model_code or "",
        )

    def evaluate_answerability(self, query: RetrievalQuery) -> AnswerabilityDecision:
        """검색 전에 적용한 Gate 결정을 평가·진단 코드와 공유한다."""
        return self.answerability_gate.evaluate(
            query_text=query.query_text,
            model_code=query.model_code or "",
            product_generation=query.product_generation or "D",
        )

    def evaluate_model_capability(
        self,
        query: RetrievalQuery,
    ) -> ModelCapabilityDecision:
        """정확 판매코드와 명시적 조작부를 Answerability보다 먼저 판정한다."""

        return self.model_capability_gate.evaluate(
            query_text=query.query_text,
            model_code=query.model_code or "",
        )

    def evaluate_pre_search_gate(
        self,
        query: RetrievalQuery,
    ) -> ModelCapabilityDecision | AnswerabilityDecision:
        """pgvector 이전 Gate를 실행 순서대로 적용한다."""

        model_decision = self.evaluate_model_capability(query)
        if model_decision.blocked:
            return model_decision
        return self.evaluate_answerability(query)

    def execution_path(self, query: RetrievalQuery) -> str:
        """평가 보고서에서 DB Query와 검색 전 정책 차단을 구분한다."""
        if not query.model_code:
            return "POLICY_BLOCK_MISSING_MODEL"
        decision = self.evaluate_pre_search_gate(query)
        if decision.blocked:
            return decision.execution_path
        if not FaqUsageValidator().allows_query(query.query_text):
            return "POLICY_BLOCK_UNVERIFIED_SOURCE"
        return "PGVECTOR_QUERY"
