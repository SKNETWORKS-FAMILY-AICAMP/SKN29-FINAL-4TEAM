"""Retrieval 품질 Gate의 지표 분리와 리포트 비노출 테스트."""

import json

import pytest
from pydantic import ValidationError

from ai.app.retrieval import RetrievedChunk
from ai.evaluation.runners.retrieval_runner import RetrievalEvaluationRunner


def _dataset_payload() -> dict:
    return {
        "config_version": "1.0.0",
        "status": "TEST_ONLY",
        "approved_chunk_count": 1,
        "evaluation_policy": {
            "default_top_k": 5,
            "positive_min_expected_hits": 1,
            "negative_max_forbidden_hits": 0,
            "required_result_metadata": [],
        },
        "cases": [
            {
                "case_id": "RET-POS-001",
                "case_type": "POSITIVE",
                "scenario_id": "SYN-001",
                "query": "양성 고객 검색 원문",
                "product_model_code": "MODEL-A",
                "expected_chunk_ids": ["RAG-EXPECTED-001"],
                "expected_document_id": "DOC-A",
                "expected_page_numbers": [1],
                "forbidden_model_codes": ["MODEL-B"],
                "forbidden_document_ids": ["DOC-B"],
                "top_k": 5,
                "expected_no_evidence": False,
            },
            {
                "case_id": "RET-NEG-001",
                "case_type": "NEGATIVE_SCOPE",
                "scenario_id": None,
                "query": "음성 고객 검색 원문",
                "product_model_code": "MODEL-B",
                "expected_chunk_ids": [],
                "expected_document_id": None,
                "expected_page_numbers": [],
                "forbidden_model_codes": ["MODEL-A"],
                "forbidden_document_ids": ["DOC-A"],
                "top_k": 5,
                "expected_no_evidence": True,
            },
        ],
        "ai_execution": {"approval_scope": "TEST_ONLY"},
    }


