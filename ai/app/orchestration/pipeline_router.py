"""파이프라인 라우터 모듈."""

from __future__ import annotations

import os
from hashlib import sha256
from threading import Lock
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import UUID

from ..integrations.embedding.embedding_client import BgeM3EmbeddingClient
from ..integrations.llm import (
    GuidanceLLMClient,
    LLMConfigurationError,
)
from ..integrations.backend import BackendContextFailureKind
from ..integrations.vector_store.vector_store import PgVectorStore
from ..retrieval.search.vector_search import VectorSearchService
from ..retrieval.indexing.index_manifest import IndexManifest
from ..retrieval.filters.product_filter import ProductFilter
from ..retrieval.verification.answerability_capability_gate import (
    AnswerabilityCapabilityGate,
)
from ..retrieval import (
    RetrievalConfigurationError,
    load_runtime_retrieval_policy,
    resolve_rag_runtime_profile,
    validate_runtime_manifest,
)
from .harness.evidence_capture import GuardedEvidenceSearchService
from .harness.product_registry import resolve_product_context
from .harness.runtime import ReliabilityRuntime
from .harness.tool_failure import McpToolFailure, McpToolFailureKind, McpToolName
from .pipeline_context import PipelineContext
from .pipeline_result import PipelineResult
from .pipelines.multi_agent_pipeline import MultiAgentPipeline
from .pipelines.single_rag_pipeline import SingleRAGPipeline
from .stages.safety_check_stage import execute_safety_check_stage
from .stages.structuring_stage import execute_structuring_stage
from ..common.timeout import CancellationToken
from ..schemas import TraceContext
from ..structuring.llm_contracts import (
    FollowUpWordingLLMClient,
    SymptomStructuringLLMClient,
)

if TYPE_CHECKING:
    from ..integrations.mcp.context_service import (
        McpBackendContextError,
        McpBackendContextService,
    )


_AUTO_SEARCH_SERVICE = object()
_AUTO_MCP_CONTEXT_SERVICE = object()
_AUTO_NATURAL_LANGUAGE_CLIENT = object()
_SEARCH_SERVICE_LOCK = Lock()
_LLM_CONFIGURATION_LOG_LOCK = Lock()
_LLM_CONFIGURATION_LOGGED: set[tuple[str, str]] = set()
_SEARCH_SERVICE_CACHE_KEY: tuple[str, ...] | None = None
_SEARCH_SERVICE_CACHE: VectorSearchService | None = None


def _create_mcp_backend_context_service():
    from ..integrations.mcp.context_service import (
        McpBackendContextService,
    )

    return McpBackendContextService()


def _create_mcp_evidence_search_service():
    from ..integrations.mcp.search_service import (
        McpEvidenceSearchService,
    )

    return McpEvidenceSearchService()


