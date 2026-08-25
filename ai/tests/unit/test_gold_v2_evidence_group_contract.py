from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "ai/evaluation/contracts/gold_v2_evidence_group_contract.json"
)
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "ai/evaluation/schemas/gold_v2_evidence_group_contract.schema.json"
)
REGISTRY_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "ai/evaluation/schemas/evidence_group_registry_v2.schema.json"
)
GROUP_ID_PATTERN = re.compile(r"^EVD-WPUJAC104DWH-[A-Z0-9-]+-001$")
CHILD_ID_PATTERN = re.compile(r"^CHILD-WPUJAC104DWH-P\d{3}-[A-Z0-9-]+-001$")


class GoldV2EvidenceGroupContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        cls.groups = cls.contract["groups"]

    def test_contract_identity_and_rules_are_fixed(self) -> None:
        self.assertEqual(self.contract["contract_version"], "2.0.0-draft.1")
        self.assertEqual(
            self.contract["status"],
            "AI_OWNER_DECISION_DATA_QA_ACK_PENDING",
        )

    def test_contract_matches_json_schema(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        errors = sorted(
            Draft202012Validator(schema).iter_errors(self.contract),
            key=lambda error: list(error.absolute_path),
        )
        self.assertEqual([error.message for error in errors], [])
        self.assertEqual(
            self.contract["rules"],
            {
                "gold_identity_unit": "EVIDENCE_GROUP",
                "group_variant_policy": "ANY_REGISTERED_SEARCH_CANDIDATE_CHILD",
                "gold_child_ids_allowed": False,
                "page_ids_allowed_as_gold_identity": False,
                "context_only_counts_as_hit": False,
                "case_labels_override_group_defaults": True,
            },
        )

    def test_each_group_is_a_canonical_registry_v2_row(self) -> None:
        schema = json.loads(REGISTRY_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)

        errors = [
            error.message
            for group in self.groups
            for error in validator.iter_errors(group)
        ]
        self.assertEqual(errors, [])
        for group in self.groups:
            self.assertEqual(len(group["child_ids"]), len(group["source_variant_ids"]))

    def test_group_and_child_ids_are_unique_and_well_formed(self) -> None:
        group_ids = [row["evidence_group_id"] for row in self.groups]
        child_ids = [child for row in self.groups for child in row["child_ids"]]
        self.assertEqual(len(self.groups), 12)
        self.assertEqual(len(group_ids), len(set(group_ids)))
        self.assertEqual(len(child_ids), len(set(child_ids)))
        self.assertTrue(all(GROUP_ID_PATTERN.fullmatch(value) for value in group_ids))
        self.assertTrue(all(CHILD_ID_PATTERN.fullmatch(value) for value in child_ids))

    def test_p004_and_p005_semantic_groups_are_explicit(self) -> None:
        by_id = {row["evidence_group_id"]: row for row in self.groups}
        expected = {
            "EVD-WPUJAC104DWH-SPRAY-FIRE-PREVENTION-001": [4],
            "EVD-WPUJAC104DWH-WATER-INGRESS-PREVENTION-001": [4],
            "EVD-WPUJAC104DWH-LEAK-001": [5, 7, 38],
            "EVD-WPUJAC104DWH-BURNING-ODOR-RESPONSE-001": [5],
        }
        self.assertTrue(expected.keys() <= by_id.keys())
        for group_id, pages in expected.items():
            self.assertEqual(by_id[group_id]["page_refs"], pages)

        leak = by_id["EVD-WPUJAC104DWH-LEAK-001"]
        self.assertEqual(
            leak["child_ids"],
            [
                "CHILD-WPUJAC104DWH-P005-LEAK-001",
                "CHILD-WPUJAC104DWH-P007-LEAK-001",
                "CHILD-WPUJAC104DWH-P038-LEAK-001",
            ],
        )

    def test_broad_cold_and_hot_groups_are_fully_superseded(self) -> None:
        cold = [
            row for row in self.groups
            if row["supersedes_group_id"]
            == "EVD-WPUJAC104DWH-COLD-TEMPERATURE-001"
        ]
        hot = [
            row for row in self.groups
            if row["supersedes_group_id"]
            == "EVD-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001"
        ]
        self.assertEqual(len(cold), 2)
        self.assertEqual(len(hot), 6)
        self.assertEqual(
            {row["topic_code"] for row in cold},
            {"COLD_TEMPERATURE_NORMAL_CHECK", "COLD_TEMPERATURE_FAULT"},
        )
        self.assertEqual(
            {row["topic_code"] for row in hot},
            {
                "HOT_STEAM",
                "HOT_INTERRUPTION",
                "HOT_LUKEWARM",
                "HOT_NO_OUTPUT",
                "HOT_MODULE_CHECK",
                "HOT_CHECK_PROCESS",
            },
        )

    def test_contract_contains_no_source_text_or_runtime_secrets(self) -> None:
        forbidden_keys = {
            "text",
            "child_text",
            "source_text",
            "prompt",
            "vector",
            "dsn",
            "api_key",
            "token",
        }

        def visit(value: object) -> None:
            if isinstance(value, dict):
                self.assertTrue(forbidden_keys.isdisjoint(value))
                for nested in value.values():
                    visit(nested)
            elif isinstance(value, list):
                for nested in value:
                    visit(nested)

        visit(self.contract)


if __name__ == "__main__":
    unittest.main()
