from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
REPOSITORY_ROOT = DATA_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.config import load_pipeline
from watercare.io import read_json, sha256_text_file
from watercare.validation import validate_schema


class RagEvaluationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)
        cls.contract = cls.config.config("rag_evaluation_cases")
        cls.rag = cls.config.config("rag")

    def repository_artifact(self, relative_path: str) -> Path:
        repository_root = REPOSITORY_ROOT.resolve()
        artifact = (repository_root / relative_path).resolve()
        self.assertTrue(
            artifact.is_relative_to(repository_root),
            f"저장소 밖 RAG 실행 증거 경로입니다: {relative_path}",
        )
        self.assertTrue(
            artifact.is_file(),
            f"RAG 실행 증거 파일이 없습니다: {relative_path}",
        )
        return artifact

    def assert_text_sha256(self, path: Path, expected: str) -> None:
        actual = sha256_text_file(path)
        self.assertEqual(expected, actual)

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

    def test_ai_execution_evidence_is_complete_and_hash_pinned(self) -> None:
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
        execution = self.contract["ai_execution"]
        self.assertEqual("PASS", execution["status"])
        self.assertEqual(
            "APPROVED_FOR_MVP_INGEST",
            execution["approval_scope"],
        )
        self.assertEqual("UTF8_LF_NO_BOM", execution["hash_policy"])

        dataset_evidence = execution["canonical_dataset"]
        dataset_path = self.repository_artifact(dataset_evidence["path"])
        self.assert_text_sha256(dataset_path, dataset_evidence["sha256"])
        dataset_rows = [
            json.loads(line)
            for line in dataset_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(dataset_evidence["records"], len(dataset_rows))
        self.assertEqual(
            len(dataset_rows),
            len({row["chunk_id"] for row in dataset_rows}),
        )

        report_evidence = execution["result_manifest"]
        report_path = self.repository_artifact(report_evidence["path"])
        self.assert_text_sha256(report_path, report_evidence["sha256"])
        self.assertNotEqual(
            report_evidence["sha256"],
            report_evidence["received_sha256"],
        )
        report = read_json(report_path)
        self.assertEqual(
            report_evidence["verification_status"],
            report["verification_status"],
        )
        self.assertEqual(report_evidence["case_count"], report["summary"]["case_count"])
        self.assertEqual(
            report_evidence["passed_count"],
            report["summary"]["passed_count"],
        )
        self.assertEqual(
            report_evidence["failed_count"],
            report["summary"]["failed_count"],
        )
        self.assertEqual(0, report["summary"]["forbidden_hit_count"])
        self.assertAlmostEqual(
            1.0,
            report["summary"]["mean_positive_recall_at_5"],
        )
        self.assertAlmostEqual(
            0.8857142857142858,
            report["summary"]["mean_positive_mrr"],
        )
        self.assertEqual(
            {row["case_id"] for row in self.contract["cases"]},
            {row["case_id"] for row in report["cases"]},
        )
        self.assertTrue(
            report["sql_filter_verification"]["metadata_filter_passed"]
        )
        self.assertEqual(
            [],
            report["sql_filter_verification"]["leaked_fixture_ids"],
        )

        leak = next(
            row for row in report["cases"] if row["case_id"] == "RAG-POS-LEAK"
        )
        expected_leak_chunk = next(
            row["expected_chunk_ids"][0]
            for row in self.contract["cases"]
            if row["case_id"] == "RAG-POS-LEAK"
        )
        self.assertEqual(5, leak["ranked_chunk_ids"].index(expected_leak_chunk) + 1)
        self.assertAlmostEqual(0.2, leak["mrr"])

        index_evidence = execution["index_manifest"]
        index_path = self.repository_artifact(index_evidence["path"])
        self.assert_text_sha256(index_path, index_evidence["sha256"])
        self.assertNotEqual(
            index_evidence["sha256"],
            index_evidence["received_sha256"],
        )
        index = read_json(index_path)
        self.assertEqual(index_evidence["embedding_model"], index["model_name"])
        self.assertEqual(
            index_evidence["embedding_model_version"],
            index["model_revision"],
        )
        self.assertEqual(index_evidence["index_version"], index["index_version"])
        self.assertEqual(index_evidence["dimension"], index["dimension"])
        self.assertEqual(
            index_evidence["chunk_set_sha256"],
            index["chunk_set_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
