"""Static ownership gates for Data and Contract CI."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_WORKFLOW = ROOT / ".github/workflows/data-ci.yml"
CONTRACT_WORKFLOW = ROOT / ".github/workflows/contracts-ci.yml"


class DataCIWorkflowTests(unittest.TestCase):
    def test_contract_ci_exclusively_owns_state_machine_validation(self) -> None:
        data_text = DATA_WORKFLOW.read_text(encoding="utf-8")
        contract_text = CONTRACT_WORKFLOW.read_text(encoding="utf-8")
        commands = (
            "scripts/contracts/validate_state_machine.py",
            "scripts/contracts/render_state_machine.py --check",
        )
        for command in commands:
            with self.subTest(command=command):
                self.assertNotIn(command, data_text)
                self.assertEqual(contract_text.count(command), 1)

    def test_data_ci_keeps_contract_compatibility_without_validator_trigger(self) -> None:
        text = DATA_WORKFLOW.read_text(encoding="utf-8")
        contract_text = CONTRACT_WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(text.count('      - "contracts/state-machine/**"'), 2)
        self.assertNotIn('      - "scripts/contracts/**"', text)
        self.assertEqual(
            text.count('      - "tests/deployment/test_data_ci_workflow.py"'), 2
        )
        self.assertEqual(
            contract_text.count(
                '      - "tests/deployment/test_data_ci_workflow.py"'
            ),
            2,
        )
        self.assertIn("tests.deployment.test_data_ci_workflow -v", text)
        self.assertIn("tests.deployment.test_data_ci_workflow -v", contract_text)
        self.assertIn("python -B -m unittest discover -s data/tools/tests -v", text)
        self.assertIn("python -B data/tools/pipeline.py qa --verify-rebuild", text)
        self.assertIn("git diff --exit-code -- data", text)


if __name__ == "__main__":
    unittest.main()
