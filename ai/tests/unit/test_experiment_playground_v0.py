from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

from ai.app.bootstrap import create_app
from ai.app.experiments.playground import (
    DEFAULT_PROFILE,
    ExperimentPlaygroundEngine,
    REPOSITORY_ROOT,
    build_playground_index,
)
from ai.evaluation.evidence_scoring_v2 import LEGACY_SCORING_CONTRACT_VERSION
from ai.scripts.run_full_corpus_baseline_v1 import _metrics


class TargetPageEmbedder:
    dimension = 1024

    def __init__(self, target_index: int = 37) -> None:
        self.target_index = target_index

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for index in range(len(texts)):
            matrix[index, index] = 1.0
        return matrix

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dimension), dtype=np.float32)
        matrix[:, self.target_index] = 1.0
        return matrix


class ExperimentPlaygroundV0Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile_path = REPOSITORY_ROOT / DEFAULT_PROFILE
        cls.document_vectors = TargetPageEmbedder().embed_documents([""] * 96)

    def test_single_query_returns_gold_page_and_product_safe_result(self) -> None:
        engine = ExperimentPlaygroundEngine(
            self.profile_path,
            embedding_provider=TargetPageEmbedder(),
            document_vectors=self.document_vectors,
        )
        result = engine.search(
            product_model_code="WPUJAC104DWH",
            query="정수기 밑이 축축하고 물이 새는 것 같아요.",
            top_k=5,
            product_filter=True,
        )

        self.assertEqual(result["status"], "DRAFT_RETRIEVAL_COMPLETE")
        self.assertEqual(result["retrieval"]["result_count"], 1)
        self.assertEqual(result["retrieval"]["results"][0]["page_refs"], [38])
        self.assertEqual(result["retrieval"]["wrong_product_hit_count"], 0)
        self.assertTrue(result["gold"]["matched"])
        self.assertTrue(result["gold"]["retrieval_pass"])
        self.assertEqual(result["gold"]["scoring_status"], "DRAFT_SCORED")
        self.assertEqual(
            result["gold"]["scoring_contract_version"],
            LEGACY_SCORING_CONTRACT_VERSION,
        )
        self.assertTrue(result["gold"]["metrics"]["passed"])
        self.assertEqual(result["generation"]["status"], "NOT_IMPLEMENTED_V0")

    def test_playground_all_policy_matches_full_b1_shared_scorer(self) -> None:
        embedder = TargetPageEmbedder(target_index=36)
        engine = ExperimentPlaygroundEngine(
            self.profile_path,
            embedding_provider=embedder,
            document_vectors=embedder.embed_documents([""] * 96),
        )
        case = next(row for row in engine.gold_rows if row["case_id"] == "RAGV2-GOLD-0036")

        result = engine.search(
            product_model_code=case["product_model_code"],
            query=case["query"],
            top_k=5,
            product_filter=True,
        )
        b1_metrics = _metrics(
            [{"chunk": engine.corpus_rows[36], "score": 1.0}],
            case["expected_evidence"],
            case["expected_no_evidence"],
            case["product_model_code"],
            case["evidence_match_policy"],
        )

        self.assertTrue(result["gold"]["matched"])
        self.assertFalse(result["gold"]["retrieval_pass"])
        self.assertEqual(result["gold"]["metrics"]["evidence_match_policy"], "ALL")
        self.assertEqual(result["gold"]["metrics"]["hit_at_5"], 0.0)
        self.assertIsNone(result["gold"]["metrics"]["evidence_completion_rank"])
        for key in (
            "hit_at_1",
            "hit_at_3",
            "hit_at_5",
            "mrr",
            "evidence_completion_rank",
            "covered_evidence_unit_ids",
            "no_evidence_passed",
        ):
            self.assertEqual(result["gold"]["metrics"][key], b1_metrics[key], key)

    def test_index_builder_and_loader_round_trip(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPOSITORY_ROOT) as directory:
            root = Path(directory)
            index_path = root / "index.npz"
            manifest_path = root / "manifest.json"
            manifest = build_playground_index(
                self.profile_path,
                index_path,
                manifest_path,
                embedding_provider=TargetPageEmbedder(),
            )
            engine = ExperimentPlaygroundEngine(
                self.profile_path,
                index_path,
                embedding_provider=TargetPageEmbedder(),
            )

            self.assertEqual(manifest["status"], "READY")
            self.assertEqual(manifest["index"]["shape"], [96, 1024])
            self.assertEqual(engine.document_vectors.shape, (96, 1024))
            stored_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertFalse(stored_manifest["official_metrics_allowed"])

    def test_non_comparable_profile_does_not_expose_pass_boolean(self) -> None:
        engine = ExperimentPlaygroundEngine(
            self.profile_path,
            embedding_provider=TargetPageEmbedder(),
            document_vectors=self.document_vectors,
        )

        result = engine.search(
            product_model_code="WPUJAC104DWH",
            query="정수기 밑이 축축하고 물이 새는 것 같아요.",
            top_k=1,
            product_filter=True,
        )

        self.assertEqual(result["gold"]["scoring_status"], "NOT_COMPARABLE")
        self.assertIsNone(result["gold"]["retrieval_pass"])
        self.assertIsNotNone(result["gold"]["metrics"])
        self.assertIsNone(result["gold"]["metrics"]["passed"])
        self.assertIsNone(result["gold"]["metrics"]["semantic_passed"])
        self.assertIsNone(
            result["gold"]["metrics"]["execution_contract_passed"]
        )

    def test_non_comparable_no_evidence_hides_every_verdict_boolean(self) -> None:
        engine = ExperimentPlaygroundEngine(
            self.profile_path,
            embedding_provider=TargetPageEmbedder(target_index=200),
            document_vectors=self.document_vectors,
        )
        case = next(
            row for row in engine.gold_rows
            if row["case_id"] == "RAGV2-GOLD-0059"
        )

        result = engine.search(
            product_model_code=case["product_model_code"],
            query=case["query"],
            top_k=1,
            product_filter=True,
        )

        self.assertEqual(result["gold"]["scoring_status"], "NOT_COMPARABLE")
        self.assertTrue(result["gold"]["metrics"]["no_evidence_retrieval_empty"])
        for verdict_field in (
            "passed",
            "semantic_passed",
            "execution_contract_passed",
            "no_evidence_passed",
            "no_evidence_success",
            "policy_block_success",
            "answerability_gate_passed",
        ):
            self.assertIsNone(result["gold"]["metrics"][verdict_field])

    def test_page_and_retrieval_api_are_connected(self) -> None:
        class FakeEngine:
            @staticmethod
            def search(**payload):
                return {
                    "status": "DRAFT_RETRIEVAL_COMPLETE",
                    "request": payload,
                    "retrieval": {"results": [], "result_count": 0},
                }

        with patch.dict("os.environ", {"AI_ENABLE_EXPERIMENT_PLAYGROUND": "true"}), patch(
            "ai.app.interfaces.http.routes.experiment_playground_routes.get_playground_engine",
            return_value=FakeEngine(),
        ):
            client = TestClient(create_app())
            page = client.get("/experiments/playground")
            response = client.post(
                "/api/v1/ai/experiments/playground/retrieval",
                json={
                    "product_model_code": "WPUJAC104DWH",
                    "query": "정수기 밑이 축축하고 물이 새는 것 같아요.",
                    "top_k": 5,
                },
            )

        self.assertEqual(page.status_code, 200)
        self.assertIn("Experiment Playground", page.text)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["request"]["top_k"], 5)

    def test_playground_routes_are_closed_by_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            client = TestClient(create_app())

        self.assertEqual(client.get("/experiments/playground").status_code, 404)
        self.assertEqual(
            client.get("/api/v1/ai/experiments/playground/options").status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