def _log_llm_configuration_fallback_once(task_name: str, reason: str) -> None:
    key = (task_name, reason)
    with _LLM_CONFIGURATION_LOG_LOCK:
        if key in _LLM_CONFIGURATION_LOGGED:
            return
        _LLM_CONFIGURATION_LOGGED.add(key)

    from ..integrations.llm.token_usage import log_llm_fallback

    log_llm_fallback(
        event="llm_client_configuration_fallback",
        task=task_name,
        reason=reason,
        validation_result="FALLBACK",
    )


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

    profile = resolve_rag_runtime_profile()
    manifest_path = profile.manifest_path
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise RetrievalConfigurationError(
            "AI_VECTOR_DSN 사용 시 Index Manifest가 필요합니다."
        ) from exc

    cache_key = (
        sha256(dsn.encode("utf-8")).hexdigest(),
        profile.name,
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
            validate_runtime_manifest(profile, manifest)
            runtime_policy = load_runtime_retrieval_policy(profile)
            metadata_filters = runtime_policy.metadata_filters
            service = VectorSearchService(
                BgeM3EmbeddingClient(model_revision=model_revision),
                PgVectorStore(dsn, table_name=table_name),
                index_manifest=manifest,
                answerability_gate=AnswerabilityCapabilityGate(
                    definition=runtime_policy.answerability_gate
                ),
                product_filter=ProductFilter(
                    allowed_generations=metadata_filters["allowed_generations"],
                    excluded_models=metadata_filters["excluded_models"],
                    target_models=metadata_filters["target_models"],
                ),
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
        symptom_llm_client: SymptomStructuringLLMClient | None | object = (
            _AUTO_NATURAL_LANGUAGE_CLIENT
        ),
        followup_llm_client: FollowUpWordingLLMClient | None | object = (
            _AUTO_NATURAL_LANGUAGE_CLIENT
        ),
        mcp_context_service: McpBackendContextService | None | object = (
            _AUTO_MCP_CONTEXT_SERVICE
        ),
    ):
        self.retrieval_configuration_error: RetrievalConfigurationError | None = None
        try:
            self.rag_runtime_profile = resolve_rag_runtime_profile()
        except RetrievalConfigurationError as exc:
            self.rag_runtime_profile = None
            self.retrieval_configuration_error = exc

        if search_service is _AUTO_SEARCH_SERVICE and self.rag_runtime_profile is not None:
            try:
                self.search_service = self._configured_search_service()
            except RetrievalConfigurationError as exc:
                self.search_service = None
                self.retrieval_configuration_error = exc
        elif search_service is _AUTO_SEARCH_SERVICE:
            self.search_service = None
        else:
            self.search_service = search_service
        self.llm_client = llm_client
        self.symptom_llm_client = self._resolve_natural_language_client(
            symptom_llm_client,
            task_name="symptom_structuring",
        )
        self.followup_llm_client = self._resolve_natural_language_client(
            followup_llm_client,
            task_name="followup_question",
        )
        self.mcp_context_service = mcp_context_service
        self.reliability_runtime = ReliabilityRuntime()

    @staticmethod
    def _configured_search_service() -> VectorSearchService | None:
        return _configured_search_service()

    @staticmethod
    def _resolve_natural_language_client(configured, *, task_name: str):
        if configured is not _AUTO_NATURAL_LANGUAGE_CLIENT:
            return configured
        if not os.getenv("OPENAI_API_KEY", "").strip():
            _log_llm_configuration_fallback_once(
                task_name,
                "OPENAI_API_KEY_MISSING",
            )
            return None
        try:
            from ..integrations.llm.natural_language_client import (
                OpenAIResponsesFollowUpWordingClient,
                OpenAIResponsesSymptomStructuringClient,
            )

            client_class = (
                OpenAIResponsesSymptomStructuringClient
                if task_name == "symptom_structuring"
                else OpenAIResponsesFollowUpWordingClient
            )
            return client_class.from_environment()
        except LLMConfigurationError:
            # 구조화·질문 표현은 기존 결정적 구현으로 안전하게 복귀한다.
            _log_llm_configuration_fallback_once(
                task_name,
                "CLIENT_CONFIGURATION_INVALID",
            )
            return None

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
        if self.rag_runtime_profile is None:
            raise self.retrieval_configuration_error or RetrievalConfigurationError(
                "RAG Runtime Profile을 확인할 수 없습니다."
            )

        selected_runtime = runtime_name or os.getenv(
            "AI_PIPELINE_RUNTIME",
            "single_rag",
        )
        if selected_runtime not in {"single_rag", "multi_agent"}:
            raise RuntimeError(
                "AI_PIPELINE_RUNTIME은 single_rag 또는 multi_agent여야 합니다."
            )
        retrieval_transport = os.getenv(
            "AI_RETRIEVAL_TRANSPORT",
            "direct",
        ).strip().lower()
        if retrieval_transport not in {"direct", "mcp"}:
            raise RuntimeError(
                "AI_RETRIEVAL_TRANSPORT는 direct 또는 mcp여야 합니다."
            )

        if retrieval_transport == "mcp":
            from ..integrations.mcp.context_service import (
                McpBackendContextError,
                McpBackendContextToolName,
            )
            from ..integrations.mcp.search_service import (
                McpEvidenceSearchError,
            )

            try:
                context_service = self.mcp_context_service
                if context_service is _AUTO_MCP_CONTEXT_SERVICE:
                    context_service = (
                        _create_mcp_backend_context_service()
                    )
                if context_service is None:
                    raise McpBackendContextError(
                        tool_name=(
                            McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT
                        ),
                        kind=BackendContextFailureKind.UNAVAILABLE,
                        retryable=False,
                    )
                resolved_context = context_service.resolve(
                    inquiry_id=inquiry_id,
                    correlation_id=correlation_id,
                    expected_state_version=state_version,
                    expected_model_code=model_code,
                    cancellation_token=token,
                )
            except McpBackendContextError as exc:
                return self._context_failure_result(
                    inquiry_id=inquiry_id,
                    correlation_id=correlation_id,
                    ai_request_id=ai_request_id,
                    state_version=state_version,
                    raw_symptom=raw_symptom,
                    model_code=model_code,
                    selected_symptoms=selected_symptoms,
                    previous_answers=previous_answers,
                    cancellation_token=token,
                    runtime_name=selected_runtime,
                    failure=exc,
                )

            backend_product = resolved_context.product_context
            backend_inquiry = resolved_context.inquiry_context
            model_code = backend_product.model_code
            raw_symptom = backend_inquiry.customer_query
            selected_symptoms = list(backend_inquiry.selected_symptoms)
            previous_answers = [
                answer.model_dump()
                for answer in backend_inquiry.previous_answers
            ]

        product_context = resolve_product_context(
            model_code,
            supported_functions=(
                set(resolved_context.product_context.features.supported_functions)
                if retrieval_transport == "mcp"
                else None
            ),
            runtime_approved_model_codes=self.rag_runtime_profile.approved_model_codes,
        )
        if retrieval_transport == "mcp" and (
            product_context.model_code != model_code
            or product_context.product_family.value
            != resolved_context.product_context.product_family
        ):
            return self._context_failure_result(
                inquiry_id=inquiry_id,
                correlation_id=correlation_id,
                ai_request_id=ai_request_id,
                state_version=state_version,
                raw_symptom=raw_symptom,
                model_code=model_code,
                selected_symptoms=selected_symptoms,
                previous_answers=previous_answers,
                cancellation_token=token,
                runtime_name=selected_runtime,
                failure=McpBackendContextError(
                    tool_name=McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT,
                    kind=BackendContextFailureKind.INVALID_RESPONSE,
                    retryable=False,
                ),
            )
        ctx = PipelineContext(
            trace_context=TraceContext(
                inquiry_id=inquiry_id,
                correlation_id=correlation_id,
                ai_request_id=ai_request_id,
                state_version=state_version,
            ),
            raw_symptom=raw_symptom,
            model_code=product_context.model_code,
            selected_symptoms=selected_symptoms or [],
            previous_answers=previous_answers or []
        )

        base_search_service = (
            _create_mcp_evidence_search_service()
            if retrieval_transport == "mcp"
            else self.search_service
        )
        guarded_search_service = (
            GuardedEvidenceSearchService(base_search_service, product_context)
            if base_search_service is not None
            else None
        )
        if guarded_search_service is not None:
            guarded_search_service.begin_attempt()
        runtime_search_service = guarded_search_service or base_search_service
        retrieval_configuration_error = (
            None if retrieval_transport == "mcp" else self.retrieval_configuration_error
        )

        if selected_runtime == "single_rag":
            pipeline = SingleRAGPipeline(
                runtime_search_service,
                retrieval_configuration_error=retrieval_configuration_error,
                llm_client=self.llm_client,
                symptom_llm_client=self.symptom_llm_client,
                followup_llm_client=self.followup_llm_client,
            )
        elif selected_runtime == "multi_agent":
            pipeline = MultiAgentPipeline(
                runtime_search_service,
                retrieval_configuration_error=retrieval_configuration_error,
                llm_client=self.llm_client,
                symptom_llm_client=self.symptom_llm_client,
                followup_llm_client=self.followup_llm_client,
            )
        if retrieval_transport == "mcp":
            try:
                pipeline_result = pipeline.run(
                    ctx,
                    cancellation_token=token,
                )
            except McpEvidenceSearchError as exc:
                failure = McpToolFailure(
                    tool_name=McpToolName.SEARCH_OFFICIAL_EVIDENCE,
                    kind=McpToolFailureKind(exc.kind.value),
                    retryable=exc.retryable,
                )
                reliability = self.reliability_runtime.run(
                    ctx=ctx,
                    product=product_context,
                    evidence_capture=guarded_search_service,
                    search_service=runtime_search_service,
                    llm_client=self.llm_client,
                    cancellation_token=token,
                    tool_failure=failure,
                )
                return PipelineResult(
                    success=False,
                    context=ctx,
                    runtime_name=selected_runtime,
                    reliability_runtime=reliability,
                )
        else:
            pipeline_result = pipeline.run(
                ctx,
                cancellation_token=token,
            )

        pipeline_result.reliability_runtime = self.reliability_runtime.run(
            ctx=pipeline_result.context,
            product=product_context,
            evidence_capture=guarded_search_service,
            search_service=runtime_search_service,
            llm_client=self.llm_client,
            cancellation_token=token,
        )
        return pipeline_result

    def _context_failure_result(
        self,
        *,
        inquiry_id: UUID,
        correlation_id: UUID,
        ai_request_id: str,
        state_version: int,
        raw_symptom: str,
        model_code: str,
        selected_symptoms: Optional[List[str]],
        previous_answers: Optional[List[Dict[str, str]]],
        cancellation_token: CancellationToken,
        runtime_name: str,
        failure: McpBackendContextError,
    ) -> PipelineResult:
        """Stop before retrieval/provider and route a sanitized Tool failure."""

        product_context = resolve_product_context(
            model_code,
            runtime_approved_model_codes=self.rag_runtime_profile.approved_model_codes,
        )
        ctx = PipelineContext(
            trace_context=TraceContext(
                inquiry_id=inquiry_id,
                correlation_id=correlation_id,
                ai_request_id=ai_request_id,
                state_version=state_version,
            ),
            raw_symptom=raw_symptom,
            model_code=product_context.model_code,
            selected_symptoms=selected_symptoms or [],
            previous_answers=previous_answers or [],
        )
        # Backend Context가 실패해도 공개 응답의 필수 계약과 명시적 안전 규칙은
        # 유지한다. 검색과 Provider는 아래 Tool failure 경계에서 계속 차단된다.
        execute_structuring_stage(ctx)
        execute_safety_check_stage(ctx)
        tool_failure = McpToolFailure(
            tool_name=McpToolName(failure.tool_name.value),
            kind=McpToolFailureKind(failure.kind.value),
            retryable=failure.retryable,
        )
        reliability = self.reliability_runtime.run(
            ctx=ctx,
            product=product_context,
            evidence_capture=None,
            search_service=None,
            llm_client=self.llm_client,
            cancellation_token=cancellation_token,
            tool_failure=tool_failure,
        )
        return PipelineResult(
            success=False,
            context=ctx,
            runtime_name=runtime_name,
            reliability_runtime=reliability,
        )