def _write_dataset(tmp_path):
    path = tmp_path / "retrieval_cases.json"
    path.write_text(
        json.dumps(_dataset_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _chunk(
    *,
    chunk_id: str = "RAG-EXPECTED-001",
    model_code: str = "MODEL-A",
    document_id: str = "DOC-A",
    page: int | None = 1,
    page_refs: list[int] | None = None,
    embedding_model: str | None = None,
    embedding_model_revision: str | None = None,
    index_version: str | None = None,
    chunk_set_sha256: str | None = None,
    content: str = "민감한 Evidence 원문",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        document_title="테스트 문서",
        manual_model=model_code,
        model_code=model_code,
        page=page,
        page_refs=page_refs or [],
        content=content,
        similarity_score=0.9,
        verification_status="official_verified",
        allowed_use=True,
        embedding_model=embedding_model,
        embedding_model_revision=embedding_model_revision,
        index_version=index_version,
        chunk_set_sha256=chunk_set_sha256,
    )


class _FakeSearchService:
    def __init__(self, outputs):
        self.outputs = outputs
        self.call_count = 0

    def execution_path(self, query):
        return (
            "PGVECTOR_QUERY"
            if query.model_code == "MODEL-A"
            else "POLICY_BLOCK_PRODUCT"
        )

    def search(self, query, *, cancellation_token=None):
        self.call_count += 1
        output = self.outputs[query.query_text]
        if isinstance(output, Exception):
            raise output
        return output


def test_retrieval_runner_reports_not_run_without_search_service():
    report = RetrievalEvaluationRunner().run()

    assert report["status"] == "NOT_RUN"
    assert report["summary"]["case_count"] == 13
    assert report["summary"]["positive_case_count"] == 8
    assert report["summary"]["negative_case_count"] == 5
    assert report["summary"]["search_call_count"] == 0
    assert report["mean_recall_at_5"] is None
    assert report["mean_mrr"] is None
    assert report["search_service_called"] is False


def test_retrieval_runner_separates_metrics_and_excludes_sensitive_text(tmp_path):
    dataset_path = _write_dataset(tmp_path)
    service = _FakeSearchService(
        {
            "양성 고객 검색 원문": [_chunk()],
            "음성 고객 검색 원문": [],
        }
    )

    report = RetrievalEvaluationRunner(service, dataset_path).run()
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "PASS"
    assert report["summary"]["passed_count"] == 2
    assert report["summary"]["mean_recall_at_5"] == 1.0
    assert report["summary"]["mean_mrr"] == 1.0
    assert report["summary"]["negative_no_evidence_rate"] == 1.0
    assert report["summary"]["wrong_model_evidence_rate"] == 0.0
    assert report["summary"]["product_contamination_rate"] == 0.0
    assert report["summary"]["latency"]["sample_count"] == 2
    assert report["summary"]["execution_path_counts"] == {
        "PGVECTOR_QUERY": 1,
        "POLICY_BLOCK_PRODUCT": 1,
    }
    assert service.call_count == 2
    assert "양성 고객 검색 원문" not in serialized
    assert "음성 고객 검색 원문" not in serialized
    assert "민감한 Evidence 원문" not in serialized
    assert "RAG-EXPECTED-001" not in serialized
    assert report["query_text_printed"] is False
    assert report["evidence_content_printed"] is False
    assert report["vector_values_printed"] is False
    assert report["secret_values_printed"] is False


def test_retrieval_runner_fails_wrong_model_and_negative_evidence(tmp_path):
    dataset_path = _write_dataset(tmp_path)
    contaminated = _chunk(model_code="MODEL-B", document_id="DOC-B")
    forbidden = _chunk(chunk_id="RAG-FORBIDDEN-001")
    service = _FakeSearchService(
        {
            "양성 고객 검색 원문": [contaminated],
            "음성 고객 검색 원문": [forbidden],
        }
    )

    report = RetrievalEvaluationRunner(service, dataset_path).run()

    assert report["status"] == "FAIL"
    assert report["summary"]["passed_count"] == 0
    assert report["summary"]["failed_count"] == 2
    assert report["summary"]["wrong_model_hit_count"] == 2
    assert report["summary"]["wrong_model_evidence_rate"] == 1.0
    assert report["summary"]["product_contamination_hit_count"] == 2
    assert report["summary"]["product_contamination_rate"] == 1.0
    assert report["summary"]["negative_no_evidence_rate"] == 0.0


def test_retrieval_runner_redacts_search_exception_message(tmp_path):
    dataset_path = _write_dataset(tmp_path)
    service = _FakeSearchService(
        {
            "양성 고객 검색 원문": RuntimeError("dsn=secret-value"),
            "음성 고객 검색 원문": [],
        }
    )

    report = RetrievalEvaluationRunner(service, dataset_path).run()
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "FAIL"
    assert report["summary"]["search_error_count"] == 1
    assert report["cases"][0]["error_type"] == "RuntimeError"
    assert "secret-value" not in serialized


def test_retrieval_runner_fails_expected_page_mismatch_without_exposing_pages(
    tmp_path,
):
    dataset_path = _write_dataset(tmp_path)
    service = _FakeSearchService(
        {
            "양성 고객 검색 원문": [_chunk(page=2)],
            "음성 고객 검색 원문": [],
        }
    )

    report = RetrievalEvaluationRunner(service, dataset_path).run()
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "FAIL"
    assert report["summary"]["expected_page_mismatch_count"] == 1
    assert report["cases"][0]["expected_page_mismatch_count"] == 1
    assert "expected_page_numbers" not in serialized
    assert "page_refs" not in serialized


def test_retrieval_runner_requires_configured_lineage_metadata(tmp_path):
    payload = _dataset_payload()
    payload["evaluation_policy"]["required_result_metadata"] = [
        "embedding_model",
        "embedding_model_version",
        "chunk_set_sha256",
        "index_version",
        "filter",
        "ranked_chunk_ids",
        "recall_at_k",
        "mrr",
    ]
    dataset_path = tmp_path / "retrieval_cases.json"
    dataset_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    service = _FakeSearchService(
        {
            "양성 고객 검색 원문": [_chunk()],
            "음성 고객 검색 원문": [],
        }
    )

    report = RetrievalEvaluationRunner(service, dataset_path).run()

    assert report["status"] == "FAIL"
    assert report["summary"]["missing_required_metadata_count"] == 4
    assert report["cases"][0]["missing_required_metadata_count"] == 4


def test_retrieval_runner_accepts_complete_lineage_metadata(tmp_path):
    payload = _dataset_payload()
    payload["evaluation_policy"]["required_result_metadata"] = [
        "embedding_model",
        "embedding_model_version",
        "chunk_set_sha256",
        "index_version",
        "filter",
        "ranked_chunk_ids",
        "recall_at_k",
        "mrr",
    ]
    dataset_path = tmp_path / "retrieval_cases.json"
    dataset_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    service = _FakeSearchService(
        {
            "양성 고객 검색 원문": [
                _chunk(
                    embedding_model="BAAI/bge-m3",
                    embedding_model_revision="revision",
                    index_version="1.0.0",
                    chunk_set_sha256="A" * 64,
                )
            ],
            "음성 고객 검색 원문": [],
        }
    )

    report = RetrievalEvaluationRunner(service, dataset_path).run()

    assert report["status"] == "PASS"
    assert report["summary"]["missing_required_metadata_count"] == 0
    assert {case["effective_top_k"] for case in report["cases"]} == {5}


def test_retrieval_dataset_rejects_case_top_k_different_from_policy(tmp_path):
    payload = _dataset_payload()
    payload["cases"][0]["top_k"] = 3
    dataset_path = tmp_path / "retrieval_cases.json"
    dataset_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="default_top_k"):
        RetrievalEvaluationRunner(dataset_path=dataset_path).load_dataset()
