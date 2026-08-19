"""Pipeline -> pre-generation evidence gate -> Harness retry/HITL/Handoff integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from ai.app.orchestration.harness import (
    HarnessDecision,
    ProductContext,
    ProductFamily,
)
from ai.app.orchestration.harness.evidence_capture import GuardedEvidenceSearchService
from ai.app.orchestration.harness.product_registry import SUPPORTED_EXACT_MODEL_CODES
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
    def generate_guidance(self, *args, **kwargs):
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


def test_guarded_search_rewrites_iac_product_generation_before_delegate_search():
    product = ProductContext(
        model_code="WPUIAC425SNW",
        product_family=ProductFamily.ICE_WATER_PURIFIER,
    )

    class RecordingSearchService:
        def __init__(self):
            self.query = None

        def search(self, query, *args, **kwargs):
            self.query = query
            return []

    delegate = RecordingSearchService()
    guarded = GuardedEvidenceSearchService(delegate, product)
    guarded.search(
        RetrievalQuery(
            query_text="얼음이 나오지 않아요.",
            model_code="WPUIAC425SNW",
            product_generation="D",
        )
    )

    assert delegate.query.model_code == "WPUIAC425SNW"
    assert delegate.query.product_generation == "IAC425"

def test_runtime_registry_matches_current_three_product_data_contract():
    repository_root = Path(__file__).resolve().parents[4]
    contract = json.loads(
        (repository_root / "data" / "config" / "rag" / "supported_products.json").read_text(
            encoding="utf-8"
        )
    )
    contract_codes = {item["exact_sales_code"] for item in contract["products"]}

    assert set(SUPPORTED_EXACT_MODEL_CODES) == contract_codes
    assert set(SUPPORTED_EXACT_MODEL_CODES) == {
        "WPUJAC104DWH",
        "WPUIAC425SNW",
        "WPUIAC606SNW",
    }

def test_reliability_metadata_is_excluded_from_pipeline_serialization():
    result = _run_danger_pipeline()

    assert result.reliability_runtime is not None
    assert "reliability_runtime" not in result.model_dump()
