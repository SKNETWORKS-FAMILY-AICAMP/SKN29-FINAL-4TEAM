from __future__ import annotations

import sys
import unittest
import json
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from watercare.config import load_pipeline
from watercare.io import read_json
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
                "t005_physical_contract_v1_2",
                "public_api_idempotency_conflict",
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
                "backend_runtime_verified": False,
            },
            self.mapping["state_machine_contract"],
        )

    def test_backend_crosswalk_blocks_direct_pk_and_unconfirmed_care(self) -> None:
        self.assertEqual([], validate_backend_import_crosswalk(self.config))
        crosswalk = self.config.config("backend_crosswalk")
        self.assertEqual(
            "FORBIDDEN",
            crosswalk["identifier_resolution"]["backend_primary_key_injection"],
        )
        self.assertIsNone(
            crosswalk["code_mappings"]["care_type"]["VISIT_SERVICE"]
        )
        self.assertTrue(
            all(
                row["treatment"] == "EXCLUDE_FROM_DIRECT_LOAD"
                for row in crosswalk["blocked_mappings"]
            )
        )

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
