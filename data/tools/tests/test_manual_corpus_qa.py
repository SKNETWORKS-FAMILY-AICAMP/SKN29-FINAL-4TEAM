from __future__ import annotations

import unittest

from data.tools.rag_experiments.qa_manual_pages import (
    REPOSITORY_ROOT,
    build_qa_report,
)


class ManualCorpusQaTests(unittest.TestCase):
    def test_jac104_full_page_dataset_is_structurally_ready(self) -> None:
        report = build_qa_report(
            REPOSITORY_ROOT
            / "data/processed/documents/manuals/mvp/manual_pages_jac104d.jsonl",
            REPOSITORY_ROOT / "data/schemas/processed/manualPage.schema.json",
        )

        self.assertEqual(report["status"], "STRUCTURAL_PASS_VISUAL_REVIEW_PENDING")
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["pages_found"], 44)
        self.assertEqual(report["summary"]["unique_pages"], 44)
        self.assertEqual(report["summary"]["missing_pages"], [])
        self.assertEqual(report["summary"]["duplicate_pages"], [])
        self.assertEqual(report["summary"]["duplicate_text_groups"], [])
        self.assertEqual(report["summary"]["blank_text_pages"], [])
        self.assertEqual(report["summary"]["text_hash_mismatch_pages"], [])
        self.assertEqual(report["summary"]["mojibake_pages"], [])
        self.assertEqual(report["summary"]["visual_review_pending_count"], 42)
        self.assertEqual(report["decision"]["experimental_corpus_text_use"], "READY")
        self.assertEqual(report["decision"]["gold_evidence_use"], "REVIEW_REQUIRED")
        self.assertEqual(report["source_binary_verification"]["status"], "NOT_PROVIDED")


if __name__ == "__main__":
    unittest.main()
