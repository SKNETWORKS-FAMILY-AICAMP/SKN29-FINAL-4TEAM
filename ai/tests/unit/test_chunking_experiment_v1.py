from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ai.evaluation.chunking import build_profile_chunks, profile_statistics
from ai.scripts.run_chunking_experiment_v1 import (
    DEFAULT_CHUNKING_PROFILE,
    run_chunking_experiment,
)
from ai.scripts.run_full_corpus_baseline_v1 import DEFAULT_PROFILE, REPOSITORY_ROOT
from ai.scripts.run_full_corpus_baseline_v1 import _metrics


class DeterministicChunkingEmbedder:
    dimension = 1024

    @staticmethod
    def _embed(texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), 1024), dtype=np.float32)
        for row_index, text in enumerate(texts):
            for token in text.lower().split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                matrix[row_index, int.from_bytes(digest[:2], "big") % 1024] += 1.0
            if not matrix[row_index].any():
                matrix[row_index, 0] = 1.0
        return matrix

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)


class ChunkingExperimentV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profiles_path = REPOSITORY_ROOT / DEFAULT_CHUNKING_PROFILE
        cls.baseline_path = REPOSITORY_ROOT / DEFAULT_PROFILE
        cls.config = json.loads(cls.profiles_path.read_text(encoding="utf-8"))
        corpus_path = json.loads(cls.baseline_path.read_text(encoding="utf-8"))["corpus"]["path"]
        cls.source_rows = [
            json.loads(line)
            for line in (REPOSITORY_ROOT / corpus_path).read_text(encoding="utf-8").splitlines()
        ]

    def test_runnable_profiles_are_deterministic_and_restore_lineage(self) -> None:
        runnable = [row for row in self.config["profiles"] if row["status"] == "RUNNABLE"]
        self.assertEqual(len(runnable), 5)
        for profile in runnable:
            first = build_profile_chunks(self.source_rows, profile)
            second = build_profile_chunks(self.source_rows, profile)
            self.assertEqual(first, second)
            stats = profile_statistics(self.source_rows, first)
            self.assertGreater(stats["chunk_count"], 0)
            self.assertEqual(stats["lineage_restore_rate"], 1.0)

    def test_table_row_is_explicitly_blocked_without_row_metadata(self) -> None:
        table = next(row for row in self.config["profiles"] if row["profile_id"] == "table_row_v1")
        self.assertEqual(table["status"], "BLOCKED_SOURCE_STRUCTURE_UNAVAILABLE")
        with self.assertRaises(ValueError):
            build_profile_chunks(self.source_rows, table)

    def test_duplicate_children_do_not_inflate_ndcg(self) -> None:
        chunk = {
            "document_id": "DOC-1",
            "page_refs": [3],
            "exact_sales_code": "MODEL-1",
            "evidence_unit_ids": ["EVD-1"],
        }
        metrics = _metrics(
            [{"chunk": chunk, "score": 0.9}, {"chunk": chunk, "score": 0.8}],
            [{
                "document_id": "DOC-1",
                "page_refs": [3],
                "evidence_unit_id": "EVD-1",
            }],
            False,
            "MODEL-1",
            "ANY",
        )

        self.assertEqual(metrics["hit_at_1"], 1.0)
        self.assertEqual(metrics["ndcg_at_5"], 1.0)

    def test_runner_compares_profiles_with_fixed_retrieval_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = run_chunking_experiment(
                self.profiles_path,
                self.baseline_path,
                Path(directory),
                embedding_provider=DeterministicChunkingEmbedder(),
                allow_draft_gold=True,
                cache_directory=Path(directory) / "cache",
            )
            summary = json.loads((Path(directory) / "summary.json").read_text(encoding="utf-8"))
            failure_analysis = json.loads(
                (Path(directory) / "failure_analysis.json").read_text(encoding="utf-8")
            )
            results = (Path(directory) / "case_results.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertEqual(manifest["run_status"], "DRAFT_CHUNKING_EXPERIMENT_COMPLETE")
        self.assertFalse(manifest["metrics_publishable_as_official"])
        self.assertEqual(manifest["performance"]["case_result_count"], 5 * 2 * 35)
        self.assertEqual(len(results), 5 * 2 * 35)
        self.assertEqual(len(summary["comparisons"]), 10)
        self.assertEqual(summary["selection_status"], "PENDING_GOLD_REVIEW_AND_PM_GATE")
        self.assertEqual(failure_analysis["status"], "AUTOMATED_TRIAGE_REVIEW_REQUIRED")
        self.assertTrue(failure_analysis["items"])


if __name__ == "__main__":
    unittest.main()
