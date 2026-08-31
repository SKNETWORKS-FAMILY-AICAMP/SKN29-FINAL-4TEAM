"""Backend Context MCP Tools -> official-evidence Pipeline integration."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from ai.app.generation.customer_guidance.models import GuidanceGenerationResult
from ai.app.integrations.backend import (
    BackendContextFailureKind,
    BackendInquiryPayload,
    BackendProductContext,
)
from ai.app.integrations.llm import GuidanceLLMResponse, LLMUsage
from ai.app.integrations.mcp.context_service import (
    McpBackendContextError,
    McpBackendContextToolName,
    ResolvedBackendContext,
)
from ai.app.orchestration import pipeline_router as pipeline_router_module
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.retrieval import RetrievedChunk, RetrievalOutcome


class _ContextService:
    def __init__(self, resolved=None, error=None):
        self.resolved = resolved
        self.error = error
        self.calls = []

    def resolve(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.resolved


class _SearchService:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.queries = []

    def search(self, query, *, cancellation_token=None):
        self.queries.append(query)
        return [chunk.model_copy(deep=True) for chunk in self.chunks]


class _LLM:
    def __init__(self):
        self.calls = 0

    def generate_guidance(self, request, *, timeout_seconds):
        self.calls += 1
        return GuidanceLLMResponse(
            output=GuidanceGenerationResult(
                message=request.evidence_summaries[0],
                next_actions=list(request.allowed_next_actions[:1]),
            ),
            model_name="gpt-4.1-mini",
            usage=LLMUsage(input_tokens=10, output_tokens=8, total_tokens=18),
            latency_ms=10.0,
        )


def _resolved(
    inquiry_id,
    correlation_id,
    *,
    model_code="WPUIAC425SNW",
    state_version=4,
    customer_query="냉수가 미지근합니다.",
    selected_symptoms=None,
):
    return ResolvedBackendContext(
        inquiry_id=inquiry_id,
        correlation_id=correlation_id,
        inquiry_code="INQ-MCP-TEST",
        status_code="QUESTIONNAIRE_IN_PROGRESS",
        state_version=state_version,
        product_context=BackendProductContext.model_validate(
            {
                "subscription_id": uuid4(),
                "subscription_status_code": "ACTIVE",
                "management_type_code": "SELF_MANAGED",
                "product_model_id": uuid4(),
                "model_code": model_code,
                "model_name": model_code,
                "product_family": (
                    "DIRECT_WATER_PURIFIER"
                    if model_code == "WPUJAC104DWH"
                    else "ICE_WATER_PURIFIER"
                ),
                "generation_code": (
                    "D" if model_code == "WPUJAC104DWH" else "ICE"
                ),
                "manufacturer": "SK매직",
                "features": {
                    "model_family": model_code,
                    "water_modes": ["COLD"],
                    "supported_functions": ["COLD_WATER"],
                },
            }
        ),
        inquiry_context=BackendInquiryPayload(
            customer_query=customer_query,
            symptom_type="COLD_WATER_TEMPERATURE",
            selected_symptoms=(
                ["COLD_WATER_TEMPERATURE"]
                if selected_symptoms is None
                else selected_symptoms
            ),
            previous_answers=[],
        ),
    )


def _chunk(model_code="WPUIAC425SNW"):
    return RetrievedChunk(
        chunk_id=f"CHILD-{model_code}-TEST",
        document_title=f"{model_code} 사용설명서",
        document_version="REV.00",
        page=10,
        page_refs=[10],
        manual_model=model_code,
        model_code=model_code,
        product_generation=(
            "D" if model_code == "WPUJAC104DWH" else model_code[3:9]
        ),
        content="냉수 상태를 확인하는 공식 안내입니다.",
        topic_code="symptom_cold_temperature",
        similarity_score=0.91,
        official_url="https://example.invalid/manual",
        verification_status="official_verified",
        allowed_use=True,
        runtime_eligible=True,
    )


def _three_model_profile(router):
    router.rag_runtime_profile = SimpleNamespace(
        approved_model_codes=frozenset(
            {"WPUJAC104DWH", "WPUIAC425SNW", "WPUIAC606SNW"}
        )
    )


def test_mcp_pipeline_uses_backend_model_code_unchanged(monkeypatch):
    monkeypatch.setenv("AI_RETRIEVAL_TRANSPORT", "mcp")
    inquiry_id = uuid4()
    correlation_id = uuid4()
    context_service = _ContextService(_resolved(inquiry_id, correlation_id))
    search_service = _SearchService([_chunk()])
    monkeypatch.setattr(
        pipeline_router_module,
        "_create_mcp_evidence_search_service",
        lambda: search_service,
    )
    router = PipelineRouter(
        search_service=None,
        llm_client=_LLM(),
        mcp_context_service=context_service,
    )
    _three_model_profile(router)

    result = router.run_pipeline(
        inquiry_id=inquiry_id,
        correlation_id=correlation_id,
        ai_request_id="mcp-context-success",
        state_version=4,
        raw_symptom="호출 Body의 값보다 Backend Context가 우선합니다.",
        model_code="WPUIAC425SNW",
    )

    assert result.context.model_code == "WPUIAC425SNW"
    assert result.context.raw_symptom == "냉수가 미지근합니다."
    assert search_service.queries[0].model_code == "WPUIAC425SNW"
    assert search_service.queries[0].product_generation == "IAC425"
    assert result.context.evidence_references[0].chunk_id == (
        "CHILD-WPUIAC425SNW-TEST"
    )
    assert context_service.calls[0]["expected_model_code"] == (
        "WPUIAC425SNW"
    )


def test_mcp_unapproved_iac606_leak_code_applies_safety_before_retrieval(
    monkeypatch,
):
    monkeypatch.setenv("AI_RETRIEVAL_TRANSPORT", "mcp")
    inquiry_id = uuid4()
    correlation_id = uuid4()
    context_service = _ContextService(
        _resolved(
            inquiry_id,
            correlation_id,
            model_code="WPUIAC606SNW",
            state_version=1,
            customer_query="제품 밑으로 물이 번지고 있습니다.",
            selected_symptoms=["symptom_leak"],
        )
    )
    search_service = _SearchService([])
    llm = _LLM()
    monkeypatch.setattr(
        pipeline_router_module,
        "_create_mcp_evidence_search_service",
        lambda: search_service,
    )

    result = PipelineRouter(
        search_service=None,
        llm_client=llm,
        mcp_context_service=context_service,
    ).run_pipeline(
        inquiry_id=inquiry_id,
        correlation_id=correlation_id,
        ai_request_id="mcp-context-iac606-leak-safety",
        state_version=1,
        raw_symptom="호출 Body보다 Backend Context가 우선합니다.",
        model_code="WPUIAC606SNW",
    )

    response = result.to_analysis_result()
    assert search_service.queries == []
    assert llm.calls == 0
    assert response.status.value == "FALLBACK"
    assert response.fallback_reason_code.value == (
        "RUNTIME_PRODUCT_NOT_APPROVED"
    )
    assert response.safety_assessment.risk_level.value == "danger"
    assert response.safety_assessment.matched_safety_rule_ids == [
        "SAFETY-LEAK-001"
    ]
    assert response.usage_guidance.guidance_status.value == "TOTAL_STOP"
    assert response.evidence_references == []


def test_mcp_context_timeout_stops_before_search_and_provider(monkeypatch):
    monkeypatch.setenv("AI_RETRIEVAL_TRANSPORT", "mcp")
    failure = McpBackendContextError(
        tool_name=McpBackendContextToolName.LOOKUP_PRODUCT_CONTEXT,
        kind=BackendContextFailureKind.TIMEOUT,
        retryable=True,
    )
    context_service = _ContextService(error=failure)
    llm = _LLM()
    search_created = []
    correlation_id = uuid4()
    monkeypatch.setattr(
        pipeline_router_module,
        "_create_mcp_evidence_search_service",
        lambda: search_created.append(True),
    )

    result = PipelineRouter(
        search_service=None,
        llm_client=llm,
        mcp_context_service=context_service,
    ).run_pipeline(
        inquiry_id=uuid4(),
        correlation_id=correlation_id,
        ai_request_id="mcp-context-timeout",
        state_version=1,
        raw_symptom="냉수가 미지근합니다.",
        model_code="WPUJAC104DWH",
    )

    harness = result.reliability_runtime.harness_runtime.harness
    assert result.success is False
    assert harness.error_code.value == "MCP_TOOL_FAILURE"
    assert result.reliability_runtime.harness_runtime.handoff is not None
    assert result.context.evidence_references == []
    assert search_created == []
    assert llm.calls == 0
    response = result.to_analysis_result()
    assert response.status.value == "FALLBACK"
    assert response.model_code == "WPUJAC104DWH"
    assert response.fallback_reason_code.value == "MCP_TOOL_FAILURE"
    assert str(response.correlation_id) == str(correlation_id)
    assert response.structured_symptom is not None
    assert response.safety_assessment is not None
    assert response.evidence_references == []


def test_mcp_no_evidence_and_cross_model_evidence_fail_closed(monkeypatch):
    monkeypatch.setenv("AI_RETRIEVAL_TRANSPORT", "mcp")
    inquiry_id = uuid4()
    correlation_id = uuid4()
    context_service = _ContextService(_resolved(inquiry_id, correlation_id))

    empty_search = _SearchService([])
    monkeypatch.setattr(
        pipeline_router_module,
        "_create_mcp_evidence_search_service",
        lambda: empty_search,
    )
    empty_router = PipelineRouter(
        search_service=None,
        mcp_context_service=context_service,
    )
    _three_model_profile(empty_router)
    empty = empty_router.run_pipeline(
        inquiry_id=inquiry_id,
        correlation_id=correlation_id,
        ai_request_id="mcp-no-evidence",
        state_version=4,
        raw_symptom="냉수가 미지근합니다.",
        model_code="WPUIAC425SNW",
    )
    assert empty.context.retrieval_outcome == RetrievalOutcome.NO_MATCH
    assert empty.to_analysis_result().status.value == "FALLBACK"
    assert empty.context.evidence_references == []

    wrong_search = _SearchService([_chunk("WPUIAC606SNW")])
    monkeypatch.setattr(
        pipeline_router_module,
        "_create_mcp_evidence_search_service",
        lambda: wrong_search,
    )
    wrong_router = PipelineRouter(
        search_service=None,
        mcp_context_service=context_service,
    )
    _three_model_profile(wrong_router)
    wrong = wrong_router.run_pipeline(
        inquiry_id=inquiry_id,
        correlation_id=correlation_id,
        ai_request_id="mcp-cross-model",
        state_version=4,
        raw_symptom="냉수가 미지근합니다.",
        model_code="WPUIAC425SNW",
    )

    assert wrong.context.evidence_references == []
    assert wrong.reliability_runtime.blocked_evidence_chunk_ids == [
        "CHILD-WPUIAC606SNW-TEST"
    ]
    assert wrong.reliability_runtime.harness_runtime.handoff is not None



def test_mcp_multi_agent_combined_path_uses_backend_context_and_mcp_evidence(
    monkeypatch,
):
    monkeypatch.setenv(
        "AI_RETRIEVAL_TRANSPORT",
        "mcp",
    )

    inquiry_id = uuid4()
    correlation_id = uuid4()

    backend_query = (
        "\uc5b4\uc81c\ubd80\ud130 "
        "\ub0c9\uc218 \ubc84\ud2bc\uc744 "
        "\ub204\ub974\uba74 \ubb3c\uc774 "
        "\uc878\uc878 \ub098\uc635\ub2c8\ub2e4. "
        "\uc804\uc6d0\uc744 \uaecd\ub2e4 "
        "\ucf30\uc5b4\uc694."
    )

    context_service = _ContextService(
        _resolved(
            inquiry_id,
            correlation_id,
            model_code="WPUJAC104DWH",
            state_version=1,
            customer_query=backend_query,
            selected_symptoms=["LOW_FLOW"],
        )
    )

    search_service = _SearchService(
        [_chunk("WPUJAC104DWH").model_copy(update={
            "topic_code": "symptom_low_flow",
            "content": "출수량이 적을 때 원수 공급과 필터 상태를 확인합니다.",
        })]
    )

    llm = _LLM()

    monkeypatch.setattr(
        pipeline_router_module,
        "_create_mcp_evidence_search_service",
        lambda: search_service,
    )

    result = PipelineRouter(
        search_service=None,
        llm_client=llm,
        mcp_context_service=context_service,
    ).run_pipeline(
        inquiry_id=inquiry_id,
        correlation_id=correlation_id,
        ai_request_id="mcp-multi-agent-combined",
        state_version=1,
        raw_symptom="BODY_VALUE_MUST_NOT_WIN",
        model_code="WPUJAC104DWH",
        runtime_name="multi_agent",
    )

    response = result.to_analysis_result()

    assert result.runtime_name == "multi_agent"
    assert result.context.model_code == "WPUJAC104DWH"

    # Backend MCP Context must override the caller body.
    assert result.context.raw_symptom == backend_query
    assert len(context_service.calls) == 1

    # Retrieval must follow the exact Backend product identity.
    assert len(search_service.queries) == 1
    assert search_service.queries[0].model_code == (
        "WPUJAC104DWH"
    )
    assert search_service.queries[0].product_generation == "D"

    # Evidence must survive into the Multi-Agent path.
    assert result.context.evidence_references
    assert result.multi_agent_metadata is not None

    # Care Decision / generation must complete successfully.
    assert llm.calls == 1
    assert response.status.value == "SUCCEEDED"
