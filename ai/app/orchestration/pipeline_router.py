"""파이프라인 라우터 모듈."""

import os
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional
from uuid import UUID

from ..integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ..integrations.llm import GuidanceLLMClient
from ..integrations.vector_store.vector_store import PgVectorStore
from ..retrieval.search.vector_search import VectorSearchService
from ..retrieval.indexing.index_manifest import IndexManifest
from ..retrieval import RetrievalConfigurationError
from .pipeline_context import PipelineContext
from .pipeline_result import PipelineResult
from .pipelines.multi_agent_pipeline import MultiAgentPipeline
from .pipelines.single_rag_pipeline import SingleRAGPipeline
from ..common.timeout import CancellationToken
from ..schemas import TraceContext


_AUTO_SEARCH_SERVICE = object()
_SEARCH_SERVICE_LOCK = Lock()
_SEARCH_SERVICE_CACHE_KEY: tuple[str, str, str, str] | None = None
_SEARCH_SERVICE_CACHE: VectorSearchService | None = None


def _configured_search_service() -> VectorSearchService | None:
    """프로세스에서 공유할 Local RAG 검색 서비스를 구성한다."""

    global _SEARCH_SERVICE_CACHE_KEY, _SEARCH_SERVICE_CACHE

    dsn = os.getenv("AI_VECTOR_DSN")
    if not dsn:
        return None
    model_revision = os.getenv("AI_EMBEDDING_REVISION")
    if not model_revision:
        raise RetrievalConfigurationError(
            "AI_VECTOR_DSN 사용 시 재현 가능한 AI_EMBEDDING_REVISION이 필요합니다."
        )
    table_name = os.getenv("AI_VECTOR_TABLE_NAME", "ai_rag_chunks")

    repository_root = Path(__file__).resolve().parents[3]
    manifest_path = repository_root / "ai" / "configs" / "index_manifest.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise RetrievalConfigurationError(
            "AI_VECTOR_DSN 사용 시 Index Manifest가 필요합니다."
        ) from exc

    cache_key = (
        sha256(dsn.encode("utf-8")).hexdigest(),
        model_revision,
        table_name,
        sha256(manifest_bytes).hexdigest(),
    )
    with _SEARCH_SERVICE_LOCK:
        if _SEARCH_SERVICE_CACHE_KEY == cache_key and _SEARCH_SERVICE_CACHE is not None:
            return _SEARCH_SERVICE_CACHE
        try:
            manifest = IndexManifest.load_manifest(str(manifest_path))
            if manifest is None:
                raise RetrievalConfigurationError(
                    "AI_VECTOR_DSN 사용 시 Index Manifest가 필요합니다."
                )
            service = VectorSearchService(
                BgeM3EmbeddingClient(model_revision=model_revision),
                PgVectorStore(dsn, table_name=table_name),
                index_manifest=manifest,
            )
        except RetrievalConfigurationError:
            raise
        except Exception as exc:
            raise RetrievalConfigurationError(
                "Vector Store 검색 설정이 Index Manifest와 일치하지 않습니다."
            ) from exc
        _SEARCH_SERVICE_CACHE_KEY = cache_key
        _SEARCH_SERVICE_CACHE = service
        return service


def warmup_configured_search_service() -> bool:
    """Local RAG 모델을 HTTP 요청 처리 전에 초기화한다."""

    service = _configured_search_service()
    if service is None:
        return False
    embedding_client = service.embedding_client
    warmup = getattr(embedding_client, "warmup", None)
    if not callable(warmup):
        raise RetrievalConfigurationError(
            "설정된 Embedding Provider가 Runtime Warmup을 지원하지 않습니다."
        )
    warmup()
    return True


class PipelineRouter:
    """파이프라인 실행 라우터 싱글톤"""
    def __init__(
        self,
        search_service: VectorSearchService | None | object = _AUTO_SEARCH_SERVICE,
        llm_client: GuidanceLLMClient | None = None,
    ):
        self.retrieval_configuration_error: RetrievalConfigurationError | None = None
        if search_service is _AUTO_SEARCH_SERVICE:
            try:
                self.search_service = self._configured_search_service()
            except RetrievalConfigurationError as exc:
                self.search_service = None
                self.retrieval_configuration_error = exc
        else:
            self.search_service = search_service
        self.llm_client = llm_client

    @staticmethod
    def _configured_search_service() -> VectorSearchService | None:
        return _configured_search_service()

    def run_pipeline(
        self,
        inquiry_id: UUID,
        correlation_id: UUID,
        ai_request_id: str,
        state_version: int,
        raw_symptom: str,
        model_code: str = "WPUJAC104DWH",
        selected_symptoms: Optional[List[str]] = None,
        previous_answers: Optional[List[Dict[str, str]]] = None,
        cancellation_token: CancellationToken | None = None,
        runtime_name: str | None = None,
    ) -> PipelineResult:
        """명시된 Runtime을 실행하되 기본값은 안정된 Single RAG로 유지한다."""
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

        selected_runtime = runtime_name or os.getenv("AI_PIPELINE_RUNTIME", "single_rag")
        if selected_runtime == "single_rag":
            pipeline = SingleRAGPipeline(
                self.search_service,
                retrieval_configuration_error=self.retrieval_configuration_error,
                llm_client=self.llm_client,
            )
        elif selected_runtime == "multi_agent":
            pipeline = MultiAgentPipeline(
                self.search_service,
                retrieval_configuration_error=self.retrieval_configuration_error,
                llm_client=self.llm_client,
            )
        else:
            raise RuntimeError(
                "AI_PIPELINE_RUNTIME은 single_rag 또는 multi_agent여야 합니다."
            )
        return pipeline.run(ctx, cancellation_token=token)
