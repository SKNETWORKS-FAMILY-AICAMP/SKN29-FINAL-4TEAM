"""파이프라인 라우터 모듈."""

import os
from pathlib import Path
from typing import Dict, List, Optional

from ..integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ..integrations.vector_store.vector_store import PgVectorStore
from ..retrieval.search.vector_search import VectorSearchService
from ..retrieval.indexing.index_manifest import IndexManifest
from .pipeline_context import PipelineContext
from .pipeline_result import PipelineResult
from .pipelines.single_rag_pipeline import SingleRAGPipeline
from ..common.timeout import CancellationToken
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
        model_revision = os.getenv("AI_EMBEDDING_REVISION")
        if not model_revision:
            raise RuntimeError(
                "AI_VECTOR_DSN 사용 시 재현 가능한 AI_EMBEDDING_REVISION이 필요합니다."
            )
        repository_root = Path(__file__).resolve().parents[3]
        manifest_path = repository_root / "ai" / "configs" / "index_manifest.json"
        manifest = IndexManifest.load_manifest(str(manifest_path))
        if manifest is None:
            raise RuntimeError("AI_VECTOR_DSN 사용 시 Index Manifest가 필요합니다.")
        return VectorSearchService(
            BgeM3EmbeddingClient(model_revision=model_revision),
            PgVectorStore(dsn),
            index_manifest=manifest,
        )

    def run_pipeline(
        self,
        inquiry_id: str,
        correlation_id: str,
        ai_request_id: str,
        state_version: int,
        raw_symptom: str,
        model_code: str = "WPUJAC104DWH",
        selected_symptoms: Optional[List[str]] = None,
        previous_answers: Optional[List[Dict[str, str]]] = None,
        cancellation_token: CancellationToken | None = None,
    ) -> PipelineResult:
        """단일 RAG 파이프라인 가동 및 결과 반환"""
        token = cancellation_token or CancellationToken()
        token.raise_if_cancelled()
        ctx = PipelineContext(
            trace_context=TraceContext(
                inquiry_id=inquiry_id,
                correlation_id=correlation_id,
                ai_request_id=ai_request_id,
                state_version=state_version,
            ),
            raw_symptom=raw_symptom,
            model_code=model_code,
            selected_symptoms=selected_symptoms or [],
            previous_answers=previous_answers or []
        )

        pipeline = SingleRAGPipeline(self.search_service)
        return pipeline.run(ctx, cancellation_token=token)
