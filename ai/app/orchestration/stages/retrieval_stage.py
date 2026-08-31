"""공식 문서 RAG 검색 Stage 모듈."""

import time

from ...common.retry import get_retry_policy
from ...common.timeout import CancellationToken, PipelineCancelledError
from ...retrieval import (
    EvidenceApplicabilityGate,
    EvidenceTopicFilter,
    ScenarioEvidenceSelector,
    RetrievalConfigurationError,
    RetrievalExecutionError,
    RetrievalOutcome,
    RetrievalQuery,
    RetrievalToolError,
)
from ...retrieval.search.vector_search import VectorSearchService
from ...schemas import AiStage, EvidenceReference, ProcessingTrace
from ..harness.product_registry import resolve_product_generation
from ..pipeline_context import PipelineContext
from ...retrieval.query.context_builder import RetrievalContextBuilder


def execute_retrieval_stage(
    ctx: PipelineContext,
    search_service: VectorSearchService | None = None,
    cancellation_token: CancellationToken | None = None,
) -> None:
    """bge-m3 pgvector Exact Search 기반 관련 매뉴얼/FAQ 청크 검색"""
    start_time = time.perf_counter()

    # Known products use their exact configured generation. Unknown products are
    # still passed through unchanged so the outer fail-closed product guard can
    # reject them without rewriting customer-provided identity.
    product_generation = resolve_product_generation(ctx.model_code) or "D"

    ctx.retrieval_query_text = RetrievalContextBuilder().build(
        raw_symptom=ctx.raw_symptom,
        structured_symptom=ctx.structured_symptom,
    )
    query = RetrievalQuery(
        query_text=ctx.retrieval_query_text,
        model_code=ctx.model_code,
        product_generation=product_generation,
        top_k=5,
        require_official_verified=True
    )

    if search_service is None:
        raise RetrievalConfigurationError(
            "Vector Store가 설정되지 않아 검색을 시작할 수 없습니다."
        )

    retry_policy = get_retry_policy()
    retry_count = 0
    while True:
        try:
            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            chunks = search_service.search(
                query,
                cancellation_token=cancellation_token,
            )
            chunks = EvidenceTopicFilter().filter_chunks(
                chunks,
                symptom_type=(
                    ctx.structured_symptom.symptom_type
                    if ctx.structured_symptom is not None
                    else None
                ),
                target_water_type=(
                    ctx.structured_symptom.target_water_type
                    if ctx.structured_symptom is not None
                    else None
                ),
            )
            applicability_gate = EvidenceApplicabilityGate()
            symptom_type = (
                ctx.structured_symptom.symptom_type
                if ctx.structured_symptom is not None
                else None
            )
            ctx.evidence_applicability = applicability_gate.classify_for_symptom(
                symptom_type=symptom_type,
                previous_answers=ctx.previous_answers,
            )
            chunks = applicability_gate.filter_chunks(
                chunks,
                symptom_type=symptom_type,
                applicability=ctx.evidence_applicability,
            )
            selection = ScenarioEvidenceSelector().select_chunks(
                chunks,
                structured_symptom=ctx.structured_symptom,
                raw_symptom=ctx.raw_symptom,
                applicability=ctx.evidence_applicability,
            )
            chunks = list(selection.chunks)
            ctx.evidence_selection_reasons = list(selection.reasons)

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
            break
        except PipelineCancelledError:
            raise
        except RetrievalToolError:
            raise
        except Exception as exc:
            if not retry_policy.can_retry(exc, retry_count):
                ctx.retry_count = max(ctx.retry_count, retry_count)
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                ctx.processing_traces.append(
                    ProcessingTrace(
                        stage=AiStage.RETRIEVING,
                        status="FAILED",
                        latency_ms=round(elapsed_ms, 2),
                        retry_count=retry_count,
                        error_code="AI-FAILED-01",
                    )
                )
                raise RetrievalExecutionError(
                    "설정된 Vector Store 검색 실행에 실패했습니다.",
                    retry_count=retry_count,
                    retryable=retry_policy.is_retryable_exception(exc),
                ) from exc
            next_retry_count = retry_count + 1
            backoff_seconds = retry_policy.backoff_seconds(next_retry_count)
            if cancellation_token is not None:
                cancellation_token.wait(backoff_seconds)
            elif backoff_seconds > 0:
                time.sleep(backoff_seconds)
            retry_count = next_retry_count
            ctx.retry_count = max(ctx.retry_count, retry_count)
            if cancellation_token is not None:
                cancellation_token.record_retry(retry_count)

    ctx.evidence_references = evidence_list
    ctx.retrieval_outcome = (
        RetrievalOutcome.AVAILABLE if evidence_list else RetrievalOutcome.NO_MATCH
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    ctx.processing_traces.append(
        ProcessingTrace(
            stage=AiStage.RETRIEVING,
            status="SUCCEEDED",
            latency_ms=round(elapsed_ms, 2),
            retry_count=retry_count,
        )
    )
