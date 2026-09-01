"""RAG Retrieval 및 메타데이터 필터 단위 테스트."""

import json
from pathlib import Path

import psycopg
import pytest

from ai.app.common.protected_database import ProtectedDatabaseOperationError
from ai.app.common.timeout import CancellationToken, PipelineCancelledError
from ai.app.retrieval.filters.document_policy_filter import DocumentPolicyFilter
from ai.app.retrieval.filters.evidence_applicability_gate import (
    EvidenceApplicability,
    EvidenceApplicabilityGate,
)
from ai.app.retrieval.filters.evidence_topic_filter import EvidenceTopicFilter
from ai.app.retrieval.filters.product_filter import ProductFilter
from ai.app.retrieval.filters.scope_filter import SearchCandidateFilter
from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.app.retrieval.indexing.index_manifest import IndexManifest
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.retrieval.search.vector_search import VectorSearchService
from ai.app.retrieval.verification.answerability_capability_gate import (
    AnswerabilityCapabilityGate,
)


def test_product_filter_s_generation_exclusion():
    """S세대 및 제거 대상 모델 필터링 테스트"""
    product_filter = ProductFilter()

    # D세대 (정상)
    d_chunk = RetrievedChunk(
        chunk_id="chunk_1",
        document_title="정수기 매뉴얼",
        manual_model="WPUJAC104DWH",
        product_generation="D",
        content="내용",
        similarity_score=0.9
    )
    assert product_filter.is_valid_chunk(d_chunk) is True

    # S세대 (배제 대상)
    s_chunk = RetrievedChunk(
        chunk_id="chunk_2",
        document_title="구형 정수기 매뉴얼",
        manual_model="WPU-OLD100",
        product_generation="S",
        content="내용",
        similarity_score=0.9
    )
    assert product_filter.is_valid_chunk(s_chunk) is False

    # 제거 대상 모델 WPU-IAC506 (배제 대상)
    excluded_chunk = RetrievedChunk(
        chunk_id="chunk_3",
        document_title="제거 대상 매뉴얼",
        manual_model="WPU-IAC506",
        product_generation="D",
        content="내용",
        similarity_score=0.9
    )
    assert product_filter.is_valid_chunk(excluded_chunk) is False


def test_vector_search_top_k_and_filtering():
    """검색 서비스가 임베딩과 Vector Store에 모델 필터를 전달하는지 검증"""
    class FakeEmbedding:
        dimension = 1024
        def embed_query(self, text):
            return [0.0] * 1024

    class FakeStore:
        def search(self, vector, *, model_code, product_generation, top_k):
            assert len(vector) == 1024
            assert model_code == "WPUJAC104DWH"
            assert product_generation == "D"
            return ChunkLoader().load_verified_chunks()[:top_k]

    search_service = VectorSearchService(FakeEmbedding(), FakeStore())
    query = RetrievalQuery(query_text="제품 밑에서 물이 새요", model_code="WPUJAC104DWH", top_k=5)

    results = search_service.search(query)

    # 1. Top-K 개수 이하인지 확인
    assert len(results) <= 5

    # 2. 결과에 S세대나 WPU-IAC506 모델이 포함되지 않았는지 확인
    for chunk in results:
        assert chunk.product_generation == "D"
        assert chunk.model_code == "WPUJAC104DWH"


def test_chunk_loader_reads_verified_common_data():
    chunks = ChunkLoader().load_verified_chunks()
    assert len(chunks) >= 7
    assert {chunk.page for chunk in chunks}.issuperset({37, 38})
    assert all(chunk.source_hash for chunk in chunks)
    assert all(chunk.verification_status == "official_verified" for chunk in chunks)
    assert all(chunk.topic_code for chunk in chunks)
    assert all(chunk.record_type == "CHILD" for chunk in chunks)
    assert all(chunk.retrieval_role == "SEARCH_CANDIDATE" for chunk in chunks)
    hot_water = next(chunk for chunk in chunks if chunk.chunk_id.endswith("HOT-WATER-SAFETY-001"))
    assert hot_water.page_refs == [38, 39]


