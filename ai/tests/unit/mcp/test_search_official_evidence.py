from types import SimpleNamespace

import ai.app.retrieval.filters.evidence_topic_filter as topic_filter_module

from ai.app.integrations.mcp.tools.search_official_evidence import (
    SearchOfficialEvidenceAdapter,
    SearchOfficialEvidenceInput,
)
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk

# 실제 VectorSearchService를 사용해서
# "다른 제품의 Evidence가 정말 제거되는지" 검증합니다.
from ai.app.retrieval.search.vector_search import VectorSearchService


class FakeSearchService:
    """실제 Embedding/pgvector 없이 Adapter 경계만 검증하는 Fake."""

    def __init__(
        self,
        decision,
        *,
        execution_path="PGVECTOR_QUERY",
        chunks=None,
    ) -> None:
        self.decision = decision
        self._execution_path = execution_path
        self._chunks = list(chunks or [])

        self.search_called = 0
        self.last_query = None

    def evaluate_pre_search_gate(self, query):
        self.last_query = query
        return self.decision

    def execution_path(self, query):
        self.last_query = query
        return self._execution_path

    def search(self, query):
        self.last_query = query
        self.search_called += 1
        return list(self._chunks)

class FakeEmbeddingProvider:
    # 실제 Embedding 모델을 실행하지 않고
    # 테스트용 1024차원 Vector를 반환합니다.
    #
    # 이번 테스트의 목적은 검색 품질이 아니라
    # "제품 필터가 잘 작동하는가?"이기 때문에
    # 실제 Embedding 모델을 사용할 필요가 없습니다.

    dimension = 1024

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        return [0.0] * self.dimension

    def embed_documents(
        self,
        texts,
    ) -> list[list[float]]:
        return [
            [0.0] * self.dimension
            for _ in texts
        ]


class FakeVectorStore:
    # 실제 PostgreSQL / pgvector 대신 사용하는
    # 테스트용 가짜 Vector Store입니다.
    #
    # 일부러 "정상 모델 + 잘못된 모델"을 함께 반환해서
    # VectorSearchService가 잘못된 모델을 제거하는지 확인합니다.

    def __init__(
        self,
        chunks,
    ) -> None:
        self.chunks = list(chunks)
        self.search_called = 0

        self.last_model_code = None
        self.last_product_generation = None

    def search(
        self,
        vector,
        *,
        model_code: str,
        product_generation: str,
        top_k: int,
    ):
        self.search_called += 1

        self.last_model_code = model_code
        self.last_product_generation = product_generation

        # 여기서는 일부러 필터링하지 않고
        # 준비한 Chunk를 전부 반환합니다.
        #
        # 즉 Vector Store가 잘못된 데이터를 줬다고 가정합니다.
        return list(self.chunks)

def _allowed_decision():
    """검색 허용 정책 Decision."""
    return SimpleNamespace(
        blocked=False,
        execution_path="PGVECTOR_QUERY",
        rule_id=None,
        reason=None,
    )

def _sample_chunk(
    *,
    chunk_id="chunk-001",
    topic_code="symptom_taste_odor",

    # 기존 테스트가 사용하던 기본 문서명을 그대로 유지합니다.
    document_title="JAC104 사용설명서",

    # 테스트마다 제품 정보를 바꿀 수 있도록
    # 제품 관련 값을 매개변수로 분리합니다.
    manual_model="JAC104",
    model_code="WPUJAC104DWH",
    product_generation="D",
):
    """Evidence 변환 테스트용 공식 검색 Chunk."""

    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="manual-jac104",

        # 테스트에서 전달받은 문서 제목 사용
        document_title=document_title,

        document_version="1.0",
        page=10,
        page_refs=[10],

        manual_model=manual_model,
        model_code=model_code,
        product_generation=product_generation,

        content="장기간 사용하지 않은 경우 충분히 출수한 뒤 사용하세요.",
        similarity_score=0.92,
        official_url="https://example.com/manual",
        verification_status="official_verified",
        allowed_use=True,
        topic_code=topic_code,
        runtime_eligible=True,
    )

def test_policy_block_returns_block_metadata():
    """HOLD 모델은 정책 차단 정보를 반환하고 Vector Search는 실행하지 않는다."""

    decision = SimpleNamespace(
        blocked=True,
        execution_path="POLICY_BLOCK_UNSUPPORTED_MODEL",
        rule_id="GATE-MODEL-001",
        reason="지원 대상이 아닌 제품 모델",
    )

    service = FakeSearchService(decision)
    adapter = SearchOfficialEvidenceAdapter(service)

    result = adapter.execute(
        SearchOfficialEvidenceInput(
            customer_query="물이 이상해요",
            model_code="WPUIAC425SNW",
            symptom_type="물맛/냄새 이상",
            previous_answers=[],
        )
    )

    assert result.policy_blocked is True
    assert result.vector_search_executed is False
    assert result.search_result_found is False
    assert result.evidence_found is False

    assert (
        result.policy_execution_path
        == "POLICY_BLOCK_UNSUPPORTED_MODEL"
    )
    assert result.applied_rule_id == "GATE-MODEL-001"
    assert result.block_reason == "지원 대상이 아닌 제품 모델"

    # Adapter는 반드시 VectorSearchService.search() 공개 인터페이스를 호출한다.
    # 실제 VectorSearchService 내부에서는 Gate 차단 후 pgvector 이전에 종료된다.
    assert service.search_called == 1

    # Product Registry의 판매코드별 Generation 적용 확인
    assert service.last_query.model_code == "WPUIAC425SNW"
    assert service.last_query.product_generation == "IAC425"


