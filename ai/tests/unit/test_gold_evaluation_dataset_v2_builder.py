from __future__ import annotations

import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator

from ai.scripts.build_gold_evaluation_v2 import (
    COND_COLD_AFTER_2H,
    COND_HOT_STEAM_PERSISTS,
    COND_LOW_FLOW_AFTER_FILTER,
    COND_NO_WATER_AFTER_FILTER,
    EXCLUDED_REASONS,
    GROUP_BURNING_ODOR,
    GROUP_COLD_FAULT,
    GROUP_COLD_NORMAL,
    GROUP_HOT_STEAM,
    GROUP_LEAK,
    GROUP_LOW_FLOW,
    GROUP_NO_WATER,
    GROUP_SPRAY_PREVENTION,
    IAC425_QUERY_OVERRIDES,
    OUTPUT_DATASET,
    OUTPUT_IAC425_CANDIDATE_MANIFEST,
    OUTPUT_IAC425_CANDIDATES,
    OUTPUT_MANIFEST,
    QUERY_OVERRIDES,
    QUERY_REVIEW_PACKET_PATH,
    REPOSITORY_ROOT,
    SCHEMA_PATH,
    _jsonl_bytes,
    build_cases,
    build_iac425_candidates,
    write_outputs,
)
from ai.scripts.validate_gold_evaluation_v2 import validate_case_logic