def test_taste_or_odor_topic_filter_keeps_only_matching_evidence():
    chunks = ChunkLoader().load_verified_chunks()

    selected = EvidenceTopicFilter().filter_chunks(
        chunks,
        symptom_type="물맛/냄새 이상",
    )

    assert [chunk.topic_code for chunk in selected] == ["symptom_taste_odor"]


def test_taste_or_odor_topic_filter_uses_canonical_id_when_view_omits_topic():
    taste_chunk = next(
        chunk
        for chunk in ChunkLoader().load_verified_chunks()
        if chunk.topic_code == "symptom_taste_odor"
    ).model_copy(update={"topic_code": None})
    unrelated = RetrievedChunk(
        chunk_id="UNKNOWN-OFFICIAL-CHUNK",
        document_title="공식 문서",
        manual_model="WPUJAC104DWH",
        model_code="WPUJAC104DWH",
        product_generation="D",
        content="다른 주제의 근거",
        similarity_score=0.99,
        verification_status="official_verified",
        allowed_use=True,
    )

    selected = EvidenceTopicFilter().filter_chunks(
        [unrelated, taste_chunk],
        symptom_type="물맛/냄새 이상",
    )

    assert [chunk.chunk_id for chunk in selected] == [taste_chunk.chunk_id]


def test_taste_or_odor_applicability_requires_all_questionnaire_fields():
    gate = EvidenceApplicabilityGate()
    applicable_answer = [
        {
            "question_id": gate.QUESTION_ID,
            "answer_text": "10일 이상 부재 후",
        }
    ]

    assert gate.requires_more_information(
        symptom_type="물맛/냄새 이상",
        missing_field_names=[gate.TARGET_FIELD],
        previous_answers=applicable_answer,
    ) is True
    assert gate.requires_more_information(
        symptom_type="물맛/냄새 이상",
        missing_field_names=[],
        previous_answers=applicable_answer,
    ) is False
    assert gate.requires_more_information(
        symptom_type="물맛/냄새 이상",
        missing_field_names=[],
    ) is True


def test_other_symptom_does_not_acquire_taste_or_odor_questionnaire_gate():
    assert EvidenceApplicabilityGate().requires_more_information(
        symptom_type="출수량 저하",
        missing_field_names=["occurrence_condition"],
    ) is False


@pytest.mark.parametrize(
    ("answer_text", "expected"),
    [
        ("10일 이내 부재 후", EvidenceApplicability.ABSENCE_WITHIN_10_DAYS),
        ("10일 이상 부재 후", EvidenceApplicability.ABSENCE_OVER_10_DAYS),
        ("장시간 미사용 후", EvidenceApplicability.LONG_UNUSED),
        ("부적합 장소 설치 후", EvidenceApplicability.UNSUITABLE_INSTALLATION),
        ("해당 없음", EvidenceApplicability.NOT_APPLICABLE),
        ("확인 불가", EvidenceApplicability.UNKNOWN),
    ],
)
def test_taste_or_odor_applicability_answer_uses_fixed_codes(answer_text, expected):
    gate = EvidenceApplicabilityGate()

    assert gate.classify([
        {"question_id": gate.QUESTION_ID, "answer_text": answer_text},
    ]) == expected


def test_invalid_taste_or_odor_applicability_answer_is_reasked():
    gate = EvidenceApplicabilityGate()
    previous_answers = [
        {"question_id": gate.QUESTION_ID, "answer_text": "잘 모르겠습니다"},
    ]

    question = gate.followup_question(
        symptom_type="물맛/냄새 이상",
        previous_answers=previous_answers,
    )

    assert question is not None
    assert question.question_id == gate.QUESTION_ID
    assert "해당 없음" in question.options


