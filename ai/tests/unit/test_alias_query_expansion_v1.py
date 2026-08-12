from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ai.evaluation.query_expansion import DraftAliasQueryExpander
from ai.scripts.run_alias_query_expansion_v1 import (
    DEFAULT_ALIAS_PROFILE,
    run_alias_query_expansion,
)
from ai.scripts.run_chunking_experiment_v1 import DEFAULT_CHUNKING_PROFILE
from ai.scripts.run_full_corpus_baseline_v1 import DEFAULT_PROFILE, REPOSITORY_ROOT
from ai.scripts.run_query_intent_domain_experiment_v1 import DEFAULT_INTENT_PROFILE
from ai.scripts.run_retrieval_threshold_scope_experiment_v1 import (
    DEFAULT_RETRIEVAL_PROFILE,
)


class DeterministicAliasEmbedder:
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


class AliasQueryExpansionV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.alias_path = REPOSITORY_ROOT / DEFAULT_ALIAS_PROFILE
        cls.scope_path = REPOSITORY_ROOT / DEFAULT_RETRIEVAL_PROFILE
        cls.intent_path = REPOSITORY_ROOT / DEFAULT_INTENT_PROFILE
        cls.chunking_path = REPOSITORY_ROOT / DEFAULT_CHUNKING_PROFILE
        cls.baseline_path = REPOSITORY_ROOT / DEFAULT_PROFILE
        cls.profile = json.loads(cls.alias_path.read_text(encoding="utf-8"))
        cls.expander = DraftAliasQueryExpander(cls.profile["alias_policy"])

    def test_expander_appends_reviewable_terms_for_target_phrase(self) -> None:
        decision = self.expander.expand("바닥에 물이 흥건함")

        self.assertTrue(decision.applied)
        self.assertEqual(decision.applied_rule_ids, ("ALIAS-JAC104-LEAK-001",))
        self.assertIn("누수", decision.appended_terms)
        self.assertTrue(decision.expanded_query.endswith("누수 제품 누수 발생"))

    def test_expander_blocks_negated_hard_negative(self) -> None:
        decision = self.expander.expand(
            "물이 한 방울도 안 나오는 게 아니라 기사님 도착 시간을 묻는 것입니다."
        )

        self.assertFalse(decision.applied)
        self.assertEqual(decision.expanded_query, decision.original_query)

    def test_expander_blocks_every_declared_hard_negative(self) -> None:
        for case in self.profile["hard_negative_cases"]:
            with self.subTest(case_id=case["case_id"]):
                decision = self.expander.expand(case["query"])
                self.assertEqual(
                    list(decision.applied_rule_ids),
                    case["expected_alias_rule_ids"],
                )

    def test_runner_requires_explicit_draft_alias_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "draft_alias_explicit_opt_in"):
                run_alias_query_expansion(
                    self.alias_path,
                    self.scope_path,
                    self.intent_path,
                    self.chunking_path,
                    self.baseline_path,
                    Path(directory) / "output",
                    embedding_provider=DeterministicAliasEmbedder(),
                    allow_draft_gold=True,
                    allow_draft_aliases=False,
                    cache_directory=Path(directory) / "cache",
                )

    def test_runner_creates_paired_dev_and_hard_negative_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = run_alias_query_expansion(
                self.alias_path,
                self.scope_path,
                self.intent_path,
                self.chunking_path,
                self.baseline_path,
                root / "output",
                embedding_provider=DeterministicAliasEmbedder(),
                allow_draft_gold=True,
                allow_draft_aliases=True,
                cache_directory=root / "cache",
            )
            summary = json.loads(
                (root / "output" / "summary.json").read_text(encoding="utf-8")
            )
            results = [
                json.loads(line)
                for line in (root / "output" / "case_results.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            hard_results = (
                root / "output" / "hard_negative_results.jsonl"
            ).read_text(encoding="utf-8").splitlines()

        self.assertEqual(
            manifest["run_status"],
            "DRAFT_ALIAS_QUERY_EXPANSION_COMPARISON_COMPLETE",
        )
        self.assertFalse(manifest["metrics_publishable_as_official"])
        self.assertEqual(manifest["performance"]["case_result_count"], 2 * 35)
        self.assertEqual(manifest["performance"]["hard_negative_result_count"], 2 * 7)
        self.assertEqual(len(results), 2 * 35)
        self.assertEqual(len(hard_results), 2 * 7)
        self.assertEqual(len(summary["variant_summaries"]), 2)
        self.assertEqual(len(summary["rule_outcomes"]), 2)
        self.assertEqual(
            {row["rule_id"] for row in summary["rule_outcomes"]},
            {"ALIAS-JAC104-LEAK-001", "ALIAS-JAC104-NO-WATER-001"},
        )
        self.assertEqual(summary["comparison"]["target_case_ids"], [
            "RAGV2-GOLD-0004",
            "RAGV2-GOLD-0025",
            "RAGV2-GOLD-0027",
        ])
        self.assertEqual(
            summary["comparison"]["unexpected_alias_activation_case_ids"],
            [],
        )
        self.assertEqual(
            summary["comparison"][
                "missing_expected_alias_activation_case_ids"
            ],
            [],
        )
        expanded_target = next(
            row
            for row in results
            if row["case_id"] == "RAGV2-GOLD-0025"
            and row["query_expansion_applied"]
        )
        self.assertIn("출수되지 않음", expanded_target["retrieval_query"])
        self.assertEqual(
            summary["hard_negative_summary"][
                "unexpected_alias_activation_case_ids"
            ],
            [],
        )


if __name__ == "__main__":
    unittest.main()
