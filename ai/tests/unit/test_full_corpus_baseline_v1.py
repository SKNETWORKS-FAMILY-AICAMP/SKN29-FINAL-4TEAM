from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from jsonschema import Draft202012Validator

from ai.scripts.build_full_corpus_chunks_v1 import (
    OUTPUT_DATASET,
    OUTPUT_MANIFEST,
    REPOSITORY_ROOT,
    SCHEMA_PATH,
    _jsonl_bytes,
    build_chunks,
)
from ai.scripts.run_full_corpus_baseline_v1 import (
    DEFAULT_PROFILE,
    build_preflight_report,
    run_baseline,
)


class DeterministicTestEmbedder:
    dimension = 1024

    @staticmethod
    def _embed(texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), DeterministicTestEmbedder.dimension), dtype=np.float32)
        for row_index, text in enumerate(texts):
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                column = int.from_bytes(digest[:2], "big") % matrix.shape[1]
                matrix[row_index, column] += 1.0
            if not matrix[row_index].any():
                matrix[row_index, 0] = 1.0
        return matrix

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)


class FullCorpusBaselineV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile_path = REPOSITORY_ROOT / DEFAULT_PROFILE
        cls.dataset_path = REPOSITORY_ROOT / OUTPUT_DATASET
        cls.manifest_path = REPOSITORY_ROOT / OUTPUT_MANIFEST
        cls.schema_path = REPOSITORY_ROOT / SCHEMA_PATH
        cls.rows = [
            json.loads(line)
            for line in cls.dataset_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_full_manual_corpus_has_44_plus_52_page_chunks(self) -> None:
        self.assertEqual(len(self.rows), 96)
        self.assertEqual(
            sum(row["corpus_scope"] == "JAC104_ONLY" for row in self.rows),
            44,
        )
        self.assertEqual(
            sum(row["corpus_scope"] == "IAC425_ONLY" for row in self.rows),
            52,
        )
        self.assertEqual(len({row["chunk_id"] for row in self.rows}), 96)
        validator = Draft202012Validator(
            json.loads(self.schema_path.read_text(encoding="utf-8"))
        )
        self.assertEqual(
            [error.message for row in self.rows for error in validator.iter_errors(row)],
            [],
        )

    def test_chunk_builder_is_byte_deterministic(self) -> None:
        self.assertEqual(self.dataset_path.read_bytes(), _jsonl_bytes(build_chunks()))
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        actual_hash = hashlib.sha256(self.dataset_path.read_bytes()).hexdigest().upper()
        self.assertEqual(manifest["dataset"]["sha256"], actual_hash)
        self.assertEqual(manifest["status"], "READY_FOR_EMBEDDING")

    def test_injected_provider_makes_draft_preflight_ready(self) -> None:
        report = build_preflight_report(
            self.profile_path,
            allow_draft_gold=True,
            embedding_provider_supplied=True,
        )
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["blockers"], [])
        review = next(
            check for check in report["checks"]
            if check["name"] == "gold_two_person_review"
        )
        self.assertEqual(review["detail"]["pending_records"], 60)
        self.assertFalse(review["detail"]["official_metrics_allowed"])

    def test_dense_runner_produces_three_corpora_by_two_filter_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = run_baseline(
                self.profile_path,
                output,
                embedding_provider=DeterministicTestEmbedder(),
                allow_draft_gold=True,
            )
            self.assertEqual(manifest["run_status"], "DRAFT_BASELINE_COMPLETE")
            self.assertFalse(manifest["metrics_publishable_as_official"])
            self.assertEqual(manifest["corpus"]["chunks"], 96)

            results = [
                json.loads(line)
                for line in (output / "case_results.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            self.assertEqual(len(results), 35 * 3 * 2)
            self.assertEqual(
                len({(row["corpus_variant"], row["filter_mode"]) for row in results}),
                6,
            )
            summary = json.loads((output / "retrieval_summary.json").read_text(
                encoding="utf-8"
            ))
            self.assertEqual(len(summary["groups"]), 6)
            self.assertFalse(summary["metrics_publishable_as_official"])
            performance = json.loads((output / "performance_summary.json").read_text(
                encoding="utf-8"
            ))
            self.assertEqual(performance["document_count"], 96)
            self.assertEqual(performance["query_count"], 35)
            self.assertEqual(performance["case_result_count"], 210)


if __name__ == "__main__":
    unittest.main()
