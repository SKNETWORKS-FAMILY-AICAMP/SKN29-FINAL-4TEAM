from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.config import load_pipeline
from watercare.io import data_path, read_json, read_jsonl, sha256_file
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

    def test_db_smoke_selects_six_existing_scenarios(self) -> None:
        selected = self.definitions["profiles"]["db-smoke"]["selection"][
            "scenario_ids"
        ]
        inquiries = read_json(DATA_ROOT / "synthetic/fixtures/inquiries.json")
        available = {row["scenario_id"] for row in inquiries}
        self.assertEqual(6, len(selected))
        self.assertEqual(6, len(set(selected)))
        self.assertLessEqual(set(selected), available)

    def test_db_profiles_record_verified_runtime_import(self) -> None:
        fixture_paths = {
            f"synthetic/fixtures/{name}.json"
            for name in (
                "users",
                "customer_profiles",
                "products",
                "customer_products",
                "subscriptions",
                "inquiries",
                "consultations",
                "visits",
                "followup_confirmations",
                "care_histories",
                "inquiry_status_histories",
                "audit_events",
            )
        }
        expected_readiness = {
            "db-smoke": "DB_SMOKE_VERIFIED",
            "db-full": "DB_FULL_VERIFIED",
        }
        for profile_name in ("db-smoke", "db-full"):
            profile = self.definitions["profiles"][profile_name]
            self.assertEqual(
                expected_readiness[profile_name],
                profile["readiness"],
            )
            self.assertEqual(
                "NONE",
                profile["contract_dependency"],
            )
            items = {
                row["path"]: row["role"]
                for row in profile["items"]
            }
            self.assertLessEqual(fixture_paths, set(items))
            self.assertEqual(
                "MAPPING_DB_FULL_VERIFIED",
                items["config/handoff/backend_import_crosswalk.json"],
            )

        smoke = self.definitions["profiles"]["db-smoke"]
        smoke_items = {
            row["path"]: row["role"] for row in smoke["items"]
        }
        self.assertEqual(37, smoke["selection"]["source_count"])
        self.assertEqual(
            "VALIDATE_ONLY_PROFILE_EXCLUDED",
            smoke_items["synthetic/fixtures/care_histories.json"],
        )
        self.assertEqual(
            "LOAD_FILTERED",
            smoke_items["synthetic/fixtures/customer_profiles.json"],
        )

        full = self.definitions["profiles"]["db-full"]
        full_items = {
            row["path"]: row["role"] for row in full["items"]
        }
        self.assertEqual(367, full["selection"]["source_count"])
        self.assertEqual(
            "LOAD",
            full_items["synthetic/fixtures/care_histories.json"],
        )
        self.assertEqual(
            "LOAD",
            full_items["synthetic/fixtures/customer_profiles.json"],
        )
        self.assertEqual(
            "PROJECT",
            full_items["synthetic/fixtures/customer_products.json"],
        )

    def test_handoff_manifest_is_deterministic(self) -> None:
        first = build_handoff_manifest(self.config)
        target = self.config.path("handoff_manifest")
        first_hash = sha256_file(target)
        second = build_handoff_manifest(self.config)
        self.assertEqual(first["summary"], second["summary"])
        self.assertEqual(first_hash, sha256_file(target))


if __name__ == "__main__":
    unittest.main()
