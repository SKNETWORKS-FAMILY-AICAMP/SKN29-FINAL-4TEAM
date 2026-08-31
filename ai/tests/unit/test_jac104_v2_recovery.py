"""Recovery regressions through the real factory, filters and both pipelines.

Only the embedding/DB/LLM adapters are fake. These are not AWS or Provider E2E
results, and the v2 candidate fixture does not constitute public Data approval.
"""

from types import SimpleNamespace

import pytest

from ai.app.generation.customer_guidance.models import GuidanceGenerationResult
from ai.app.integrations.llm import GuidanceLLMResponse, LLMUsage
from ai.app.orchestration import pipeline_router
from ai.app.retrieval.filters.evidence_applicability_gate import EvidenceApplicabilityGate
from ai.app.retrieval.filters.evidence_topic_filter import EvidenceTopicFilter
from ai.app.retrieval.filters.scope_filter import SearchCandidateFilter
from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.app.retrieval.indexing.index_manifest import IndexManifest
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.runtime_profile import (
    JAC104_V2_RECOVERY_PROFILE,
    resolve_rag_runtime_profile,
)
from ai.app.retrieval.search.vector_search import VectorSearchService


COLD_ID = "CHILD-WPUJAC104DWH-P037-COLD-NORMAL-001"
TASTE_ID = "CHILD-WPUJAC104DWH-P038-TASTE-ODOR-001"
COLD_SYMPTOM = "어제부터 냉수 버튼을 누르면 냉수가 미지근합니다. 전원을 껐다 켰어요."


class FakeGuidance:
    def __init__(self):
        self.calls = 0

    def generate_guidance(self, request, *, timeout_seconds):
        self.calls += 1
        return GuidanceLLMResponse(
            output=GuidanceGenerationResult(
                message=request.evidence_summaries[0],
                next_actions=[request.allowed_next_actions[0]],
            ),
            model_name="test-only-fake-provider",
            usage=LLMUsage(input_tokens=10, output_tokens=8, total_tokens=18),
            latency_ms=1.0,
        )


@pytest.fixture
def recovery(monkeypatch):
    profile = resolve_rag_runtime_profile(JAC104_V2_RECOVERY_PROFILE)
    manifest = IndexManifest.load_manifest(str(profile.manifest_path))
    chunks = {
        chunk.chunk_id: chunk.model_copy(update={
            "runtime_eligible": True,
            "similarity_score": 0.9,
            "embedding_model": manifest.model_name,
            "embedding_model_revision": manifest.model_revision,
            "index_version": manifest.index_version,
            "chunk_set_sha256": manifest.chunk_set_sha256.lower(),
            # Match the actual Backend View, not richer local fixtures.
            "record_type": None,
            "topic_code": None,
            "safe_actions": [],
        })
        for chunk in ChunkLoader.from_handoff_profile("rag-expansion").load_verified_chunks()
    }

    class FakeEmbedding:
        model_name = "BAAI/bge-m3"
        model_revision = manifest.model_revision
        dimension = 1024

        def __init__(self):
            self.calls = 0
            self.warmup_calls = 0

        def warmup(self):
            self.warmup_calls += 1

        def embed_query(self, text):
            self.calls += 1
            return [0.0] * self.dimension

    class FakeStore:
        def __init__(self):
            self.calls = []
            self.chunks = [chunks[COLD_ID]]

        def search(self, vector, *, model_code, product_generation, top_k):
            self.calls.append((model_code, product_generation, top_k))
            return self.chunks[:top_k]

    embedding = FakeEmbedding()
    store = FakeStore()
    monkeypatch.setenv("AI_RAG_RUNTIME_PROFILE", JAC104_V2_RECOVERY_PROFILE)
    monkeypatch.setenv("AI_VECTOR_DSN", "postgresql://unused")
    monkeypatch.setenv("AI_VECTOR_TABLE_NAME", "backend_ai_rag_chunks_v1")
    monkeypatch.setenv("AI_EMBEDDING_REVISION", manifest.model_revision)
    monkeypatch.setenv("AI_RETRIEVAL_TRANSPORT", "direct")
    monkeypatch.setattr(pipeline_router, "BgeM3EmbeddingClient", lambda **kwargs: embedding)
    monkeypatch.setattr(pipeline_router, "PgVectorStore", lambda *args, **kwargs: store)
    monkeypatch.setattr(pipeline_router, "_SEARCH_SERVICE_CACHE_KEY", None)
    monkeypatch.setattr(pipeline_router, "_SEARCH_SERVICE_CACHE", None)
    service = pipeline_router.PipelineRouter._configured_search_service()
    return SimpleNamespace(profile=profile, manifest=manifest, service=service,
                           store=store, embedding=embedding, chunks=chunks)


