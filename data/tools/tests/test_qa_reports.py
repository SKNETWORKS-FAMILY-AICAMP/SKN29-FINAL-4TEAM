from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.config import load_pipeline
from watercare.io import read_json, sha256_file


class QaReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)

    def test_summary_tracks_all_current_detailed_report_hashes(self) -> None:
        summary = read_json(self.config.path("qa_summary"))
        expected_paths = {
            self.config.path(name).relative_to(DATA_ROOT).as_posix()
            for name in (
                "schema_report",
                "integrity_report",
                "quality_report",
                "business_report",
                "reproducibility_report",
            )
        }
        reports = {row["path"]: row for row in summary["reports"]}
        self.assertEqual(expected_paths, set(reports))
        for path, item in reports.items():
            report_path = DATA_ROOT / path
            report = read_json(report_path)
            self.assertEqual(self.config.dataset_version, report["dataset_version"])
            self.assertEqual(self.config.generated_at, report["generated_at"])
            self.assertIsInstance(report["records"], int)
            self.assertEqual(item["sha256"], sha256_file(report_path))

    def test_detailed_reports_hold_current_projection_counts(self) -> None:
        business = read_json(self.config.path("business_report"))
        integrity = read_json(self.config.path("integrity_report"))
        self.assertEqual(24, business["summary"]["source_scenarios"])
        self.assertEqual(22, business["summary"]["active_scenarios"])
        self.assertEqual(33, business["summary"]["subset_records"])
        self.assertEqual(125, integrity["summary"]["status_histories"])
        self.assertEqual(125, integrity["summary"]["audit_events"])
        self.assertEqual(12, integrity["summary"]["customer_profiles"])


if __name__ == "__main__":
    unittest.main()
