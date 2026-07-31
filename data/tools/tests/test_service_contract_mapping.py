from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.config import load_pipeline
from watercare.io import normalize_text_bytes, read_json, sha256_bytes
from watercare.validation import (
    validate_backend_import_crosswalk,
    validate_contract_alignment_registry,
    validate_schema,
    validate_service_contract_mapping,
)


class ServiceContractMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)
        cls.mapping = cls.config.config("contract_mapping")

    def test_contract_sources_and_vocabularies_are_current(self) -> None:
        self.assertEqual([], validate_service_contract_mapping(self.config))
        self.assertEqual(
            {
                "data_state_crosswalk",
                "representative_e2e_contract",
                "adr_0010_identifier_bridge",
                "adr_0011_idempotency_scope",
                "t005_physical_contract_v1_3",
                "public_api_idempotency_conflict",
                "care_results",
            },
            set(self.mapping["contract_sources"]) - {
                "user_roles",
                "inquiry_states",
                "inquiry_events",
                "transition_rules",
                "allowed_actions",
            },
        )
        self.assertEqual(
            {
                "version": "1.0.0",
                "status": "TEAM_APPROVED",
                "data_projection_consumes_contract": True,
                "backend_runtime_verified": True,
            },
            self.mapping["state_machine_contract"],
        )

    def test_care_results_match_contract_schema_and_fixture_values(
        self,
    ) -> None:
        contract_text = (
            DATA_ROOT.parent / "contracts" / "codes" / "care-results.yaml"
        ).read_text(encoding="utf-8")
        contract_codes = set(
            re.findall(
                r"^\s*-\s+([A-Z][A-Z0-9_]*)\s*$",
                contract_text,
                re.M,
            )
        )
        care_schema = read_json(
            DATA_ROOT
            / "schemas"
            / "synthetic"
            / "syntheticCareHistory.schema.json"
        )
        fixture_rows = read_json(
            DATA_ROOT / "synthetic" / "fixtures" / "care_histories.json"
        )

        self.assertEqual(
            {"NORMAL", "FILTER_REPLACED", "ISSUE_RESOLVED"},
            contract_codes,
        )
        self.assertEqual(
            contract_codes,
            set(care_schema["properties"]["result"]["enum"]),
        )
        self.assertEqual(
            contract_codes,
            {row["result"] for row in fixture_rows},
        )

    def test_text_source_hash_is_line_ending_and_bom_independent(self) -> None:
        lf = b"version: 1\nstate: approved\n"
        crlf = b"version: 1\r\nstate: approved\r\n"
        cr = b"version: 1\rstate: approved\r"
        bom = b"\xef\xbb\xbf" + cr

        expected = sha256_bytes(normalize_text_bytes(lf))
        for variant in (crlf, cr, bom):
            self.assertEqual(
                expected,
                sha256_bytes(normalize_text_bytes(variant)),
            )
        self.assertEqual(
            {
                "algorithm": "SHA-256",
                "encoding": "UTF-8",
                "bom": "IGNORE",
                "text_line_endings": "LF",
            },
            self.mapping["hash_policy"],
        )

    def test_text_source_hash_changes_when_content_changes(self) -> None:
        approved = normalize_text_bytes(b"version: 1\nstate: approved\n")
        blocked = normalize_text_bytes(b"version: 1\nstate: blocked\n")
        self.assertNotEqual(sha256_bytes(approved), sha256_bytes(blocked))

    def test_text_source_hash_rejects_invalid_utf8(self) -> None:
        with self.assertRaises(UnicodeDecodeError):
            normalize_text_bytes(b"version: 1\nstate: \xff\n")

    def test_backend_crosswalk_is_db_full_verified(self) -> None:
        self.assertEqual([], validate_backend_import_crosswalk(self.config))
        crosswalk = self.config.config("backend_crosswalk")
        self.assertEqual("2.0.0", crosswalk["mapping_version"])
        self.assertEqual("DB_FULL_VERIFIED", crosswalk["status"])
        self.assertTrue(crosswalk["service_contracts_used"])
        self.assertEqual(17, len(crosswalk["backend_sources"]))
        self.assertEqual(
            "FORBIDDEN",
            crosswalk["identifier_resolution"]["backend_primary_key_injection"],
        )
        mappings = {
            row["fixture"]: row
            for row in crosswalk["entity_mappings"]
        }
        expected_fixtures = {
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
        self.assertEqual(expected_fixtures, set(mappings))
        self.assertEqual(12, len(crosswalk["entity_mappings"]))
        self.assertEqual(
            "PROJECTED",
            mappings[
                "synthetic/fixtures/customer_products.json"
            ]["load_mode"],
        )
        self.assertTrue(
            all(
                row["load_mode"] == "DIRECT"
                for path, row in mappings.items()
                if path != "synthetic/fixtures/customer_products.json"
            )
        )
        self.assertEqual(
            "PROJECTED_DB_FULL_VERIFIED",
            mappings[
                "synthetic/fixtures/customer_products.json"
            ]["readiness"],
        )
        self.assertTrue(
            all(
                row["readiness"] == "DB_FULL_VERIFIED"
                for path, row in mappings.items()
                if path != "synthetic/fixtures/customer_products.json"
            )
        )
        self.assertEqual(
            "full_name",
            mappings["synthetic/fixtures/users.json"][
                "field_mappings"
            ]["display_name"],
        )
        self.assertEqual(
            "model_name",
            mappings["synthetic/fixtures/products.json"][
                "field_mappings"
            ]["product_model"],
        )
        inquiry_mapping = mappings[
            "synthetic/fixtures/inquiries.json"
        ]
        self.assertEqual(
            ["inquiries.SymptomEntry"],
            inquiry_mapping["derived_backend_models"],
        )
        care_mapping = mappings[
            "synthetic/fixtures/care_histories.json"
        ]["field_mappings"]
        self.assertEqual("performed_on", care_mapping["performed_on"])
        self.assertEqual("result_code", care_mapping["result"])
        self.assertEqual(
            {
                "REGULAR_INSPECTION": "PERIODIC_CHECK",
                "FILTER_REPLACEMENT": "FILTER_REPLACEMENT",
                "VISIT_SERVICE": "VISIT_SERVICE",
            },
            crosswalk["code_mappings"]["care_type"],
        )
        self.assertEqual([], crosswalk["blocked_mappings"])

        verification = crosswalk["verification"]
        self.assertEqual("DB_FULL_VERIFIED", verification["status"])
        self.assertEqual(
            verification["expected"]["db-smoke"],
            verification["actual"]["db-smoke"],
        )
        self.assertEqual(
            verification["expected"]["db-full"],
            verification["actual"]["db-full"],
        )
        self.assertTrue(
            verification["actual"]["database_version"].startswith(
                "PostgreSQL 16.14"
            )
        )
        evidence = verification["actual"]["evidence"]
        self.assertEqual(
            "7C407CB6F013BE584011E446650BACD4A6A958895F88448B17EE523AA5B9D068",
            evidence["fixture_set_sha256"],
        )
        self.assertEqual(
            {"db-smoke", "db-full"},
            set(evidence["profiles"]),
        )
        for profile, kind in (
            ("db-smoke", "smoke"),
            ("db-full", "full"),
        ):
            self.assertRegex(
                evidence["profiles"][profile]["database_name"],
                rf"^watercare_synthetic_{kind}_verify_20260729"
                r"(?:_[a-z0-9]+)?$",
            )
        batch_codes = {
            value[key]
            for value in evidence["profiles"].values()
            for key in ("first_batch_code", "replay_batch_code")
        }
        self.assertEqual(4, len(batch_codes))
        self.assertEqual(
            "UNCOMMITTED_VERIFIED_CHANGES",
            evidence["worktree_state"],
        )
        self.assertEqual(
            (37, 31, 6, 31),
            (
                verification["expected"]["db-smoke"]["source_count"],
                verification["expected"]["db-smoke"]["first_run"][
                    "created_count"
                ],
                verification["expected"]["db-smoke"]["first_run"][
                    "projected_count"
                ],
                verification["expected"]["db-smoke"]["replay_run"][
                    "unchanged_count"
                ],
            ),
        )
        self.assertEqual(
            (367, 355, 12, 355, 26, 125),
            (
                verification["expected"]["db-full"]["source_count"],
                verification["expected"]["db-full"]["first_run"][
                    "created_count"
                ],
                verification["expected"]["db-full"]["first_run"][
                    "projected_count"
                ],
                verification["expected"]["db-full"]["replay_run"][
                    "unchanged_count"
                ],
                verification["expected"]["db-full"][
                    "aggregate_checks"
                ],
                verification["expected"]["db-full"][
                    "audit_history_checks"
                ],
            ),
        )
        schema = read_json(
            DATA_ROOT
            / "schemas"
            / "config"
            / "backendImportCrosswalk.schema.json"
        )
        self.assertEqual([], validate_schema(crosswalk, schema))

    def test_canonical_role_is_consultant(self) -> None:
        self.assertEqual(
            ["CUSTOMER", "CONSULTANT", "TECHNICIAN", "OPERATOR"],
            self.mapping["canonical_role_codes"],
        )
        self.assertEqual(
            {"COUNSELOR": "CONSULTANT"},
            self.mapping["legacy_role_aliases"],
        )

    def test_legacy_role_and_field_are_absent_from_active_synthetic_data(self) -> None:
        active_text = json.dumps(
            self.config.config("synthetic"),
            ensure_ascii=False,
            sort_keys=True,
        )
        schema_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((DATA_ROOT / "schemas" / "synthetic").glob("*.json"))
        )
        self.assertNotIn("COUNSELOR", active_text)
        self.assertNotIn("counselor_id", active_text)
        self.assertNotIn("COUNSELOR", schema_text)
        self.assertNotIn("counselor_id", schema_text)

    def test_inquiry_and_visit_states_are_separated(self) -> None:
        synthetic = self.config.config("synthetic")["materialized_outputs"]
        workflows = {
            row["scenario_id"]: row for row in synthetic["workflow_states"]
        }
        inquiries = {
            row["scenario_id"]: row for row in synthetic["inquiries"]
        }
        visits_by_inquiry = {
            row["inquiry_id"]: row for row in synthetic["visits"]
        }

        review = inquiries["SYN-JAC104-008"]
        self.assertEqual("VISIT_REVIEW_PENDING", review["status"])
        self.assertNotIn(review["id"], visits_by_inquiry)

        in_progress = inquiries["SYN-JAC104-014"]
        self.assertEqual("VISIT_SCHEDULED", in_progress["status"])
        self.assertEqual(
            "IN_PROGRESS",
            visits_by_inquiry[in_progress["id"]]["status"],
        )

        representative = workflows["SYN-JAC104-002"]
        visit_steps = [
            row
            for row in representative["steps"]
            if row["event"]
            in {
                "VISIT_REVIEW_REQUIRED",
                "VISIT_NEEDED",
                "UPDATE_VISIT_SCHEDULE",
                "CONFIRM_VISIT",
                "START_VISIT",
                "VISIT_COMPLETED",
            }
        ]
        self.assertEqual(
            [
                "VISIT_REVIEW_REQUIRED",
                "VISIT_NEEDED",
                "UPDATE_VISIT_SCHEDULE",
                "CONFIRM_VISIT",
                "START_VISIT",
                "VISIT_COMPLETED",
            ],
            [row["event"] for row in visit_steps],
        )
        self.assertEqual(
            [
                (None, None),
                (None, "ASSIGNING"),
                ("ASSIGNING", "SCHEDULING"),
                ("SCHEDULING", "CONFIRMED"),
                ("CONFIRMED", "IN_PROGRESS"),
                ("IN_PROGRESS", "COMPLETED"),
            ],
            [
                (
                    row.get("visit_from_status"),
                    row.get("visit_to_status"),
                )
                for row in visit_steps
            ],
        )

    def test_legacy_inquiry_states_are_not_materialized(self) -> None:
        active_text = json.dumps(
            self.config.config("synthetic"),
            ensure_ascii=False,
            sort_keys=True,
        )
        for legacy in (
            "PRODUCT_VALIDATION_FAILED",
            "AI_GUIDANCE_READY",
            "CONSULTATION_PENDING",
            "VISIT_PENDING",
            "VISIT_IN_PROGRESS",
        ):
            self.assertNotIn(legacy, active_text)

    def test_unresolved_business_decisions_remain_blocked(self) -> None:
        blocked = {item["id"]: item for item in self.mapping["blocked_decisions"]}
        self.assertEqual(
            {
                "DEC-PRODUCT-VALIDATION-001",
                "DEC-RESOLVED-REOPEN-001",
            },
            set(blocked),
        )
        self.assertEqual(
            ["SYN-JAC104-012", "SYN-JAC104-016"],
            blocked["DEC-RESOLVED-REOPEN-001"]["affected_scenario_ids"],
        )
        self.assertIn(
            "terminal 문의의 동일 ID 재개를 금지",
            blocked["DEC-RESOLVED-REOPEN-001"]["description"],
        )
        self.assertEqual(
            [],
            blocked["DEC-PRODUCT-VALIDATION-001"]["affected_scenario_ids"],
        )

    def test_blocked_scenarios_are_excluded_by_registry(self) -> None:
        self.assertEqual([], validate_contract_alignment_registry(self.config))
        registry = self.config.config("synthetic")["materialized_outputs"][
            "contract_alignment_registry"
        ]
        blocked = {
            row["scenario_id"]: row
            for row in registry
            if row["contract_alignment_status"] == "BLOCKED_DECISION"
        }
        aligned = [
            row
            for row in registry
            if row["contract_alignment_status"] == "ALIGNED"
        ]
        self.assertEqual(24, len(registry))
        self.assertEqual(22, len(aligned))
        self.assertEqual(2, len(blocked))
        self.assertEqual(
            {"SYN-JAC104-012", "SYN-JAC104-016"},
            set(blocked),
        )
        self.assertTrue(
            all(not row["include_in_contract_projection"] for row in blocked.values())
        )
        schema = read_json(
            DATA_ROOT
            / "schemas"
            / "synthetic"
            / "contractAlignmentRegistryItem.schema.json"
        )
        for index, row in enumerate(registry):
            self.assertEqual([], validate_schema(row, schema), index)


if __name__ == "__main__":
    unittest.main()
