from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.config import load_pipeline
from watercare.io import data_path, read_json, read_jsonl
from watercare.operations import build_handoff_manifest


class HandoffProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)
        cls.definitions = cls.config.config("handoff")

    def test_profiles_are_data_only_and_all_paths_exist(self) -> None:
        self.assertTrue(self.definitions["service_contracts_used"])
        self.assertEqual(
            {
                "state_machine_version": "1.0.0",
                "state_machine_status": "TEAM_APPROVED",
                "data_projection_consumes_contract": True,
                "backend_runtime_verified": True,
                "legacy_service_contracts_used_semantics": (
                    "BACKEND_RUNTIME_INTEGRATION_ONLY"
                ),
            },
            self.definitions["contract_alignment"],
        )
        for name, profile in self.definitions["profiles"].items():
            self.assertTrue(profile["items"], name)
            for item in profile["items"]:
                self.assertNotIn("contracts/", item["path"])
                self.assertTrue(data_path(DATA_ROOT, item["path"]).is_file())

    def test_profile_values_are_limited_by_consumer_schema_enums(self) -> None:
        schema = read_json(
            DATA_ROOT / "schemas/config/consumerProfiles.schema.json"
        )
        profile_schema = schema["$defs"]["profile"]["properties"]
        allowed_readiness = set(profile_schema["readiness"]["enum"])
        allowed_dependencies = set(
            profile_schema["contract_dependency"]["enum"]
        )
        allowed_roles = set(
            profile_schema["items"]["items"]["properties"]["role"]["enum"]
        )
        self.assertTrue(schema["properties"]["service_contracts_used"]["const"])
        for name, profile in self.definitions["profiles"].items():
            self.assertIn(profile["readiness"], allowed_readiness, name)
            self.assertIn(
                profile["contract_dependency"],
                allowed_dependencies,
                name,
            )
            for item in profile["items"]:
                self.assertIn(item["role"], allowed_roles, item["path"])

    def test_rag_profile_indexes_only_verified_chunks(self) -> None:
        profile = self.definitions["profiles"]["rag"]
        ingest = [item for item in profile["items"] if item["role"] == "INGEST"]
        self.assertEqual(1, len(ingest))
        self.assertEqual(7, len(read_jsonl(data_path(DATA_ROOT, ingest[0]["path"]))))
        faq = next(
            item
            for item in profile["items"]
            if item["path"].endswith("faq_snapshot_normalized.jsonl")
        )
        self.assertEqual("REFERENCE_ONLY", faq["role"])
        evaluation = next(
            item
            for item in profile["items"]
            if item["role"] == "EVALUATION_CONTRACT"
        )
        cases = read_json(data_path(DATA_ROOT, evaluation["path"]))
        self.assertEqual(12, len(cases["cases"]))
        self.assertEqual(
            {"POSITIVE", "NEGATIVE_SCOPE", "NEGATIVE_SOURCE"},
            {row["case_type"] for row in cases["cases"]},
        )

    def test_rag_expansion_is_candidate_only_and_exact_model_filtered(self) -> None:
        profile = self.definitions["profiles"]["rag-expansion"]
        self.assertEqual("DATA_READY_AI_REVERIFY_REQUIRED", profile["readiness"])
        self.assertEqual(
            "BACKEND_RUNTIME_MAPPING_PENDING",
            profile["contract_dependency"],
        )
        roles = {item["path"]: item["role"] for item in profile["items"]}
        self.assertEqual(
            "INGEST_CANDIDATE",
            roles["processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl"],
        )
        self.assertEqual(
            "CONTEXT_ONLY",
            roles["processed/structured/rag/expansion/rag_parent_pages_3model_v1.jsonl"],
        )
        self.assertEqual("exact_sales_code", profile["selection"]["required_pre_score_filter"])

    def test_db_smoke_selects_six_existing_scenarios(self) -> None:
        selected = self.definitions["profiles"]["db-smoke"]["selection"][
            "scenario_ids"
        ]
        inquiries = read_json(DATA_ROOT / "synthetic/fixtures/inquiries.json")
        available = {row["scenario_id"] for row in inquiries}
        self.assertEqual(6, len(selected))
        self.assertEqual(6, len(set(selected)))
        self.assertLessEqual(set(selected), available)
        self.assertEqual(
            37,
            self.definitions["profiles"]["db-smoke"]["selection"][
                "source_count"
            ],
        )

    def test_db_smoke_roles_match_verified_37_item_closure(self) -> None:
        profile = self.definitions["profiles"]["db-smoke"]
        self.assertEqual("DB_SMOKE_VERIFIED", profile["readiness"])
        self.assertEqual("NONE", profile["contract_dependency"])
        items = {row["path"]: row["role"] for row in profile["items"]}
        expected_fixture_roles = {
            "synthetic/fixtures/users.json": "LOAD_FILTERED",
            "synthetic/fixtures/customer_profiles.json": "LOAD_FILTERED",
            "synthetic/fixtures/products.json": "LOAD_FILTERED",
            "synthetic/fixtures/customer_products.json": "PROJECT_FILTERED",
            "synthetic/fixtures/subscriptions.json": "LOAD_FILTERED",
            "synthetic/fixtures/inquiries.json": "LOAD_FILTERED",
            "synthetic/fixtures/consultations.json": "LOAD_FILTERED",
            "synthetic/fixtures/visits.json": "LOAD_FILTERED",
            "synthetic/fixtures/followup_confirmations.json": (
                "VALIDATE_ONLY_PROFILE_EXCLUDED"
            ),
            "synthetic/fixtures/care_histories.json": (
                "VALIDATE_ONLY_PROFILE_EXCLUDED"
            ),
            "synthetic/fixtures/inquiry_status_histories.json": (
                "VALIDATE_ONLY_PROFILE_EXCLUDED"
            ),
            "synthetic/fixtures/audit_events.json": (
                "VALIDATE_ONLY_PROFILE_EXCLUDED"
            ),
        }
        self.assertEqual(
            expected_fixture_roles,
            {
                path: role
                for path, role in items.items()
                if path.startswith("synthetic/fixtures/")
            },
        )
        self.assertEqual(
            "MAPPING_DB_FULL_VERIFIED",
            items["config/handoff/backend_import_crosswalk.json"],
        )

    def test_db_full_roles_match_verified_367_item_closure(self) -> None:
        profile = self.definitions["profiles"]["db-full"]
        self.assertEqual("DB_FULL_VERIFIED", profile["readiness"])
        self.assertEqual("NONE", profile["contract_dependency"])
        self.assertEqual(367, profile["selection"]["source_count"])
        self.assertEqual(
            ["SYN-JAC104-012", "SYN-JAC104-016"],
            profile["selection"]["excluded_scenario_ids"],
        )
        items = {row["path"]: row["role"] for row in profile["items"]}
        fixture_roles = {
            path: role
            for path, role in items.items()
            if path.startswith("synthetic/fixtures/")
        }
        self.assertEqual(12, len(fixture_roles))
        self.assertEqual(
            "PROJECT",
            fixture_roles.pop("synthetic/fixtures/customer_products.json"),
        )
        self.assertEqual(
            "LOAD_FILTERED",
            fixture_roles.pop("synthetic/fixtures/products.json"),
        )
        self.assertEqual({"LOAD"}, set(fixture_roles.values()))
        self.assertEqual(
            "MAPPING_DB_FULL_VERIFIED",
            items["config/handoff/backend_import_crosswalk.json"],
        )

    def test_handoff_manifest_is_deterministic(self) -> None:
        with patch("watercare.operations.write_json") as write_json_mock:
            first = build_handoff_manifest(self.config)
            first_manifest = write_json_mock.call_args.args[2]
            second = build_handoff_manifest(self.config)
            second_manifest = write_json_mock.call_args.args[2]
        self.assertEqual(first["summary"], second["summary"])
        self.assertEqual(first_manifest, second_manifest)
        self.assertTrue(first_manifest["service_contracts_used"])
        self.assertEqual(2, write_json_mock.call_count)


if __name__ == "__main__":
    unittest.main()
