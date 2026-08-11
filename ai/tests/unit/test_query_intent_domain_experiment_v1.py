from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from jsonschema import Draft202012Validator

from ai.evaluation.query_intent_domain_policy import ExperimentalQueryIntentDomainPolicy
from ai.scripts.build_query_intent_domain_dataset_v1 import _jsonl_bytes, build_cases
from ai.scripts.run_chunking_experiment_v1 import DEFAULT_CHUNKING_PROFILE
from ai.scripts.run_full_corpus_baseline_v1 import DEFAULT_PROFILE, REPOSITORY_ROOT
from ai.scripts.run_query_intent_domain_experiment_v1 import (
    DEFAULT_INTENT_PROFILE,
    run_query_intent_domain_experiment,
)
from ai.scripts.run_retrieval_threshold_scope_experiment_v1 import DEFAULT_RETRIEVAL_PROFILE


class DeterministicIntentEmbedder:
    dimension = 1024

    @staticmethod
    def _embed(texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), 1024), dtype=np.float32)
        for row_index, value in enumerate(texts):
            for token in value.casefold().split():
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                matrix[row_index, int.from_bytes(digest[:2], "big") % 1024] += 1.0
            if not matrix[row_index].any():
                matrix[row_index, 0] = 1.0
        return matrix

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._embed(texts)


class QueryIntentDomainExperimentV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile_path = REPOSITORY_ROOT / DEFAULT_INTENT_PROFILE
        cls.scope_path = REPOSITORY_ROOT / DEFAULT_RETRIEVAL_PROFILE
        cls.chunking_path = REPOSITORY_ROOT / DEFAULT_CHUNKING_PROFILE
        cls.baseline_path = REPOSITORY_ROOT / DEFAULT_PROFILE
        cls.profile = json.loads(cls.profile_path.read_text(encoding="utf-8"))
        cls.schema_path = REPOSITORY_ROOT / cls.profile["dataset"]["schema_path"]

    def test_dataset_is_balanced_valid_and_unreviewed(self) -> None:
        cases = build_cases()
        validator = Draft202012Validator(
            json.loads(self.schema_path.read_text(encoding="utf-8"))
        )
        for case in cases:
            validator.validate(case)

        self.assertEqual(len(cases), 18)
        self.assertEqual(sum(row["expected_decision"] == "BLOCK" for row in cases), 9)
        self.assertEqual(sum(row["expected_decision"] == "ALLOW" for row in cases), 9)
        self.assertTrue(all(row["review_status"] == "UNREVIEWED_DRAFT" for row in cases))
        dataset_path = REPOSITORY_ROOT / self.profile["dataset"]["path"]
        self.assertEqual(dataset_path.read_bytes(), _jsonl_bytes(cases))

    def test_policy_blocks_compound_intent_but_allows_overlap(self) -> None:
        definition = next(
            row for row in self.profile["intent_policies"]
            if row["policy_id"] == "MANUAL_DOMAIN_INTENT_V1"
        )
        policy = ExperimentalQueryIntentDomainPolicy(definition)

        commercial = policy.evaluate(
            product_model_code="WPUJAC104DWH",
            query="제휴카드 할인 금액을 알려주세요",
        )
        rental_failure = policy.evaluate(
            product_model_code="WPUJAC104DWH",
            query="렌탈 중인 정수기에서 물이 안 나와요",
        )
        replacement_cycle = policy.evaluate(
            product_model_code="WPUJAC104DWH",
            query="필터 가격이 아니라 교체 주기를 알려주세요",
        )
        color_cleaning = policy.evaluate(
            product_model_code="WPUJAC104DWH",
            query="외관 색상이 변색됐는데 청소 방법을 알려주세요",
        )

        self.assertEqual(commercial.rule_id, "EXP-INTENT-COMMERCIAL-001")
        self.assertTrue(commercial.blocked)
        self.assertFalse(rental_failure.blocked)
        self.assertFalse(replacement_cycle.blocked)
        self.assertFalse(color_cleaning.blocked)

    def test_runner_creates_supplemental_and_gold_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = run_query_intent_domain_experiment(
                self.profile_path,
                self.scope_path,
                self.chunking_path,
                self.baseline_path,
                root / "output",
                embedding_provider=DeterministicIntentEmbedder(),
                allow_draft_gold=True,
                cache_directory=root / "cache",
            )
            summary = json.loads(
                (root / "output" / "summary.json").read_text(encoding="utf-8")
            )
            results = (root / "output" / "case_results.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()

        self.assertEqual(manifest["run_status"], "DRAFT_QUERY_INTENT_DOMAIN_EXPERIMENT_COMPLETE")
        self.assertFalse(manifest["metrics_publishable_as_official"])
        self.assertEqual(manifest["performance"]["case_result_count"], 2 * (18 + 35))
        self.assertEqual(len(results), 2 * (18 + 35))
        self.assertEqual(len(summary["comparisons"]), 2)
        enabled = next(
            row for row in summary["comparisons"]
            if row["intent_policy_id"] == "MANUAL_DOMAIN_INTENT_V1"
        )
        self.assertEqual(enabled["supplemental_policy"]["decision_accuracy"], 1.0)
        self.assertEqual(enabled["supplemental_policy"]["false_block_case_ids"], [])
        self.assertEqual(enabled["supplemental_policy"]["missed_block_case_ids"], [])


if __name__ == "__main__":
    unittest.main()