def test_unverified_source_policy_block_does_not_execute_vector_search():
    """비공식 근거 단독 요청은 정책 차단 응답으로 구분한다."""

    service = FakeSearchService(
        _allowed_decision(),
        execution_path="POLICY_BLOCK_UNVERIFIED_SOURCE",
    )

    adapter = SearchOfficialEvidenceAdapter(service)

    result = adapter.execute(
        SearchOfficialEvidenceInput(
            customer_query="비공식 문서만 근거로 알려줘",
            model_code="WPUJAC104DWH",
            symptom_type=None,
            previous_answers=[],
        )
    )

    assert result.policy_blocked is True
    assert result.vector_search_executed is False
    assert result.search_result_found is False
    assert result.evidence_found is False

    assert (
        result.policy_execution_path
        == "POLICY_BLOCK_UNVERIFIED_SOURCE"
    )

    assert result.applied_rule_id is None

    # VectorSearchService.search() 자체는 호출하지만
    # 실제 pgvector 검색 경로는 실행되지 않는다는 계약이다.
    assert service.search_called == 1


def test_pgvector_search_runs_but_returns_no_match():
    """검색 경로는 실행됐지만 검색 결과가 0건인 경우를 구분한다."""

    service = FakeSearchService(
        _allowed_decision(),
        chunks=[],
    )

    adapter = SearchOfficialEvidenceAdapter(service)

    result = adapter.execute(
        SearchOfficialEvidenceInput(
            customer_query="정수기에서 이상한 소리가 나요",
            model_code="WPUJAC104DWH",
            symptom_type=None,
            previous_answers=[],
        )
    )

    assert result.policy_blocked is False

    assert result.vector_search_executed is True
    assert result.search_result_found is False
    assert result.evidence_found is False

    assert result.policy_execution_path == "PGVECTOR_QUERY"

    assert service.search_called == 1

    # MCP Input -> RetrievalQuery 변환 검증
    assert service.last_query.model_code == "WPUJAC104DWH"
    assert service.last_query.product_generation == "D"
    assert service.last_query.top_k == 5
    assert service.last_query.require_official_verified is True


def test_search_result_can_be_removed_by_topic_filter(monkeypatch):
    """검색 결과가 있어도 구조화 증상과 주제가 다르면 제거한다."""

    monkeypatch.setattr(
        topic_filter_module,
        "_canonical_topic_by_chunk_id",
        lambda: {},
    )

    service = FakeSearchService(
        _allowed_decision(),
        chunks=[
            _sample_chunk(
                topic_code="different_topic",
            )
        ],
    )

    adapter = SearchOfficialEvidenceAdapter(service)

    result = adapter.execute(
        SearchOfficialEvidenceInput(
            customer_query="물에서 냄새가 나요",
            model_code="WPUJAC104DWH",
            symptom_type="물맛/냄새 이상",
            previous_answers=[
                {
                    "question_id": (
                        "followup-taste-odor-applicability"
                    ),
                    "answer_text": "10일 이내 부재 후",
                }
            ],
        )
    )

    # Vector 검색 결과 자체는 존재
    assert result.vector_search_executed is True
    assert result.search_result_found is True

    # Topic Filter 이후 최종 Evidence 없음
    assert result.evidence_found is False
    assert result.evidence_references == []

    assert service.search_called == 1


def test_search_result_can_be_removed_by_applicability_gate(
    monkeypatch,
):
    """검색/Topic 결과가 있어도 문진 조건 불충족이면 Evidence를 제거한다."""

    monkeypatch.setattr(
        topic_filter_module,
        "_canonical_topic_by_chunk_id",
        lambda: {},
    )

    service = FakeSearchService(
        _allowed_decision(),
        chunks=[_sample_chunk()],
    )

    adapter = SearchOfficialEvidenceAdapter(service)

    result = adapter.execute(
        SearchOfficialEvidenceInput(
            customer_query="물에서 냄새가 나요",
            model_code="WPUJAC104DWH",
            symptom_type="물맛/냄새 이상",
            previous_answers=[],
        )
    )

    assert result.vector_search_executed is True
    assert result.search_result_found is True

    # Applicability 조건 미확정이므로 최종 Evidence 사용 불가
    assert result.evidence_found is False
    assert result.evidence_references == []

    assert service.search_called == 1


