from __future__ import annotations

from copy import deepcopy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.builders import build_synthetic_preview
from watercare.config import load_pipeline
from watercare.io import read_json, sha256_file
from watercare.validation import validate_manual_three_model_candidates


LEGACY_PRODUCT_CANDIDATE_SHA256 = (
    "12CB780CCCE1AF1201390A05E687CF9084826F8B8AC191C63DC550F138123F71"
)


class ManualThreeModelCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)
        cls.output_path = cls.config.path("manual_three_model_candidate_output")
        cls.rows = read_json(cls.output_path)
        cls.by_id = {row["scenario_id"]: row for row in cls.rows}

    def test_candidate_gate_passes_for_all_30_scenarios(self) -> None:
        report = validate_manual_three_model_candidates(self.config)
        self.assertEqual([], report["errors"])
        self.assertEqual("PASS", report["status"])
        self.assertEqual(30, report["records"])

    def test_model_families_have_ten_cases_each(self) -> None:
        counts = {
            prefix: sum(row["scenario_id"].startswith(prefix) for row in self.rows)
            for prefix in ("SYN-IAC425-", "SYN-IAC606-", "SYN-JAC104-")
        }
        self.assertEqual(
            {"SYN-IAC425-": 10, "SYN-IAC606-": 10, "SYN-JAC104-": 10},
            counts,
        )

    def test_output_matches_deterministic_builder(self) -> None:
        path, content, records = build_synthetic_preview(self.config)[
            "manual_three_model_candidates"
        ]
        self.assertEqual(30, records)
        self.assertEqual(path.read_bytes(), content)

    def test_iac_ids_are_renumbered_and_source_ids_are_preserved(self) -> None:
        for family in ("IAC425", "IAC606"):
            for source_index in range(1, 11):
                canonical_id = f"SYN-{family}-{source_index + 100:03d}"
                self.assertEqual(
                    f"SYN-{family}-{source_index:03d}",
                    self.by_id[canonical_id]["source_design_id"],
                )

    def test_mvp_iac_current_and_target_are_separate(self) -> None:
        for row in self.rows:
            if not row["scenario_id"].startswith(("SYN-IAC425-", "SYN-IAC606-")):
                continue
            profile = row["runtime_profiles"]["mvp"]
            current = profile["current_runtime"]
            target = profile["target_oracle"]
            is_leak = row["scenario_id"] in {
                "SYN-IAC425-108",
                "SYN-IAC606-107",
            }
            self.assertEqual("FALLBACK", current["ai"]["execution_status"])
            self.assertEqual(
                "VALIDATING" if is_leak else "RETRIEVING",
                current["ai"]["failure_stage"],
            )
            self.assertEqual(
                "danger" if is_leak else "caution",
                current["ai"]["risk_level"],
            )
            self.assertEqual(
                "TOTAL_STOP" if is_leak else "PENDING_CONSULTATION",
                current["ai"]["usage_guidance_status"],
            )
            self.assertTrue(current["ai"]["requires_consultation"])
            self.assertEqual(
                ["RUNTIME_PRODUCT_NOT_APPROVED"],
                current["ai"]["internal_issue_codes"],
            )
            self.assertIsNone(current["backend"]["event_candidate"])
            self.assertEqual("HOLD", target["verification_status"])
            self.assertEqual(
                "PRODUCT_VALIDATION_FAILED",
                target["backend"]["event_candidate"],
            )

    def test_hot_water_and_long_absence_target_policies(self) -> None:
        for scenario_id in (
            "SYN-IAC425-109",
            "SYN-IAC606-108",
            "SYN-JAC104-031",
        ):
            target = self.by_id[scenario_id]["runtime_profiles"][
                "three_model_integration"
            ]["target_oracle"]
            self.assertEqual("HOLD", target["verification_status"])
            self.assertEqual("danger", target["ai"]["risk_level"])
            self.assertEqual(
                "PARTIAL_STOP", target["ai"]["usage_guidance_status"]
            )
            self.assertTrue(target["ai"]["requires_consultation"])
        absence = self.by_id["SYN-IAC606-109"]["runtime_profiles"][
            "three_model_integration"
        ]["target_oracle"]
        self.assertEqual("general", absence["ai"]["risk_level"])
        self.assertEqual("PARTIAL_STOP", absence["ai"]["usage_guidance_status"])
        self.assertFalse(absence["ai"]["requires_consultation"])
        self.assertIsNone(absence["backend"]["event_candidate"])
        self.assertEqual(
            "SELF_RESOLUTION",
            self.by_id["SYN-IAC606-109"]["workflow_kind"],
        )
        self.assertEqual(
            "SELF_RESOLUTION_AFTER_CUSTOMER_CONFIRMATION",
            self.by_id["SYN-IAC606-109"]["expected_outcome"],
        )

    def test_reopened_base_and_followup_are_distinct_phases(self) -> None:
        phases = self.by_id["SYN-IAC606-103"]["workflow_phases"]
        self.assertEqual("REOPENED", phases[0]["success_state"])
        self.assertEqual(
            ["CUSTOMER_REPORTED_UNRESOLVED"],
            [step["event"] for step in phases[0]["steps"]],
        )
        self.assertEqual("CONSULTATION_IN_PROGRESS", phases[1]["success_state"])
        self.assertEqual(
            ["RESUME_CONSULTATION", "START_CONSULTATION"],
            [step["event"] for step in phases[1]["steps"]],
        )

    def test_negative_cases_have_no_expected_evidence(self) -> None:
        for scenario_id in (
            "SYN-IAC425-110",
            "SYN-IAC606-110",
            "SYN-JAC104-032",
            "SYN-JAC104-033",
            "SYN-JAC104-034",
        ):
            retrieval = self.by_id[scenario_id]["retrieval_expectation"]
            self.assertEqual([], retrieval["expected_evidence_group_ids"])
            self.assertTrue(retrieval["expected_no_evidence"])

    def test_all_26_referenced_evidence_groups_are_preserved(self) -> None:
        evidence_ids = {
            evidence_id
            for row in self.rows
            for evidence_id in row["retrieval_expectation"][
                "expected_evidence_group_ids"
            ]
        }
        self.assertEqual(26, len(evidence_ids))

    def test_common_questions_and_product_targets_are_separate(self) -> None:
        expected_common_ids = {
            "followup-occurrence-time",
            "followup-target-water-type",
            "followup-occurrence-condition",
            "followup-actions-taken",
        }
        for row in self.rows:
            questions = row["question_expectations"]
            self.assertEqual(
                expected_common_ids,
                {item["question_id"] for item in questions["common"]},
            )
            self.assertIn("product_specific_target", questions)

    def test_validator_rejects_golden_claim(self) -> None:
        tampered = deepcopy(self.rows)
        tampered[0]["promotion"]["golden"] = True
        real_read_json = read_json

        def substitute(path: Path):
            if Path(path).resolve() == self.output_path.resolve():
                return tampered
            return real_read_json(path)

        with patch("watercare.validation.read_json", side_effect=substitute):
            report = validate_manual_three_model_candidates(self.config)
        self.assertIn(
            f"manual_candidates:golden_claim:{tampered[0]['scenario_id']}",
            report["errors"],
        )

    def test_legacy_product_candidate_is_byte_identical(self) -> None:
        self.assertEqual(
            LEGACY_PRODUCT_CANDIDATE_SHA256,
            sha256_file(self.config.path("product_expansion_candidate_output")),
        )


if __name__ == "__main__":
    unittest.main()