class GoldEvaluationDatasetV2BuilderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = build_cases()
        cls.by_id = {case["case_id"]: case for case in cls.cases}

    def test_preserves_sixty_case_ids_and_draft_review_boundary(self) -> None:
        self.assertEqual(len(self.cases), 60)
        self.assertEqual(
            [case["case_id"] for case in self.cases],
            [f"RAGV2-GOLD-{index:04d}" for index in range(1, 61)],
        )
        self.assertEqual(
            Counter(case["evaluation_status"] for case in self.cases),
            Counter({"ACTIVE": 55, "EXCLUDED": 5}),
        )
        self.assertEqual(
            {
                case["case_id"]
                for case in self.cases
                if case["evaluation_status"] == "EXCLUDED"
            },
            set(EXCLUDED_REASONS),
        )
        self.assertTrue(all(
            case["review_status"] == "UNREVIEWED_DRAFT"
            and case["reviewer_ids"] == []
            and case["label_generation"] == "ASSISTED_DRAFT_NOT_APPROVED"
            for case in self.cases
        ))

    def test_uses_packet_approved_queries_except_declared_redrafts(self) -> None:
        packet = json.loads((
            REPOSITORY_ROOT / QUERY_REVIEW_PACKET_PATH
        ).read_text(encoding="utf-8"))
        approved = {
            row["case_id"]: row["approved_query"] for row in packet["reviews"]
        }
        for case in self.cases:
            case_id = case["case_id"]
            if case_id in QUERY_OVERRIDES:
                self.assertEqual(case["query"], QUERY_OVERRIDES[case_id])
            elif case_id != "RAGV2-GOLD-0040":
                self.assertEqual(case["query"], approved[case_id])

    def test_applies_case_specific_evidence_group_decisions(self) -> None:
        case_0039 = self.by_id["RAGV2-GOLD-0039"]
        self.assertEqual(case_0039["query_variant_type"], "DIRECT")
        self.assertEqual(case_0039["required_evidence_group_ids"], [GROUP_NO_WATER])
        self.assertEqual(case_0039["evidence_match_policy"], "ANY")

        case_0045 = self.by_id["RAGV2-GOLD-0045"]
        self.assertEqual(case_0045["evaluation_status"], "ACTIVE")
        self.assertEqual(case_0045["required_evidence_group_ids"], [GROUP_LEAK])
        self.assertEqual(case_0045["expected_risk_level"], "danger")

        case_0049 = self.by_id["RAGV2-GOLD-0049"]
        self.assertEqual(
            case_0049["required_evidence_group_ids"],
            [GROUP_BURNING_ODOR],
        )
        self.assertEqual(
            case_0049["supporting_evidence_group_ids"],
            [GROUP_SPRAY_PREVENTION],
        )
        self.assertEqual(case_0049["evidence_match_policy"], "ANY")

    def test_splits_cold_and_hot_groups_by_meaning(self) -> None:
        for case_id in (
            "RAGV2-GOLD-0002",
            "RAGV2-GOLD-0009",
            "RAGV2-GOLD-0022",
            "RAGV2-GOLD-0030",
            "RAGV2-GOLD-0032",
        ):
            case = self.by_id[case_id]
            self.assertEqual(case["required_evidence_group_ids"], [GROUP_COLD_NORMAL])
            self.assertEqual(case["supporting_evidence_group_ids"], [GROUP_COLD_FAULT])

        case_0016 = self.by_id["RAGV2-GOLD-0016"]
        self.assertEqual(case_0016["required_evidence_group_ids"], [GROUP_COLD_FAULT])
        self.assertEqual(case_0016["supporting_evidence_group_ids"], [GROUP_COLD_NORMAL])

        case_0036 = self.by_id["RAGV2-GOLD-0036"]
        self.assertEqual(
            case_0036["required_evidence_group_ids"],
            [GROUP_COLD_NORMAL, GROUP_LOW_FLOW],
        )
        self.assertEqual(case_0036["evidence_match_policy"], "ALL")
        self.assertEqual(case_0036["supporting_evidence_group_ids"], [GROUP_COLD_FAULT])

        for case_id in (
            "RAGV2-GOLD-0007",
            "RAGV2-GOLD-0014",
            "RAGV2-GOLD-0029",
        ):
            case = self.by_id[case_id]
            self.assertEqual(case["required_evidence_group_ids"], [GROUP_HOT_STEAM])
            self.assertEqual(case["expected_risk_level"], "caution")
            self.assertEqual(case["expected_usage_guidance_status"], "PARTIAL_STOP")

    def test_uses_only_registered_condition_contract_ids(self) -> None:
        expected_ids = {
            COND_NO_WATER_AFTER_FILTER,
            COND_COLD_AFTER_2H,
            COND_LOW_FLOW_AFTER_FILTER,
            COND_HOT_STEAM_PERSISTS,
        }
        actual_ids = {
            condition_id
            for case in self.cases
            for condition_id in case["consultation_condition_ids"]
        }
        self.assertEqual(actual_ids, expected_ids)

        self.assertEqual(
            self.by_id["RAGV2-GOLD-0015"]["consultation_basis_codes"],
            ["SOURCE_CONDITION_MET"],
        )
        self.assertEqual(
            self.by_id["RAGV2-GOLD-0016"]["consultation_basis_codes"],
            ["SOURCE_CONDITION_MET"],
        )
        self.assertEqual(
            self.by_id["RAGV2-GOLD-0036"]["consultation_condition_ids"],
            [COND_COLD_AFTER_2H, COND_LOW_FLOW_AFTER_FILTER],
        )
        for case_id in ("RAGV2-GOLD-0017", "RAGV2-GOLD-0033"):
            case = self.by_id[case_id]
            self.assertEqual(case["evaluation_status"], "EXCLUDED")
            self.assertEqual(case["consultation_condition_ids"], [])
            self.assertEqual(case["consultation_basis_codes"], ["NONE"])

    def test_separates_corpus_absence_and_policy_blocks(self) -> None:
        for case_id in (
            "RAGV2-GOLD-0051",
            "RAGV2-GOLD-0052",
            "RAGV2-GOLD-0053",
            "RAGV2-GOLD-0054",
        ):
            case = self.by_id[case_id]
            self.assertEqual(case["expected_execution_path"], "PGVECTOR_QUERY")
            self.assertEqual(case["consultation_basis_codes"], ["NO_EVIDENCE"])

        case_0055 = self.by_id["RAGV2-GOLD-0055"]
        self.assertEqual(case_0055["evaluation_status"], "ACTIVE")
        self.assertEqual(
            case_0055["expected_execution_path"],
            "POLICY_BLOCK_UNVERIFIED_SOURCE",
        )
        self.assertEqual(case_0055["consultation_basis_codes"], ["POLICY_BLOCK"])

        for case_id in ("RAGV2-GOLD-0056", "RAGV2-GOLD-0057", "RAGV2-GOLD-0058"):
            self.assertEqual(
                self.by_id[case_id]["expected_execution_path"],
                "POLICY_BLOCK_UNSUPPORTED_CAPABILITY",
            )
        for case_id in ("RAGV2-GOLD-0059", "RAGV2-GOLD-0060"):
            self.assertEqual(
                self.by_id[case_id]["expected_execution_path"],
                "POLICY_BLOCK_UNSUPPORTED_MODEL",
            )

    def test_all_rows_pass_schema_and_logic_validation(self) -> None:
        schema = json.loads((
            REPOSITORY_ROOT / SCHEMA_PATH
        ).read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        for case in self.cases:
            self.assertEqual(list(validator.iter_errors(case)), [], case["case_id"])
            self.assertEqual(validate_case_logic(case), [], case["case_id"])

    def test_iac425_candidates_remain_separate_and_unapproved(self) -> None:
        candidates = build_iac425_candidates()
        by_id = {candidate["case_id"]: candidate for candidate in candidates}
        self.assertEqual(len(candidates), 18)
        self.assertEqual(
            [candidate["case_id"] for candidate in candidates],
            [f"RAGV2-GOLD-{index:04d}" for index in range(61, 79)],
        )
        self.assertTrue(all(
            candidate["evaluation_status"] == "ACTIVE"
            and candidate["source_query_origin"] == "CURATED_VARIANT"
            and candidate["source_case_ids"] == []
            and candidate["review_status"] == "UNREVIEWED_DRAFT"
            and candidate["reviewer_ids"] == []
            and "본체에 포함하지 않음" in candidate["review_notes"]
            for candidate in candidates
        ))
        schema = json.loads((
            REPOSITORY_ROOT / SCHEMA_PATH
        ).read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        for candidate in candidates:
            self.assertEqual(
                list(validator.iter_errors(candidate)),
                [],
                candidate["case_id"],
            )
            self.assertEqual(
                validate_case_logic(candidate),
                [],
                candidate["case_id"],
            )

        candidate_002 = by_id["RAGV2-GOLD-0062"]
        self.assertEqual(
            candidate_002["query"],
            IAC425_QUERY_OVERRIDES["RAGV2-IAC425-CAND-002"],
        )
        self.assertEqual(
            candidate_002["consultation_basis_codes"],
            ["SOURCE_CONDITION_MET"],
        )
        self.assertEqual(
            candidate_002["expected_consultation_requirement"],
            "REQUIRED",
        )
        self.assertIn("두 시간이 지나도", candidate_002["query"])

        self.assertEqual(
            by_id["RAGV2-GOLD-0063"]["query"],
            IAC425_QUERY_OVERRIDES["RAGV2-IAC425-CAND-003"],
        )
        candidate_010 = by_id["RAGV2-GOLD-0070"]
        self.assertEqual(
            candidate_010["query"],
            IAC425_QUERY_OVERRIDES["RAGV2-IAC425-CAND-010"],
        )
        self.assertEqual(len(candidate_010["required_evidence_group_ids"]), 1)
        self.assertEqual(candidate_010["expected_risk_level"], "danger")
        self.assertEqual(
            candidate_010["expected_usage_guidance_status"],
            "TOTAL_STOP",
        )
        self.assertIn(
            "CHILD-WPUIAC425SNW-P005-LEAK-001",
            candidate_010["review_notes"],
        )
        self.assertIn(
            "CHILD-WPUIAC425SNW-P045-LEAK-001",
            candidate_010["review_notes"],
        )
        condition_ids = {
            condition_id
            for candidate in candidates
            for condition_id in candidate["consultation_condition_ids"]
        }
        self.assertEqual(len(condition_ids), 6)
        for candidate in candidates:
            if "SOURCE_CONDITION_PENDING" in candidate["consultation_basis_codes"]:
                self.assertIn(
                    candidate["expected_usage_guidance_status"],
                    {"NORMAL", "PARTIAL_STOP"},
                )

        noise_candidate = by_id["RAGV2-GOLD-0075"]
        self.assertEqual(noise_candidate["consultation_basis_codes"], ["NONE"])
        self.assertEqual(
            noise_candidate["expected_usage_guidance_status"],
            "NORMAL",
        )

    def test_repository_outputs_are_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            dataset = temp_root / "rag_gold_v2.jsonl"
            manifest = temp_root / "rag_gold_v2_manifest.json"
            candidates = temp_root / "iac425_candidates.jsonl"
            candidate_manifest = temp_root / "iac425_candidates_manifest.json"
            generated_manifest = write_outputs(
                output_dataset=dataset,
                output_manifest=manifest,
                output_iac425_candidates=candidates,
                output_iac425_candidate_manifest=candidate_manifest,
            )
            self.assertEqual(dataset.read_bytes(), _jsonl_bytes(self.cases))
            self.assertFalse(generated_manifest["official_metrics_publishable"])
            self.assertEqual(generated_manifest["dataset"]["active_records"], 55)
            self.assertEqual(generated_manifest["dataset"]["excluded_records"], 5)
            self.assertEqual(generated_manifest["iac425_candidates"]["records"], 18)
            candidate_manifest_value = json.loads(
                candidate_manifest.read_text(encoding="utf-8")
            )
            self.assertFalse(
                candidate_manifest_value["official_metrics_publishable"]
            )
            self.assertEqual(
                candidate_manifest_value["included_in_main_gold_records"],
                0,
            )
            self.assertEqual(
                candidate_manifest_value["status"],
                "HUMAN_REVIEW_PENDING_NOT_IN_MAIN_GOLD",
            )

        self.assertEqual(
            (REPOSITORY_ROOT / OUTPUT_DATASET).read_bytes(),
            _jsonl_bytes(self.cases),
        )
        manifest_value = json.loads((
            REPOSITORY_ROOT / OUTPUT_MANIFEST
        ).read_text(encoding="utf-8"))
        self.assertFalse(manifest_value["official_metrics_publishable"])
        self.assertEqual(manifest_value["approval_policy"]["official_metric_use"], "BLOCKED")
        self.assertTrue((REPOSITORY_ROOT / OUTPUT_IAC425_CANDIDATES).is_file())
        self.assertTrue((
            REPOSITORY_ROOT / OUTPUT_IAC425_CANDIDATE_MANIFEST
        ).is_file())


if __name__ == "__main__":
    unittest.main()
