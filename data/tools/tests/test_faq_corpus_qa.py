from __future__ import annotations

import json
import unittest

from data.tools.rag_experiments.qa_faq_corpus import (
    REPOSITORY_ROOT,
    build_qa_report,
)


class FaqCorpusQaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset_path = (
            REPOSITORY_ROOT
            / "data/processed/documents/faq/faq_snapshot_normalized.jsonl"
        )
        cls.schema_path = (
            REPOSITORY_ROOT / "data/schemas/processed/faqNormalized.schema.json"
        )
        cls.rows = [
            json.loads(line)
            for line in cls.dataset_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_dataset_has_all_119_faq_records(self) -> None:
        self.assertEqual(len(self.rows), 119)
        self.assertEqual(
            [row["ordinal"] for row in self.rows],
            list(range(1, 120)),
        )
        self.assertEqual(len({row["faq_id"] for row in self.rows}), 119)
        self.assertTrue(all(row["mvp_rag_eligible"] is False for row in self.rows))

    def test_text_and_image_only_classification_is_explicit(self) -> None:
        counts = {
            status: sum(row["text_status"] == status for row in self.rows)
            for status in {"PUBLISHER_TEXT", "OCR_VERIFIED", "NOT_TRANSCRIBED"}
        }
        self.assertEqual(counts["PUBLISHER_TEXT"], 111)
        self.assertEqual(counts["OCR_VERIFIED"], 5)
        self.assertEqual(counts["NOT_TRANSCRIBED"], 3)
        self.assertTrue(all(
            row["retrieval_scope"] == "EXCLUDED"
            for row in self.rows
            if row["text_status"] == "NOT_TRANSCRIBED"
        ))

    def test_dataset_passes_structural_qa_without_external_source(self) -> None:
        report = build_qa_report(self.dataset_path, self.schema_path)
        self.assertEqual(report["status"], "STRUCTURAL_PASS_SOURCE_NOT_PROVIDED")
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["records_found"], 119)
        self.assertEqual(report["summary"]["conditional_text_count"], 116)
        self.assertEqual(report["summary"]["image_only_excluded_count"], 3)
        self.assertEqual(report["summary"]["duplicate_title_groups"], [])
        self.assertEqual(report["summary"]["duplicate_answer_groups"], [])
        self.assertEqual(
            report["decision"]["conditional_experimental_text_use"],
            "READY",
        )
        self.assertEqual(report["decision"]["mvp_search_use"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
