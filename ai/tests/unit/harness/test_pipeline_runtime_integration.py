"""Pipeline -> pre-generation evidence gate -> Harness retry/HITL/Handoff integration tests."""

from __future__ import annotations

import json

import pytest
from pathlib import Path
from types import SimpleNamespace

from ai.app.orchestration.harness import (
    HarnessDecision,
    ProductContext,
    ProductFamily,
)
from ai.app.orchestration.harness.evidence_capture import GuardedEvidenceSearchService
from ai.app.orchestration.harness.product_registry import (
    KNOWN_EXACT_MODEL_CODES,
    RUNTIME_APPROVED_EXACT_MODEL_CODES,
    resolve_product_context,
)
from ai.app.orchestration.harness.verification_result import (
    VerificationIssue,
    VerificationIssueCode,
)
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.schemas import UsageGuidanceStatus


class CrossProductSearchService:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, *args, **kwargs):
        self.calls += 1
        return [_chunk("wrong-iac606", "WPUIAC606SNW")]


class FailIfCalledLLM:
    def __init__(self) -> None:
        self.calls = 0

    def generate_guidance(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("cross-product evidence must be blocked before LLM generation")


def _chunk(
    chunk_id: str,
    model_code: str,
    *,
    runtime_eligible: bool = True,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_title=f"{model_code} official manual",
        manual_model=model_code,
        model_code=model_code,
        content="official evidence",
        similarity_score=0.95,
        verification_status="official_verified",
        allowed_use=True,
        runtime_eligible=runtime_eligible,
    )


def _run_danger_pipeline():
    return PipelineRouter(search_service=None).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b401",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88e401",
        ai_request_id="ai-req-harness-danger-001",
        state_version=1,
        raw_symptom="정수기 전원선 주변에 심한 누수가 발생했습니다.",
        model_code="WPUJAC104DWH",
        selected_symptoms=["누수"],
    )

def test_danger_path_passes_harness_without_evidence_or_retrieval_retry():
    result = _run_danger_pipeline()

    reliability = result.reliability_runtime
    assert reliability is not None
    assert reliability.harness_runtime.harness.decision == HarnessDecision.PASS
    assert reliability.retrieval_retry_performed is False
    assert reliability.harness_runtime.harness.verification.evidence_present is False
    assert not any(
        issue.code.value == "NO_EVIDENCE"
        for issue in reliability.harness_runtime.harness.verification.issues
    )
    assert result.context.usage_guidance.guidance_status == UsageGuidanceStatus.TOTAL_STOP
    assert reliability.harness_runtime.handoff is not None
    assert reliability.harness_runtime.handoff.escalation_reason == "DANGER_PRIORITY"

def test_cross_product_evidence_is_blocked_before_llm_then_escalates_after_one_retry():
    search_service = CrossProductSearchService()
    result = PipelineRouter(
        search_service=search_service,
        llm_client=FailIfCalledLLM(),
    ).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b402",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88e402",
        ai_request_id="ai-req-cross-product-001",
        state_version=1,
        raw_symptom="냉수가 미지근합니다.",
        model_code="WPUJAC104DWH",
    )

    reliability = result.reliability_runtime
    response = result.to_analysis_result()
    assert search_service.calls == 2
    assert reliability is not None
    assert reliability.retrieval_retry_performed is True
    assert reliability.harness_runtime.harness.decision == HarnessDecision.ESCALATE
    assert reliability.blocked_evidence_chunk_ids == ["wrong-iac606"]
    assert reliability.harness_runtime.handoff is not None
    assert reliability.harness_runtime.handoff.model_code == "WPUJAC104DWH"
    assert response.evidence_references == []
    assert response.usage_guidance.guidance_status == UsageGuidanceStatus.PENDING_CONSULTATION
    assert response.status.value == "FALLBACK"

def test_guarded_search_forwards_only_exact_runtime_eligible_evidence():
    product = ProductContext(
        model_code="WPUJAC104DWH",
        product_family=ProductFamily.DIRECT_WATER_PURIFIER,
    )

    class MixedSearchService:
        def search(self, *args, **kwargs):
            return [
                _chunk("correct", "WPUJAC104DWH"),
                _chunk("wrong", "WPUIAC606SNW"),
                _chunk("disabled", "WPUJAC104DWH", runtime_eligible=False),
            ]

    guarded = GuardedEvidenceSearchService(MixedSearchService(), product)
    guarded.begin_attempt()
    forwarded = guarded.search(object())
    ctx = SimpleNamespace(
        evidence_references=[SimpleNamespace(chunk_id="correct")],
    )
    harness_chunks = guarded.evidence_for_harness(ctx)

    assert [chunk.chunk_id for chunk in forwarded] == ["correct"]
    assert {chunk.chunk_id for chunk in harness_chunks} == {
        "correct",
        "wrong",
        "disabled",
    }
    assert guarded.rejected_chunk_ids == ["wrong", "disabled"]


