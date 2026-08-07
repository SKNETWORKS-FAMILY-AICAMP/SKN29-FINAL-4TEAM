"""T-026 증상 구조화·누락 필드·추가 질문 평가 실행기."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai.app.safety import RiskClassifier
from ai.app.structuring import (
    DuplicateQuestionGuard,
    FollowUpQuestionGenerator,
    MissingFieldChecker,
    SymptomStructurer,
)
from ai.evaluation.eval_dataset_loader import EvalDatasetLoader
from ai.evaluation.metrics import calculate_structuring_accuracy


class StructuringEvaluationRunner:
    """팀 DB 없이 결정적 구조화 규칙과 질문 정책을 검증한다."""

    def __init__(self, loader: EvalDatasetLoader | None = None) -> None:
        self.loader = loader or EvalDatasetLoader()
        self.structurer = SymptomStructurer()
        self.missing_checker = MissingFieldChecker()
        self.question_generator = FollowUpQuestionGenerator()
        self.duplicate_guard = DuplicateQuestionGuard()
        self.risk_classifier = RiskClassifier()

    @staticmethod
    def _dataset_path(loader: EvalDatasetLoader) -> Path:
        return Path(loader.dataset_dir) / "structuring" / "symptom_eval_dataset.json"

    @staticmethod
    def _file_sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest().upper()

    def run(self) -> dict[str, Any]:
        dataset = self.loader.load_structuring_dataset()
        case_results: list[dict[str, Any]] = []
        total_field_accuracy = 0.0
        missing_passed = 0
        question_passed = 0
        safety_routing_passed = 0

        for case in dataset["cases"]:
            expected = case["expected"]
            previous_answers = case.get("previous_answers", [])
            symptom = self.structurer.structure(
                case["raw_symptom"],
                case.get("selected_symptoms", []),
                previous_answers,
            )
            missing = self.missing_checker.check(symptom)
            questions = self.duplicate_guard.filter(
                self.question_generator.generate(missing),
                previous_answers,
            )

            assessment = self.risk_classifier.classify(
                case["raw_symptom"],
                case.get("selected_symptoms", []),
            )
            actual_safety_route = (
                "danger_skip_questions"
                if assessment.risk_level.value == "danger"
                else "questionnaire"
            )
            expected_safety_route = expected.get("safety_priority", "questionnaire")
            safety_priority_ok = actual_safety_route == expected_safety_route
            safety_routing_passed += int(safety_priority_ok)
            if actual_safety_route == "danger_skip_questions":
                missing = []
                questions = []

            actual_structured = symptom.model_dump(mode="json")
            expected_structured = expected["structured_symptom"]
            field_accuracy = calculate_structuring_accuracy(actual_structured, expected_structured)
            actual_missing = [item.field_name for item in missing]
            actual_questions = [item.target_field for item in questions]
            missing_ok = actual_missing == expected["missing_fields"]
            questions_ok = actual_questions == expected["followup_question_fields"]
            passed = field_accuracy == 1.0 and missing_ok and questions_ok and safety_priority_ok

            total_field_accuracy += field_accuracy
            missing_passed += int(missing_ok)
            question_passed += int(questions_ok)
            case_results.append(
                {
                    "case_id": case["case_id"],
                    "category": case["category"],
                    "field_accuracy": round(field_accuracy, 4),
                    "missing_fields_match": missing_ok,
                    "followup_questions_match": questions_ok,
                    "safety_priority_match": safety_priority_ok,
                    "passed": passed,
                    "actual": {
                        "structured_symptom": actual_structured,
                        "missing_fields": actual_missing,
                        "followup_question_fields": actual_questions,
                    },
                }
            )

        total_cases = len(case_results)
        passed_cases = sum(int(result["passed"]) for result in case_results)
        dataset_path = self._dataset_path(self.loader)
        repository_root = Path(__file__).resolve().parents[3]
        return {
            "status": "PASS" if passed_cases == total_cases else "FAIL",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "evaluation_scope": "deterministic_structuring_rules_without_backend_or_vector_db",
            "dataset": {
                "dataset_id": dataset["dataset_id"],
                "version": dataset["version"],
                "path": dataset_path.relative_to(repository_root).as_posix(),
                "file_sha256": self._file_sha256(dataset_path),
            },
            "summary": {
                "case_count": total_cases,
                "passed_count": passed_cases,
                "failed_count": total_cases - passed_cases,
                "mean_field_accuracy": round(total_field_accuracy / total_cases, 4),
                "missing_fields_exact_match_rate": round(missing_passed / total_cases, 4),
                "followup_questions_exact_match_rate": round(question_passed / total_cases, 4),
                "safety_routing_case_count": total_cases,
                "safety_routing_passed_count": safety_routing_passed,
            },
            "cases": case_results,
        }

    def run_and_save(self, output_path: str | Path) -> dict[str, Any]:
        report = self.run()
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description="T-026 구조화 평가 실행")
    parser.add_argument(
        "--output",
        default="ai/evaluation/reports/structuring_evaluation_20260807.json",
        help="평가 JSON 저장 경로",
    )
    args = parser.parse_args()
    report = StructuringEvaluationRunner().run_and_save(args.output)
    print(json.dumps(report["summary"], ensure_ascii=False))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
