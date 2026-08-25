from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jsonschema import Draft202012Validator

from data.tools.rag_experiments.build_gold_query_label_revalidation import build


REPO_ROOT = Path(__file__).resolve().parents[3]
GOLD_PATH = REPO_ROOT / "ai/evaluation/datasets/gold/rag_gold_v1.jsonl"
PACKET_PATH = (
    REPO_ROOT
    / "data/processed/validation/rag_experiments"
    / "gold_v1_post_query_label_revalidation_packet.json"
)
SCHEMA_PATH = (
    REPO_ROOT
    / "data/schemas/config/goldPostQueryLabelRevalidationPacket.schema.json"
)
WORKING_REVIEW_PATH = (
    REPO_ROOT
    / "data/processed/validation/rag_experiments"
    / "gold_v1_post_query_label_human_review_working.json"
)
EXPECTED_GOLD_SHA256 = (
    "9B52AF026B7C8F21AC4D59ECD4D0F2E1A528E78448225EBE1F5E542A71A8E54A"
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class GoldPostQueryLabelRevalidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.packet = _read_json(PACKET_PATH)
        cls.by_id = {row["case_id"]: row for row in cls.packet["reviews"]}

    def test_packet_matches_schema_and_pinned_gold(self) -> None:
        errors = list(
            Draft202012Validator(_read_json(SCHEMA_PATH)).iter_errors(self.packet)
        )
        self.assertEqual([], errors, [error.message for error in errors])
        self.assertEqual(EXPECTED_GOLD_SHA256, hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest().upper())
        self.assertEqual(EXPECTED_GOLD_SHA256, self.packet["source_dataset"]["sha256"])

    def test_all_cases_are_revalidated_without_human_signoff_claim(self) -> None:
        self.assertEqual(60, len(self.by_id))
        self.assertEqual(
            {
                "CHANGE_PROPOSED": 7,
                "REJECT_PROPOSED": 1,
                "SOURCE_CHECK_REQUIRED": 19,
                "SUPPORTED": 33,
            },
            self.packet["summary"]["assessment_counts"],
        )
        self.assertEqual(0, self.packet["summary"]["human_signed_records"])
        self.assertTrue(
            all(row["human_signoff_status"] == "PENDING" for row in self.by_id.values())
        )

    def test_expected_change_and_reject_cases_are_explicit(self) -> None:
        changed = {
            case_id
            for case_id, row in self.by_id.items()
            if row["assistant_assessment"] == "CHANGE_PROPOSED"
        }
        self.assertEqual(
            {
                "RAGV2-GOLD-0001",
                "RAGV2-GOLD-0016",
                "RAGV2-GOLD-0017",
                "RAGV2-GOLD-0028",
                "RAGV2-GOLD-0033",
                "RAGV2-GOLD-0039",
                "RAGV2-GOLD-0047",
            },
            changed,
        )
        self.assertEqual(
            "REJECT_PROPOSED",
            self.by_id["RAGV2-GOLD-0040"]["assistant_assessment"],
        )
        self.assertIsNone(self.by_id["RAGV2-GOLD-0040"]["approved_query"])

    def test_compound_and_conditional_source_checks_are_preserved(self) -> None:
        for case_id in ("RAGV2-GOLD-0036", "RAGV2-GOLD-0037", "RAGV2-GOLD-0038"):
            self.assertEqual("SUPPORTED", self.by_id[case_id]["assistant_assessment"])
            self.assertIn(
                "COMPOUND_ALL_EVIDENCE_CONFIRMATION",
                self.by_id[case_id]["required_human_checks"],
            )
        for case_id in ("RAGV2-GOLD-0045", "RAGV2-GOLD-0049"):
            self.assertEqual("SOURCE_CHECK_REQUIRED", self.by_id[case_id]["assistant_assessment"])
            self.assertTrue(self.by_id[case_id]["proposed_changes"])

    def test_rebuild_is_byte_identical(self) -> None:
        with TemporaryDirectory() as directory:
            rebuilt = Path(directory) / PACKET_PATH.name
            build(rebuilt)
            self.assertEqual(PACKET_PATH.read_bytes(), rebuilt.read_bytes())

    def test_primary_label_working_log_records_0001_without_signoff(self) -> None:
        working = _read_json(WORKING_REVIEW_PATH)
        self.assertEqual(
            "GOLD_POST_QUERY_LABEL_PRIMARY_REVIEW_COMPLETED_HUMAN_SIGNOFF_PENDING",
            working["status"],
        )
        self.assertEqual(EXPECTED_GOLD_SHA256, working["source_dataset"]["sha256"])
        self.assertEqual(60, working["summary"]["reviewed_records"])
        self.assertEqual(8, working["summary"]["human_decision_records"])
        self.assertEqual(18, working["summary"]["ai_resolution_records"])
        self.assertEqual(33, working["summary"]["packet_supported_records"])
        self.assertEqual(1, working["summary"]["query_rejection_records"])
        self.assertEqual(0, working["summary"]["unresolved_primary_records"])
        self.assertEqual(0, working["summary"]["primary_human_action_required_records"])
        self.assertEqual("PENDING", working["summary"]["human_signoff_status"])
        self.assertEqual("PENDING", working["summary"]["second_review_status"])
        self.assertEqual("PENDING", working["reviewer"]["signoff_status"])
        self.assertEqual(8, len(working["decisions"]))
        decisions = {row["case_id"]: row for row in working["decisions"]}
        self.assertEqual("0001-LA", decisions["RAGV2-GOLD-0001"]["decision_code"])
        self.assertEqual("KEEP_CURRENT_LABELS", decisions["RAGV2-GOLD-0001"]["decision"])
        self.assertEqual(
            "PARTIAL_STOP",
            decisions["RAGV2-GOLD-0001"]["approved_labels"]["expected_guidance_policy"],
        )
        self.assertEqual(
            "caution",
            decisions["RAGV2-GOLD-0001"]["approved_labels"]["expected_risk_level"],
        )
        self.assertEqual("0016-LB", decisions["RAGV2-GOLD-0016"]["decision_code"])
        self.assertEqual(
            "APPROVE_PROPOSED_LABEL_CHANGE",
            decisions["RAGV2-GOLD-0016"]["decision"],
        )
        self.assertEqual(
            "PENDING_CONSULTATION",
            decisions["RAGV2-GOLD-0016"]["approved_labels"]["expected_guidance_policy"],
        )
        self.assertEqual(
            "general",
            decisions["RAGV2-GOLD-0016"]["approved_labels"]["expected_risk_level"],
        )
        self.assertEqual("0041-H-A", decisions["RAGV2-GOLD-0041"]["decision_code"])
        self.assertEqual(
            "CONFIRM_SOURCE_AND_KEEP_CURRENT_LABELS",
            decisions["RAGV2-GOLD-0041"]["decision"],
        )
        self.assertEqual(
            "CONFIRMED_BY_PRIMARY_REVIEWER",
            decisions["RAGV2-GOLD-0041"]["source_visual_confirmation"]["status"],
        )
        self.assertEqual(
            "TOTAL_STOP",
            decisions["RAGV2-GOLD-0041"]["approved_labels"]["expected_guidance_policy"],
        )
        self.assertEqual("0042-H-A", decisions["RAGV2-GOLD-0042"]["decision_code"])
        self.assertEqual(
            "TOTAL_STOP",
            decisions["RAGV2-GOLD-0042"]["approved_labels"]["expected_guidance_policy"],
        )
        self.assertEqual("0043-H-A", decisions["RAGV2-GOLD-0043"]["decision_code"])
        self.assertEqual(
            "플러그 주변이 젖어 있고 전원 코드가 뜨거워요. 지금 어떻게 해야 하나요?",
            decisions["RAGV2-GOLD-0043"]["approved_query"],
        )
        self.assertEqual(
            "TOTAL_STOP",
            decisions["RAGV2-GOLD-0043"]["approved_labels"]["expected_guidance_policy"],
        )
        self.assertEqual("0045-H-A", decisions["RAGV2-GOLD-0045"]["decision_code"])
        self.assertEqual(
            "ALL",
            decisions["RAGV2-GOLD-0045"]["approved_labels"]["evidence_match_policy"],
        )
        self.assertEqual(
            [
                "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P004",
                "MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00-P005",
            ],
            decisions["RAGV2-GOLD-0045"]["approved_labels"]["evidence_unit_ids"],
        )
        self.assertEqual("0049-H-B", decisions["RAGV2-GOLD-0049"]["decision_code"])
        self.assertIn(
            "정수기에서 타는 냄새",
            decisions["RAGV2-GOLD-0049"]["approved_query"],
        )
        self.assertEqual(
            "ALL",
            decisions["RAGV2-GOLD-0049"]["approved_labels"]["evidence_match_policy"],
        )
        self.assertEqual("0051-N-A", decisions["RAGV2-GOLD-0051"]["decision_code"])
        self.assertTrue(
            decisions["RAGV2-GOLD-0051"]["approved_labels"]["expected_no_evidence"]
        )
        self.assertEqual(
            "NONE",
            decisions["RAGV2-GOLD-0051"]["approved_labels"]["evidence_match_policy"],
        )
        self.assertEqual(
            "CONFIRMED_BY_PRIMARY_REVIEWER",
            decisions["RAGV2-GOLD-0051"]["corpus_absence_confirmation"]["status"],
        )
        ai_resolutions = {
            row["case_id"]: row for row in working["ai_resolutions"]
        }
        self.assertEqual(
            {
                "RAGV2-GOLD-0017",
                "RAGV2-GOLD-0028",
                "RAGV2-GOLD-0033",
                "RAGV2-GOLD-0039",
                "RAGV2-GOLD-0044",
                "RAGV2-GOLD-0047",
                "RAGV2-GOLD-0046",
                "RAGV2-GOLD-0048",
                "RAGV2-GOLD-0050",
                "RAGV2-GOLD-0052",
                "RAGV2-GOLD-0053",
                "RAGV2-GOLD-0054",
                "RAGV2-GOLD-0055",
                "RAGV2-GOLD-0056",
                "RAGV2-GOLD-0057",
                "RAGV2-GOLD-0058",
                "RAGV2-GOLD-0059",
                "RAGV2-GOLD-0060",
            },
            set(ai_resolutions),
        )
        self.assertTrue(
            all(not row["confirmed_by_primary_reviewer"] for row in ai_resolutions.values())
        )
        self.assertTrue(
            all(row["human_signoff_status"] == "PENDING" for row in ai_resolutions.values())
        )
        self.assertEqual(
            "PENDING_CONSULTATION",
            ai_resolutions["RAGV2-GOLD-0028"]["resolved_labels"]["expected_guidance_policy"],
        )
        self.assertEqual(
            ["EVD-WPUJAC104DWH-NO-WATER-001"],
            ai_resolutions["RAGV2-GOLD-0039"]["resolved_labels"]["evidence_unit_ids"],
        )
        self.assertEqual(
            "PARTIAL_STOP",
            ai_resolutions["RAGV2-GOLD-0047"]["resolved_labels"]["expected_guidance_policy"],
        )
        for case_id in (
            "RAGV2-GOLD-0052",
            "RAGV2-GOLD-0053",
            "RAGV2-GOLD-0054",
            "RAGV2-GOLD-0055",
            "RAGV2-GOLD-0056",
            "RAGV2-GOLD-0057",
            "RAGV2-GOLD-0058",
            "RAGV2-GOLD-0059",
            "RAGV2-GOLD-0060",
        ):
            self.assertTrue(ai_resolutions[case_id]["resolved_labels"]["expected_no_evidence"])
            self.assertEqual(
                "NONE",
                ai_resolutions[case_id]["resolved_labels"]["evidence_match_policy"],
            )


if __name__ == "__main__":
    unittest.main()
