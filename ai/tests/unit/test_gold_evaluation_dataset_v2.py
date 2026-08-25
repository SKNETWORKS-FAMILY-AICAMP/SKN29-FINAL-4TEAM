from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from ai.scripts.validate_gold_evaluation_v2 import (
    REPOSITORY_ROOT,
    build_qa_report,
    validate_case_logic,
)


SCHEMA_PATH = (
    REPOSITORY_ROOT / "ai/evaluation/schemas/gold_evaluation_case_v2.schema.json"
)


def _valid_case() -> dict[str, object]:
    return {
        "schema_version": "2.0.0-draft.1",
        "case_id": "RAGV2-GOLD-0001",
        "dataset_version": "2.0.0-draft.1",
        "evaluation_status": "ACTIVE",
        "split": "DEV",
        "query_variant_type": "DIRECT",
        "query": "물이 나오지 않을 때 확인할 사항을 알려주세요.",
        "product_model_code": "WPUJAC104DWH",
        "expected_retrieval_outcome": "EVIDENCE",
        "expected_execution_path": "PGVECTOR_QUERY",
        "required_evidence_group_ids": ["EVD-WPUJAC104DWH-NO-WATER-001"],
        "supporting_evidence_group_ids": [],
        "evidence_match_policy": "ANY",
        "expected_risk_level": "general",
        "expected_usage_guidance_status": "NORMAL",
        "expected_consultation_requirement": "NONE",
        "consultation_basis_codes": ["NONE"],
        "consultation_condition_ids": [],
        "forbidden_document_ids": [],
        "forbidden_model_codes": ["WPUIAC425SNW", "WPUIAC606SNW"],
        "source_query_origin": "CURATED_VARIANT",
        "source_case_ids": [],
        "label_generation": "ASSISTED_DRAFT_NOT_APPROVED",
        "review_status": "UNREVIEWED_DRAFT",
        "reviewer_ids": [],
        "review_notes": "Gold v2 계약 표적 테스트 Fixture",
    }