def _run(recovery, *, runtime, model_code="WPUJAC104DWH",
         raw_symptom=COLD_SYMPTOM, previous_answers=None):
    llm = FakeGuidance()
    # Do not inject a separate search service: exercise the production factory.
    result = pipeline_router.PipelineRouter(llm_client=llm).run_pipeline(
        inquiry_id="018f2f9b-7c30-7981-b541-1a987c88b601",
        correlation_id="018f2f9b-7c30-7981-b541-1a987c88b602",
        ai_request_id="ai-jac104-recovery-unit",
        state_version=1,
        model_code=model_code,
        raw_symptom=raw_symptom,
        previous_answers=previous_answers or [],
        runtime_name=runtime,
    )
    return result.to_analysis_result(), llm


def test_legacy_mvp_discards_v2_row_but_recovery_uses_it(recovery):
    legacy = resolve_rag_runtime_profile("mvp")
    legacy_service = VectorSearchService(
        recovery.embedding, recovery.store,
        index_manifest=IndexManifest.load_manifest(str(legacy.manifest_path)),
    )
    query = RetrievalQuery(query_text="냉수가 미지근합니다.", model_code="WPUJAC104DWH")

    assert legacy_service.search(query) == []
    assert [chunk.chunk_id for chunk in recovery.service.search(query)] == [COLD_ID]
    assert recovery.service.index_manifest.chunk_count == 53
    assert recovery.service.answerability_gate.definition["supported_model_codes"] == [
        "WPUJAC104DWH"
    ]
    assert recovery.store.calls == [("WPUJAC104DWH", "D", 5)] * 2


@pytest.mark.parametrize("model_code,generation", [
    ("WPUIAC425SNW", "IAC425"), ("WPUIAC606SNW", "IAC606"),
])
def test_recovery_blocks_other_models_before_embedding_or_sql(recovery, model_code, generation):
    query = RetrievalQuery(query_text="냉수가 미지근합니다.", model_code=model_code,
                           product_generation=generation)
    assert recovery.service.execution_path(query) == "POLICY_BLOCK_UNSUPPORTED_MODEL"
    assert recovery.service.search(query) == []
    assert recovery.embedding.calls == 0
    assert recovery.store.calls == []


def test_recovery_still_rejects_cross_model_and_mismatched_index_rows(recovery):
    valid = recovery.chunks[COLD_ID]
    wrong_model = next(chunk for chunk in recovery.chunks.values()
                       if chunk.model_code == "WPUIAC425SNW")
    recovery.store.chunks = [
        wrong_model,
        valid.model_copy(update={"index_version": "1.0.0"}),
        valid.model_copy(update={"chunk_set_sha256": "0" * 64}),
        valid.model_copy(update={"source_hash": "0" * 64}),
        valid,
    ]
    query = RetrievalQuery(query_text="냉수가 미지근합니다.", model_code="WPUJAC104DWH")
    assert recovery.service.search(query) == [valid]


@pytest.mark.parametrize("runtime", ["single_rag", "multi_agent"])
def test_recovery_cold_path_reaches_fake_provider_once(recovery, runtime):
    response, llm = _run(recovery, runtime=runtime)

    assert response.status.value == "SUCCEEDED"
    assert response.fallback_reason_code is None
    assert [item.chunk_id for item in response.evidence_references] == [COLD_ID]
    assert llm.calls == 1


@pytest.mark.parametrize("runtime", ["single_rag", "multi_agent"])
def test_real_no_match_still_returns_no_evidence_without_provider(recovery, runtime):
    recovery.store.chunks = []
    response, llm = _run(recovery, runtime=runtime)

    assert response.status.value == "FALLBACK"
    assert response.fallback_reason_code.value == "NO_EVIDENCE"
    assert response.failure_stage.value == "RETRIEVING"
    assert response.safety_assessment.risk_level.value == "caution"
    assert response.safety_assessment.requires_consultation is True
    assert response.usage_guidance.guidance_status.value == "PENDING_CONSULTATION"
    assert response.evidence_references == []
    assert llm.calls == 0


