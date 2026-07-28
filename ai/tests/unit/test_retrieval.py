"""RAG Retrieval 및 메타데이터 필터 단위 테스트."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import pytest
from ai.app.retrieval.filters.document_policy_filter import DocumentPolicyFilter
from ai.app.retrieval.filters.product_filter import ProductFilter
from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
from ai.app.retrieval.indexing.index_manifest import IndexManifest
from ai.app.retrieval.models.retrieval_query import RetrievalQuery
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk
from ai.app.retrieval.search.vector_search import VectorSearchService


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
    """VectorSearchService Top-5 반환 및 필터링 적용 테스트"""
    search_service = VectorSearchService()
    query = RetrievalQuery(query_text="제품 밑에서 물이 새요", model_code="WPUJAC104DWH", top_k=5)

    results = search_service.search(query)

    # 1. Top-K 개수 이하인지 확인
    assert len(results) <= 5

    # 2. 결과에 S세대나 WPU-IAC506 모델이 포함되지 않았는지 확인
    for chunk in results:
        assert chunk.product_generation == "D"
        assert chunk.manual_model != "WPU-IAC506"
        assert chunk.manual_model != "WPUIAC425SNW"


def test_index_manifest_save_and_load(tmp_path):
    """IndexManifest 저장 및 로딩 테스트"""
    manifest_file = tmp_path / "index_manifest.json"

    manifest = IndexManifest(
        model_name="BAAI/bge-m3",
        dimension=1024,
        chunk_count=10,
        document_hashes={"manual.pdf": "hash_123"}
    )
    manifest.save_manifest(str(manifest_file))

    loaded = IndexManifest.load_manifest(str(manifest_file))
    assert loaded is not None
    assert loaded.model_name == "BAAI/bge-m3"
    assert loaded.dimension == 1024
    assert loaded.chunk_count == 10
