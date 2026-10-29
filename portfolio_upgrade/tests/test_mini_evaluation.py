"""실습 04: 기대 결과를 먼저 정해 둔 작은 단위 테스트 (외부 패키지 불필요)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from evaluate_mini import score_one, evaluate_saved_report  # noqa: E402


class MiniEvaluationTests(unittest.TestCase):
    def test_rank_one_means_hit1_and_rr1(self):
        actual = score_one(["GOOD", "WRONG"], ["GOOD"], 3)
        self.assertEqual(actual["hit_at_1"], 1)
        self.assertEqual(actual["hit_at_3"], 1)
        self.assertEqual(actual["rr_at_3"], 1.0)

    def test_rank_three_is_hit3_but_not_hit1(self):
        actual = score_one(["A", "B", "GOOD"], ["GOOD"], 3)
        self.assertEqual(actual["hit_at_1"], 0)
        self.assertEqual(actual["hit_at_3"], 1)
        self.assertAlmostEqual(actual["rr_at_3"], 1 / 3)

    def test_no_result_is_zero_not_excluded(self):
        actual = score_one([], ["GOOD"], 3)
        self.assertEqual((actual["hit_at_1"], actual["hit_at_3"], actual["rr_at_3"]), (0, 0, 0))

    def test_multiple_alternative_gold_ids_count_as_hit(self):
        actual = score_one(["B"], ["A", "B", "C"], 3)
        self.assertEqual(actual["hit_at_1"], 1)
        self.assertEqual(actual["rr_at_3"], 1.0)

    def test_duplicate_retrieved_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "중복 검색"):
            score_one(["A", "A"], ["B"], 3)

    def test_missing_record_still_counts_in_denominator(self):
        gold = {"cases": [
            {"case_id": "Q1", "acceptable_chunk_ids": ["A"]},
            {"case_id": "Q2", "acceptable_chunk_ids": ["B"]},
        ]}
        saved = {"top_k": 3, "cases": [
            {"method": "embedding", "case_id": "Q1", "gold_ids": ["A"],
             "retrieved": [{"chunk_id": "A"}]},
        ]}
        report = evaluate_saved_report(saved, gold)
        emb = report["summary"]["embedding"]
        self.assertEqual(emb["n_questions"], 2)
        self.assertEqual(emb["hit_at_1"], 1)
        self.assertEqual(emb["missing_count"], 1)
        self.assertEqual(emb["mrr_at_3"], 0.5)
        self.assertEqual(report["summary"]["overlap"]["mrr_at_3"], 0.0)

    def test_search_error_counts_as_zero(self):
        gold = {"cases": [{"case_id": "Q1", "acceptable_chunk_ids": ["A"]}]}
        saved = {"top_k": 3, "cases": [
            {"method": "embedding", "case_id": "Q1", "error_type": "TimeoutError",
             "retrieved": [{"chunk_id": "A"}]},
        ]}
        report = evaluate_saved_report(saved, gold)
        self.assertEqual(report["summary"]["embedding"]["error_count"], 1)
        self.assertEqual(report["summary"]["embedding"]["mrr_at_3"], 0.0)

    def test_recomputes_instead_of_trusting_saved_scores(self):
        gold = {"cases": [{"case_id": "Q1", "acceptable_chunk_ids": ["A"]}]}
        saved = {"top_k": 3, "cases": [
            {"method": "embedding", "case_id": "Q1", "gold_ids": ["A"],
             "retrieved": [{"chunk_id": "A"}], "hit_at_1": 0, "mrr_at_3": 0.0},
        ]}
        report = evaluate_saved_report(saved, gold)
        self.assertEqual(report["summary"]["embedding"]["hit_at_1"], 1)
        self.assertEqual(report["summary"]["embedding"]["mrr_at_3"], 1.0)

    def test_reject_gold_mismatch_and_too_large_k(self):
        gold = {"cases": [{"case_id": "Q1", "acceptable_chunk_ids": ["A"]}]}
        saved = {"top_k": 3, "cases": [
            {"method": "embedding", "case_id": "Q1", "gold_ids": ["B"], "retrieved": []}
        ]}
        with self.assertRaisesRegex(ValueError, "정답지가 다릅니다"):
            evaluate_saved_report(saved, gold)
        with self.assertRaisesRegex(ValueError, "Top-3"):
            evaluate_saved_report({"top_k": 3, "cases": []}, gold, k=5)


if __name__ == "__main__":
    unittest.main()
