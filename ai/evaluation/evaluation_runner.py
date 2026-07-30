"""AI/RAG 파이프라인 종합 평가 실행기 모듈."""

import json
import os
from typing import Any, Dict
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.retrieval import RetrievalQuery
from ai.app.retrieval.search.vector_search import VectorSearchService
from ai.evaluation.eval_dataset_loader import EvalDatasetLoader
from ai.evaluation.metrics import calculate_mrr, calculate_recall_at_k, is_safety_compliant


class EvaluationRunner:
    """RAG 정답률(Recall@5) 및 안전 규칙 준수율 평가 실행기"""

    def __init__(self, search_service: VectorSearchService | None = None):
        self.loader = EvalDatasetLoader()
        self.search_service = search_service
        self.pipeline_router = PipelineRouter(search_service)

    def run_rag_evaluation(self) -> Dict[str, Any]:
        """RAG 검색 Recall@5 및 MRR 지표 평가"""
        dataset = self.loader.load_rag_dataset()
        if self.search_service is None:
            return {
                "total_cases": len(dataset),
                "mean_recall_at_5": 0.0,
                "mean_mrr": 0.0,
                "status": "vector_store_not_configured",
            }
        if not dataset:
            return {"total_cases": 0, "mean_recall_at_5": 0.0, "mean_mrr": 0.0}

        total_recall = 0.0
        total_mrr = 0.0

        for item in dataset:
            query = RetrievalQuery(
                query_text=item["query"],
                model_code=item.get("model_code", "WPUJAC104DWH"),
                top_k=5
            )
            chunks = self.search_service.search(query)
            retrieved_ids = [c.chunk_id for c in chunks]

            expected_ids = item["expected_chunk_ids"]
            recall = calculate_recall_at_k(retrieved_ids, expected_ids, k=5)
            mrr = calculate_mrr(retrieved_ids, expected_ids)

            total_recall += recall
            total_mrr += mrr

        count = len(dataset)
        return {
            "total_cases": count,
            "mean_recall_at_5": round(total_recall / count, 4),
            "mean_mrr": round(total_mrr / count, 4)
        }

    def run_safety_evaluation(self) -> Dict[str, Any]:
        """안전 규칙 준수율 (Safety Compliance Rate) 평가"""
        dataset = self.loader.load_safety_dataset()
        if not dataset:
            return {"total_cases": 0, "safety_compliance_rate": 0.0}

        compliant_count = 0

        for idx, item in enumerate(dataset, start=1):
            res = self.pipeline_router.run_pipeline(
                inquiry_id=f"00000000-0000-0000-0000-{idx:012d}",
                correlation_id=f"eval-corr-{idx}",
                ai_request_id=f"eval-ai-request-{idx}",
                state_version=1,
                raw_symptom=item["raw_symptom"],
                selected_symptoms=item.get("selected_symptoms", [])
            ).to_analysis_result()

            actual_risk = res.safety_assessment.risk_level.value
            actual_status = res.usage_guidance.guidance_status.value

            if is_safety_compliant(actual_risk, actual_status, item["expected_risk_level"], item["expected_guidance_status"]):
                compliant_count += 1

        count = len(dataset)
        return {
            "total_cases": count,
            "compliant_cases": compliant_count,
            "safety_compliance_rate": round(compliant_count / count, 4) * 100.0
        }

    def run_all_evaluations(self, save_report: bool = True) -> Dict[str, Any]:
        """전체 RAG 및 안전 준수율 평가 일괄 수행 및 리포트 저장"""
        rag_metrics = self.run_rag_evaluation()
        safety_metrics = self.run_safety_evaluation()

        report = {
            "rag_evaluation": rag_metrics,
            "safety_evaluation": safety_metrics
        }

        if save_report:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            reports_dir = os.path.join(base_dir, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            report_file = os.path.join(reports_dir, "latest_eval_report.json")
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

        return report


if __name__ == "__main__":
    runner = EvaluationRunner()
    results = runner.run_all_evaluations(save_report=True)
    print("=== AI / RAG 종합 평가 결과 ===")
    print(results)
