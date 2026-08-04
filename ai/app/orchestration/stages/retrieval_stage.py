"""공식 문서 RAG 검색 Stage 모듈."""

import time
from ...retrieval import (
    RetrievalConfigurationError,
    RetrievalExecutionError,
    RetrievalOutcome,
    RetrievalQuery,
)
from ...retrieval.search.vector_search import VectorSearchService
from ...schemas import AiStage, EvidenceReference, ProcessingTrace
from ..pipeline_context import PipelineContext
from ...common.timeout import CancellationToken, PipelineCancelledError


def execute_retrieval_stage(
    ctx: PipelineContext,
    search_service: VectorSearchService | None = None,
    cancellation_token: CancellationToken | None = None,
) -> None:
    """bge-m3 pgvector Exact Search 기반 관련 매뉴얼/FAQ 청크 검색"""
    start_time = time.perf_counter()

    query = RetrievalQuery(
        query_text=ctx.raw_symptom,
        model_code=ctx.model_code,
        product_generation="D",
        top_k=5,
        require_official_verified=True
    )

    if search_service is None:
        raise RetrievalConfigurationError(
            "Vector Store가 설정되지 않아 검색을 시작할 수 없습니다."
        )

    try:
        chunks = search_service.search(
            query,
            cancellation_token=cancellation_token,
        )

        # RetrievedChunk -> EvidenceReference 변환
        evidence_list = []
        for chunk in chunks:
            evidence_list.append(
                EvidenceReference(
                    document_title=chunk.document_title,
                    document_version=chunk.document_version,
                    page=chunk.page,
                    page_refs=chunk.page_refs,
                    chunk_id=chunk.chunk_id,
                    official_url=chunk.official_url,
                    summary=chunk.content,
                    similarity_score=chunk.similarity_score,
                    verification_status=chunk.verification_status
                )
            )
    except PipelineCancelledError:
        raise
    except Exception as exc:
        raise RetrievalExecutionError(
            "설정된 Vector Store 검색 실행에 실패했습니다."
        ) from exc

    ctx.evidence_references = evidence_list
    ctx.retrieval_outcome = (
        RetrievalOutcome.AVAILABLE if evidence_list else RetrievalOutcome.NO_MATCH
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(stage=AiStage.RETRIEVING, status="SUCCEEDED", latency_ms=round(elapsed_ms, 2))
    )