def test_declined_taste_or_odor_applicability_is_not_reasked():
    gate = EvidenceApplicabilityGate()
    previous_answers = [
        {"question_id": gate.QUESTION_ID, "answer_text": "답변하지 않음"},
    ]

    assert gate.classify(previous_answers) == EvidenceApplicability.UNKNOWN
    assert gate.followup_question(
        symptom_type="물맛/냄새 이상",
        previous_answers=previous_answers,
    ) is None


def test_taste_or_odor_answer_is_not_reused_for_another_symptom():
    gate = EvidenceApplicabilityGate()
    previous_answers = [
        {"question_id": gate.QUESTION_ID, "answer_text": "10일 이내 부재 후"},
    ]

    assert gate.classify_for_symptom(
        symptom_type="출수량 저하",
        previous_answers=previous_answers,
    ) is None


def test_taste_or_odor_conditional_evidence_is_removed_when_not_applicable():
    gate = EvidenceApplicabilityGate()
    taste_chunk = next(
        chunk
        for chunk in ChunkLoader().load_verified_chunks()
        if chunk.topic_code == "symptom_taste_odor"
    )

    assert gate.filter_chunks(
        [taste_chunk],
        symptom_type="물맛/냄새 이상",
        applicability=EvidenceApplicability.NOT_APPLICABLE,
    ) == []
    assert gate.filter_chunks(
        [taste_chunk],
        symptom_type="물맛/냄새 이상",
        applicability=EvidenceApplicability.ABSENCE_WITHIN_10_DAYS,
    ) == [taste_chunk]
    for consultation_context in (
        EvidenceApplicability.ABSENCE_OVER_10_DAYS,
        EvidenceApplicability.LONG_UNUSED,
        EvidenceApplicability.UNSUITABLE_INSTALLATION,
    ):
        assert gate.filter_chunks(
            [taste_chunk],
            symptom_type="물맛/냄새 이상",
            applicability=consultation_context,
        ) == [taste_chunk]
    assert gate.filter_chunks(
        [taste_chunk],
        symptom_type="물맛/냄새 이상",
        applicability=EvidenceApplicability.UNKNOWN,
    ) == []


def test_index_manifest_save_and_load(tmp_path):
    """IndexManifest 저장 및 로딩 테스트"""
    manifest_file = tmp_path / "index_manifest.json"

    manifest = IndexManifest(
        model_name="BAAI/bge-m3",
        model_revision="a" * 40,
        dimension=1024,
        chunk_count=10,
        chunk_set_sha256="b" * 64,
        document_hashes={"manual.pdf": "hash_123"}
    )
    manifest.save_manifest(str(manifest_file))

    loaded = IndexManifest.load_manifest(str(manifest_file))
    assert loaded is not None
    assert loaded.model_name == "BAAI/bge-m3"
    assert loaded.dimension == 1024
    assert loaded.chunk_count == 10
    assert loaded.model_revision == "a" * 40
    assert loaded.chunk_set_sha256 == "b" * 64


def test_pgvector_rejects_non_1024_dimension_and_invalid_table_name():
    from ai.app.integrations.vector_store.vector_store import PgVectorStore

    store = PgVectorStore("postgresql://unused")
    try:
        store._vector_literal([0.0] * 3)
        assert False, "3차원 Vector를 거부해야 합니다."
    except ValueError as exc:
        assert "1024" in str(exc)

    try:
        PgVectorStore("postgresql://unused", table_name="ai_rag_chunks; DROP TABLE users")
        assert False, "허용되지 않은 Table 이름을 거부해야 합니다."
    except ValueError:
        pass


