"""결정적 Safety 규칙을 Candidate Matrix로 검증하는 평가 실행기."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai.app.safety import RiskClassifier, UsageGuidanceClassifier
from ai.app.schemas import RiskLevel, SafetyPriority, UsageGuidanceStatus


class _EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedSafetyOutcome(_EvaluationModel):
    """Case별 공개 Safety 불변식."""

    risk_level: RiskLevel
    priority: SafetyPriority
    requires_consultation: bool
    matched_safety_rule_ids: list[str]
    guidance_status: UsageGuidanceStatus
    restricted_functions_contains: list[str] = Field(default_factory=list)


class SafetyQualityCase(_EvaluationModel):
    case_id: str = Field(pattern=r"^T049-SAF-\d{3}$")
    category: str = Field(min_length=1, max_length=100)
    raw_symptom: str = Field(min_length=1, max_length=2000)
    selected_symptoms: list[str] = Field(default_factory=list)
    has_evidence: bool
    expected: ExpectedSafetyOutcome


class SafetyQualityDataset(_EvaluationModel):
    dataset_id: str = Field(min_length=1, max_length=100)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    approval_status: Literal["CANDIDATE_NOT_QA_APPROVED"]
    scope: str = Field(min_length=1, max_length=300)
    cases: list[SafetyQualityCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> "SafetyQualityDataset":
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Safety Candidate case_id는 중복될 수 없습니다.")
        return self


class SafetyEvaluationRunner:
    """Backend·Vector·Provider 없이 Safety와 No-Evidence 정책을 평가한다."""

    DEFAULT_DATASET_PATH = (
        Path(__file__).resolve().parents[1]
        / "datasets"
        / "candidates"
        / "safety_quality_candidate_v1.json"
    )

    def __init__(self, dataset_path: str | Path | None = None) -> None:
        self.dataset_path = Path(dataset_path or self.DEFAULT_DATASET_PATH).resolve()
        self.risk_classifier = RiskClassifier()
        self.guidance_classifier = UsageGuidanceClassifier()

    def load_dataset(self) -> SafetyQualityDataset:
        if not self.dataset_path.is_file():
            raise FileNotFoundError(
                f"Safety Candidate 평가셋이 없습니다: {self.dataset_path}"
            )
        payload = json.loads(self.dataset_path.read_text(encoding="utf-8"))
        return SafetyQualityDataset.model_validate(payload)

    def run(self) -> dict[str, object]:
        dataset = self.load_dataset()
        case_results: list[dict[str, object]] = []

        for case in dataset.cases:
            initial_assessment = self.risk_classifier.classify(
                case.raw_symptom,
                case.selected_symptoms,
            )
            assessment, guidance = (
                self.guidance_classifier.determine_assessment_and_guidance(
                    initial_assessment,
                    case.raw_symptom,
                    has_evidence=case.has_evidence,
                )
            )
            expected = case.expected
            checks = {
                "risk_level": assessment.risk_level == expected.risk_level,
                "priority": assessment.priority == expected.priority,
                "requires_consultation": (
                    assessment.requires_consultation
                    == expected.requires_consultation
                ),
                "matched_safety_rule_ids": (
                    assessment.matched_safety_rule_ids
                    == expected.matched_safety_rule_ids
                ),
                "guidance_status": (
                    guidance.guidance_status == expected.guidance_status
                ),
                "restricted_functions": all(
                    required in guidance.restricted_functions
                    for required in expected.restricted_functions_contains
                ),
            }
            case_results.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "has_evidence": case.has_evidence,
                    "passed": all(checks.values()),
                    "checks": checks,
                    "expected": {
                        "risk_level": expected.risk_level.value,
                        "priority": expected.priority.value,
                        "requires_consultation": expected.requires_consultation,
                        "matched_safety_rule_ids": expected.matched_safety_rule_ids,
                        "guidance_status": expected.guidance_status.value,
                    },
                    "actual": {
                        "risk_level": assessment.risk_level.value,
                        "priority": assessment.priority.value,
                        "requires_consultation": assessment.requires_consultation,
                        "matched_safety_rule_ids": (
                            assessment.matched_safety_rule_ids
                        ),
                        "guidance_status": guidance.guidance_status.value,
                    },
                }
            )

        passed_count = sum(result["passed"] is True for result in case_results)
        category_counts = Counter(case.category for case in dataset.cases)
        category_passed = Counter(
            result["category"]
            for result in case_results
            if result["passed"] is True
        )
        return {
            "status": (
                "PASS" if passed_count == len(case_results) else "FAIL"
            ),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "evaluation_scope": (
                "deterministic_safety_rules_without_backend_vector_or_provider"
            ),
            "dataset": {
                "dataset_id": dataset.dataset_id,
                "version": dataset.version,
                "approval_status": dataset.approval_status,
                "path": self._report_path(self.dataset_path),
                "file_sha256": hashlib.sha256(
                    self.dataset_path.read_bytes()
                ).hexdigest().upper(),
            },
            "summary": {
                "case_count": len(case_results),
                "passed_count": passed_count,
                "failed_count": len(case_results) - passed_count,
                "category_results": {
                    category: {
                        "case_count": category_counts[category],
                        "passed_count": category_passed[category],
                    }
                    for category in sorted(category_counts)
                },
            },
            "cases": case_results,
            "raw_symptom_printed": False,
            "secret_values_printed": False,
        }

    @staticmethod
    def _report_path(path: Path) -> str:
        repository_root = Path(__file__).resolve().parents[3]
        try:
            return path.relative_to(repository_root).as_posix()
        except ValueError:
            return path.name

    def run_and_save(self, output_path: str | Path) -> dict[str, object]:
        report = self.run()
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return report


__all__ = [
    "ExpectedSafetyOutcome",
    "SafetyEvaluationRunner",
    "SafetyQualityCase",
    "SafetyQualityDataset",
]
