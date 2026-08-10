"""Contract tests for the Action–OpenAPI–Runtime crosswalk."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = REPO_ROOT / "scripts" / "contracts"
sys.path.insert(0, str(SCRIPT_DIR))

import validate_contract_crosswalk as validator  # noqa: E402


class ActionOperationCrosswalkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        (
            cls.crosswalk_path,
            cls.crosswalk,
            cls.registry,
            cls.allowed_actions,
            cls.inquiry_events,
            cls.operations,
        ) = validator.load_repository_documents(REPO_ROOT)

    def validate(self, crosswalk: dict) -> validator.ValidationSummary:
        return validator.validate_documents(
            repo_root=REPO_ROOT,
            crosswalk_path=self.crosswalk_path,
            crosswalk=crosswalk,
            registry=self.registry,
            allowed_actions=self.allowed_actions,
            inquiry_events=self.inquiry_events,
            operations=self.operations,
        )

    def test_current_crosswalk_matches_all_sources(self) -> None:
        result = self.validate(deepcopy(self.crosswalk))

        self.assertEqual(23, result.total_actions)
        self.assertEqual(
            {
                "RUNTIME_IMPLEMENTED": 12,
                "OPENAPI_CONFIRMED": 7,
                "CONTRACT_ONLY": 0,
                "DEFERRED": 4,
            },
            result.classifications,
        )
        self.assertEqual(19, result.confirmed_operations)

    def test_rejects_http_path_drift(self) -> None:
        crosswalk = deepcopy(self.crosswalk)
        start_consultation = next(
            item
            for item in crosswalk["actions"]
            if item["action"] == "START_CONSULTATION"
        )
        start_consultation["openapi"]["path"] = "/incorrect"

        with self.assertRaisesRegex(validator.ContractError, "HTTP 연결"):
            self.validate(crosswalk)

    def test_rejects_runtime_without_test_evidence(self) -> None:
        crosswalk = deepcopy(self.crosswalk)
        submit_symptom = next(
            item
            for item in crosswalk["actions"]
            if item["action"] == "SUBMIT_SYMPTOM"
        )
        submit_symptom["runtime"]["test_evidence"] = []

        with self.assertRaisesRegex(validator.ContractError, "Source와 Test 증거"):
            self.validate(crosswalk)

    def test_rejects_summary_drift(self) -> None:
        crosswalk = deepcopy(self.crosswalk)
        crosswalk["summary"]["RUNTIME_IMPLEMENTED"] = 13

        with self.assertRaisesRegex(
            validator.ContractError, "summary.RUNTIME_IMPLEMENTED"
        ):
            self.validate(crosswalk)


if __name__ == "__main__":
    unittest.main()
