"""T-049 결정적 Safety Candidate 품질 Gate 테스트."""

import json

import pytest
from pydantic import ValidationError

from ai.evaluation.runners.safety_runner import SafetyEvaluationRunner
from ai.scripts.run_evaluation import _combined_status, build_deterministic_report


def test_safety_candidate_matrix_passes_required_categories():
    report = SafetyEvaluationRunner().run()

    assert report["status"] == "PASS"
    assert report["dataset"]["approval_status"] == "CANDIDATE_NOT_QA_APPROVED"
    assert report["summary"]["case_count"] == 20
    assert report["summary"]["passed_count"] == 20
    assert report["summary"]["failed_count"] == 0
    assert set(report["summary"]["category_results"]) >= {
        "leak_raw_expression",
        "leak_selected_alias",
        "leak_negation",
        "leak_negation_no_evidence",
        "electrical_danger",
        "electrical_negation",
        "hot_water_danger",
        "hot_water_heater_danger",
        "caution_with_evidence",
        "caution_no_evidence",
        "general_with_evidence",
        "general_no_evidence",
        "mixed_danger",
    }


def test_safety_report_does_not_include_raw_symptom_or_secrets():
    runner = SafetyEvaluationRunner()
    report = runner.run()
    serialized = json.dumps(report, ensure_ascii=False)

    assert all(
        case.raw_symptom not in serialized
        for case in runner.load_dataset().cases
    )
    assert report["raw_symptom_printed"] is False
    assert report["secret_values_printed"] is False


def test_safety_candidate_rejects_duplicate_case_ids(tmp_path):
    runner = SafetyEvaluationRunner()
    payload = json.loads(runner.dataset_path.read_text(encoding="utf-8"))
    payload["cases"][1]["case_id"] = payload["cases"][0]["case_id"]
    invalid_path = tmp_path / "duplicate.json"
    invalid_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="case_id는 중복"):
        SafetyEvaluationRunner(invalid_path).load_dataset()


def test_deterministic_quality_report_is_honest_about_not_run_runtime():
    report = build_deterministic_report()

    assert report["schema_version"] == "1.1.0"
    assert report["overall_status"] == "PARTIAL"
    assert report["deterministic_quality_status"] == "PASS"
    assert report["retrieval_runtime_status"] == "NOT_RUN"
    assert len(report["execution"]["git_sha"]) == 40
    assert report["execution"]["python_version"] == "3.13.13"
    assert report["execution"]["contract_version"] == "4.0.0"
    assert report["safety_evaluation"]["summary"]["case_count"] == 20
    assert report["structuring_evaluation"]["summary"]["case_count"] == 12
    assert report["retrieval_evaluation"]["status"] == "NOT_RUN"
    assert report["retrieval_evaluation"]["mean_recall_at_5"] is None
    assert report["retrieval_evaluation"]["mean_mrr"] is None
    assert report["retrieval_evaluation"]["summary"]["search_call_count"] == 0
    assert report["generation_evaluation"]["status"] == "PASS"
    assert report["provider_generation_evaluation"]["status"] == "NOT_RUN"
    assert set(report["external_runtime"].values()) == {"NOT_RUN"}
    assert report["secret_values_printed"] is False
    assert report["raw_customer_text_printed"] is False


@pytest.mark.parametrize(
    ("deterministic_status", "retrieval_status", "external_status", "expected"),
    (
        ("PASS", "PASS", "PASS", "PASS"),
        ("PASS", "NOT_RUN", "NOT_RUN", "PARTIAL"),
        ("PASS", "FAIL", "NOT_RUN", "FAIL"),
        ("FAIL", "NOT_RUN", "NOT_RUN", "FAIL"),
    ),
)
def test_combined_status_never_promotes_not_run_or_fail_to_pass(
    deterministic_status: str,
    retrieval_status: str,
    external_status: str,
    expected: str,
) -> None:
    assert (
        _combined_status(
            deterministic_status=deterministic_status,
            retrieval_status=retrieval_status,
            external_runtime={"provider": external_status},
        )
        == expected
    )
