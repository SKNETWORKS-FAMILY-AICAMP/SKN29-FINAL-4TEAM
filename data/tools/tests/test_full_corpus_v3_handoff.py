from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai.scripts.validate_gold_corpus_compatibility_v2 import (
    build_compatibility_report,
)
from data.tools.rag_experiments.build_full_corpus_v3_handoff import build
from data.tools.rag_experiments.qa_full_corpus_v3_handoff import build_qa_report


REPO_ROOT = Path(__file__).resolve().parents[3]


class FullCorpusV3HandoffTests(unittest.TestCase):
    canonical = (
        REPO_ROOT
        / "data/processed/structured/rag/experimental/full_corpus_chunks_v3.jsonl",
        REPO_ROOT
        / "data/processed/structured/rag/experimental/full_corpus_v3_coverage.json",
        REPO_ROOT
        / "data/processed/structured/rag/experimental/full_corpus_v3_context_parents.jsonl",
        REPO_ROOT
        / "data/processed/structured/rag/experimental/full_corpus_v3_children.jsonl",
        REPO_ROOT
        / "data/processed/structured/evidence/full_corpus_v3_evidence_groups.jsonl",
        REPO_ROOT
        / "data/processed/metadata/full_corpus_v3_handoff_manifest.json",
    )

    def test_canonical_outputs_pass_all_data_qa_gates(self) -> None:
        report = build_qa_report(*self.canonical)
        self.assertEqual("PASS", report["status"], report["errors"])
        self.assertEqual(132, report["counts"]["search_candidates"])
        self.assertEqual(34, report["counts"]["evidence_groups"])
        self.assertEqual(37, report["counts"]["children"])
        self.assertEqual(18, report["counts"]["iac425_evidence_groups"])
        self.assertEqual(19, report["counts"]["iac425_children"])

    def test_rebuild_is_byte_identical(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            generated = tuple(root / path.name for path in self.canonical)
            build(*generated)
            for expected, actual in zip(self.canonical, generated, strict=True):
                self.assertEqual(
                    expected.read_bytes(), actual.read_bytes(), expected.name
                )

    def test_source_span_decisions_are_recorded_without_gold_approval(self) -> None:
        review = json.loads(
            (
                REPO_ROOT
                / "data/processed/validation/rag_experiments/"
                "full_corpus_v3_source_span_human_review.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            {"1-A", "2-A", "3-A", "4-A"},
            {row["decision_code"] for row in review["decisions"]},
        )
        self.assertEqual("DATA_QA_SOURCE_SPAN_VERIFIED", review["status"])
        self.assertEqual("HUMAN_SIGNOFF_PENDING", review["gold_signoff_status"])

    def test_fixed_corpus_composition_and_product_isolation(self) -> None:
        rows = [
            json.loads(line)
            for line in self.canonical[0].read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(132, len(rows))
        self.assertEqual(85, sum(row["record_type"] == "SOURCE_PAGE" for row in rows))
        self.assertEqual(37, sum(row["record_type"] == "CHILD" for row in rows))
        self.assertEqual(10, sum(row["record_type"] == "PRESERVATION" for row in rows))
        self.assertEqual(64, sum(row["exact_sales_code"] == "WPUJAC104DWH" for row in rows))
        self.assertEqual(68, sum(row["exact_sales_code"] == "WPUIAC425SNW" for row in rows))

    def test_iac425_group_child_contract_is_fully_linked(self) -> None:
        with TemporaryDirectory() as directory:
            empty_gold = Path(directory) / "empty_gold.jsonl"
            empty_gold.write_text("", encoding="utf-8")
            report = build_compatibility_report(
                empty_gold,
                self.canonical[4],
                self.canonical[3],
                self.canonical[0],
            )
        self.assertEqual("PASS", report["status"], report["error_code_counts"])
        self.assertEqual(34, report["counts"]["linked_evidence_groups"])
        self.assertEqual(37, report["counts"]["linked_group_children"])
        self.assertEqual({}, report["error_code_counts"])

    def test_full_corpus_v2_is_preserved(self) -> None:
        manifest = json.loads(self.canonical[5].read_text(encoding="utf-8"))
        self.assertEqual(
            "2D4A022A8FEABD376C9F5D42E7D28BA8E18571274D19A05794D066B7113D6FC6",
            manifest["preserved_baselines"]["full_corpus_v2_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
