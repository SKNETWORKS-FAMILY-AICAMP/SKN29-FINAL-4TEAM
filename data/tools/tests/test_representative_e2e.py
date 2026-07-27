from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
REPO_ROOT = DATA_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.config import load_pipeline
from watercare.validation import validate_representative_e2e


class RepresentativeE2EInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)
        cls.contract = cls.config.config("e2e")

    def test_cross_document_and_fixture_invariants_pass(self) -> None:
        result = validate_representative_e2e(self.config)
        self.assertEqual("PASS", result["status"], result["errors"])
        self.assertEqual(4, result["summary"]["documents_checked"])
        self.assertGreaterEqual(result["summary"]["checks"], 15)

    def test_wrong_manual_page_is_detected(self) -> None:
        drifted = deepcopy(self.contract)
        drifted["manual_page"] = 37
        result = validate_representative_e2e(self.config, contract=drifted)
        self.assertEqual("FAIL", result["status"])
        self.assertIn(
            "representative_e2e:representative_evidence_lineage",
            result["errors"],
        )

    def test_workflow_order_drift_is_detected(self) -> None:
        drifted = deepcopy(self.contract)
        drifted["expected_events"][2:4] = reversed(drifted["expected_events"][2:4])
        result = validate_representative_e2e(self.config, contract=drifted)
        self.assertEqual("FAIL", result["status"])
        self.assertIn(
            "representative_e2e:representative_workflow_sequence",
            result["errors"],
        )

    def test_retired_representative_placeholders_are_absent_from_screen_spec(self) -> None:
        screen = (
            REPO_ROOT / "docs" / "planning" / "md" / "화면설계서.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("MAN-WPU-JAC104D-P38-LOW-FLOW", screen)
        self.assertNotIn("EVD-JAC104D-MAN-P38-LOW-FLOW", screen)


if __name__ == "__main__":
    unittest.main()
