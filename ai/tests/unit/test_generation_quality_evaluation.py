"""T-029 결정적 Generation Candidate 품질 Gate 테스트."""

import json

import pytest
from pydantic import ValidationError

from ai.evaluation.runners.generation_runner import GenerationEvaluationRunner


def test_generation_candidate_matrix_passes_required_categories():
    report = GenerationEvaluationRunner().run()

    assert report["status"] == "PASS"
    assert report["dataset"]["approval_status"] == "CANDIDATE_NOT_QA_APPROVED"
    assert report["summary"]["case_count"] == 13
    assert report["summary"]["passed_count"] == 13
    assert report["summary"]["failed_count"] == 0
    assert set(report["summary"]["category_results"]) >= {
        "accepted_grounded_caution",
        "accepted_runtime_evidence_selection",
        "accepted_multiple_actions",
        "evidence_selection_rejection",
        "diagnosis_rejection",
        "guarantee_rejection",
        "repair_message_rejection",
        "repair_action_rejection",
        "guidance_status_conflict",
        "action_allowlist_rejection",
        "output_schema_rejection",
        "internal_metadata_rejection",
    }


def test_generation_report_excludes_candidate_and_evidence_text():
    runner = GenerationEvaluationRunner()
    report = runner.run()
    serialized = json.dumps(report, ensure_ascii=False)

    dataset = runner.load_dataset()
    assert all(
        str(evidence_text) not in serialized
        for case in dataset.cases
        for evidence_text in case.request["evidence_summaries"]
    )
    assert report["provider_called"] is False
    assert report["candidate_text_printed"] is False
    assert report["evidence_text_printed"] is False
    assert report["secret_values_printed"] is False


def test_generation_candidate_rejects_duplicate_case_ids(tmp_path):
    runner = GenerationEvaluationRunner()
    payload = json.loads(runner.dataset_path.read_text(encoding="utf-8"))
    payload["cases"][1]["case_id"] = payload["cases"][0]["case_id"]
    invalid_path = tmp_path / "duplicate.json"
    invalid_path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="case_id는 중복"):
        GenerationEvaluationRunner(invalid_path).load_dataset()
