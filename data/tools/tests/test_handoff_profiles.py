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
        self.assertFalse(self.definitions["service_contracts_used"])
        self.assertEqual(
            {
                "state_machine_version": "1.0.0",
                "state_machine_status": "TEAM_APPROVED",
                "data_projection_consumes_contract": True,
                "backend_runtime_verified": False,
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

    def test_db_profiles_use_crosswalk_and_exclude_unconfirmed_care_load(self) -> None:
        for profile_name in ("db-smoke", "db-full"):
            self.assertEqual(
                "BACKEND_RUNTIME_MAPPING_PENDING",
                self.definitions["profiles"][profile_name][
                    "contract_dependency"
                ],
            )
            items = {
                row["path"]: row["role"]
                for row in self.definitions["profiles"][profile_name]["items"]
            }
            self.assertEqual(
                "MAPPING_NOT_DB_VERIFIED",
                items["config/handoff/backend_import_crosswalk.json"],
            )
            self.assertEqual(
                "EXCLUDE_BLOCKED_OWNER_CONFIRMATION",
                items["synthetic/fixtures/care_histories.json"],
            )
            self.assertEqual(
                "LOAD_AFTER_LOOKUP_MAPPING",
                items["synthetic/fixtures/customer_profiles.json"],
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
