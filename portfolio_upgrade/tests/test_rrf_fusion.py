"""S02: 데이터 정답과 무관한 RRF 결합 로직, 보고서 재계산 테스트."""
from __future__ import annotations
import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from rrf_fusion import fuse_rrf  # noqa: E402
from compare_rrf_step05 import evaluate_rrf  # noqa: E402


class RRFTests(unittest.TestCase):
    def test_agreement_gets_more_score_than_single_searcher(self):
        r = fuse_rrf({"bm25": ["A", "B"], "e5": ["A", "C"]})
        self.assertEqual(r[0]["chunk_id"], "A")
        self.assertAlmostEqual(r[0]["rrf_score"], 2 / 61)
        self.assertEqual(r[0]["source_ranks"], {"bm25": 1, "e5": 1})

    def test_empty_bm25_uses_embedding_order(self):
        r = fuse_rrf({"bm25": [], "e5": ["C", "B", "A"]})
        self.assertEqual([x["chunk_id"] for x in r], ["C", "B", "A"])

    def test_both_empty_returns_empty(self):
        self.assertEqual(fuse_rrf({"bm25": [], "e5": []}), [])

    def test_deterministic_ties_use_chunk_id(self):
        r = fuse_rrf({"bm25": ["WB-006"], "e5": ["WB-002"]})
        self.assertEqual([x["chunk_id"] for x in r], ["WB-002", "WB-006"])

    def test_duplicates_or_invalid_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            fuse_rrf({"bm25": ["A", "A"], "e5": ["B"]})
        with self.assertRaises(ValueError):
            fuse_rrf({"bm25": ["A"]}, rank_constant=0)
        with self.assertRaises(ValueError):
            fuse_rrf({"bm25": ["A"]}, limit=0)

    def test_rank_constant_is_not_top_k(self):
        a = fuse_rrf({"bm25": ["A", "B"], "e5": ["B", "A"]}, rank_constant=60, limit=1)
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["chunk_id"], "A")

    def test_never_uses_gold_ids_to_compute_rrf(self):
        saved = {"k": 3, "cases": [
            {"case_id": "Q1", "method": "bm25", "retrieved_ids": ["A", "C"],
             "acceptable_ids": ["B"], "status": "OK"},
            {"case_id": "Q1", "method": "embedding", "retrieved_ids": ["B", "A"],
             "acceptable_ids": ["B"], "status": "OK"},
        ]}
        gold = {"cases": [{"case_id": "Q1", "question": "test question", "acceptable_chunk_ids": ["B"]}]}
        report = evaluate_rrf(saved, gold)
        # A는 검색기 2곳에 등장해 Gold B보다 앞선다. 정답을 보고 RRF를 조작하지 않는다.
        self.assertEqual(report["cases"][0]["rrf_ranking"][0]["chunk_id"], "A")
        self.assertEqual(report["summary"]["rrf"]["hit_at_1"], 0)

    def test_missing_source_or_gold_mismatch_is_rejected(self):
        gold = {"cases": [{"case_id": "Q1", "question": "?", "acceptable_chunk_ids": ["A"]}]}
        saved = {"k": 3, "cases": [
            {"case_id": "Q1", "method": "bm25", "retrieved_ids": ["A"],
             "acceptable_ids": ["A"], "status": "OK"},
        ]}
        with self.assertRaises(ValueError):
            evaluate_rrf(saved, gold)
        saved["cases"].append({"case_id": "Q1", "method": "embedding", "retrieved_ids": ["B"],
                               "acceptable_ids": ["C"], "status": "OK"})
        with self.assertRaises(ValueError):
            evaluate_rrf(saved, gold)

    def test_original_saved_practice_result_when_available(self):
        ranking_path = ROOT / "experiments" / "step04" / "metrics_recomputed.json"
        gold_path = ROOT / "data" / "gold" / "mini10_gold_step02.json"
        if not ranking_path.is_file() or not gold_path.is_file():
            self.skipTest("실습 원시 순위 또는 Gold가 없으면 통합 테스트 건너뜀")
        r = evaluate_rrf(json.loads(ranking_path.read_text(encoding="utf-8")),
                         json.loads(gold_path.read_text(encoding="utf-8")))
        self.assertEqual(r["summary"]["bm25"]["hit_at_1"], 6)
        self.assertEqual(r["summary"]["embedding"]["hit_at_3"], 8)
        self.assertEqual(r["summary"]["rrf"]["hit_at_1"], 6)
        self.assertEqual(r["summary"]["rrf"]["hit_at_3"], 9)
        self.assertEqual(r["summary"]["rrf"]["mrr_at_3"], 0.7)


if __name__ == "__main__":
    unittest.main()
