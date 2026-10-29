"""실습 02: 직접 이해할 수 있는 네 가지 요구사항 테스트."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from compare_search_step02 import load_inputs, bm25_search, evaluate, compare  # noqa: E402


class SearchStep02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus, cls.gold = load_inputs()

    def test_corpus_and_gold_referential_integrity(self):
        self.assertEqual(len(self.corpus), 8)
        self.assertEqual(len(self.gold), 10)
        known = {x["chunk_id"] for x in self.corpus}
        self.assertTrue(all(set(q["acceptable_chunk_ids"]) <= known for q in self.gold))

    def test_bm25_returns_empty_when_no_words_match(self):
        self.assertEqual(bm25_search("고양이 우주선", self.corpus), [])

    def test_bm25_limits_top_k_and_has_deterministic_order(self):
        a = bm25_search("필터", self.corpus, top_k=2)
        b = bm25_search("필터", self.corpus, top_k=2)
        self.assertLessEqual(len(a), 2)
        self.assertEqual(a, b)

    def test_hit_at_1_and_mrr_can_differ(self):
        gold = ["GOOD"]
        rank_1 = [{"chunk_id": "GOOD"}, {"chunk_id": "BAD"}]
        rank_2 = [{"chunk_id": "BAD"}, {"chunk_id": "GOOD"}]
        self.assertEqual(evaluate(rank_1, gold, k=3)["mrr_at_3"], 1.0)
        self.assertEqual(evaluate(rank_2, gold, k=3)["hit_at_1"], 0)
        self.assertEqual(evaluate(rank_2, gold, k=3)["mrr_at_3"], 0.5)

    def test_gold_does_not_change_search_rank(self):
        before = bm25_search("물줄기가 약해요", self.corpus, top_k=3)
        _ = compare(self.corpus, self.gold, top_k=3)
        after = bm25_search("물줄기가 약해요", self.corpus, top_k=3)
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