def test_search_success_returns_evidence_reference(monkeypatch):
    """검색과 모든 Evidence Gate를 통과하면 공식 근거를 반환한다."""

    monkeypatch.setattr(
        topic_filter_module,
        "_canonical_topic_by_chunk_id",
        lambda: {},
    )

    service = FakeSearchService(
        _allowed_decision(),
        chunks=[_sample_chunk()],
    )

    adapter = SearchOfficialEvidenceAdapter(service)

    result = adapter.execute(
        SearchOfficialEvidenceInput(
            customer_query=(
                "10일 이내 집을 비웠다가 왔는데 "
                "물에서 냄새가 나요"
            ),
            model_code="WPUJAC104DWH",
            symptom_type="물맛/냄새 이상",
            previous_answers=[
                {
                    "question_id": (
                        "followup-taste-odor-applicability"
                    ),
                    "answer_text": "10일 이내 부재 후",
                }
            ],
        )
    )

    assert result.policy_blocked is False

    assert result.vector_search_executed is True
    assert result.search_result_found is True
    assert result.evidence_found is True

    assert len(result.evidence_references) == 1

    evidence = result.evidence_references[0]

    assert evidence.chunk_id == "chunk-001"
    assert evidence.document_title == "JAC104 사용설명서"
    assert evidence.page == 10
    assert evidence.page_refs == [10]
    assert evidence.similarity_score == 0.92
    assert evidence.verification_status.value == "official_verified"

    assert service.search_called == 1

def test_wrong_model_evidence_is_removed_before_mcp_output(
    monkeypatch,
):
    # ---------------------------------------------------------------
    # 테스트 목적
    # ---------------------------------------------------------------
    #
    # 고객 제품:
    # WPUJAC104DWH
    #
    # Vector Store가 실수로:
    #
    # 1. JAC104 공식 근거
    # 2. IAC425 공식 근거
    #
    # 를 동시에 반환했다고 가정합니다.
    #
    # 최종 MCP 결과에는 JAC104 Evidence만 있어야 합니다.


    # 테스트 중 실제 Canonical Chunk 파일을 읽지 않도록 막습니다.
    monkeypatch.setattr(
        topic_filter_module,
        "_canonical_topic_by_chunk_id",
        lambda: {},
    )


    # ---------------------------------------------------------------
    # Vector Store가 반환할 가짜 검색 결과
    # ---------------------------------------------------------------

    correct_chunk = _sample_chunk(
        chunk_id="chunk-jac104",
        document_title="JAC104 사용설명서",
        manual_model="JAC104",
        model_code="WPUJAC104DWH",
        product_generation="D",
    )

    wrong_model_chunk = _sample_chunk(
        chunk_id="chunk-iac425",
        document_title="IAC425 사용설명서",
        manual_model="IAC425",
        model_code="WPUIAC425SNW",
        product_generation="IAC425",
    )


    # 일부러 두 제품의 Chunk를 모두 반환하게 합니다.
    vector_store = FakeVectorStore(
        [
            correct_chunk,
            wrong_model_chunk,
        ]
    )


    # 이번에는 기존 테스트의 FakeSearchService가 아니라
    # 실제 프로젝트 VectorSearchService를 사용합니다.
    #
    # 이게 중요한 이유:
    #
    # 실제 VectorSearchService 안에 있는 ProductFilter까지
    # 테스트하기 위해서입니다.
    search_service = VectorSearchService(
        FakeEmbeddingProvider(),
        vector_store,
    )


    # MCP Adapter는 기존 VectorSearchService를 그대로 사용합니다.
    adapter = SearchOfficialEvidenceAdapter(
        search_service
    )


    # JAC104 고객 문의로 검색합니다.
    result = adapter.execute(
        SearchOfficialEvidenceInput(
            customer_query=(
                "10일 이내 집을 비웠다가 왔는데 "
                "물에서 냄새가 나요"
            ),
            model_code="WPUJAC104DWH",
            symptom_type="물맛/냄새 이상",
            previous_answers=[
                {
                    "question_id": (
                        "followup-taste-odor-applicability"
                    ),
                    "answer_text": "10일 이내 부재 후",
                }
            ],
        )
    )


    # ---------------------------------------------------------------
    # 1. Vector Store 자체는 실제로 한 번 호출되어야 합니다.
    # ---------------------------------------------------------------

    assert vector_store.search_called == 1


    # ---------------------------------------------------------------
    # 2. Vector Store에는 JAC104 조건으로 검색 요청이 전달되어야 합니다.
    # ---------------------------------------------------------------

    assert (
        vector_store.last_model_code
        == "WPUJAC104DWH"
    )

    assert (
        vector_store.last_product_generation
        == "D"
    )


    # ---------------------------------------------------------------
    # 3. 최종 사용할 Evidence는 존재해야 합니다.
    # ---------------------------------------------------------------

    assert result.evidence_found is True


    # ---------------------------------------------------------------
    # 4. 하지만 MCP Output에는 JAC104만 남아야 합니다.
    # ---------------------------------------------------------------

    returned_chunk_ids = [
        evidence.chunk_id
        for evidence in result.evidence_references
    ]

    assert returned_chunk_ids == [
        "chunk-jac104"
    ]


    # ---------------------------------------------------------------
    # 5. 다른 제품인 IAC425 Evidence는 절대로 나오면 안 됩니다.
    # ---------------------------------------------------------------

    assert (
        "chunk-iac425"
        not in returned_chunk_ids
    )