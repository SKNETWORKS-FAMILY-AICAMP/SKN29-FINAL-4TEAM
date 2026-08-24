from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from data.tools.rag_experiments.build_full_corpus_v2_review import build
from data.tools.rag_experiments.qa_full_corpus_v2_review import build_qa_report


REPO_ROOT = Path(__file__).resolve().parents[3]


class FullCorpusV2ReviewTests(unittest.TestCase):
    canonical = (
        REPO_ROOT / "data/processed/structured/rag/experimental/full_corpus_chunks_v2.jsonl",
        REPO_ROOT / "data/processed/structured/rag/experimental/full_corpus_v2_coverage.json",
        REPO_ROOT / "data/processed/validation/rag_experiments/gold_v1_primary_review_packet.json",
        REPO_ROOT / "data/config/rag/iac425_gold_candidates.json",
        REPO_ROOT / "data/processed/metadata/full_corpus_v2_handoff_manifest.json",
    )

    def test_canonical_outputs_pass_all_qa_gates(self) -> None:
        report = build_qa_report(*self.canonical)
        self.assertEqual("PASS", report["status"], report["errors"])
        self.assertEqual(111, report["counts"]["search_candidates"])
        self.assertEqual(60, report["counts"]["gold_reviews"])
        self.assertEqual(18, report["counts"]["iac425_candidates"])

    def test_manifest_pins_the_synced_main_source_commit(self) -> None:
        manifest = json.loads(self.canonical[4].read_text(encoding="utf-8"))
        config = json.loads(
            (
                REPO_ROOT / "data/config/rag/full_corpus_v2_segments.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(config["source_commit"], manifest["source_commit"])
        self.assertEqual(
            "e99cf78faa58a40f2cec49281119c437b594e470",
            manifest["source_commit"],
        )

    def test_rebuild_is_byte_identical(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            generated = tuple(root / path.name for path in self.canonical)
            build(*generated)
            for expected, actual in zip(self.canonical, generated, strict=True):
                self.assertEqual(expected.read_bytes(), actual.read_bytes(), expected.name)

    def test_corpus_counts_and_roles_are_fixed(self) -> None:
        rows = [
            json.loads(line)
            for line in self.canonical[0].read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(111, len(rows))
        self.assertEqual(15, sum(row["record_type"] == "CHILD" for row in rows))
        self.assertEqual(5, sum(row["record_type"] == "PRESERVATION" for row in rows))
        self.assertEqual(91, sum(row["record_type"] == "SOURCE_PAGE" for row in rows))
        self.assertFalse(any(row["retrieval_role"] != "SEARCH_CANDIDATE" for row in rows))

    def test_coverage_assigns_every_line_once(self) -> None:
        coverage = json.loads(self.canonical[1].read_text(encoding="utf-8"))
        self.assertEqual({5, 7, 37, 38, 39}, {row["page"] for row in coverage["pages"]})
        for page in coverage["pages"]:
            self.assertEqual(
                list(range(1, page["total_lines"] + 1)),
                [row["line_number"] for row in page["assignments"]],
            )

    def test_gold_packet_never_claims_human_approval(self) -> None:
        review = json.loads(self.canonical[2].read_text(encoding="utf-8"))
        self.assertEqual(60, len(review["reviews"]))
        self.assertEqual(0, review["summary"]["human_signed_records"])
        self.assertTrue(all(row["human_signoff_status"] == "PENDING" for row in review["reviews"]))
        self.assertEqual(
            {"SUPPORTED": 40, "SOURCE_CHECK_REQUIRED": 18, "CHANGE_PROPOSED": 2},
            review["summary"]["assessment_counts"],
        )
        self.assertEqual(
            {"RAGV2-GOLD-0045", "RAGV2-GOLD-0049"},
            {
                row["case_id"]
                for row in review["reviews"]
                if row["assistant_assessment"] == "CHANGE_PROPOSED"
            },
        )
        self.assertTrue(all(row["case_snapshot"]["query"] for row in review["reviews"]))
        self.assertTrue(
            all(
                row["required_human_checks"][-1]
                == "RECORD_REVIEWER_ID_DECISION_AND_REVIEWED_AT"
                for row in review["reviews"]
            )
        )

    def test_iac425_candidates_reuse_all_existing_positive_queries(self) -> None:
        candidates = json.loads(self.canonical[3].read_text(encoding="utf-8"))["candidates"]
        source = json.loads(
            (REPO_ROOT / "data/config/rag/three_model_evaluation_cases.json").read_text(encoding="utf-8")
        )["cases"]
        positives = {
            row["case_id"]: row["query"]
            for row in source
            if row["case_type"] == "POSITIVE" and row["exact_sales_code"] == "WPUIAC425SNW"
        }
        self.assertEqual(18, len(candidates))
        self.assertEqual(set(positives), {row["source_case_id"] for row in candidates})
        for row in candidates:
            self.assertEqual(positives[row["source_case_id"]], row["query"])
            self.assertEqual("HUMAN_REVIEW_PENDING", row["human_review_status"])


if __name__ == "__main__":
    unittest.main()