@pytest.mark.parametrize("runtime", ["single_rag", "multi_agent"])
@pytest.mark.parametrize("model_code", ["WPUJAC104DWH", "WPUIAC425SNW", "WPUIAC606SNW"])
def test_recovery_preserves_danger_even_for_unapproved_products(recovery, runtime, model_code):
    response, llm = _run(recovery, runtime=runtime, model_code=model_code,
                         raw_symptom="정수기 밑에서 물이 새고 있습니다.")

    assert response.safety_assessment.risk_level.value == "danger"
    assert response.safety_assessment.requires_consultation is True
    assert "SAFETY-LEAK-001" in response.safety_assessment.matched_safety_rule_ids
    assert response.usage_guidance.guidance_status.value == "TOTAL_STOP"
    assert response.evidence_references == []
    assert llm.calls == 0
    assert recovery.embedding.calls == 0
    assert recovery.store.calls == []
    if model_code != "WPUJAC104DWH":
        assert response.fallback_reason_code.value == "RUNTIME_PRODUCT_NOT_APPROVED"


@pytest.mark.parametrize("runtime", ["single_rag", "multi_agent"])
@pytest.mark.parametrize("model_code", ["WPUIAC425SNW", "WPUIAC606SNW"])
def test_recovery_does_not_open_iac_public_guidance(recovery, runtime, model_code):
    response, llm = _run(recovery, runtime=runtime, model_code=model_code)

    assert response.fallback_reason_code.value == "RUNTIME_PRODUCT_NOT_APPROVED"
    assert response.evidence_references == []
    assert response.safety_assessment.requires_consultation is True
    assert llm.calls == 0
    assert recovery.embedding.calls == 0
    assert recovery.store.calls == []


def test_taste_topic_recognizes_exact_v2_child_without_view_topic(recovery):
    taste = recovery.chunks[TASTE_ID]
    unrelated = recovery.chunks[COLD_ID]
    fabricated = taste.model_copy(update={"chunk_id": "UNKNOWN-TASTE-ODOR-001"})
    assert EvidenceTopicFilter().filter_chunks(
        [taste, unrelated, fabricated], symptom_type="물맛/냄새 이상",
    ) == [taste]


@pytest.mark.parametrize("field,value", [
    ("chunk_id", "CHILD-WPUJAC104DWH-P037-UNKNOWN-001"),
    ("record_type", "PARENT"), ("record_type", "SOURCE_PAGE"),
    ("record_type", "PRESERVATION"), ("retrieval_role", "CONTEXT_ONLY"),
    ("retrieval_role", None),
    ("content", "unverified replacement text"), ("source_hash", "0" * 64),
    ("chunk_set_sha256", "0" * 64), ("index_version", "1.0.0"),
    ("page_refs", [38]), ("model_code", "WPUIAC425SNW"),
    ("product_generation", "S"), ("verification_status", "unverified"),
    ("allowed_use", False), ("runtime_eligible", False),
])
def test_omitted_view_record_type_is_not_a_general_filter_bypass(recovery, field, value):
    valid = recovery.chunks[COLD_ID]
    assert SearchCandidateFilter.is_valid_chunk(valid) is True
    assert SearchCandidateFilter.is_valid_chunk(valid.model_copy(update={field: value})) is False


@pytest.mark.parametrize("runtime", ["single_rag", "multi_agent"])
@pytest.mark.parametrize("answer,expected_calls", [("10일 이내 부재 후", 1),
                                                  ("10일 이상 부재 후", 0)])
def test_v2_taste_path_keeps_the_existing_applicability_boundary(
    recovery, runtime, answer, expected_calls,
):
    recovery.store.chunks = [recovery.chunks[TASTE_ID]]
    response, llm = _run(
        recovery, runtime=runtime,
        raw_symptom="어제부터 냉수에서 이상한 냄새가 납니다. 전원을 껐다 켰어요.",
        previous_answers=[{"question_id": EvidenceApplicabilityGate.QUESTION_ID,
                           "answer_text": answer}],
    )
    assert llm.calls == expected_calls
    if expected_calls:
        assert response.status.value == "SUCCEEDED"
        assert [item.chunk_id for item in response.evidence_references] == [TASTE_ID]
    else:
        assert response.fallback_reason_code.value == "NO_EVIDENCE"
        assert response.evidence_references == []