class GoldEvaluationDatasetV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(cls.schema)
        cls.validator = Draft202012Validator(cls.schema)

    def _schema_errors(self, row: dict[str, object]) -> list[str]:
        return [error.message for error in self.validator.iter_errors(row)]

    def test_minimal_evidence_case_matches_schema_and_logic(self) -> None:
        row = _valid_case()

        self.assertEqual(self._schema_errors(row), [])
        self.assertEqual(validate_case_logic(row), [])

    def test_schema_rejects_legacy_or_unknown_fields(self) -> None:
        row = _valid_case()
        row["expected_evidence"] = []

        self.assertTrue(self._schema_errors(row))

    def test_normal_usage_separates_pending_and_met_source_conditions(self) -> None:
        pending = _valid_case()
        pending["expected_consultation_requirement"] = "CONDITIONAL"
        pending["consultation_basis_codes"] = ["SOURCE_CONDITION_PENDING"]
        pending["consultation_condition_ids"] = ["COND-SYMPTOM-PERSISTS-001"]

        met = _valid_case()
        met["expected_consultation_requirement"] = "REQUIRED"
        met["consultation_basis_codes"] = ["SOURCE_CONDITION_MET"]
        met["consultation_condition_ids"] = ["COND-SYMPTOM-PERSISTS-001"]

        for row in (pending, met):
            with self.subTest(requirement=row["expected_consultation_requirement"]):
                self.assertEqual(self._schema_errors(row), [])
                self.assertEqual(validate_case_logic(row), [])

    def test_normal_and_partial_stop_allow_all_three_consultation_states(self) -> None:
        cases = (
            ("NONE", ["NONE"]),
            ("CONDITIONAL", ["SOURCE_CONDITION_PENDING"]),
            ("REQUIRED", ["SOURCE_CONDITION_MET"]),
        )
        for usage in ("NORMAL", "PARTIAL_STOP"):
            for requirement, basis_codes in cases:
                row = _valid_case()
                row["expected_usage_guidance_status"] = usage
                row["expected_consultation_requirement"] = requirement
                row["consultation_basis_codes"] = basis_codes
                row["consultation_condition_ids"] = (
                    ["COND-SYMPTOM-PERSISTS-001"]
                    if requirement in {"CONDITIONAL", "REQUIRED"}
                    and basis_codes[0].startswith("SOURCE_CONDITION_")
                    else []
                )
                with self.subTest(usage=usage, requirement=requirement):
                    self.assertEqual(self._schema_errors(row), [])
                    self.assertEqual(validate_case_logic(row), [])

    def test_no_evidence_query_and_policy_block_are_distinct_valid_paths(self) -> None:
        corpus_absence = _valid_case()
        corpus_absence.update({
            "query_variant_type": "NO_EVIDENCE",
            "expected_retrieval_outcome": "NO_EVIDENCE",
            "expected_execution_path": "PGVECTOR_QUERY",
            "required_evidence_group_ids": [],
            "supporting_evidence_group_ids": [],
            "evidence_match_policy": "NONE",
            "expected_risk_level": "caution",
            "expected_usage_guidance_status": "PENDING_CONSULTATION",
            "expected_consultation_requirement": "REQUIRED",
            "consultation_basis_codes": ["NO_EVIDENCE"],
        })
        policy_block = copy.deepcopy(corpus_absence)
        policy_block.update({
            "expected_execution_path": "POLICY_BLOCK_UNVERIFIED_SOURCE",
            "consultation_basis_codes": ["POLICY_BLOCK"],
        })

        for row in (corpus_absence, policy_block):
            with self.subTest(path=row["expected_execution_path"]):
                self.assertEqual(self._schema_errors(row), [])
                self.assertEqual(validate_case_logic(row), [])

    def test_evidence_outcome_requires_query_required_group_and_any_or_all(self) -> None:
        invalid_rows = []
        wrong_path = _valid_case()
        wrong_path["expected_execution_path"] = "POLICY_BLOCK_UNVERIFIED_SOURCE"
        wrong_path["consultation_basis_codes"] = ["POLICY_BLOCK"]
        wrong_path["expected_consultation_requirement"] = "REQUIRED"
        invalid_rows.append(wrong_path)

        empty_required = _valid_case()
        empty_required["required_evidence_group_ids"] = []
        invalid_rows.append(empty_required)

        none_policy = _valid_case()
        none_policy["evidence_match_policy"] = "NONE"
        invalid_rows.append(none_policy)

        for row in invalid_rows:
            with self.subTest(row=row):
                self.assertTrue(self._schema_errors(row))
                self.assertTrue(validate_case_logic(row))

    def test_none_policy_requires_no_evidence_and_empty_group_arrays(self) -> None:
        row = _valid_case()
        row["evidence_match_policy"] = "NONE"

        error_codes = {error["code"] for error in validate_case_logic(row)}
        self.assertIn("NONE_REQUIRES_NO_EVIDENCE", error_codes)
        self.assertIn("NONE_REQUIRES_EMPTY_GROUPS", error_codes)
        self.assertTrue(self._schema_errors(row))

    def test_required_and_supporting_groups_must_be_disjoint(self) -> None:
        row = _valid_case()
        row["supporting_evidence_group_ids"] = list(row["required_evidence_group_ids"])

        error_codes = {error["code"] for error in validate_case_logic(row)}
        self.assertEqual(error_codes, {"EVIDENCE_GROUP_ROLE_OVERLAP"})

    def test_consultation_basis_exclusivity_and_mapping_are_enforced(self) -> None:
        invalid_rows = []

        none_mixed = _valid_case()
        none_mixed["consultation_basis_codes"] = ["NONE", "SOURCE_CONDITION_MET"]
        invalid_rows.append(none_mixed)

        pending_mixed = _valid_case()
        pending_mixed["consultation_basis_codes"] = [
            "SOURCE_CONDITION_PENDING", "DANGER_SAFETY",
        ]
        pending_mixed["expected_consultation_requirement"] = "REQUIRED"
        invalid_rows.append(pending_mixed)

        immediate_not_required = _valid_case()
        immediate_not_required["consultation_basis_codes"] = ["SOURCE_CONDITION_MET"]
        immediate_not_required["consultation_condition_ids"] = [
            "COND-SYMPTOM-PERSISTS-001"
        ]
        invalid_rows.append(immediate_not_required)

        for row in invalid_rows:
            with self.subTest(basis=row["consultation_basis_codes"]):
                self.assertTrue(self._schema_errors(row))
                self.assertTrue(validate_case_logic(row))

    def test_source_condition_basis_requires_traceable_condition_id(self) -> None:
        missing = _valid_case()
        missing["expected_consultation_requirement"] = "CONDITIONAL"
        missing["consultation_basis_codes"] = ["SOURCE_CONDITION_PENDING"]

        stray = _valid_case()
        stray["consultation_condition_ids"] = ["COND-SYMPTOM-PERSISTS-001"]

        self.assertIn(
            "SOURCE_CONDITION_REFERENCE_REQUIRED",
            {error["code"] for error in validate_case_logic(missing)},
        )
        self.assertIn(
            "CONDITION_REFERENCE_WITHOUT_SOURCE_BASIS",
            {error["code"] for error in validate_case_logic(stray)},
        )
        self.assertTrue(self._schema_errors(missing))
        self.assertTrue(self._schema_errors(stray))

    def test_danger_and_total_stop_require_safety_basis_and_consultation(self) -> None:
        valid = _valid_case()
        valid.update({
            "expected_risk_level": "danger",
            "expected_usage_guidance_status": "TOTAL_STOP",
            "expected_consultation_requirement": "REQUIRED",
            "consultation_basis_codes": ["DANGER_SAFETY"],
        })
        self.assertEqual(self._schema_errors(valid), [])
        self.assertEqual(validate_case_logic(valid), [])

        invalid = copy.deepcopy(valid)
        invalid["consultation_basis_codes"] = ["SOURCE_CONDITION_MET"]
        error_codes = {error["code"] for error in validate_case_logic(invalid)}
        self.assertIn("DANGER_REQUIRES_SAFETY_BASIS", error_codes)
        self.assertTrue(self._schema_errors(invalid))

    def test_consultation_bases_cannot_claim_an_unrelated_semantic_path(self) -> None:
        invalid_rows: list[tuple[dict[str, object], str]] = []

        no_evidence_on_positive = _valid_case()
        no_evidence_on_positive.update({
            "expected_consultation_requirement": "REQUIRED",
            "consultation_basis_codes": ["NO_EVIDENCE"],
        })
        invalid_rows.append(
            (no_evidence_on_positive, "NO_EVIDENCE_BASIS_PATH_MISMATCH")
        )

        policy_block_on_query = _valid_case()
        policy_block_on_query.update({
            "expected_consultation_requirement": "REQUIRED",
            "consultation_basis_codes": ["POLICY_BLOCK"],
        })
        invalid_rows.append(
            (policy_block_on_query, "POLICY_BLOCK_BASIS_PATH_MISMATCH")
        )

        danger_basis_on_general = _valid_case()
        danger_basis_on_general.update({
            "expected_usage_guidance_status": "PARTIAL_STOP",
            "expected_consultation_requirement": "REQUIRED",
            "consultation_basis_codes": ["DANGER_SAFETY"],
        })
        invalid_rows.append(
            (danger_basis_on_general, "DANGER_BASIS_REQUIRES_DANGER_RISK")
        )

        total_stop_on_general = _valid_case()
        total_stop_on_general.update({
            "expected_usage_guidance_status": "TOTAL_STOP",
            "expected_consultation_requirement": "REQUIRED",
            "consultation_basis_codes": ["DANGER_SAFETY"],
        })
        invalid_rows.append(
            (total_stop_on_general, "TOTAL_STOP_REQUIRES_DANGER_RISK")
        )

        for row, expected_code in invalid_rows:
            with self.subTest(expected_code=expected_code):
                self.assertTrue(self._schema_errors(row))
                self.assertIn(
                    expected_code,
                    {error["code"] for error in validate_case_logic(row)},
                )

    def test_danger_cannot_use_normal_or_pending_consultation_status(self) -> None:
        for usage in ("NORMAL", "PENDING_CONSULTATION"):
            row = _valid_case()
            row.update({
                "expected_risk_level": "danger",
                "expected_usage_guidance_status": usage,
                "expected_consultation_requirement": "REQUIRED",
                "consultation_basis_codes": ["DANGER_SAFETY"],
            })

            with self.subTest(usage=usage):
                self.assertTrue(self._schema_errors(row))
                self.assertIn(
                    "DANGER_USAGE_STATUS_INVALID",
                    {error["code"] for error in validate_case_logic(row)},
                )

    def test_target_product_cannot_also_be_forbidden(self) -> None:
        row = _valid_case()
        row["forbidden_model_codes"] = [row["product_model_code"]]

        self.assertIn(
            "TARGET_MODEL_FORBIDDEN",
            {error["code"] for error in validate_case_logic(row)},
        )

    def test_evaluation_and_review_rejection_statuses_cannot_conflict(self) -> None:
        active_rejected = _valid_case()
        active_rejected["review_status"] = "REJECTED"
        active_rejected["reviewer_ids"] = ["reviewer-a"]

        rejected_unreviewed = _valid_case()
        rejected_unreviewed["evaluation_status"] = "REJECTED"

        for row in (active_rejected, rejected_unreviewed):
            with self.subTest(status=row["evaluation_status"]):
                self.assertTrue(self._schema_errors(row))
                self.assertTrue(validate_case_logic(row))

    def test_danger_and_policy_block_can_retain_both_consultation_bases(self) -> None:
        row = _valid_case()
        row.update({
            "expected_retrieval_outcome": "NO_EVIDENCE",
            "expected_execution_path": "POLICY_BLOCK_UNSUPPORTED_MODEL",
            "required_evidence_group_ids": [],
            "supporting_evidence_group_ids": [],
            "evidence_match_policy": "NONE",
            "expected_risk_level": "danger",
            "expected_usage_guidance_status": "TOTAL_STOP",
            "expected_consultation_requirement": "REQUIRED",
            "consultation_basis_codes": ["DANGER_SAFETY", "POLICY_BLOCK"],
        })

        self.assertEqual(self._schema_errors(row), [])
        self.assertEqual(validate_case_logic(row), [])

    def test_qa_report_keeps_corpus_compatibility_as_separate_gate(self) -> None:
        row = _valid_case()
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_path = Path(temp_dir) / "rag_gold_v2.jsonl"
            dataset_path.write_text(
                json.dumps(row, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            report = build_qa_report(dataset_path, SCHEMA_PATH)

        self.assertEqual(report["status"], "STRUCTURAL_PASS_HUMAN_REVIEW_PENDING")
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["records_found"], 1)
        self.assertEqual(
            report["decision"]["gold_corpus_compatibility"],
            "NOT_CHECKED_BY_THIS_VALIDATOR",
        )
        self.assertEqual(report["decision"]["official_metric_use"], "BLOCKED")

    def test_same_query_is_allowed_for_different_product_models(self) -> None:
        first = _valid_case()
        second = copy.deepcopy(first)
        second["case_id"] = "RAGV2-GOLD-0002"
        second["product_model_code"] = "WPUIAC425SNW"
        second["required_evidence_group_ids"] = ["EVD-WPUIAC425SNW-NO-WATER-001"]
        second["forbidden_model_codes"] = ["WPUJAC104DWH", "WPUIAC606SNW"]

        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_path = Path(temp_dir) / "rag_gold_v2.jsonl"
            dataset_path.write_text(
                "".join(
                    json.dumps(row, ensure_ascii=False) + "\n"
                    for row in (first, second)
                ),
                encoding="utf-8",
            )
            report = build_qa_report(dataset_path, SCHEMA_PATH)

        self.assertEqual(report["summary"]["errors"], 0)

    def test_schema_invalid_row_is_reported_without_stopping_qa(self) -> None:
        row = _valid_case()
        del row["consultation_basis_codes"]

        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_path = Path(temp_dir) / "rag_gold_v2.jsonl"
            dataset_path.write_text(
                json.dumps(row, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            report = build_qa_report(dataset_path, SCHEMA_PATH)

        self.assertEqual(report["status"], "FAIL")
        self.assertTrue(any(
            error["code"] == "SCHEMA_VALIDATION_ERROR"
            for error in report["errors"]
        ))


if __name__ == "__main__":
    unittest.main()
