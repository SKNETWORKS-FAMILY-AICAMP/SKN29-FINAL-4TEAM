"""AI/RAG 파이프라인 종합 평가 실행기 모듈."""

import json
import os
from typing import Any, Dict
from ai.app.orchestration.pipeline_router import PipelineRouter
from ai.app.retrieval.search.vector_search import VectorSearchService
from ai.evaluation.eval_dataset_loader import EvalDatasetLoader
from ai.evaluation.runners.generation_runner import GenerationEvaluationRunner
from ai.evaluation.runners.retrieval_runner import RetrievalEvaluationRunner
from ai.evaluation.runners.safety_runner import SafetyEvaluationRunner
from ai.evaluation.runners.structuring_runner import StructuringEvaluationRunner


class EvaluationRunner:
    """RAG 정답률(Recall@5) 및 안전 규칙 준수율 평가 실행기"""

    def __init__(self, search_service: VectorSearchService | None = None):
        self.loader = EvalDatasetLoader()
        self.search_service = search_service
        self.pipeline_router = PipelineRouter(search_service)

    def run_rag_evaluation(self) -> Dict[str, Any]:
        """양성 검색과 음성 차단을 분리한 Retrieval 품질 리포트를 반환한다."""

        return RetrievalEvaluationRunner(
            self.search_service,
            self.loader.rag_config_path,
        ).run()

    def run_safety_evaluation(self) -> Dict[str, Any]:
        """T-049 Candidate Matrix의 Safety·No-Evidence 불변식을 평가한다."""

        report = SafetyEvaluationRunner().run()
        summary = report["summary"]
        count = summary["case_count"]
        compliant_count = summary["passed_count"]
        return {
            **report,
            "total_cases": count,
            "compliant_cases": compliant_count,
            "safety_compliance_rate": (
                round(compliant_count / count, 4) * 100.0 if count else 0.0
            ),
            "evaluation_mode": (
                "deterministic_safety_and_no_evidence_candidate_matrix"
            ),
        }

    def run_generation_evaluation(self) -> Dict[str, Any]:
        """합성 Candidate로 생성 출력의 결정적 계약을 평가한다."""

        return GenerationEvaluationRunner().run()

    def run_all_evaluations(self, save_report: bool = True) -> Dict[str, Any]:
        """전체 RAG 및 안전 준수율 평가 일괄 수행 및 리포트 저장"""
        rag_metrics = self.run_rag_evaluation()
        safety_metrics = self.run_safety_evaluation()
        structuring_metrics = StructuringEvaluationRunner(self.loader).run()
        generation_metrics = self.run_generation_evaluation()

        report = {
            "rag_evaluation": rag_metrics,
            "safety_evaluation": safety_metrics,
            "generation_evaluation": generation_metrics,
            "structuring_evaluation": {
                "status": structuring_metrics["status"],
                "dataset": structuring_metrics["dataset"],
                "summary": structuring_metrics["summary"],
            },
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
