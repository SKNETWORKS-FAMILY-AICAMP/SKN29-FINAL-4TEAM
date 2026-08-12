from __future__ import annotations

import json
import unittest

from jsonschema import Draft202012Validator

from ai.evaluation.file_integrity import canonical_file_bytes, file_sha256

from ai.scripts.build_gold_evaluation_v1 import (
    OUTPUT_DATASET,
    OUTPUT_MANIFEST,
    REPOSITORY_ROOT,
    SCHEMA_PATH,
    _jsonl_bytes,
    build_cases,
)
from ai.scripts.validate_gold_evaluation_v1 import build_qa_report


class GoldEvaluationDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset_path = REPOSITORY_ROOT / OUTPUT_DATASET
        cls.manifest_path = REPOSITORY_ROOT / OUTPUT_MANIFEST
        cls.schema_path = REPOSITORY_ROOT / SCHEMA_PATH
        cls.rows = [
            json.loads(line)
            for line in cls.dataset_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        cls.schema = json.loads(cls.schema_path.read_text(encoding="utf-8"))

    def test_60_cases_match_schema_and_required_distribution(self) -> None:
        validator = Draft202012Validator(self.schema)
        errors = [
            error.message
            for row in self.rows
            for error in validator.iter_errors(row)
        ]
        self.assertEqual(errors, [])
        self.assertEqual(len(self.rows), 60)
        self.assertEqual(
            {kind: sum(row["query_variant_type"] == kind for row in self.rows) for kind in {
                "DIRECT", "COLLOQUIAL", "TYPO_ABBREVIATION", "COMPOUND",
                "SAFETY", "NO_EVIDENCE", "CROSS_PRODUCT",
            }},
            {
                "DIRECT": 20,
                "COLLOQUIAL": 10,
                "TYPO_ABBREVIATION": 5,
                "COMPOUND": 5,
                "SAFETY": 10,
                "NO_EVIDENCE": 5,
                "CROSS_PRODUCT": 5,
            },
        )
        self.assertEqual(
            {split: sum(row["split"] == split for row in self.rows) for split in {
                "DEV", "TEST", "SAFETY",
            }},
            {"DEV": 35, "TEST": 15, "SAFETY": 10},
        )

    def test_labels_are_chunk_independent_and_not_auto_approved(self) -> None:
        self.assertTrue(all("expected_chunk_ids" not in row for row in self.rows))
        self.assertTrue(all(row["review_status"] == "UNREVIEWED_DRAFT" for row in self.rows))
        self.assertTrue(all(row["reviewer_ids"] == [] for row in self.rows))
        self.assertTrue(all(
            row["label_generation"] == "ASSISTED_DRAFT_NOT_APPROVED"
            for row in self.rows
        ))
        self.assertTrue(all(
            row["expected_evidence"] == [] and row["evidence_match_policy"] == "NONE"
            for row in self.rows
            if row["expected_no_evidence"]
        ))

    def test_d02_leak_cases_use_visually_verified_page_lineage(self) -> None:
        rows_by_id = {row["case_id"]: row for row in self.rows}
        for case_id in ("RAGV2-GOLD-0004", "RAGV2-GOLD-0027"):
            case = rows_by_id[case_id]
            self.assertEqual(case["dataset_version"], "1.0.0-draft.2")
            self.assertEqual(case["evidence_match_policy"], "ANY")
            self.assertEqual(case["expected_evidence"][0]["page_refs"], [5, 7, 38])
            self.assertEqual(
                case["expected_evidence"][0]["evidence_unit_id"],
                "EVD-WPUJAC104DWH-LEAK-001",
            )

    def test_builder_is_byte_deterministic_and_manifest_hash_matches(self) -> None:
        self.assertEqual(canonical_file_bytes(self.dataset_path), _jsonl_bytes(build_cases()))
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        actual_hash = file_sha256(self.dataset_path)
        self.assertEqual(manifest["dataset"]["sha256"], actual_hash)
        self.assertEqual(manifest["approval_policy"]["current_approved_records"], 0)

    def test_qa_passes_with_human_review_explicitly_pending(self) -> None:
        report = build_qa_report(
            self.dataset_path,
            self.manifest_path,
            self.schema_path,
        )
        self.assertEqual(report["status"], "STRUCTURAL_PASS_HUMAN_REVIEW_PENDING")
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["records_found"], 60)
        self.assertEqual(report["summary"]["review_pending_records"], 60)
        self.assertEqual(report["decision"]["experiment_draft_use"], "READY")
        self.assertEqual(report["decision"]["gold_approved_use"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
