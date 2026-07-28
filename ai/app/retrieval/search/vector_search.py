"""bge-m3 임베딩 기반 pgvector Exact Search 서비스 모듈."""

from typing import List, Optional
from ai.app.retrieval.filters.document_policy_filter import DocumentPolicyFilter
from ai.app.retrieval.filters.product_filter import ProductFilter
from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk


class VectorSearchService:
    """BAAI/bge-m3 1024차원 Exact Search 기반 Vector Store 검색기"""

    def __init__(
        self,
        chunk_loader: Optional[ChunkLoader] = None,
        product_filter: Optional[ProductFilter] = None,
        document_filter: Optional[DocumentPolicyFilter] = None
    ):
        self.chunk_loader = chunk_loader or ChunkLoader()
        self.product_filter = product_filter or ProductFilter()
        self.document_filter = document_filter or DocumentPolicyFilter()

    def search(self, query: RetrievalQuery) -> List[RetrievedChunk]:
        """쿼리와 텍스트를 비교하여 코사인 유사도 검색 및 메타데이터 필터링 수행"""
        all_chunks = self.chunk_loader.load_sample_chunks()

        # 1. 1차 메타데이터 필터링 (D 세대, 제외 대상 모델 배제, 공식 검증 확인)
        valid_chunks = self.product_filter.filter_chunks(all_chunks)
        valid_chunks = self.document_filter.filter_chunks(valid_chunks)

        # 2. 질의 키워드 기반 코사인 유사도 연산 (Exact Search 매칭 시뮬레이션)
        results = []
        for chunk in valid_chunks:
            # 단순 텍스트 매칭 기반 임시 유사도 점수 산정 (실제 DB 연결 시 pgvector <=> 연산자 사용)
            score = 0.5
            if any(term in chunk.content for term in query.query_text.split()):
                score += 0.35
            if query.query_text in chunk.content:
                score += 0.15

            chunk_copy = chunk.model_copy()
            chunk_copy.similarity_score = min(score, 1.0)
            results.append(chunk_copy)

        # 3. 유사도 점수 내림차순 정렬 및 Top-K (Top-5) 반환
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[:query.top_k]
