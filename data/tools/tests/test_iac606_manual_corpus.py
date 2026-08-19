from __future__ import annotations

import json
import unittest

from data.tools.rag_experiments.build_iac606_pages import (
    DOCUMENT_ID,
    REPOSITORY_ROOT,
    _section,
    normalize_extracted_text,
)
from data.tools.rag_experiments.qa_iac606_pages import build_qa_report


class Iac606ManualCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset_path = REPOSITORY_ROOT / "data/processed/documents/manuals/expansion/manual_pages_iac606.jsonl"
        cls.schema_path = REPOSITORY_ROOT / "data/schemas/processed/experimentalManualPage.schema.json"
        cls.rows = [
            json.loads(line)
            for line in cls.dataset_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_dataset_has_48_reference_only_pages(self) -> None:
        self.assertEqual(len(self.rows), 48)
        self.assertEqual([row["page"] for row in self.rows], list(range(1, 49)))
        self.assertTrue(all(row["document_id"] == DOCUMENT_ID for row in self.rows))
        self.assertTrue(all(row["allowed_use"] == "REFERENCE_ONLY" for row in self.rows))
        self.assertTrue(all(row["mvp_use"] is False for row in self.rows))
        self.assertIn("고객상담센터 1600-1661", self.rows[-1]["text"])

    def test_dataset_uses_platform_independent_lf_line_endings(self) -> None:
        self.assertNotIn(b"\r", self.dataset_path.read_bytes())

    def test_known_extraction_corrections_are_explicit(self) -> None:
        page_one, ids = normalize_extracted_text("1\nWater Puri/f_ier with Ice Dispenser", 1)
        self.assertEqual(page_one, "Water Purifier with Ice Dispenser")
        self.assertEqual(ids, ["IAC606-P001-CORRECTION-01"])
        self.assertEqual(_section(40), ("IAC606-SECTION-TROUBLESHOOTING", "고장 신고 전 확인하기"))

    def test_generated_dataset_passes_qa(self) -> None:
        report = build_qa_report(self.dataset_path, self.schema_path)
        self.assertEqual(report["status"], "RAG_SELECTED_PAGES_VERIFIED_REFERENCE_READY")
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["pages_found"], 48)
        self.assertEqual(report["summary"]["visual_review_pending_count"], 39)


if __name__ == "__main__":
    unittest.main()
