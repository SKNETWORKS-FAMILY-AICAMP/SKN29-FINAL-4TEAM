"""Legacy 7청크 Smoke 산출물 테스트."""

import json
import tempfile
import unittest
from pathlib import Path

from ai.scripts.run_legacy_7chunk_smoke import REPOSITORY_ROOT, build_smoke_artifacts


class LegacySevenChunkSmokeTest(unittest.TestCase):
    def test_historical_snapshot_keeps_retrieval_and_policy_metrics_separate(self):
        profile = REPOSITORY_ROOT / "ai/configs/experiments/legacy_7chunk_smoke_v1.yaml"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            summary = build_smoke_artifacts(profile, output)

            self.assertEqual(summary["run_status"], "SNAPSHOT_COMPLETE")
            self.assertFalse(summary["fresh_reproduction"])
            self.assertFalse(summary["metrics_publishable_as_current_run"])
            self.assertEqual(summary["case_counts"], {
                "total": 12,
                "retrieval_positive": 7,
                "policy_block": 5,
            })
            self.assertEqual(
                summary["retrieval_positive_metrics"]["mean_recall_at_5"],
                1.0,
            )
            self.assertEqual(summary["known_weakness"]["first_relevant_rank"], 5)
            self.assertAlmostEqual(
                summary["interpretation_guard"]["random_single_relevant_recall_at_5_reference"],
                5 / 7,
                places=6,
            )
            self.assertTrue((output / "manifest.json").is_file())
            self.assertTrue((output / "case_results.jsonl").is_file())
            self.assertTrue((output / "summary.json").is_file())

            cases = [
                json.loads(line)
                for line in (output / "case_results.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            policy_cases = [case for case in cases if case["evaluation_bucket"] == "POLICY_BLOCK"]
            self.assertEqual(len(policy_cases), 5)
            self.assertTrue(all(case["recall_at_5"] is None for case in policy_cases))

if __name__ == "__main__":
    unittest.main()
