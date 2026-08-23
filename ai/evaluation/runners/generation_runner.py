"""Provider 없이 고객 안내 생성 계약을 검증하는 결정적 평가 실행기."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from ai.app.generation.customer_guidance.models import (
    GuidanceGenerationRequest,
    GuidanceGenerationResult,
)
from ai.app.schemas import (
    RiskLevel,
    SafetyAssessment,
    SafetyPriority,
    UsageGuidance,
)
from ai.app.validation.safety import GuidanceMessageGuard, UsageGuidanceValidator


GenerationOutcome = Literal[
    "ACCEPTED",
    "OUTPUT_SCHEMA_INVALID",
    "ACTION_NOT_ALLOWED",
    "GROUNDING_INVALID",
    "SAFETY_INVALID",
]


class _EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerationQualityCase(_EvaluationModel):
    case_id: str = Field(pattern=r"^T029-GEN-\d{3}$")
    category: str = Field(min_length=1, max_length=100)
    request: dict[str, object]
    candidate_output: dict[str, object]
    expected_outcome: GenerationOutcome


class GenerationQualityDataset(_EvaluationModel):
    dataset_id: str = Field(min_length=1, max_length=100)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    approval_status: Literal["CANDIDATE_NOT_QA_APPROVED"]
    scope: str = Field(min_length=1, max_length=300)
    cases: list[GenerationQualityCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_case_ids(self) -> "GenerationQualityDataset":
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Generation Candidate case_id는 중복될 수 없습니다.")
        return self


class GenerationEvaluationRunner:
    """Structured Output·Grounding·Safety·Action Allowlist를 평가한다."""

    DEFAULT_DATASET_PATH = (
        Path(__file__).resolve().parents[1]
        / "datasets"
        / "candidates"
        / "generation_quality_candidate_v1.json"
    )

    def __init__(self, dataset_path: str | Path | None = None) -> None:
        self.dataset_path = Path(dataset_path or self.DEFAULT_DATASET_PATH).resolve()
        self.message_guard = GuidanceMessageGuard()
        self.guidance_validator = UsageGuidanceValidator()

    def load_dataset(self) -> GenerationQualityDataset:
        if not self.dataset_path.is_file():
            raise FileNotFoundError(
                f"Generation Candidate 평가셋이 없습니다: {self.dataset_path}"
            )
        payload = json.loads(self.dataset_path.read_text(encoding="utf-8"))
        return GenerationQualityDataset.model_validate(payload)

    def run(self) -> dict[str, object]:
        dataset = self.load_dataset()
        case_results: list[dict[str, object]] = []

        for case in dataset.cases:
            actual_outcome = self._evaluate_case(case)
            case_results.append(
                {
                    "case_id": case.case_id,
                    "category": case.category,
                    "expected_outcome": case.expected_outcome,
                    "actual_outcome": actual_outcome,
                    "passed": actual_outcome == case.expected_outcome,
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
            "status": "PASS" if passed_count == len(case_results) else "FAIL",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "evaluation_scope": (
                "deterministic_generation_contract_without_external_provider"
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
            "provider_called": False,
            "candidate_text_printed": False,
            "evidence_text_printed": False,
            "secret_values_printed": False,
        }

    def _evaluate_case(self, case: GenerationQualityCase) -> GenerationOutcome:
        try:
            request = GuidanceGenerationRequest.model_validate(case.request)
            candidate = GuidanceGenerationResult.model_validate(
                case.candidate_output
            )
        except ValidationError:
            return "OUTPUT_SCHEMA_INVALID"

        if any(
            action not in request.allowed_next_actions
            for action in candidate.next_actions
        ):
            return "ACTION_NOT_ALLOWED"

        try:
            self.message_guard.validate_grounding(
                candidate.message,
                grounding_texts=request.evidence_summaries,
            )
        except ValueError:
            return "GROUNDING_INVALID"

        assessment = SafetyAssessment(
            risk_level=RiskLevel(request.risk_level),
            priority=(
                SafetyPriority.CONSULTATION_RECOMMENDED
                if request.risk_level == "caution"
                else SafetyPriority.GENERAL_GUIDANCE
            ),
            requires_consultation=False,
            matched_safety_rule_ids=[],
            detected_risks=[],
            safety_reason=request.safety_reason,
        )
        guidance = UsageGuidance(
            guidance_status=request.guidance_status,
            message=candidate.message,
            restricted_functions=request.restricted_functions,
            next_actions=candidate.next_actions,
        )
        try:
            self.guidance_validator.validate(
                assessment,
                guidance,
                has_evidence=True,
            )
        except ValueError:
            return "SAFETY_INVALID"
        return "ACCEPTED"

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
    "GenerationEvaluationRunner",
    "GenerationQualityCase",
    "GenerationQualityDataset",
]
