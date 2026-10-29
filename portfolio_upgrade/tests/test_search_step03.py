"""사전학습 모델 다운로드 없이 실행되는 실습 03의 최소 단위 테스트."""
import sys
from pathlib import Path
import unittest

import numpy as np

# unittest discover에서 프로젝트 루트 경로를 자동으로 잡도록 구성.
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from compare_search_step03 import (  # noqa: E402
    MODEL_PRESETS,
    embedding_search_all,
    compare,
    summarize,
)
from compare_search_step02 import load_inputs  # noqa: E402


class FakeModel:
    """실제 LLM이 아니며 벡터 점수 계산을 테스트하기 위한 장난감 모델."""
    def __init__(self):
        self.seen = []

    def encode(self, texts, **kwargs):
        self.seen.append(list(texts))
        table = {
            "passage: 누수 물이 샙니다": [1.0, 0.0],
            "passage: 출수 물이 안 나옵니다": [0.0, 1.0],
            "query: 물이 새요": [1.0, 0.0],
            "query: 물이 안 나와요": [0.0, 1.0],
        }
        return np.array([table[text] for text in texts], dtype=np.float32)


class Step03Tests(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            {"chunk_id": "A", "section": "누수", "text": "물이 샙니다", "page": 38},
            {"chunk_id": "B", "section": "출수", "text": "물이 안 나옵니다", "page": 37},
        ]

    def test_e5_prefixes_and_cosine_ranking(self):
        model = FakeModel()
        rows = embedding_search_all(
            model,
            self.chunks,
            ["물이 새요", "물이 안 나와요"],
            query_prefix="query: ",
            passage_prefix="passage: ",
            top_k=2,
        )
        self.assertEqual([[r["chunk_id"] for r in row] for row in rows], [["A", "B"], ["B", "A"]])
        self.assertEqual(model.seen[0][0], "passage: 누수 물이 샙니다")
        self.assertEqual(model.seen[1][0], "query: 물이 새요")
        self.assertAlmostEqual(rows[0][0]["score"], 1.0)

    def test_top_k_and_invalid_k(self):
        m = FakeModel()
        res = embedding_search_all(m, self.chunks, ["물이 새요"], query_prefix="query: ", passage_prefix="passage: ", top_k=1)
        self.assertEqual(len(res[0]), 1)
        with self.assertRaises(ValueError):
            embedding_search_all(m, self.chunks, ["물이 새요"], query_prefix="query: ", passage_prefix="passage: ", top_k=0)

    def test_no_results_are_counted_as_failure(self):
        chunks, gold = load_inputs()
        rows = compare(chunks, gold, [[] for _ in gold], top_k=3)
        stats = summarize(rows, top_k=3)
        self.assertEqual(stats["embedding"]["hit_at_1"], 0)
        self.assertEqual(stats["embedding"]["hit_at_3"], 0)
        self.assertEqual(stats["embedding"]["mrr_at_3"], 0.0)

    def test_old_baselines_are_unchanged(self):
        chunks, gold = load_inputs()
        rows = compare(chunks, gold, [[] for _ in gold], top_k=3)
        stats = summarize(rows, top_k=3)
        self.assertEqual(stats["overlap"]["hit_at_1"], 4)
        self.assertEqual(stats["overlap"]["hit_at_3"], 6)
        self.assertAlmostEqual(stats["overlap"]["mrr_at_3"], 0.4667, places=4)
        self.assertEqual(stats["bm25"]["hit_at_1"], 6)
        self.assertEqual(stats["bm25"]["hit_at_3"], 7)
        self.assertAlmostEqual(stats["bm25"]["mrr_at_3"], 0.6333, places=4)

    def test_presets_use_proper_prefixes(self):
        self.assertEqual(MODEL_PRESETS["e5-small"]["query_prefix"], "query: ")
        self.assertEqual(MODEL_PRESETS["e5-small"]["passage_prefix"], "passage: ")
        self.assertEqual(MODEL_PRESETS["bge-m3"]["query_prefix"], "")


if __name__ == "__main__":
    unittest.main()
