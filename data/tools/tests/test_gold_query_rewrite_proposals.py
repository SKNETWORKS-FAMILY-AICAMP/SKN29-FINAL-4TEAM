from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[3]
GOLD_PATH = REPO_ROOT / "ai/evaluation/datasets/gold/rag_gold_v1.jsonl"
PROPOSAL_PATH = REPO_ROOT / "data/config/rag/gold_v1_query_rewrite_proposals.json"
SCHEMA_PATH = REPO_ROOT / "data/schemas/config/goldQueryRewriteProposals.schema.json"
WORKING_REVIEW_PATH = (
    REPO_ROOT
    / "data/processed/validation/rag_experiments"
    / "gold_v1_query_human_review_working.json"
)
EXPECTED_GOLD_SHA256 = (
    "9B52AF026B7C8F21AC4D59ECD4D0F2E1A528E78448225EBE1F5E542A71A8E54A"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class GoldQueryRewriteProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gold = _read_jsonl(GOLD_PATH)
        cls.proposals = _read_json(PROPOSAL_PATH)
        cls.working_review = _read_json(WORKING_REVIEW_PATH)

    def test_proposal_pack_matches_schema(self) -> None:
        errors = list(
            Draft202012Validator(_read_json(SCHEMA_PATH)).iter_errors(
                self.proposals
            )
        )
        self.assertEqual([], errors, [error.message for error in errors])

    def test_gold_source_is_hash_pinned_and_unmodified(self) -> None:
        self.assertEqual(EXPECTED_GOLD_SHA256, _sha256(GOLD_PATH))
        self.assertEqual(
            EXPECTED_GOLD_SHA256,
            self.proposals["source_dataset"]["sha256"],
        )

    def test_every_gold_case_has_one_variant_preserving_proposal(self) -> None:
        source = {row["case_id"]: row for row in self.gold}
        proposed = {
            row["case_id"]: row for row in self.proposals["proposals"]
        }
        self.assertEqual(60, len(proposed))
        self.assertEqual(set(source), set(proposed))
        for case_id, row in proposed.items():
            self.assertEqual(
                source[case_id]["query_variant_type"],
                row["source_query_variant_type"],
            )

    def test_proposed_queries_are_unique_and_question_like(self) -> None:
        queries = [row["proposed_query"] for row in self.proposals["proposals"]]
        self.assertEqual(60, len(set(queries)))
        self.assertTrue(
            all(query.endswith(("?", "!", ".", "요")) for query in queries),
            queries,
        )
        self.assertFalse(any("즉시 중단해야 하나요" in query for query in queries))

    def test_typo_variants_remain_explicit_chat_variants(self) -> None:
        typo_rows = [
            row
            for row in self.proposals["proposals"]
            if row["source_query_variant_type"] == "TYPO_ABBREVIATION"
        ]
        self.assertEqual(5, len(typo_rows))
        self.assertTrue(
            all(row["rewrite_class"] == "TYPO_VARIANT_PRESERVED" for row in typo_rows)
        )
        joined = " ".join(row["proposed_query"] for row in typo_rows)
        for token in ("나와여", "어떡게", "어케", "넘 커여", "어떻해요", "적어졋어요"):
            self.assertIn(token, joined)

    def test_cross_product_targets_are_not_rewritten_as_supported_models(self) -> None:
        source = {row["case_id"]: row for row in self.gold}
        proposed = {
            row["case_id"]: row["proposed_query"]
            for row in self.proposals["proposals"]
        }
        self.assertEqual(
            "WPU-IAC506",
            source["RAGV2-GOLD-0059"]["product_model_code"],
        )
        self.assertEqual(
            "WPUJAC104SWH",
            source["RAGV2-GOLD-0060"]["product_model_code"],
        )
        self.assertNotIn("WPU-IAC506", proposed["RAGV2-GOLD-0059"])
        self.assertNotIn("S세대", proposed["RAGV2-GOLD-0060"])
        self.assertIn("얼음", proposed["RAGV2-GOLD-0056"])

    def test_primary_human_review_has_one_decision_per_gold_case(self) -> None:
        review = self.working_review
        decisions = review["decisions"]
        source_case_ids = {row["case_id"] for row in self.gold}
        decision_case_ids = {row["case_id"] for row in decisions}

        self.assertEqual(
            "GOLD_QUERY_PRIMARY_REVIEW_COMPLETED_HUMAN_SIGNOFF_PENDING",
            review["status"],
        )
        self.assertEqual(60, review["summary"]["decided_records"])
        self.assertEqual(0, review["summary"]["remaining_records"])
        self.assertEqual("PENDING", review["summary"]["human_signoff_status"])
        self.assertEqual("PENDING", review["reviewer"]["signoff_status"])
        self.assertEqual(EXPECTED_GOLD_SHA256, review["source_dataset"]["sha256"])
        self.assertEqual(60, len(decisions))
        self.assertEqual(list(range(1, 61)), [row["sequence"] for row in decisions])
        self.assertEqual(source_case_ids, decision_case_ids)
        self.assertTrue(all(row["confirmed_by_primary_reviewer"] for row in decisions))

    def test_primary_decisions_match_proposal_pack_or_rejection(self) -> None:
        proposed = {
            row["case_id"]: row for row in self.proposals["proposals"]
        }
        decisions = {
            row["case_id"]: row for row in self.working_review["decisions"]
        }
        rejected = [
            case_id
            for case_id, row in decisions.items()
            if row["decision"] == "QUERY_REJECTION_PROPOSED"
        ]

        self.assertEqual(["RAGV2-GOLD-0040"], rejected)
        self.assertIsNone(decisions["RAGV2-GOLD-0040"]["approved_query"])
        for case_id, decision in decisions.items():
            self.assertEqual(
                proposed[case_id]["intent_change"],
                decision["intent_change"],
            )
            if case_id not in rejected:
                self.assertEqual(
                    proposed[case_id]["proposed_query"],
                    decision["approved_query"],
                )


if __name__ == "__main__":
    unittest.main()
