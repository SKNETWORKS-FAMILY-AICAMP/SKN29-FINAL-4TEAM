"""RAG Retrieval 및 메타데이터 필터 단위 테스트."""

from pathlib import Path
from ai.app.retrieval.filters.document_policy_filter import DocumentPolicyFilter
from ai.app.retrieval.filters.product_filter import ProductFilter
from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.app.retrieval.indexing.index_manifest import IndexManifest
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.retrieval.search.vector_search import VectorSearchService
from ai.app.common.timeout import CancellationToken, PipelineCancelledError


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
    hot_water = next(chunk for chunk in chunks if chunk.chunk_id.endswith("HOT-WATER-SAFETY-001"))
    assert hot_water.page_refs == [38, 39]


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
