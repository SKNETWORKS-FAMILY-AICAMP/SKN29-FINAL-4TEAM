"""AI/RAG 평가 모듈 단위 테스트."""

import pytest
from ai.evaluation.eval_dataset_loader import EvalDatasetLoader
from ai.evaluation.evaluation_runner import EvaluationRunner
from ai.evaluation.metrics import calculate_mrr, calculate_recall_at_k, is_safety_compliant
from ai.evaluation.runners.structuring_runner import StructuringEvaluationRunner
from ai.scripts.benchmark_pgvector_latency import _percentile, _summary
from ai.scripts.generate_candidate_baseline import canonical_contract_sha256


def test_metrics_calculation():
    """Recall@K, MRR, Safety compliance 계산 함수 단위 테스트"""
    retrieved = ["chunk_1", "chunk_2", "chunk_3", "chunk_4", "chunk_5"]
    expected = ["chunk_3"]

    recall = calculate_recall_at_k(retrieved, expected, k=5)
    assert recall == 1.0

    mrr = calculate_mrr(retrieved, expected)
    assert mrr == 1.0 / 3.0

    # danger 위험군에 NORMAL 상태 반환 시 위반 처리 검증
    assert is_safety_compliant("danger", "NORMAL", "danger", "TOTAL_STOP") is False
    # 정답 매핑 준수 시 True
    assert is_safety_compliant("danger", "TOTAL_STOP", "danger", "TOTAL_STOP") is True


def test_eval_dataset_loader():
    """평가 데이터셋 로더 구동 테스트"""
    loader = EvalDatasetLoader()
    rag_data = loader.load_rag_dataset()
    safety_data = loader.load_safety_dataset()
    structuring_data = loader.load_structuring_dataset()

    assert len(rag_data) == 13
    assert {item["case_id"] for item in rag_data}
    assert len(safety_data) == 4
    assert safety_data[0]["raw_symptom"].startswith("정수기 하부")
    assert all("ì" not in item["raw_symptom"] for item in safety_data)
    assert structuring_data["dataset_id"] == "T026-STRUCTURING-MVP"
    assert len(structuring_data["cases"]) == 12


def test_evaluation_runner_execution():
    """EvaluationRunner 전체 일괄 산출 테스트"""
    expected_by_query = {
        item["query"]: item["expected_chunk_ids"]
        for item in EvalDatasetLoader().load_rag_dataset()
    }

    class FakeSearchService:
        def search(self, query, *, cancellation_token=None):
            from ai.app.retrieval.indexing.chunk_loader import ChunkLoader
            chunks = ChunkLoader().load_verified_chunks()
            expected = expected_by_query.get(query.query_text)
            if expected is not None:
                ids = set(expected)
            elif "졸졸" in query.query_text:
                ids = {"RAG-WPUJAC104DWH-LOW-FLOW-001"}
            else:
                ids = {"RAG-WPUJAC104DWH-COLD-TEMPERATURE-001"}
            return [chunk for chunk in chunks if chunk.chunk_id in ids]

    runner = EvaluationRunner(FakeSearchService())
    results = runner.run_all_evaluations(save_report=False)

    assert "rag_evaluation" in results
    assert "safety_evaluation" in results
    assert "generation_evaluation" in results
    assert "structuring_evaluation" in results

    # Safety compliance rate 100% 준수 확인
    assert results["safety_evaluation"]["safety_compliance_rate"] == 100.0
    assert results["safety_evaluation"]["total_cases"] == 20
    assert (
        results["safety_evaluation"]["dataset"]["approval_status"]
        == "CANDIDATE_NOT_QA_APPROVED"
    )
    assert (
        results["safety_evaluation"]["evaluation_mode"]
        == "deterministic_safety_and_no_evidence_candidate_matrix"
    )
    assert results["rag_evaluation"]["mean_recall_at_5"] == 1.0
    assert results["generation_evaluation"]["summary"]["case_count"] == 13
    assert results["structuring_evaluation"]["status"] == "PASS"


def test_structuring_evaluation_runner_covers_required_categories():
    report = StructuringEvaluationRunner().run()

    assert report["status"] == "PASS"
    assert report["summary"]["case_count"] == 12
    assert report["summary"]["passed_count"] == 12
    assert report["summary"]["mean_field_accuracy"] == 1.0
    assert report["summary"]["missing_fields_exact_match_rate"] == 1.0
    assert report["summary"]["followup_questions_exact_match_rate"] == 1.0
    assert report["summary"]["safety_routing_passed_count"] == 12
    assert {case["category"] for case in report["cases"]} >= {
        "representative_symptom",
        "multiple_symptoms",
        "short_free_text",
        "typo_variation",
        "negation",
        "previous_answer",
        "declined_answer",
        "danger_priority",
    }


def test_latency_percentile_and_summary():
    values = [1.0, 2.0, 3.0, 4.0]

    assert _percentile(values, 50) == pytest.approx(2.5)
    assert _percentile(values, 95) == pytest.approx(3.85)
    assert _summary(values) == {
        "sample_count": 4,
        "mean_ms": 2.5,
        "p50_ms": 2.5,
        "p95_ms": 3.85,
        "min_ms": 1.0,
        "max_ms": 4.0,
    }

    with pytest.raises(ValueError):
        _percentile([], 50)


def test_contract_canonical_hash_is_stable_and_complete():
    first = canonical_contract_sha256()
    second = canonical_contract_sha256()

    assert first == second
    assert len(first) == 64
    assert first == first.upper()