@pytest.mark.parametrize(
    (
        "model_code",
        "raw_symptom",
        "expected_failure_stage",
        "expected_risk",
        "expected_guidance_status",
    ),
    [
        (
            "WPUIAC425SNW",
            "얼음 출수 상태를 확인하고 싶습니다.",
            "RETRIEVING",
            "caution",
            "PENDING_CONSULTATION",
        ),
        (
            "WPUIAC425SNW",
            "정수기 밑에서 물이 새고 있습니다.",
            "VALIDATING",
            "danger",
            "TOTAL_STOP",
        ),
        (
            "WPUIAC606SNW",
            "얼음 출수 상태를 확인하고 싶습니다.",
            "RETRIEVING",
            "caution",
            "PENDING_CONSULTATION",
        ),
        (
            "WPUIAC606SNW",
            "정수기 밑에서 물이 새고 있습니다.",
            "VALIDATING",
            "danger",
            "TOTAL_STOP",
        ),
    ],
)
def test_unapproved_iac_general_and_leak_never_reach_vector_or_provider(
    model_code,
    raw_symptom,
    expected_failure_stage,
    expected_risk,
    expected_guidance_status,
):
    class FailIfSearched:
        def __init__(self):
            self.calls = 0

        def search(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("runtime-unapproved product must not reach vector search")

    delegate = FailIfSearched()
    llm = FailIfCalledLLM()
    correlation_id = "018f2f9b-7c30-7981-b541-1a987c88e403"
    result = PipelineRouter(
        search_service=delegate,
        llm_client=llm,
    ).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b403",
        correlation_id=correlation_id,
        ai_request_id=f"ai-req-runtime-block-{model_code}",
        state_version=1,
        raw_symptom=raw_symptom,
        model_code=model_code,
    )

    reliability = result.reliability_runtime
    assert delegate.calls == 0
    assert llm.calls == 0
    assert reliability is not None
    assert reliability.retrieval_retry_performed is False
    assert reliability.harness_runtime.harness.decision == HarnessDecision.ESCALATE
    assert [
        issue.code.value
        for issue in reliability.harness_runtime.harness.verification.issues
    ] == ["RUNTIME_PRODUCT_NOT_APPROVED"]
    assert reliability.harness_runtime.handoff is not None
    assert reliability.harness_runtime.handoff.model_code == model_code
    assert reliability.harness_runtime.handoff.product_family == "ICE_WATER_PURIFIER"
    public_result = result.to_analysis_result()
    assert public_result.model_code == model_code
    assert str(public_result.correlation_id) == correlation_id
    assert public_result.status.value == "FALLBACK"
    assert (
        public_result.fallback_reason_code.value
        == "RUNTIME_PRODUCT_NOT_APPROVED"
    )
    # Stage는 실행 감사 정보라 증상 경로에 따라 달라져도 제품 미승인 사유는 같다.
    assert public_result.failure_stage.value == expected_failure_stage
    assert public_result.safety_assessment.risk_level.value == expected_risk
    assert public_result.safety_assessment.requires_consultation is True
    assert public_result.usage_guidance.guidance_status.value == expected_guidance_status
    assert public_result.evidence_references == []


def test_output_schema_issue_maps_to_distinct_public_fallback_reason():
    result = PipelineRouter(search_service=None).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b405",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88e405",
        ai_request_id="ai-req-output-schema-invalid",
        state_version=1,
        raw_symptom="정수기 전원선 주변에 심한 누수가 발생했습니다.",
        model_code="WPUJAC104DWH",
        selected_symptoms=["누수"],
    )
    reliability = result.reliability_runtime
    assert reliability is not None
    harness = reliability.harness_runtime.harness
    harness.decision = HarnessDecision.ESCALATE
    harness.verification.issues.append(
        VerificationIssue(
            code=VerificationIssueCode.OUTPUT_SCHEMA_INVALID,
            message="test-only invalid public output",
            retryable=False,
        )
    )

    response = result.to_analysis_result()
    assert response.status.value == "FALLBACK"
    assert response.fallback_reason_code.value == "OUTPUT_SCHEMA_INVALID"
    assert response.failure_stage.value == "VALIDATING"


@pytest.mark.parametrize("model_code", ["WPUIAC425SNW", "WPUIAC606SNW"])
def test_three_model_integration_profile_allows_iac_retrieval_only_when_explicit(
    monkeypatch,
    model_code,
):
    class EmptySearchService:
        def __init__(self):
            self.calls = 0

        def search(self, *args, **kwargs):
            self.calls += 1
            return []

    monkeypatch.setenv("AI_RAG_RUNTIME_PROFILE", "three_model_integration")
    delegate = EmptySearchService()
    result = PipelineRouter(search_service=delegate).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b404",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88e404",
        ai_request_id=f"ai-req-runtime-integration-{model_code}",
        state_version=1,
        raw_symptom="출수 기능을 확인하고 싶습니다.",
        model_code=model_code,
    )

    assert delegate.calls > 0
    assert result.to_analysis_result().status.value == "FALLBACK"


def test_runtime_registry_matches_data_contract_and_activation_status():
    repository_root = Path(__file__).resolve().parents[4]
    contract = json.loads(
        (repository_root / "data" / "config" / "rag" / "supported_products.json").read_text(
            encoding="utf-8"
        )
    )
    contract_codes = {item["exact_sales_code"] for item in contract["products"]}
    runtime_approved_codes = {
        item["exact_sales_code"]
        for item in contract["products"]
        if item["runtime_status"] == "INDEXED_MVP"
    }

    assert set(KNOWN_EXACT_MODEL_CODES) == contract_codes
    assert RUNTIME_APPROVED_EXACT_MODEL_CODES == runtime_approved_codes == {
        "WPUJAC104DWH"
    }
    assert resolve_product_context("WPUIAC425SNW").product_family == ProductFamily.ICE_WATER_PURIFIER
    assert resolve_product_context("WPUIAC425SNW").runtime_approved is False
    assert resolve_product_context("WPUJAC104DWH").runtime_approved is True

def test_reliability_metadata_is_excluded_from_pipeline_serialization():
    result = _run_danger_pipeline()

    assert result.reliability_runtime is not None
    assert "reliability_runtime" not in result.model_dump()
