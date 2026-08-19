from __future__ import annotations

import json
import unittest

from data.tools.rag_experiments.build_iac425_pages import (
    DOCUMENT_ID,
    REPOSITORY_ROOT,
    _section,
    normalize_extracted_text,
)
from data.tools.rag_experiments.qa_iac425_pages import build_qa_report


class Iac425ManualCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset_path = (
            REPOSITORY_ROOT
            / "data/processed/documents/manuals/expansion/manual_pages_iac425.jsonl"
        )
        cls.schema_path = (
            REPOSITORY_ROOT
            / "data/schemas/processed/experimentalManualPage.schema.json"
        )
        cls.rows = [
            json.loads(line)
            for line in cls.dataset_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_dataset_has_52_expansion_only_pages(self) -> None:
        self.assertEqual(len(self.rows), 52)
        self.assertEqual([row["page"] for row in self.rows], list(range(1, 53)))
        self.assertTrue(all(row["document_id"] == DOCUMENT_ID for row in self.rows))
        self.assertTrue(all(row["mvp_use"] is False for row in self.rows))
        self.assertTrue(all(row["allowed_use"] == "REFERENCE_ONLY" for row in self.rows))
        self.assertTrue(all(row["text"].strip() for row in self.rows))
        self.assertIn("고객상담센터 1600-1661", self.rows[-1]["text"])

    def test_dataset_uses_platform_independent_lf_line_endings(self) -> None:
        self.assertNotIn(b"\r", self.dataset_path.read_bytes())

    def test_known_extraction_corrections_are_explicit(self) -> None:
        page_one, ids = normalize_extracted_text(
            "1\nWater Puri/f_ier with Ice Dispenser",
            1,
        )
        self.assertEqual(page_one, "Water Purifier with Ice Dispenser")
        self.assertEqual(ids, ["IAC425-P001-CORRECTION-01"])
        self.assertEqual(_section(43), (
            "IAC425-SECTION-TROUBLESHOOTING",
            "고장 신고 전 확인하기",
        ))

    def test_generated_dataset_passes_minimum_qa(self) -> None:
        report = build_qa_report(self.dataset_path, self.schema_path)
        self.assertEqual(report["status"], "RAG_SELECTED_PAGES_VERIFIED_REFERENCE_READY")
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["pages_found"], 52)
        self.assertEqual(report["summary"]["blank_text_pages"], [])
        self.assertEqual(report["summary"]["text_hash_mismatch_pages"], [])
        self.assertEqual(report["summary"]["visual_review_pending_count"], 42)
        self.assertEqual(report["decision"]["experimental_corpus_text_use"], "READY")
        self.assertEqual(report["decision"]["mvp_search_use"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
