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
from watercare.io import read_json, sha256_file
from watercare.validation import (
    contract_risk_codes,
    contract_usage_codes,
    schema_risk_codes,
    schema_usage_codes,
    validate_schema,
)


class ConfigContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)

    def test_all_declarative_configs_match_static_schemas(self) -> None:
        for name, relative in self.config.values["config_schemas"].items():
            value = self.config.values if name == "pipeline" else self.config.config(name)
            schema = read_json(DATA_ROOT / relative)
            self.assertEqual([], validate_schema(value, schema), name)

    def test_usage_codes_match_contract_and_data_schemas(self) -> None:
        contract = contract_usage_codes(REPO_ROOT / "contracts")
        configured = self.config.config("workflow")["usage_guidance_statuses"]
        self.assertEqual(contract, configured)
        for name, codes in schema_usage_codes(DATA_ROOT).items():
            self.assertEqual(contract, codes, name)

    def test_risk_codes_match_contract_and_data_schemas(self) -> None:
        contract = contract_risk_codes(REPO_ROOT / "contracts")
        configured = self.config.config("workflow")["risk_levels"]
        self.assertEqual(["general", "caution", "danger"], contract)
        self.assertEqual(contract, configured)
        for name, codes in schema_risk_codes(DATA_ROOT).items():
            self.assertEqual(contract, codes, name)

    def test_retired_usage_code_is_absent_from_active_files(self) -> None:
        retired = "USE_" + "ALLOWED"
        suffixes = {".json", ".jsonl", ".yaml", ".yml", ".py"}
        hits: list[str] = []
        for root in (DATA_ROOT, REPO_ROOT / "contracts"):
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in suffixes:
                    if retired in path.read_text(encoding="utf-8"):
                        hits.append(path.relative_to(REPO_ROOT).as_posix())
        self.assertEqual([], hits)

    def test_danger_never_allows_normal_usage(self) -> None:
        definitions = self.config.config("synthetic")
        violations = [
            row["scenario_id"]
            for row in definitions["scenario_matrix"]
            if row["risk_level"] == "danger"
            and row["usage_guidance_status"] == "NORMAL"
        ]
        inquiries = definitions["materialized_outputs"]["inquiries"]
        violations.extend(
            row["scenario_id"]
            for row in inquiries
            if row["risk_level"] == "danger"
            and row["usage_guidance_status"] == "NORMAL"
        )
        self.assertEqual([], violations)

    def test_inquiry_number_accepts_demo_contract(self) -> None:
        schema = read_json(
            DATA_ROOT / "schemas" / "synthetic" / "syntheticInquiry.schema.json"
        )
        inquiry = deepcopy(
            self.config.config("synthetic")["materialized_outputs"]["inquiries"][0]
        )
        inquiry["inquiry_number"] = "DEMO-INQ-002"
        self.assertEqual([], validate_schema(inquiry, schema))
        inquiry["inquiry_number"] = "DEMO-002"
        self.assertNotEqual([], validate_schema(inquiry, schema))

    def test_workflow_actions_match_state_machine_contract(self) -> None:
        workflow = self.config.config("workflow")
        states = workflow["inquiry_statuses"]
        contract_states = [
            line.strip()[2:]
            for line in (
                REPO_ROOT / "contracts" / "state-machine" / "inquiry-states.yaml"
            ).read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("- ")
        ]
        contract_events = {
            line.strip()[2:]
            for line in (
                REPO_ROOT / "contracts" / "state-machine" / "inquiry-events.yaml"
            ).read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("- ")
        }
        configured_actions = {
            action
            for actions in workflow["allowed_actions"].values()
            for action in actions
        }
        self.assertEqual(contract_states, states)
        self.assertLessEqual(configured_actions - {"UPDATE_PRODUCT"}, contract_events)
        retired_answer_event = "SUBMIT_" + "FOLLOWUP_ANSWER"
        self.assertNotIn(retired_answer_event, configured_actions)
        self.assertIn(
            "SUBMIT_RESOLUTION_FEEDBACK",
            workflow["allowed_actions"]["COMPLETION_PENDING"],
        )

    def test_dataset_version_is_e2e_release(self) -> None:
        self.assertEqual("0.8.0", self.config.dataset_version)

    def test_dataset_manifest_version_and_hashes_are_current(self) -> None:
        manifest = read_json(self.config.path("dataset_manifest"))
        self.assertEqual(self.config.dataset_version, manifest["dataset_version"])
        for item in manifest["files"]:
            path = DATA_ROOT / item["path"]
            self.assertEqual(item["sha256"], sha256_file(path), item["path"])


if __name__ == "__main__":
    unittest.main()
