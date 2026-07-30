from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.config import load_pipeline
from watercare.io import read_json
from watercare.validation import validate_schema


class RagEvaluationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)
        cls.contract = cls.config.config("rag_evaluation_cases")
        cls.rag = cls.config.config("rag")

    def test_cases_match_schema_and_cover_every_approved_chunk(self) -> None:
        schema = read_json(
            DATA_ROOT / "schemas/config/ragEvaluationCases.schema.json"
        )
        self.assertEqual([], validate_schema(self.contract, schema))
        positive = [
            row for row in self.contract["cases"] if row["case_type"] == "POSITIVE"
        ]
        self.assertEqual(7, len(positive))
        expected = {
            chunk_id
            for row in positive
            for chunk_id in row["expected_chunk_ids"]
        }
        self.assertEqual(
            {row["chunk_id"] for row in self.rag["chunks"]},
            expected,
        )
        self.assertTrue(
            all(
                row["expected_document_id"] == self.rag["document_id"]
                and not row["expected_no_evidence"]
                for row in positive
            )
        )

    def test_negative_cases_require_no_evidence_and_forbid_sources(self) -> None:
        negative = [
            row for row in self.contract["cases"] if row["case_type"] != "POSITIVE"
        ]
        self.assertEqual(5, len(negative))
        self.assertTrue(
            all(
                row["expected_no_evidence"]
                and not row["expected_chunk_ids"]
                and (
                    row["forbidden_model_codes"]
                    or row["forbidden_document_ids"]
                )
                for row in negative
            )
        )
        self.assertEqual(
            {
                "WPUJAC104SWH",
                "WPUIAC425SNW",
                "WPU-IAC506",
                "WPUJAC104DWH",
                "WATERCARE-X999",
            },
            {row["product_model_code"] for row in negative},
        )

    def test_ai_result_metadata_gate_is_explicitly_pending(self) -> None:
        required = set(
            self.contract["evaluation_policy"]["required_result_metadata"]
        )
        self.assertEqual(
            {
                "embedding_model",
                "embedding_model_version",
                "chunk_set_sha256",
                "index_version",
                "filter",
                "ranked_chunk_ids",
                "recall_at_k",
                "mrr",
            },
            required,
        )
        self.assertEqual(
            "PENDING_AI_OWNER",
            self.contract["ai_execution"]["status"],
        )


if __name__ == "__main__":
    unittest.main()