@pytest.mark.parametrize(
    "operation",
    [
        lambda store: store.search(
            [0.0] * 1024,
            model_code="WPUJAC104DWH",
            product_generation="D",
            top_k=5,
        ),
        lambda store: store.count(),
        lambda store: store.upsert([], []),
        lambda store: store.initialize_schema(disposable_confirm=True),
    ],
    ids=("search", "count", "upsert", "initialize_schema"),
)
def test_pgvector_operations_suppress_driver_error_and_context(
    monkeypatch,
    operation,
):
    from ai.app.integrations.vector_store.vector_store import PgVectorStore

    secret_sentinel = "SENSITIVE_RUNTIME_DSN_SENTINEL"

    def fail_connect(*args, **kwargs):
        raise psycopg.OperationalError(
            f"connection failed with protected value {secret_sentinel}"
        )

    monkeypatch.setattr(psycopg, "connect", fail_connect)
    store = PgVectorStore("postgresql://protected-runtime-value")

    with pytest.raises(ProtectedDatabaseOperationError) as captured:
        operation(store)

    assert captured.value.retryable is True
    assert secret_sentinel not in str(captured.value)
    assert captured.value.__context__ is None


def test_unverified_source_only_query_is_blocked_before_embedding():
    class FailingEmbedding:
        dimension = 1024

        def embed_query(self, text):
            raise AssertionError("차단된 질의는 임베딩하지 않아야 합니다.")

    class FailingStore:
        def search(self, *args, **kwargs):
            raise AssertionError("차단된 질의는 DB를 조회하지 않아야 합니다.")

    service = VectorSearchService(FailingEmbedding(), FailingStore())
    query = RetrievalQuery(
        query_text="모델 확인이 안 된 FAQ만 근거로 누수 조치를 확정해 주세요.",
        model_code="WPUJAC104DWH",
    )
    assert service.search(query) == []


def test_unsupported_model_is_blocked_at_real_search_entry_before_embedding():
    class FailingEmbedding:
        dimension = 1024

        def embed_query(self, text):
            raise AssertionError("미지원 모델은 임베딩하지 않아야 합니다.")

    class FailingStore:
        def search(self, *args, **kwargs):
            raise AssertionError("미지원 모델은 DB를 조회하지 않아야 합니다.")

    service = VectorSearchService(FailingEmbedding(), FailingStore())
    query = RetrievalQuery(query_text="누수 조치", model_code="WPU-IAC506")
    assert service.execution_path(query) == "POLICY_BLOCK_UNSUPPORTED_MODEL"
    assert service.search(query) == []


