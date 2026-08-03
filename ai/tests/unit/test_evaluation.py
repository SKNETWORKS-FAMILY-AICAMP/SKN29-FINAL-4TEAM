"""AI/RAG 평가 모듈 단위 테스트."""

import pytest
from ai.evaluation.eval_dataset_loader import EvalDatasetLoader
from ai.evaluation.evaluation_runner import EvaluationRunner
from ai.evaluation.metrics import calculate_mrr, calculate_recall_at_k, is_safety_compliant


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

    assert len(rag_data) == 12
    assert {item["case_id"] for item in rag_data}
    assert len(safety_data) == 4
    assert safety_data[0]["raw_symptom"].startswith("정수기 하부")
    assert all("ì" not in item["raw_symptom"] for item in safety_data)


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

    # Safety compliance rate 100% 준수 확인
    assert results["safety_evaluation"]["safety_compliance_rate"] == 100.0
    assert results["safety_evaluation"]["evaluation_mode"] == "rule_based_with_evidence_available"
    assert results["rag_evaluation"]["mean_recall_at_5"] == 1.0
