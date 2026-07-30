"""파이프라인 라우터 모듈."""

import os
from typing import Dict, List, Optional

from ..integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ..integrations.vector_store.vector_store import PgVectorStore
from ..retrieval.search.vector_search import VectorSearchService
from .pipeline_context import PipelineContext
from .pipeline_result import PipelineResult
from .pipelines.single_rag_pipeline import SingleRAGPipeline
from ..schemas import TraceContext


class PipelineRouter:
    """파이프라인 실행 라우터 싱글톤"""
    def __init__(self, search_service: VectorSearchService | None = None):
        self.search_service = search_service if search_service is not None else self._configured_search_service()

    @staticmethod
    def _configured_search_service() -> VectorSearchService | None:
        dsn = os.getenv("AI_VECTOR_DSN")
        if not dsn:
            return None
        return VectorSearchService(BgeM3EmbeddingClient(), PgVectorStore(dsn))

    def run_pipeline(
        self,
        inquiry_id: str,
        correlation_id: str,
        raw_symptom: str,
        model_code: str = "WPUJAC104DWH",
        selected_symptoms: Optional[List[str]] = None,
        previous_answers: Optional[List[Dict[str, str]]] = None
    ) -> PipelineResult:
        """단일 RAG 파이프라인 가동 및 결과 반환"""
        ctx = PipelineContext(
            trace_context=TraceContext(
                inquiry_id=inquiry_id,
                correlation_id=correlation_id
            ),
            raw_symptom=raw_symptom,
            model_code=model_code,
            selected_symptoms=selected_symptoms or [],
            previous_answers=previous_answers or []
        )

        pipeline = SingleRAGPipeline(self.search_service)
        return pipeline.run(ctx)