def test_answerability_gate_blocks_target_gold_cases():
    expected_decisions = [
        ("0051", "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE", "GATE-COMMERCIAL-001"),
        ("0052", "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE", "GATE-PART-PRICE-001"),
        ("0053", "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE", "GATE-VISIT-SCHEDULE-001"),
        ("0054", "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE", "GATE-PRODUCT-CATALOG-001"),
        ("0056", "POLICY_BLOCK_UNSUPPORTED_CAPABILITY", "GATE-JAC104-ICE-001"),
        ("0057", "POLICY_BLOCK_UNSUPPORTED_CAPABILITY", "GATE-JAC104-ICE-001"),
        ("0058", "POLICY_BLOCK_UNSUPPORTED_CAPABILITY", "GATE-JAC104-ICE-001"),
        ("0059", "POLICY_BLOCK_UNSUPPORTED_MODEL", "GATE-MODEL-001"),
    ]
    cases = {
        row["case_id"]: row
        for row in (
            json.loads(line)
            for line in Path("ai/evaluation/datasets/gold/rag_gold_v2.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    }
    gate = AnswerabilityCapabilityGate()
    for case_suffix, expected_path, expected_rule_id in expected_decisions:
        case = cases[f"RAGV2-GOLD-{case_suffix}"]
        query = RetrievalQuery(
            query_text=case["query"],
            model_code=case["product_model_code"],
        )
        decision = gate.evaluate(
            query_text=query.query_text,
            model_code=query.model_code,
            product_generation=query.product_generation,
        )

        assert decision.blocked is True
        assert decision.execution_path == expected_path
        assert decision.rule_id == expected_rule_id


def test_answerability_gate_keeps_manual_questions_searchable():
    cases = {
        row["case_id"]: row
        for row in (
            json.loads(line)
            for line in Path("ai/evaluation/datasets/gold/rag_gold_v2.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        )
    }
    gate = AnswerabilityCapabilityGate()
    for case_suffix in ["0001", "0013", "0023", "0031"]:
        case = cases[f"RAGV2-GOLD-{case_suffix}"]
        decision = gate.evaluate(
            query_text=case["query"],
            model_code=case["product_model_code"],
            product_generation="D",
        )

        assert decision.blocked is False
        assert decision.execution_path == "PGVECTOR_QUERY"


def test_answerability_gate_blocks_before_embedding_and_vector_query():
    class FailingEmbedding:
        dimension = 1024

        def embed_query(self, text):
            raise AssertionError("Gate 차단 질의는 임베딩하지 않아야 합니다.")

    class FailingStore:
        def search(self, *args, **kwargs):
            raise AssertionError("Gate 차단 질의는 DB를 조회하지 않아야 합니다.")

    service = VectorSearchService(FailingEmbedding(), FailingStore())
    query = RetrievalQuery(
        query_text="교체용 필터의 현재 판매 가격이 얼마인가요?",
        model_code="WPUJAC104DWH",
    )

    assert service.execution_path(query) == "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE"
    assert service.search(query) == []


def test_gold_v2_policy_cases_match_real_runtime_entry_path():
    cases = [
        json.loads(line)
        for line in Path("ai/evaluation/datasets/gold/rag_gold_v2.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if json.loads(line)["expected_execution_path"].startswith("POLICY_BLOCK_")
    ]
    service = VectorSearchService(object(), object())

    assert len(cases) == 10
    for case in cases:
        query = RetrievalQuery(
            query_text=case["query"],
            model_code=case["product_model_code"],
        )
        assert service.execution_path(query) == case["expected_execution_path"], (
            case["case_id"],
            service.execution_path(query),
            case["expected_execution_path"],
        )


def test_visit_schedule_gate_blocks_before_embedding_and_vector_query():
    class FailingEmbedding:
        dimension = 1024

        def embed_query(self, text):
            raise AssertionError("실시간 방문 일정 질의는 임베딩하지 않아야 합니다.")

    class FailingStore:
        def search(self, *args, **kwargs):
            raise AssertionError("실시간 방문 일정 질의는 DB를 조회하지 않아야 합니다.")

    service = VectorSearchService(FailingEmbedding(), FailingStore())
    query = RetrievalQuery(
        query_text="오늘 방문 예정인 기사님이 몇 시쯤 도착하나요?",
        model_code="WPUJAC104DWH",
    )

    assert service.execution_path(query) == "POLICY_BLOCK_OUT_OF_MANUAL_SCOPE"
    assert service.search(query) == []


def test_low_flow_query_expansion_changes_only_embedding_input():
    embedded_queries: list[str] = []

    class CapturingEmbedding:
        dimension = 1024

        def embed_query(self, text):
            embedded_queries.append(text)
            return [0.0] * 1024

    class EmptyStore:
        def search(self, *args, **kwargs):
            return []

    service = VectorSearchService(CapturingEmbedding(), EmptyStore())
    query = RetrievalQuery(
        query_text="정수기 물이 갑자기 졸졸 나와요. 어디를 확인해야 하나요?",
        model_code="WPUJAC104DWH",
    )
    decision = service.expand_query(query)

    assert query.query_text == decision.original_query
    assert decision.applied_rule_ids == ("QUERY-LOW-FLOW-001",)
    assert decision.appended_terms == ("출수량이 적을 경우", "출수 속도가 느림")
    assert service.search(query) == []
    assert embedded_queries == [decision.expanded_query]
    assert embedded_queries[0].endswith("출수량이 적을 경우 출수 속도가 느림")


@pytest.mark.parametrize(
    "query_text",
    (
        "정수기에서 물이 한 방울도 안 나와요.",
        "정수기 물이 아예 안 나옵니다.",
        "정수기에서 물이 전혀 안 나와요.",
        "필터를 바꿨는데도 물이 나오지 않아요.",
    ),
)
def test_low_flow_query_expansion_does_not_capture_no_water(query_text):
    service = VectorSearchService(object(), object())
    decision = service.expand_query(
        RetrievalQuery(query_text=query_text, model_code="WPUJAC104DWH")
    )

    assert decision.applied is False
    assert decision.expanded_query == query_text


def test_search_candidate_filter_rejects_context_and_preservation_records():
    base = RetrievedChunk(
        chunk_id="CHILD-001",
        document_title="공식 매뉴얼",
        manual_model="WPUJAC104DWH",
        model_code="WPUJAC104DWH",
        product_generation="D",
        content="공식 근거",
        similarity_score=0.9,
        verification_status="official_verified",
        allowed_use=True,
    )
    candidate = base.model_copy(
        update={"record_type": "CHILD", "retrieval_role": "SEARCH_CANDIDATE"}
    )
    source_page = base.model_copy(
        update={
            "chunk_id": "SOURCE-001",
            "record_type": "SOURCE_PAGE",
            "retrieval_role": "SEARCH_CANDIDATE",
        }
    )
    preservation = base.model_copy(
        update={
            "chunk_id": "PRESERVE-001",
            "record_type": "PRESERVATION",
            "retrieval_role": "SEARCH_CANDIDATE",
        }
    )
    context = base.model_copy(
        update={
            "chunk_id": "PARENT-001",
            "record_type": "PARENT",
            "retrieval_role": "CONTEXT_ONLY",
        }
    )

    assert SearchCandidateFilter.is_valid_chunk(candidate) is True
    assert SearchCandidateFilter.is_valid_chunk(base) is True
    assert SearchCandidateFilter.is_valid_chunk(source_page) is False
    assert SearchCandidateFilter.is_valid_chunk(preservation) is False
    assert SearchCandidateFilter.is_valid_chunk(context) is False


def test_pgvector_filters_typed_non_child_rows_before_scoring(monkeypatch):
    from ai.app.integrations.vector_store.vector_store import PgVectorStore

    executed_sql: list[str] = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, sql, params=None):
            executed_sql.append(sql)

        def fetchall(self):
            return []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: FakeConnection())
    store = PgVectorStore("postgresql://unused")

    assert store.search(
        [0.0] * 1024,
        model_code="WPUJAC104DWH",
        product_generation="D",
        top_k=5,
    ) == []
    search_sql = next(sql for sql in executed_sql if "SELECT chunk_id" in sql)
    assert "LOWER(metadata->>'record_type') = 'child'" in search_sql
    assert "metadata->>'retrieval_role' = 'SEARCH_CANDIDATE'" in search_sql


def test_schema_initialization_requires_explicit_disposable_confirmation():
    from ai.app.integrations.vector_store.vector_store import PgVectorStore

    store = PgVectorStore("postgresql://unused")
    try:
        store.initialize_schema()
        assert False, "공유 DB에서 기본 DDL 실행을 거부해야 합니다."
    except RuntimeError as exc:
        assert "Disposable" in str(exc)


def test_index_builder_never_initializes_schema():
    source = Path("ai/scripts/build_vector_index.py").read_text(encoding="utf-8")
    assert ".initialize_schema(" not in source
    assert "schema_ddl_executed" in source


def test_timeout_during_embedding_prevents_following_db_query():
    token = CancellationToken()

    class CancellingEmbedding:
        dimension = 1024

        def embed_query(self, text):
            token.cancel()
            return [0.0] * 1024

    class FailingStore:
        def search(self, *args, **kwargs):
            raise AssertionError("취소된 임베딩 뒤에는 DB Query를 실행하지 않아야 합니다.")

    service = VectorSearchService(CancellingEmbedding(), FailingStore())
    query = RetrievalQuery(query_text="누수 조치", model_code="WPUJAC104DWH")
    try:
        service.search(query, cancellation_token=token)
        assert False, "취소 신호를 예외로 전달해야 합니다."
    except PipelineCancelledError:
        pass


def test_store_results_are_revalidated_after_search():
    class FakeEmbedding:
        dimension = 1024

        def embed_query(self, text):
            return [0.0] * 1024

    class UnsafeStore:
        def search(self, *args, **kwargs):
            return [RetrievedChunk(
                chunk_id="unsafe",
                document_title="미검증 문서",
                manual_model="WRONG",
                model_code="WRONG",
                product_generation="S",
                content="사용하면 안 되는 근거",
                similarity_score=1.0,
                verification_status="unverified",
                allowed_use=False,
            )]

    service = VectorSearchService(FakeEmbedding(), UnsafeStore())
    results = service.search(RetrievalQuery(
        query_text="출수가 안 됩니다",
        model_code="WPUJAC104DWH",
    ))
    assert results == []


def test_manifest_revision_mismatch_is_rejected_before_search():
    class FakeEmbedding:
        model_name = "BAAI/bge-m3"
        model_revision = "b" * 40
        dimension = 1024

    manifest = IndexManifest(
        model_revision="a" * 40,
        chunk_set_sha256="c" * 64,
    )
    try:
        VectorSearchService(FakeEmbedding(), object(), index_manifest=manifest)
        assert False, "Embedding Revision 불일치를 거부해야 합니다."
    except RuntimeError as exc:
        assert "Revision" in str(exc)


def test_manifest_sha256_comparison_accepts_backend_lowercase_view_values():
    class FakeEmbedding:
        model_name = "BAAI/bge-m3"
        model_revision = "a" * 40
        dimension = 1024

    manifest = IndexManifest(
        model_name="BAAI/bge-m3",
        model_revision="a" * 40,
        chunk_set_sha256="B" * 64,
        document_hashes={"DOC-001": "C" * 64},
    )
    chunk = RetrievedChunk(
        chunk_id="RAG-WPUJAC104DWH-TEST-001",
        document_id="DOC-001",
        document_title="공식 문서",
        manual_model="WPUJAC104DWH",
        model_code="WPUJAC104DWH",
        product_generation="D",
        content="공식 근거",
        similarity_score=0.9,
        verification_status="official_verified",
        allowed_use=True,
        source_hash="c" * 64,
        embedding_model="BAAI/bge-m3",
        embedding_model_revision="a" * 40,
        index_version=manifest.index_version,
        chunk_set_sha256="b" * 64,
    )
    service = VectorSearchService(
        FakeEmbedding(),
        object(),
        index_manifest=manifest,
    )

    assert service._is_valid_result(chunk, "WPUJAC104DWH") is True


def test_invalid_or_missing_manifest_hashes_fail_closed():
    class FakeEmbedding:
        model_name = "BAAI/bge-m3"
        model_revision = "a" * 40
        dimension = 1024

    manifest = IndexManifest(
        model_name="BAAI/bge-m3",
        model_revision="a" * 40,
        chunk_set_sha256="Z" * 64,
        document_hashes={"DOC-001": "Y" * 64},
    )
    chunk = RetrievedChunk(
        chunk_id="RAG-WPUJAC104DWH-TEST-INVALID",
        document_id="DOC-001",
        document_title="공식 문서",
        manual_model="WPUJAC104DWH",
        model_code="WPUJAC104DWH",
        product_generation="D",
        content="공식 근거",
        similarity_score=0.9,
        verification_status="official_verified",
        allowed_use=True,
        embedding_model="BAAI/bge-m3",
        embedding_model_revision="a" * 40,
        index_version=manifest.index_version,
    )
    service = VectorSearchService(
        FakeEmbedding(),
        object(),
        index_manifest=manifest,
    )

    assert service._is_valid_result(chunk, "WPUJAC104DWH") is False
