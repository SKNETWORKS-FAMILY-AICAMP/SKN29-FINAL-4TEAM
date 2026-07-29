from __future__ import annotations

import sys
import unittest
import uuid
from copy import deepcopy
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

import align_synthetic_contract
from watercare.config import load_pipeline
from watercare.io import read_json


class T005DataProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_pipeline(DATA_ROOT)
        cls.source = cls.config.config("synthetic")
        cls.outputs = {
            key: read_json(DATA_ROOT / path)
            for key, path in cls.source["outputs"].items()
        }

    def test_active_projection_has_expected_counts(self) -> None:
        self.assertEqual(24, len(self.source["scenario_matrix"]))
        self.assertEqual(22, len(self.outputs["inquiries"]))
        self.assertEqual(12, len(self.outputs["customer_profiles"]))
        self.assertEqual(12, len(self.outputs["consultations"]))
        self.assertEqual(4, len(self.outputs["visits"]))
        self.assertEqual(125, len(self.outputs["inquiry_status_histories"]))
        self.assertEqual(125, len(self.outputs["audit_events"]))
        self.assertEqual(22, len(self.outputs["workflow_states"]))

    def test_status_history_has_exactly_one_matching_target(self) -> None:
        target_fields = {
            "QUESTIONNAIRE": "questionnaire_session_id",
            "INQUIRY": "inquiry_id",
            "CONSULTATION": "consultation_id",
            "VISIT": "visit_id",
        }
        for row in self.outputs["inquiry_status_histories"]:
            configured = [
                field
                for field in target_fields.values()
                if row[field] is not None
            ]
            self.assertEqual(1, len(configured), row["status_history_number"])
            self.assertEqual(
                target_fields[row["target_type_code"]],
                configured[0],
                row["status_history_number"],
            )
            self.assertNotIn("target_id", row)

    def test_state_version_is_unique_per_target_not_per_request_key(self) -> None:
        versions: set[tuple[str, int, int]] = set()
        keys: dict[str, set[str]] = {}
        for row in self.outputs["inquiry_status_histories"]:
            target_type = row["target_type_code"]
            target_id = row[f"{target_type.lower()}_id"]
            version = (target_type, target_id, row["state_version"])
            self.assertNotIn(version, versions)
            versions.add(version)
            keys.setdefault(row["idempotency_key"], set()).add(target_type)
        self.assertTrue(
            any(target_types == {"INQUIRY", "VISIT"} for target_types in keys.values())
        )

    def test_compound_visit_events_create_two_correlated_histories(self) -> None:
        compound_events = {
            "VISIT_NEEDED",
            "UPDATE_VISIT_SCHEDULE",
            "CONFIRM_VISIT",
            "START_VISIT",
            "VISIT_COMPLETED",
        }
        workflows = {
            row["scenario_id"]: row for row in self.outputs["workflow_states"]
        }
        inquiries = {
            row["scenario_id"]: row for row in self.outputs["inquiries"]
        }
        for scenario_id, workflow in workflows.items():
            inquiry = inquiries[scenario_id]
            for step in workflow["steps"]:
                if step["event"] not in compound_events:
                    continue
                rows = [
                    row
                    for row in self.outputs["inquiry_status_histories"]
                    if row["event_code"] == step["event"]
                    and row["idempotency_key"] == step["idempotency_key"]
                    and (
                        row["inquiry_id"] == inquiry["id"]
                        or row["target_type_code"] == "VISIT"
                    )
                ]
                self.assertEqual(2, len(rows), (scenario_id, step["event"]))
                self.assertEqual(
                    {"INQUIRY", "VISIT"},
                    {row["target_type_code"] for row in rows},
                )
                self.assertEqual(1, len({row["correlation_id"] for row in rows}))

    def test_api_idempotency_cases_separate_replay_and_conflict(self) -> None:
        cases = {
            row["expected_outcome"]: row
            for row in self.outputs["api_idempotency_cases"]
        }
        self.assertEqual({"PROCESSED", "REPLAY", "CONFLICT"}, set(cases))
        processed = cases["PROCESSED"]
        replay = cases["REPLAY"]
        conflict = cases["CONFLICT"]
        self.assertEqual(
            processed["request_payload_sha256"],
            replay["request_payload_sha256"],
        )
        self.assertEqual(0, replay["expected_history_rows_created"])
        self.assertNotEqual(
            processed["request_payload_sha256"],
            conflict["request_payload_sha256"],
        )
        self.assertEqual(
            "IDEMPOTENCY_KEY_REUSE_CONFLICT",
            conflict["internal_conflict_code"],
        )
        self.assertEqual(
            "DUPLICATE-EVENT-01",
            conflict["expected_api_error_code"],
        )
        self.assertIsNone(processed["internal_conflict_code"])
        self.assertIsNone(processed["expected_api_error_code"])
        self.assertIsNone(replay["internal_conflict_code"])
        self.assertIsNone(replay["expected_api_error_code"])
        self.assertEqual(2, processed["expected_history_rows_created"])

    def test_fixture_identifier_layers_and_fk_types_are_separate(self) -> None:
        fixture_names = (
            "users",
            "customer_profiles",
            "products",
            "customer_products",
            "subscriptions",
            "inquiries",
            "consultations",
            "visits",
            "care_histories",
            "followup_confirmations",
            "inquiry_status_histories",
            "audit_events",
        )
        for name in fixture_names:
            for row in self.outputs[name]:
                self.assertIsInstance(row["id"], int, name)
                uuid.UUID(row["public_id"])
        fk_fields = {
            "customer_products": ("customer_id", "product_id"),
            "customer_profiles": ("user_id",),
            "subscriptions": ("customer_profile_id", "customer_product_id"),
            "inquiries": ("customer_id", "subscription_id"),
            "consultations": ("inquiry_id", "consultant_id"),
            "visits": ("inquiry_id", "technician_id"),
        }
        for name, fields in fk_fields.items():
            for row in self.outputs[name]:
                for field in fields:
                    if row[field] is not None:
                        self.assertIsInstance(row[field], int, (name, field))
        for name in ("evidence_references", "safety_assessments", "role_handoffs"):
            for row in self.outputs[name]:
                self.assertNotIn("inquiry_id", row)
                uuid.UUID(row["inquiry_public_id"])

        for row in self.outputs["workflow_states"]:
            for step in row["steps"]:
                self.assertNotIn("actor_id", step)
                if step["actor_public_id"] is not None:
                    uuid.UUID(step["actor_public_id"])

        for row in self.outputs["api_idempotency_cases"]:
            uuid.UUID(row["actor"]["public_id"])
            uuid.UUID(row["first_result"]["resource_public_id"])

    def test_customer_profile_chain_is_one_to_one_and_traceable(self) -> None:
        users = {row["id"]: row for row in self.outputs["users"]}
        profiles = {
            row["id"]: row for row in self.outputs["customer_profiles"]
        }
        customer_products = {
            row["id"]: row for row in self.outputs["customer_products"]
        }
        self.assertEqual(
            len(profiles),
            len({row["user_id"] for row in profiles.values()}),
        )
        for subscription in self.outputs["subscriptions"]:
            profile = profiles[subscription["customer_profile_id"]]
            user = users[profile["user_id"]]
            customer_product = customer_products[
                subscription["customer_product_id"]
            ]
            self.assertEqual("CUSTOMER", user["role"])
            self.assertEqual(user["id"], customer_product["customer_id"])
        for care in self.outputs["care_histories"]:
            self.assertIn(care["customer_product_id"], customer_products)

    def test_history_versions_are_contiguous_and_audits_correspond(self) -> None:
        target_fields = {
            "INQUIRY": "inquiry_id",
            "VISIT": "visit_id",
        }
        versions: dict[tuple[str, int], list[int]] = {}
        history_keys = set()
        for row in self.outputs["inquiry_status_histories"]:
            target_type = row["target_type_code"]
            target_id = row[target_fields[target_type]]
            versions.setdefault((target_type, target_id), []).append(
                row["state_version"]
            )
            history_keys.add(
                (
                    target_type,
                    target_id,
                    row["event_code"],
                    row["state_version"],
                    row["idempotency_key"],
                    row["correlation_id"],
                )
            )
        for values in versions.values():
            self.assertEqual(list(range(1, max(values) + 1)), sorted(values))
        audit_keys = {
            (
                row["entity_type"],
                row["entity_id"],
                row["event_type"],
                row["state_version"],
                row["idempotency_key"],
                row["correlation_id"],
            )
            for row in self.outputs["audit_events"]
        }
        self.assertEqual(history_keys, audit_keys)

    def test_inquiry_and_visit_history_status_sets_do_not_mix(self) -> None:
        inquiry_states = set(
            self.config.config("vocabulary")["inquiry_statuses"]
        )
        visit_states = set(self.config.config("vocabulary")["visit_statuses"])
        for row in self.outputs["inquiry_status_histories"]:
            allowed = (
                inquiry_states
                if row["target_type_code"] == "INQUIRY"
                else visit_states
            )
            for field in ("from_status_code", "to_status_code"):
                if row[field] is not None:
                    self.assertIn(row[field], allowed, row["status_history_number"])

    def test_blocked_scenarios_are_preserved_but_not_projected(self) -> None:
        blocked = {"SYN-JAC104-012", "SYN-JAC104-016"}
        source_ids = {row["scenario_id"] for row in self.source["scenario_matrix"]}
        projected_ids = {row["scenario_id"] for row in self.outputs["inquiries"]}
        demo_ids = {
            row["scenario_id"]
            for row in self.outputs["demo_scenarios"]["scenarios"]
        }
        self.assertLessEqual(blocked, source_ids)
        self.assertLessEqual(blocked, demo_ids)
        self.assertTrue(blocked.isdisjoint(projected_ids))
        registry = {
            row["scenario_id"]: row
            for row in self.outputs["contract_alignment_registry"]
        }
        self.assertTrue(
            all(
                registry[scenario_id]["contract_alignment_status"]
                == "BLOCKED_DECISION"
                and not registry[scenario_id]["include_in_contract_projection"]
                for scenario_id in blocked
            )
        )

    def test_product_validation_failure_is_event_expectation_not_state(self) -> None:
        mapping = self.config.config("contract_mapping")
        expectation = mapping["product_validation_expectation"]
        self.assertEqual("PRODUCT_VALIDATION_FAILED", expectation["event_code"])
        self.assertEqual(
            "CONSULTATION_REQUIRED", expectation["to_inquiry_status"]
        )
        self.assertFalse(expectation["materialize_event_as_inquiry_status"])
        self.assertFalse(
            any(
                row["to_status_code"] == "PRODUCT_VALIDATION_FAILED"
                for row in self.outputs["inquiry_status_histories"]
            )
        )

    def test_revisit_needed_normalizer_supports_visit_projection(self) -> None:
        workflow = {
            "steps": [
                {
                    "order": 1,
                    "event": "REVISIT_NEEDED",
                    "from_status": "VISIT_SCHEDULED",
                    "to_status": "REVISIT_REQUIRED",
                    "actor_role": "TECHNICIAN",
                    "actor_public_id": str(uuid.uuid4()),
                    "state_version": 1,
                    "occurred_at": "2026-07-29T00:00:00+09:00",
                    "idempotency_key": "idem-revisit-test",
                    "correlation_id": str(uuid.uuid4()),
                    "expected_allowed_actions": [],
                    "visit_from_status": "IN_PROGRESS",
                    "visit_to_status": "FOLLOW_UP_REQUIRED",
                    "visit_state_version": 6,
                }
            ],
            "final_status": "REVISIT_REQUIRED",
        }
        align_synthetic_contract._normalize_workflow(workflow)
        step = workflow["steps"][0]
        self.assertEqual("FOLLOW_UP_REQUIRED", step["visit_to_status"])
        self.assertEqual(6, step["visit_state_version"])

    def test_manifest_records_match_materialized_files(self) -> None:
        manifest = read_json(self.config.path("dataset_manifest"))
        for item in manifest["files"]:
            path = DATA_ROOT / item["path"]
            if path.suffix != ".json":
                continue
            value = read_json(path)
            if isinstance(value, list):
                self.assertEqual(len(value), item["records"], item["path"])
            elif isinstance(value, dict) and isinstance(value.get("scenarios"), list):
                self.assertEqual(
                    len(value["scenarios"]), item["records"], item["path"]
                )


if __name__ == "__main__":
    unittest.main()
