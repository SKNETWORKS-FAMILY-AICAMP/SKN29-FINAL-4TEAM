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
        self.assertEqual(result["generation"]["status"], "NOT_IMPLEMENTED_V0")

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
