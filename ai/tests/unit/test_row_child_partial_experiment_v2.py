from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ai.evaluation.row_child_partial import expand_parent_context
from ai.scripts.run_full_corpus_baseline_v1 import DEFAULT_PROFILE, REPOSITORY_ROOT
from ai.scripts.run_row_child_partial_experiment_v2 import (
    DEFAULT_EXPERIMENT,
    run_row_child_partial_experiment,
)


class DeterministicRowChildEmbedder:
    dimension = 1024

    @staticmethod
    def _embed(texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), 1024), dtype=np.float32)
        for row_index, text in enumerate(texts):
            for token in text.casefold().split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                matrix[row_index, int.from_bytes(digest[:2], "big") % 1024] += 1.0
            if not matrix[row_index].any():
                matrix[row_index, 0] = 1.0
        return matrix

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)


class RowChildPartialExperimentV2Tests(unittest.TestCase):
    def test_parent_context_is_deduplicated_and_not_scored(self) -> None:
        child_rows = [
            {"parent_id": "P1", "evidence_group_id": "E1"},
            {"parent_id": "P1", "evidence_group_id": "E2"},
        ]
        ranked = [
            {"chunk": {"parent_id": "P1", "evidence_unit_ids": ["E1"], "text": "자식 하나"}},
            {"chunk": {"parent_id": "P1", "evidence_unit_ids": ["E1"], "text": "자식 둘"}},
            {"chunk": {"evidence_unit_ids": [], "text": "기존 청크"}},
        ]
        context = expand_parent_context(
            ranked,
            {"P1": {"parent_text": "문맥 하나"}},
            child_rows,
        )

        self.assertEqual(context["deduplicated_parent_count"], 1)
        self.assertEqual(context["deduplicated_parent_reference_count"], 1)
        self.assertEqual(context["additional_context_evidence_group_ids"], ["E2"])
        self.assertEqual(context["context_whitespace_tokens"], 4)

    def test_runner_creates_paired_partial_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            manifest = run_row_child_partial_experiment(
                REPOSITORY_ROOT / DEFAULT_EXPERIMENT,
                REPOSITORY_ROOT / DEFAULT_PROFILE,
                output,
                embedding_provider=DeterministicRowChildEmbedder(),
                allow_draft_gold=True,
                cache_directory=Path(directory) / "cache",
            )
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            results = [
                json.loads(line)
                for line in (output / "case_results.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(manifest["run_status"], "PARTIAL_SCOPE_DIAGNOSTIC_COMPLETE")
        self.assertEqual(manifest["candidate_corpus"]["record_count"], 106)
        self.assertEqual(manifest["selected_cases"]["total"], 16)
        self.assertEqual(len(results), 48)
        self.assertTrue(summary["comparison"]["v2_child_rankings_identical"])
        self.assertFalse(summary["metrics_publishable_as_official"])
        self.assertEqual(summary["production_adoption"], "NOT_APPROVED")
        child = {row["case_id"]: row for row in results if row["variant_id"] == "CHILD_ONLY_V2"}
        parent = {row["case_id"]: row for row in results if row["variant_id"] == "CHILD_PARENT_CONTEXT_V2"}
        self.assertEqual(
            {case_id: row["ranked_results"] for case_id, row in child.items()},
            {case_id: row["ranked_results"] for case_id, row in parent.items()},
        )


if __name__ == "__main__":
    unittest.main()
