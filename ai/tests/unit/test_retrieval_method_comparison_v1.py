from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ai.evaluation.lexical_retrieval import BM25Index, BM25Parameters, korean_mixed_terms
from ai.scripts.run_chunking_experiment_v1 import DEFAULT_CHUNKING_PROFILE
from ai.scripts.run_full_corpus_baseline_v1 import DEFAULT_PROFILE, REPOSITORY_ROOT
from ai.scripts.run_query_intent_domain_experiment_v1 import DEFAULT_INTENT_PROFILE
from ai.scripts.run_retrieval_method_comparison_v1 import (
    DEFAULT_METHOD_PROFILE,
    run_retrieval_method_comparison,
)
from ai.scripts.run_retrieval_threshold_scope_experiment_v1 import DEFAULT_RETRIEVAL_PROFILE


class DeterministicMethodEmbedder:
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


class RetrievalMethodComparisonV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.method_path = REPOSITORY_ROOT / DEFAULT_METHOD_PROFILE
        cls.scope_path = REPOSITORY_ROOT / DEFAULT_RETRIEVAL_PROFILE
        cls.intent_path = REPOSITORY_ROOT / DEFAULT_INTENT_PROFILE
        cls.chunking_path = REPOSITORY_ROOT / DEFAULT_CHUNKING_PROFILE
        cls.baseline_path = REPOSITORY_ROOT / DEFAULT_PROFILE

    def test_korean_analyzer_preserves_word_and_particle_robust_bigrams(self) -> None:
        terms = korean_mixed_terms("정수기에서 WPU-JAC104DWH 필터를 확인해요")

        self.assertIn("w:정수기에서", terms)
        self.assertIn("c:정수", terms)
        self.assertIn("c:수기", terms)
        self.assertIn("w:wpu", terms)
        self.assertIn("w:jac104dwh", terms)

    def test_bm25_ranks_lexically_relevant_document_first(self) -> None:
        index = BM25Index(
            [
                "물이 출수되지 않으면 필터 교체 주기를 확인합니다",
                "외관 청소 시 젖은 헝겊으로 닦아주세요",
            ],
            parameters=BM25Parameters(k1=1.5, b=0.75),
        )

        scores = index.scores("필터를 확인했는데 물이 출수되지 않아요")

        self.assertGreater(scores[0], scores[1])
        self.assertGreater(scores[0], 0)

    def test_runner_creates_dense_bm25_matrix_and_complementarity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = run_retrieval_method_comparison(
                self.method_path,
                self.scope_path,
                self.intent_path,
                self.chunking_path,
                self.baseline_path,
                root / "output",
                embedding_provider=DeterministicMethodEmbedder(),
                allow_draft_gold=True,
                cache_directory=root / "cache",
            )
            summary = json.loads(
                (root / "output" / "summary.json").read_text(encoding="utf-8")
            )
            results = (root / "output" / "case_results.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()

        self.assertEqual(manifest["run_status"], "DRAFT_RETRIEVAL_METHOD_COMPARISON_COMPLETE")
        self.assertFalse(manifest["metrics_publishable_as_official"])
        self.assertEqual(manifest["performance"]["case_result_count"], 2 * 2 * 35)
        self.assertEqual(len(results), 2 * 2 * 35)
        self.assertEqual(len(summary["comparisons"]), 4)
        self.assertEqual(len(summary["complementarity"]), 2)
        for row in summary["complementarity"]:
            self.assertEqual(row["positive_case_count"], 27)
            self.assertIn("bm25_only_recovery_case_ids", row)
            self.assertIn("oracle_union_hit_at_5", row)
            self.assertGreater(row["candidate_overlap_case_count"], 0)


if __name__ == "__main__":
    unittest.main()
