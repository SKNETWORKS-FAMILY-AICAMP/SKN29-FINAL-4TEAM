"""MCP official-evidence Tool -> Harness bounded retry integration."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from ai.app.integrations.mcp.search_service import (
    McpEvidenceFailureKind,
    McpEvidenceSearchError,
    McpEvidenceSearchService,
)
from ai.app.orchestration.harness.product_registry import resolve_product_context
from ai.app.orchestration.harness.runtime import ReliabilityRuntime
from ai.app.orchestration.harness.tool_failure import (
    McpToolFailure,
    McpToolFailureKind,
    McpToolName,
)
from ai.app.orchestration.harness.verification_result import HarnessDecision
from ai.app.orchestration.pipeline_context import PipelineContext
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.schemas import (
    TraceContext,
    UsageGuidance,
    UsageGuidanceStatus,
)
from ai.app.common.timeout import CancellationToken


class _FakeCallResult:
    def __init__(self, payload):
        self.structuredContent = payload
        self.isError = False


class _FakeMcpClient:
    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def call_tool(self, tool_name, arguments):
        assert tool_name == "search_official_evidence"
        return _FakeCallResult(self.payload)


def _output_payload():
    return {
        "evidence_references": [
            {
                "document_title": "JAC104 사용설명서",
                "document_version": "1.0",
                "page": 10,
                "page_refs": [10],
                "chunk_id": "RAG-WPUJAC104DWH-TEST-001",
                "official_url": "https://example.com/manual",
                "summary": "공식 근거입니다.",
                "similarity_score": 0.91,
                "verification_status": "official_verified",
            }
        ],
        "vector_search_executed": True,
        "search_result_found": True,
        "evidence_found": True,
        "policy_blocked": False,
        "policy_execution_path": "PGVECTOR_QUERY",
        "applied_rule_id": None,
        "block_reason": None,
    }


def test_mcp_search_service_reconstructs_exact_request_product_identity():
    payload = _output_payload()
    service = McpEvidenceSearchService(
        client_factory=lambda: _FakeMcpClient(payload)
    )

    results = service.search(
        RetrievalQuery(
            query_text="물이 나오지 않아요",
            model_code="WPUJAC104DWH",
            product_generation="D",
            top_k=5,
        )
    )

    assert len(results) == 1
    assert results[0].model_code == "WPUJAC104DWH"
    assert results[0].product_generation == "D"
    assert results[0].verification_status == "official_verified"
    assert results[0].allowed_use is True
    assert results[0].runtime_eligible is True


def test_invalid_mcp_response_is_sanitized():
    service = McpEvidenceSearchService(
        client_factory=lambda: _FakeMcpClient({"unexpected": "shape"})
    )

    with pytest.raises(McpEvidenceSearchError) as exc_info:
        service.search(
            RetrievalQuery(
                query_text="물이 나오지 않아요",
                model_code="WPUJAC104DWH",
                product_generation="D",
                top_k=5,
            )
        )

    assert exc_info.value.kind == McpEvidenceFailureKind.INVALID_RESPONSE
    assert exc_info.value.retryable is False
    assert "unexpected" not in str(exc_info.value)


def _ctx() -> PipelineContext:
    ctx = PipelineContext(
        trace_context=TraceContext(
            inquiry_id=uuid4(),
            correlation_id=uuid4(),
            ai_request_id=f"mcp-harness-{uuid4().hex[:8]}",
            state_version=1,
        ),
        raw_symptom="물이 나오지 않아요",
        model_code="WPUJAC104DWH",
    )
    ctx.usage_guidance = UsageGuidance(
        guidance_status=UsageGuidanceStatus.PENDING_CONSULTATION,
        message="테스트 안내",
        restricted_functions=[],
        next_actions=[],
    )
    return ctx


class _AlwaysFailSearch:
    def search(self, query, *, cancellation_token=None):
        raise McpEvidenceSearchError(
            kind=McpEvidenceFailureKind.UNAVAILABLE,
            retryable=True,
        )


def test_retryable_mcp_failure_retries_once_then_escalates_to_handoff():
    ctx = _ctx()
    product = resolve_product_context("WPUJAC104DWH")
    failure = McpToolFailure(
        tool_name=McpToolName.SEARCH_OFFICIAL_EVIDENCE,
        kind=McpToolFailureKind.UNAVAILABLE,
        retryable=True,
    )

    runtime = ReliabilityRuntime()
    result = runtime.run(
        ctx=ctx,
        product=product,
        evidence_capture=None,
        search_service=_AlwaysFailSearch(),
        llm_client=None,
        cancellation_token=CancellationToken(),
        tool_failure=failure,
    )

    assert result.retrieval_retry_performed is True
    assert result.harness_runtime.harness.decision == HarnessDecision.ESCALATE
    assert result.harness_runtime.handoff is not None
    assert (
        result.harness_runtime.handoff.escalation_reason
        == "MCP_TOOL_FAILURE"
    )


def test_non_retryable_mcp_failure_escalates_without_retry():
    ctx = _ctx()
    product = resolve_product_context("WPUJAC104DWH")
    failure = McpToolFailure(
        tool_name=McpToolName.SEARCH_OFFICIAL_EVIDENCE,
        kind=McpToolFailureKind.INVALID_RESPONSE,
        retryable=False,
    )

    result = ReliabilityRuntime().run(
        ctx=ctx,
        product=product,
        evidence_capture=None,
        search_service=_AlwaysFailSearch(),
        llm_client=None,
        cancellation_token=CancellationToken(),
        tool_failure=failure,
    )

    assert result.retrieval_retry_performed is False
    assert result.harness_runtime.harness.decision == HarnessDecision.ESCALATE
    assert result.harness_runtime.handoff is not None

