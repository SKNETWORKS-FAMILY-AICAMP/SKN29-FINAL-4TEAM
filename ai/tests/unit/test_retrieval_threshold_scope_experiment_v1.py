from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ai.evaluation.query_scope_policy import ExperimentalQueryScopePolicy
from ai.scripts.run_chunking_experiment_v1 import DEFAULT_CHUNKING_PROFILE
from ai.scripts.run_full_corpus_baseline_v1 import DEFAULT_PROFILE, REPOSITORY_ROOT
from ai.scripts.run_retrieval_threshold_scope_experiment_v1 import (
    DEFAULT_RETRIEVAL_PROFILE,
    run_retrieval_threshold_scope_experiment,
)


class DeterministicRetrievalEmbedder:
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


class RetrievalThresholdScopeExperimentV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile_path = REPOSITORY_ROOT / DEFAULT_RETRIEVAL_PROFILE
        cls.chunking_path = REPOSITORY_ROOT / DEFAULT_CHUNKING_PROFILE
        cls.baseline_path = REPOSITORY_ROOT / DEFAULT_PROFILE
        cls.profile = json.loads(cls.profile_path.read_text(encoding="utf-8"))

    def test_scope_policy_uses_explicit_model_and_capability_rules(self) -> None:
        definition = next(
            row for row in self.profile["scope_policies"]
            if row["policy_id"] == "MODEL_CAPABILITY_SCOPE_V1"
        )
        policy = ExperimentalQueryScopePolicy(definition)

        allowed = policy.evaluate(
            product_model_code="WPUJAC104DWH",
            query="정수기에서 물이 새요",
        )
        ice = policy.evaluate(
            product_model_code="WPUJAC104DWH",
            query="얼음 크기와 제빙량을 설정하고 싶어요",
        )
        other_model = policy.evaluate(
            product_model_code="WPU-IAC506",
            query="필터 교체 방법을 알려주세요",
        )

        self.assertFalse(allowed.blocked)
        self.assertEqual(ice.rule_id, "EXP-SCOPE-JAC104-ICE-001")
        self.assertTrue(ice.blocked)
        self.assertEqual(other_model.rule_id, "EXP-SCOPE-MODEL-001")
        self.assertTrue(other_model.blocked)

    def test_runner_creates_complete_draft_threshold_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = run_retrieval_threshold_scope_experiment(
                self.profile_path,
                self.chunking_path,
                self.baseline_path,
                root / "output",
                embedding_provider=DeterministicRetrievalEmbedder(),
                allow_draft_gold=True,
                cache_directory=root / "cache",
            )
            summary = json.loads(
                (root / "output" / "summary.json").read_text(encoding="utf-8")
            )
            failures = json.loads(
                (root / "output" / "failure_analysis.json").read_text(encoding="utf-8")
            )
            result_count = len(
                (root / "output" / "case_results.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            )

        expected = 2 * 2 * 7 * 35
        self.assertEqual(manifest["run_status"], "DRAFT_THRESHOLD_SCOPE_EXPERIMENT_COMPLETE")
        self.assertFalse(manifest["metrics_publishable_as_official"])
        self.assertEqual(manifest["performance"]["case_result_count"], expected)
        self.assertEqual(result_count, expected)
        self.assertEqual(len(summary["comparisons"]), 2 * 2 * 7)
        self.assertEqual(failures["status"], "AUTOMATED_TRIAGE_REVIEW_REQUIRED")
        self.assertTrue(failures["items"])

    def test_higher_threshold_cannot_reduce_no_evidence_accuracy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_retrieval_threshold_scope_experiment(
                self.profile_path,
                self.chunking_path,
                self.baseline_path,
                root / "output",
                embedding_provider=DeterministicRetrievalEmbedder(),
                allow_draft_gold=True,
                cache_directory=root / "cache",
            )
            comparisons = json.loads(
                (root / "output" / "summary.json").read_text(encoding="utf-8")
            )["comparisons"]

        groups: dict[tuple[str, str], list[dict]] = {}
        for row in comparisons:
            groups.setdefault((
                row["chunking_profile_id"], row["scope_policy_id"]
            ), []).append(row)
        for rows in groups.values():
            ordered = sorted(rows, key=lambda row: row["score_threshold"])
            accuracies = [row["no_evidence_accuracy"] for row in ordered]
            self.assertEqual(accuracies, sorted(accuracies))


if __name__ == "__main__":
    unittest.main()
