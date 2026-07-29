"""공식 문서 RAG 검색 Stage 모듈."""

import time
from ...retrieval import RetrievalQuery
from ...retrieval.search.vector_search import VectorSearchService
from ...schemas import EvidenceReference, ProcessingTrace
from ..pipeline_context import PipelineContext


def execute_retrieval_stage(ctx: PipelineContext, search_service: VectorSearchService | None = None) -> None:
    """bge-m3 pgvector Exact Search 기반 관련 매뉴얼/FAQ 청크 검색"""
    start_time = time.perf_counter()

    query = RetrievalQuery(
        query_text=ctx.raw_symptom,
        model_code=ctx.model_code,
        product_generation="D",
        top_k=5,
        require_official_verified=True
    )

    chunks = search_service.search(query) if search_service is not None else []

    # RetrievedChunk -> EvidenceReference 변환
    evidence_list = []
    for chunk in chunks:
        evidence_list.append(
            EvidenceReference(
                document_title=chunk.document_title,
                document_version=chunk.document_version,
                page=chunk.page,
                chunk_id=chunk.chunk_id,
                official_url=chunk.official_url,
                summary=chunk.content,
                similarity_score=chunk.similarity_score,
                verification_status=chunk.verification_status
            )
        )

    ctx.evidence_references = evidence_list

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(stage="retrieval_stage", status="success", latency_ms=round(elapsed_ms, 2))
    )
