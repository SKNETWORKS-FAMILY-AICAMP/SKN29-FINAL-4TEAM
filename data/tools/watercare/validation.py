"""Equivalence and declarative dataset validation."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import PipelineConfig
from .e2e_validation import validate_representative_e2e
from .io import (
    ensure_within,
    json_bytes,
    read_json,
    read_jsonl,
    sha256_bytes,
    sha256_text_file,
)

TEXT_HASH_POLICY = {
    "algorithm": "SHA-256",
    "encoding": "UTF-8",
    "bom": "IGNORE",
    "text_line_endings": "LF",
}

SYNTHETIC_FIXTURE_OUTPUTS = (
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

BACKEND_CROSSWALK_SOURCE_PATHS = {
    "user_model": "backend/apps/accounts/models/user.py",
    "customer_profile_model": (
        "backend/apps/accounts/models/customer_profile.py"
    ),
    "product_model": (
        "backend/apps/products/models/product_model_registry.py"
    ),
    "subscription_model": (
        "backend/apps/subscriptions/models/subscription.py"
    ),
    "inquiry_model": "backend/apps/inquiries/models/inquiry.py",
    "symptom_entry_model": (
        "backend/apps/inquiries/models/symptom_entry.py"
    ),
    "consultation_model": (
        "backend/apps/consultations/models/consultation.py"
    ),
    "visit_model": "backend/apps/visits/models/visit.py",
    "followup_confirmation_model": (
        "backend/apps/inquiries/models/followup_confirmation.py"
    ),
    "care_model": "backend/apps/care/models/care_history.py",
    "transition_history_model": (
        "backend/apps/workflow/models/transition_history.py"
    ),
    "audit_event_model": (
        "backend/apps/audit/models/audit_event.py"
    ),
    "import_ledger_model": (
        "backend/apps/operations/models/synthetic_import_ledger.py"
    ),
    "import_repository": (
        "backend/apps/operations/repositories/operations_repository.py"
    ),
    "import_service": (
        "backend/apps/operations/services/operations_service.py"
    ),
    "import_command": (
        "backend/apps/operations/management/commands/"
        "import_synthetic_handoff.py"
    ),
    "demo_auth_repository": (
        "backend/apps/accounts/repositories/account_repository.py"
    ),
}

BACKEND_CROSSWALK_ENTITY_RULES = {
    "synthetic/fixtures/users.json": (
        "accounts.User",
        "DIRECT",
        "user_number",
    ),
    "synthetic/fixtures/customer_profiles.json": (
        "accounts.CustomerProfile",
        "DIRECT",
        "customer_profile_number",
    ),
    "synthetic/fixtures/products.json": (
        "products.ProductModel",
        "DIRECT",
        "product_code",
    ),
    "synthetic/fixtures/customer_products.json": (
        "subscriptions.CustomerSubscription",
        "PROJECTED",
        "serial_number",
    ),
    "synthetic/fixtures/subscriptions.json": (
        "subscriptions.CustomerSubscription",
        "DIRECT",
        "subscription_number",
    ),
    "synthetic/fixtures/inquiries.json": (
        "inquiries.Inquiry",
        "DIRECT",
        "inquiry_number",
    ),
    "synthetic/fixtures/consultations.json": (
        "consultations.Consultation",
        "DIRECT",
        "consultation_number",
    ),
    "synthetic/fixtures/visits.json": (
        "visits.Visit",
        "DIRECT",
        "visit_number",
    ),
    "synthetic/fixtures/followup_confirmations.json": (
        "inquiries.FollowupConfirmation",
        "DIRECT",
        "followup_number",
    ),
    "synthetic/fixtures/care_histories.json": (
        "care.CareRecord",
        "DIRECT",
        "care_history_number",
    ),
    "synthetic/fixtures/inquiry_status_histories.json": (
        "workflow.TransitionHistory",
        "DIRECT",
        "status_history_number",
    ),
    "synthetic/fixtures/audit_events.json": (
        "audit.AuditEvent",
        "DIRECT",
        "audit_record_number",
    ),
}

BACKEND_CROSSWALK_REQUIRED_FIELD_MAPPINGS = {
    "synthetic/fixtures/users.json": {
        "public_id": "public_id",
        "user_number": (
            "username; employee_no when role is not CUSTOMER"
        ),
        "display_name": "full_name",
        "role": "role_code",
    },
    "synthetic/fixtures/customer_profiles.json": {
        "public_id": "public_id",
        "customer_profile_number": "customer_no",
        "user_id": "user lookup",
    },
    "synthetic/fixtures/products.json": {
        "public_id": "public_id",
        "product_code": "model_code",
        "product_model": "model_name",
        "product_generation": "generation_code",
    },
    "synthetic/fixtures/customer_products.json": {
        "public_id": "source_customer_product_public_id",
        "serial_number": "serial_no",
        "installation_date": "installed_on",
        "installation_location": "installation_address",
    },
    "synthetic/fixtures/subscriptions.json": {
        "public_id": "public_id",
        "subscription_number": "contract_no",
        "customer_profile_id": "customer lookup",
        "customer_product_id": "customer product projection lookup",
    },
    "synthetic/fixtures/inquiries.json": {
        "public_id": "public_id",
        "inquiry_number": "inquiry_code",
        "subscription_id": "subscription lookup",
        "customer_id": "initiated_by customer user lookup",
        "topic_code": "representative_symptom.symptom_type_code",
        "status": "status_code",
    },
    "synthetic/fixtures/consultations.json": {
        "public_id": "public_id",
        "consultation_number": "consultation_code",
        "inquiry_id": "inquiry lookup",
        "status": "status",
    },
    "synthetic/fixtures/visits.json": {
        "public_id": "public_id",
        "visit_number": "visit_code",
        "inquiry_id": "inquiry lookup",
        "status": "status",
    },
    "synthetic/fixtures/followup_confirmations.json": {
        "public_id": "public_id",
        "followup_number": "followup_code",
        "inquiry_id": "inquiry lookup",
        "resolution_status_code": "resolution_status_code",
    },
    "synthetic/fixtures/care_histories.json": {
        "public_id": "public_id",
        "care_history_number": "care_code",
        "customer_product_id": "subscription lookup",
        "care_type": "care_type_code",
        "performed_on": "performed_on",
        "result": "result_code",
    },
    "synthetic/fixtures/inquiry_status_histories.json": {
        "public_id": "public_id",
        "status_history_number": "status_history_code",
        "target_type_code": "target_type_code",
        "to_status_code": "to_state",
        "state_version": "state_version",
    },
    "synthetic/fixtures/audit_events.json": {
        "public_id": "public_id",
        "audit_record_number": "audit_code",
        "entity_type": "entity_type",
        "event_type": "event_code",
        "state_version": "state_version; transition lookup",
    },
}

EXPECTED_BACKEND_VERIFICATION_GATES = {
    "db-smoke": {
        "source_count": 37,
        "dry_run_persisted_domain_rows": 0,
        "dry_run_persisted_batch_rows": 0,
        "dry_run_persisted_item_rows": 0,
        "first_run": {
            "created_count": 31,
            "updated_count": 0,
            "unchanged_count": 0,
            "projected_count": 6,
        },
        "replay_run": {
            "created_count": 0,
            "updated_count": 0,
            "unchanged_count": 31,
            "projected_count": 6,
        },
        "source_items": 37,
        "projection_checks": 6,
        "aggregate_checks": 0,
        "audit_history_checks": 0,
    },
    "db-full": {
        "source_count": 367,
        "dry_run_persisted_domain_rows": 0,
        "dry_run_persisted_batch_rows": 0,
        "dry_run_persisted_item_rows": 0,
        "first_run": {
            "created_count": 355,
            "updated_count": 0,
            "unchanged_count": 0,
            "projected_count": 12,
        },
        "replay_run": {
            "created_count": 0,
            "updated_count": 0,
            "unchanged_count": 355,
            "projected_count": 12,
        },
        "source_items": 367,
        "projection_checks": 12,
        "aggregate_checks": 26,
        "audit_history_checks": 125,
    },
}

EXPECTED_CARE_TYPE_MAPPING = {
    "REGULAR_INSPECTION": "PERIODIC_CHECK",
    "FILTER_REPLACEMENT": "FILTER_REPLACEMENT",
    "VISIT_SERVICE": "VISIT_SERVICE",
}

EXPECTED_SYNTHETIC_FIXTURE_SET_SHA256 = (
    "7C407CB6F013BE584011E446650BACD4A6A958895F88448B17EE523AA5B9D068"
)

EXPECTED_ACTIVE_PRODUCT_CODES = {
    "WPUJAC104DWH",
    "WPUIAC425SNW",
    "WPUIAC606SNW",
}

EXPECTED_PRODUCT_EXPANSION_CASES = {
    "WPUIAC425SNW": {
        "topic_code": "hot_water_stopped",
        "risk_level": "danger",
        "requires_consultation": True,
        "evidence_group_id": (
            "EVD-WPUIAC425SNW-HOT-WATER-STOPPED-001"
        ),
        "resolution_mode": "CONSULTANT_HANDOFF",
        "handoff_target": "CONSULTANT",
    },
    "WPUIAC606SNW": {
        "topic_code": "no_ice",
        "risk_level": "caution",
        "requires_consultation": False,
        "evidence_group_id": "EVD-WPUIAC606SNW-NO-ICE-001",
        "resolution_mode": "SELF_RESOLUTION",
        "handoff_target": "NONE",
    },
}

EXPECTED_MANUAL_CANDIDATE_IDS = {
    *(f"SYN-IAC425-{index:03d}" for index in range(101, 111)),
    *(f"SYN-IAC606-{index:03d}" for index in range(101, 111)),
    *(f"SYN-JAC104-{index:03d}" for index in range(25, 35)),
}

EXPECTED_MANUAL_SOURCE_ID_MAP = {
    **{
        f"SYN-IAC425-{index:03d}": f"SYN-IAC425-{index - 100:03d}"
        for index in range(101, 111)
    },
    **{
        f"SYN-IAC606-{index:03d}": f"SYN-IAC606-{index - 100:03d}"
        for index in range(101, 111)
    },
    **{
        f"SYN-JAC104-{index:03d}": f"SYN-JAC104-{index:03d}"
        for index in range(25, 35)
    },
}

MANUAL_NEGATIVE_SCENARIOS = {
    "SYN-IAC425-110",
    "SYN-IAC606-110",
    "SYN-JAC104-032",
    "SYN-JAC104-033",
    "SYN-JAC104-034",
}

MANUAL_HOT_WATER_DANGER_SCENARIOS = {
    "SYN-IAC425-109",
    "SYN-IAC606-108",
    "SYN-JAC104-031",
}

MANUAL_LEAK_DANGER_SCENARIOS = {
    "SYN-IAC425-108",
    "SYN-IAC606-107",
    "SYN-JAC104-029",
}

RUNTIME_DATABASE_PATTERN = re.compile(
    r"^watercare_synthetic_(smoke|full)_verify_[0-9]{8}"
    r"(?:_[a-z0-9]+)?$"
)


def count_synthetic_fixture_records(outputs: dict[str, Any]) -> int:
    """Count only the 12 active backend handoff fixture collections."""

    return sum(len(outputs[name]) for name in SYNTHETIC_FIXTURE_OUTPUTS)


def validate_service_contract_mapping(config: PipelineConfig) -> list[str]:
    mapping = config.config("contract_mapping")
    vocabulary = config.config("vocabulary")
    repo_root = config.data_root.parent.resolve()
    errors: list[str] = []

    if mapping.get("hash_policy") != TEXT_HASH_POLICY:
        errors.append("contract_source_hash_policy_mismatch")

    for source_name, source in mapping["contract_sources"].items():
        try:
            path = ensure_within(repo_root, repo_root / source["path"])
        except ValueError:
            errors.append(f"contract_source_path_escape:{source_name}")
            continue
        if not path.is_file():
            errors.append(f"contract_source_missing:{source_name}:{source['path']}")
            continue
        actual_hash = sha256_text_file(path)
        if actual_hash != source["sha256"]:
            errors.append(
                f"contract_source_hash_mismatch:{source_name}:"
                f"{actual_hash}!={source['sha256']}"
            )

    if mapping["canonical_inquiry_statuses"] != vocabulary["inquiry_statuses"]:
        errors.append("contract_mapping_inquiry_vocabulary_mismatch")
    if mapping["canonical_visit_statuses"] != vocabulary["visit_statuses"]:
        errors.append("contract_mapping_visit_vocabulary_mismatch")
    return errors


def validate_backend_import_crosswalk(config: PipelineConfig) -> list[str]:
    crosswalk = config.config("backend_crosswalk")
    repo_root = config.data_root.parent.resolve()
    errors: list[str] = []

    if crosswalk.get("mapping_version") != "2.0.0":
        errors.append("backend_mapping_version_mismatch")
    status = crosswalk.get("status")
    if status not in {
        "IMPLEMENTED_PENDING_DB_VERIFICATION",
        "DB_FULL_VERIFIED",
    }:
        errors.append("backend_mapping_status_invalid")
    if crosswalk.get("service_contracts_used") is not True:
        errors.append("backend_service_contracts_not_enabled")
    if crosswalk.get("hash_policy") != TEXT_HASH_POLICY:
        errors.append("backend_source_hash_policy_mismatch")

    backend_sources = crosswalk.get("backend_sources", {})
    if {
        name: source.get("path")
        for name, source in backend_sources.items()
    } != BACKEND_CROSSWALK_SOURCE_PATHS:
        errors.append("backend_source_registry_mismatch")
    for source_name, source in backend_sources.items():
        try:
            path = ensure_within(repo_root, repo_root / source["path"])
        except ValueError:
            errors.append(f"backend_source_path_escape:{source_name}")
            continue
        if not path.is_file():
            errors.append(f"backend_source_missing:{source_name}:{source['path']}")
            continue
        actual_hash = sha256_text_file(path)
        if actual_hash != source["sha256"]:
            errors.append(
                f"backend_source_hash_mismatch:{source_name}:"
                f"{actual_hash}!={source['sha256']}"
            )
    resolution = crosswalk["identifier_resolution"]
    if resolution["backend_primary_key_injection"] != "FORBIDDEN":
        errors.append("backend_fixture_pk_injection_not_forbidden")
    if resolution["foreign_key_resolution"] != "LOOKUP_THEN_USE_BACKEND_INTERNAL_PK":
        errors.append("backend_fk_resolution_policy_mismatch")

    mappings = crosswalk.get("entity_mappings", [])
    fixtures = [row.get("fixture") for row in mappings]
    if (
        len(mappings) != len(BACKEND_CROSSWALK_ENTITY_RULES)
        or len(fixtures) != len(set(fixtures))
        or set(fixtures) != set(BACKEND_CROSSWALK_ENTITY_RULES)
    ):
        errors.append("backend_entity_fixture_coverage_mismatch")
    expected_readiness = (
        "IMPLEMENTED_PENDING_DB_VERIFICATION"
        if status == "IMPLEMENTED_PENDING_DB_VERIFICATION"
        else None
    )
    for row in mappings:
        fixture = row.get("fixture")
        rule = BACKEND_CROSSWALK_ENTITY_RULES.get(fixture)
        if rule is None:
            continue
        actual_rule = (
            row.get("backend_model"),
            row.get("load_mode"),
            row.get("business_key"),
        )
        if actual_rule != rule:
            errors.append(f"backend_entity_mapping_mismatch:{fixture}")
        field_mappings = row.get("field_mappings", {})
        required_fields = BACKEND_CROSSWALK_REQUIRED_FIELD_MAPPINGS[
            fixture
        ]
        if any(
            field_mappings.get(source_field) != target_field
            for source_field, target_field in required_fields.items()
        ):
            errors.append(
                f"backend_entity_field_mapping_mismatch:{fixture}"
            )
        readiness = row.get("readiness")
        if expected_readiness is not None:
            if readiness != expected_readiness:
                errors.append(
                    f"backend_entity_readiness_mismatch:{fixture}"
                )
        else:
            final_readiness = (
                "PROJECTED_DB_FULL_VERIFIED"
                if row.get("load_mode") == "PROJECTED"
                else "DB_FULL_VERIFIED"
            )
            if readiness != final_readiness:
                errors.append(
                    f"backend_entity_readiness_mismatch:{fixture}"
                )

    care_mapping = crosswalk["code_mappings"]["care_type"]
    if care_mapping != EXPECTED_CARE_TYPE_MAPPING:
        errors.append("backend_care_mapping_mismatch")
    if crosswalk.get("blocked_mappings") != []:
        errors.append("backend_blocked_mapping_present")

    verification = crosswalk.get("verification", {})
    verification_status = verification.get("status")
    actual_evidence = verification.get("actual")
    if verification.get("database_engine") != "PostgreSQL":
        errors.append("backend_verification_engine_mismatch")
    if verification.get("dry_run_rollback_required") is not True:
        errors.append("backend_dry_run_rollback_not_required")
    if verification.get("expected") != EXPECTED_BACKEND_VERIFICATION_GATES:
        errors.append("backend_verification_gate_mismatch")
    if status == "IMPLEMENTED_PENDING_DB_VERIFICATION":
        if verification_status != "PENDING" or actual_evidence is not None:
            errors.append("backend_pending_verification_state_mismatch")
    elif (
        verification_status != "DB_FULL_VERIFIED"
        or not isinstance(actual_evidence, dict)
    ):
        errors.append("backend_full_verification_evidence_missing")
    else:
        for profile, expected_gate in (
            EXPECTED_BACKEND_VERIFICATION_GATES.items()
        ):
            if actual_evidence.get(profile) != expected_gate:
                errors.append(
                    f"backend_full_verification_evidence_mismatch:{profile}"
                )
        if not str(actual_evidence.get("verified_at", "")).strip():
            errors.append("backend_full_verification_time_missing")
        if not str(actual_evidence.get("database_version", "")).startswith(
            "PostgreSQL "
        ):
            errors.append("backend_full_verification_version_invalid")
        runtime_evidence = actual_evidence.get("evidence")
        if not isinstance(runtime_evidence, dict):
            errors.append("backend_runtime_evidence_missing")
        else:
            if (
                runtime_evidence.get("fixture_set_sha256")
                != EXPECTED_SYNTHETIC_FIXTURE_SET_SHA256
            ):
                errors.append("backend_runtime_fixture_hash_mismatch")

            base_commit_sha = str(
                runtime_evidence.get("base_commit_sha", "")
            )
            if re.fullmatch(r"[a-f0-9]{40}", base_commit_sha) is None:
                errors.append("backend_runtime_base_commit_invalid")

            document = runtime_evidence.get("runtime_document", {})
            try:
                document_path = ensure_within(
                    repo_root,
                    repo_root / document["path"],
                )
            except (KeyError, ValueError):
                errors.append("backend_runtime_document_path_invalid")
            else:
                if not document_path.is_file():
                    errors.append("backend_runtime_document_missing")
                elif (
                    sha256_text_file(document_path)
                    != document.get("text_sha256")
                ):
                    errors.append("backend_runtime_document_hash_mismatch")
            profiles = runtime_evidence.get("profiles", {})
            batch_codes: list[str] = []
            for profile in ("db-smoke", "db-full"):
                profile_evidence = profiles.get(profile, {})
                database_name = str(
                    profile_evidence.get("database_name", "")
                )
                match = RUNTIME_DATABASE_PATTERN.fullmatch(database_name)
                expected_kind = profile.removeprefix("db-")
                if match is None or match.group(1) != expected_kind:
                    errors.append(
                        f"backend_runtime_database_mismatch:{profile}"
                    )
                expected_command = (
                    "python backend/manage.py import_synthetic_handoff "
                    f"--profile {profile}"
                )
                if (
                    profile_evidence.get("migration_command")
                    != "python backend/manage.py migrate --noinput"
                    or profile_evidence.get("dry_run_command")
                    != f"{expected_command} --dry-run"
                    or profile_evidence.get("first_run_command")
                    != expected_command
                    or profile_evidence.get("replay_run_command")
                    != expected_command
                ):
                    errors.append(
                        f"backend_runtime_command_mismatch:{profile}"
                    )
                batch_codes.extend(
                    [
                        str(profile_evidence.get("first_batch_code", "")),
                        str(profile_evidence.get("replay_batch_code", "")),
                    ]
                )
                try:
                    first_completed = datetime.fromisoformat(
                        profile_evidence["first_completed_at"]
                    )
                    replay_completed = datetime.fromisoformat(
                        profile_evidence["replay_completed_at"]
                    )
                except (KeyError, TypeError, ValueError):
                    errors.append(
                        f"backend_runtime_timestamp_invalid:{profile}"
                    )
                else:
                    if replay_completed <= first_completed:
                        errors.append(
                            f"backend_runtime_replay_order_invalid:{profile}"
                        )
            if (
                len(batch_codes) != 4
                or len(set(batch_codes)) != 4
                or any(
                    re.fullmatch(r"SYN-IMPORT-[A-F0-9]{32}", code) is None
                    for code in batch_codes
                )
            ):
                errors.append("backend_runtime_batch_codes_invalid")
    return errors


def validate_contract_alignment_registry(config: PipelineConfig) -> list[str]:
    synthetic = config.config("synthetic")
    mapping = config.config("contract_mapping")
    registry = synthetic["materialized_outputs"]["contract_alignment_registry"]
    errors: list[str] = []

    scenario_ids = {row["scenario_id"] for row in synthetic["scenario_matrix"]}
    registry_ids = {row["scenario_id"] for row in registry}
    if registry_ids != scenario_ids or len(registry) != len(scenario_ids):
        errors.append("contract_alignment_registry_scenario_mismatch")

    expected_blocked: dict[str, list[str]] = {}
    for decision in mapping["blocked_decisions"]:
        for scenario_id in decision["affected_scenario_ids"]:
            expected_blocked.setdefault(scenario_id, []).append(decision["id"])

    for row in registry:
        scenario_id = row["scenario_id"]
        blocker_ids = sorted(row["blocker_ids"])
        expected_ids = sorted(expected_blocked.get(scenario_id, []))
        should_include = not expected_ids
        if blocker_ids != expected_ids:
            errors.append(f"contract_alignment_registry_blocker_mismatch:{scenario_id}")
        if row["include_in_contract_projection"] != should_include:
            errors.append(f"contract_alignment_registry_inclusion_mismatch:{scenario_id}")
        expected_status = "ALIGNED" if should_include else "BLOCKED_DECISION"
        if row["contract_alignment_status"] != expected_status:
            errors.append(f"contract_alignment_registry_status_mismatch:{scenario_id}")
    return errors


def validate_configs(config: PipelineConfig) -> list[dict[str, Any]]:
    rag = config.config("rag")
    synthetic = config.config("synthetic")
    vocabulary = config.config("vocabulary")
    ocr = config.config("ocr")
    e2e = config.config("e2e")
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    expected = config.values["expected_counts"]
    add(
        "ocr_record_count",
        len(ocr["records"]) == expected["faq_ocr_verified"],
        f"records={len(ocr['records'])}",
    )
    add(
        "rag_chunk_count",
        len(rag["chunks"]) == expected["rag_chunks"],
        f"chunks={len(rag['chunks'])}",
    )
    add(
        "evidence_count",
        len(rag["evidence"]) == expected["evidence"],
        f"evidence={len(rag['evidence'])}",
    )
    add(
        "scenario_count",
        len(synthetic["scenario_matrix"])
        == expected["synthetic_source_scenarios"],
        f"scenarios={len(synthetic['scenario_matrix'])}",
    )
    add(
        "risk_codes_present",
        vocabulary["risk_levels"] == ["general", "caution", "danger"],
        ",".join(vocabulary["risk_levels"]),
    )
    add(
        "usage_codes_present",
        bool(vocabulary["usage_guidance_statuses"]),
        ",".join(vocabulary["usage_guidance_statuses"]),
    )
    contract_mapping_errors = validate_service_contract_mapping(config)
    add(
        "service_contract_mapping",
        not contract_mapping_errors,
        ",".join(contract_mapping_errors) if contract_mapping_errors else "hashes_and_vocabularies_match",
    )
    alignment_registry_errors = validate_contract_alignment_registry(config)
    add(
        "contract_alignment_registry",
        not alignment_registry_errors,
        ",".join(alignment_registry_errors) if alignment_registry_errors else "blocked_scenarios_excluded",
    )
    backend_crosswalk_errors = validate_backend_import_crosswalk(config)
    add(
        "backend_import_crosswalk",
        not backend_crosswalk_errors,
        ",".join(backend_crosswalk_errors)
        if backend_crosswalk_errors
        else "lookup_bridge_and_runtime_verification_gate_verified",
    )
    danger_normal = [
        row["scenario_id"]
        for row in synthetic["scenario_matrix"]
        if row["risk_level"] == "danger"
        and row["usage_guidance_status"] == "NORMAL"
    ]
    add("danger_normal_blocked", not danger_normal, f"violations={danger_normal}")
    active_text = json_bytes(
        {
            "rag": rag,
            "synthetic": synthetic,
            "vocabulary": vocabulary,
            "ocr": ocr,
            "e2e": e2e,
        }
    ).decode("utf-8")
    retired_code = "USE_" + "ALLOWED"
    add("legacy_usage_code_absent", retired_code not in active_text, "active config scan")
    representative = validate_representative_e2e(config)
    add(
        "representative_e2e_invariants",
        representative["status"] == "PASS",
        (
            f"checks={representative['summary']['checks']},"
            f"failed={representative['summary']['failed']}"
        ),
    )
    return checks


def compare_bytes(
    canonical: Path,
    generated: bytes,
    *,
    display_path: str,
    record_count: int | None = None,
) -> dict[str, Any]:
    expected = canonical.read_bytes()
    return {
        "path": display_path,
        "records": record_count,
        "canonical_sha256": sha256_bytes(expected),
        "declarative_sha256": sha256_bytes(generated),
        "byte_equal": expected == generated,
        "canonical_bytes": len(expected),
        "declarative_bytes": len(generated),
    }


def schema_risk_codes(data_root: Path) -> dict[str, list[str]]:
    targets = {
        "faq": data_root / "schemas/processed/faqCandidate.schema.json",
        "rag": data_root / "schemas/processed/ragChunk.schema.json",
        "evidence": data_root / "schemas/processed/evidenceRegistry.schema.json",
        "inquiry": data_root / "schemas/synthetic/syntheticInquiry.schema.json",
        "safety": data_root / "schemas/synthetic/expectedSafety.schema.json",
    }
    result: dict[str, list[str]] = {}
    for name, path in targets.items():
        schema = read_json(path)
        result[name] = schema["properties"]["risk_level"]["enum"]
    return result


def schema_usage_codes(data_root: Path) -> dict[str, list[str]]:
    targets = {
        "rag": data_root / "schemas/processed/ragChunk.schema.json",
        "evidence": data_root / "schemas/processed/evidenceRegistry.schema.json",
        "inquiry": data_root / "schemas/synthetic/syntheticInquiry.schema.json",
        "safety": data_root / "schemas/synthetic/expectedSafety.schema.json",
    }
    result: dict[str, list[str]] = {}
    for name, path in targets.items():
        schema = read_json(path)
        field = "use_guidance" if name in {"rag", "evidence"} else "usage_guidance_status"
        result[name] = schema["properties"][field]["enum"]
    return result


def _type_matches(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, True)


def _format_valid(value: str, format_name: str) -> bool:
    try:
        if format_name == "uuid":
            uuid.UUID(value)
        elif format_name == "date-time":
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif format_name == "uri":
            return bool(re.match(r"^https?://", value))
    except (ValueError, TypeError):
        return False
    return True


def validate_schema(
    value: Any,
    schema: dict[str, Any],
    *,
    path: str = "$",
) -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected] if expected else []
    if types and not any(_type_matches(value, item) for item in types):
        return [f"{path}: expected {types}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: const mismatch")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is not in enum")
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: pattern mismatch")
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: shorter than minLength")
        if schema.get("format") and not _format_valid(value, schema["format"]):
            errors.append(f"{path}: invalid {schema['format']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: fewer than minItems")
        if schema.get("uniqueItems"):
            markers = [json_bytes(item) for item in value]
            if len(markers) != len(set(markers)):
                errors.append(f"{path}: duplicate array items")
        item_schema = schema.get("items", {})
        for index, item in enumerate(value):
            errors.extend(validate_schema(item, item_schema, path=f"{path}[{index}]"))
    if isinstance(value, dict):
        if len(value) < schema.get("minProperties", 0):
            errors.append(f"{path}: fewer than minProperties")
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}.{key}: required")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}.{key}: additional property")
        for key, item in value.items():
            if key in properties:
                errors.extend(
                    validate_schema(item, properties[key], path=f"{path}.{key}")
                )
    return errors


def _load_dataset(path: Path) -> Any:
    return read_jsonl(path) if path.suffix == ".jsonl" else read_json(path)


def _duplicates(rows: list[dict[str, Any]], key: str) -> list[str]:
    values = [row.get(key) for row in rows]
    return sorted({str(value) for value in values if values.count(value) > 1})


def _walk_candidate_values(
    value: Any,
    *,
    path: str = "$",
) -> list[tuple[str, str | Any]]:
    values: list[tuple[str, str | Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}"
            values.append((item_path, key))
            values.extend(_walk_candidate_values(item, path=item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            values.extend(
                _walk_candidate_values(item, path=f"{path}[{index}]")
            )
    else:
        values.append((path, value))
    return values


def validate_p1_account_link_candidates(
    config: PipelineConfig,
) -> dict[str, Any]:
    """P1 계정연결 후보가 미승격·합성 상태를 유지하는지 검증한다."""

    errors: list[str] = []
    candidates = read_json(config.path("p1_account_link_candidate_output"))
    expected_count = config.values["expected_counts"][
        "p1_account_link_candidates"
    ]
    if len(candidates) != expected_count:
        errors.append(
            f"p1_account_link:count:{len(candidates)}!={expected_count}"
        )

    fixture_ids = [row.get("fixture_id") for row in candidates]
    customer_codes = [
        row.get("customer_candidate", {}).get("customer_code")
        for row in candidates
    ]
    contract_nos = [
        row.get("subscription", {}).get("contract_no")
        for row in candidates
    ]
    serial_nos = [
        row.get("subscription", {}).get("serial_no")
        for row in candidates
    ]
    for label, values in (
        ("fixture_id", fixture_ids),
        ("customer_code", customer_codes),
        ("contract_no", contract_nos),
        ("serial_no", serial_nos),
    ):
        if len(values) != len(set(values)):
            errors.append(f"p1_account_link:duplicate:{label}")

    products = {
        row["product_code"]: row
        for row in read_json(
            config.data_root / "synthetic" / "fixtures" / "products.json"
        )
    }
    forbidden_keys = {
        "email_ciphertext",
        "email_hmac",
        "jwt",
        "otp",
        "password",
        "phone",
        "public_id",
        "secret",
        "token",
        "user_id",
        "username",
    }
    email_pattern = re.compile(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    )
    expected_blockers = {
        "P1_CONTRACT_CUSTOMER_RUNTIME_NOT_IMPLEMENTED",
        "P1_CONTRACT_EMAIL_RUNTIME_NOT_IMPLEMENTED",
        "P1_ACCOUNT_LINK_RUNTIME_NOT_IMPLEMENTED",
        "POSTGRESQL_NOT_VERIFIED",
    }
    for row in candidates:
        fixture_id = row.get("fixture_id", "UNKNOWN")
        values = _walk_candidate_values(row)
        for item_path, item in values:
            if item in forbidden_keys:
                errors.append(
                    f"p1_account_link:forbidden_field:{fixture_id}:{item_path}"
                )
            if isinstance(item, str) and email_pattern.fullmatch(item):
                if item != "customer-p1-001@waterbridge.invalid":
                    errors.append(
                        f"p1_account_link:non_synthetic_email:{fixture_id}"
                    )

        product_code = row.get("subscription", {}).get(
            "product_model_code"
        )
        product = products.get(product_code)
        if product is None or product.get("support_scope") != "MVP":
            errors.append(
                f"p1_account_link:unsupported_product:{fixture_id}:{product_code}"
            )
        initial_state = row.get("initial_state", {})
        if set(initial_state.values()) != {"ABSENT"}:
            errors.append(
                f"p1_account_link:linked_initial_state:{fixture_id}"
            )
        promotion = row.get("promotion", {})
        if (
            promotion.get("canonical_fixture_included") is not False
            or promotion.get("db_handoff_profile_included") is not False
            or set(promotion.get("blockers", [])) != expected_blockers
        ):
            errors.append(
                f"p1_account_link:promotion_state_mismatch:{fixture_id}"
            )

    crosswalk = config.config("backend_crosswalk")
    crosswalk_fixtures = {
        row["fixture"] for row in crosswalk["entity_mappings"]
    }
    candidate_relative = "synthetic/candidates/p1_account_link_candidates.json"
    if candidate_relative in crosswalk_fixtures:
        errors.append("p1_account_link:premature_backend_crosswalk")

    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "records": len(candidates),
        "fixture_ids": sorted(str(value) for value in fixture_ids),
    }


def validate_dataset_catalog(
    config: PipelineConfig,
    manifest: dict[str, Any],
) -> list[str]:
    catalog_path = config.data_root / "catalog/datasets.yaml"
    lines = catalog_path.read_text(encoding="utf-8").splitlines()
    errors: list[str] = []
    version_match = re.match(r"^version:\s*(\S+)", lines[0]) if lines else None
    if not version_match or version_match.group(1) != config.dataset_version:
        errors.append("catalog_dataset_version_mismatch")
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines:
        item_match = re.match(r"^\s*-\s+id:\s*(\S+)\s*$", line)
        if item_match:
            if current is not None:
                rows.append(current)
            current = {"id": item_match.group(1)}
            continue
        field_match = re.match(
            r"^\s+(path|records|schema):\s*(.*?)\s*$",
            line,
        )
        if current is not None and field_match:
            key, raw_value = field_match.groups()
            current[key] = (
                int(raw_value)
                if key == "records"
                else raw_value.strip("\"'")
            )
    if current is not None:
        rows.append(current)
    catalog_by_path = {row.get("path"): row for row in rows if row.get("path")}
    manifest_by_path = {row["path"]: row for row in manifest["files"]}
    if set(catalog_by_path) != set(manifest_by_path):
        errors.append("catalog_manifest_path_set_mismatch")
    for path, manifest_row in manifest_by_path.items():
        catalog_row = catalog_by_path.get(path)
        if catalog_row is None:
            continue
        if catalog_row.get("records") != manifest_row["records"]:
            errors.append(f"catalog_record_count_mismatch:{path}")
        if catalog_row.get("schema") != manifest_row["schema"]:
            errors.append(f"catalog_schema_mismatch:{path}")
        schema_path = catalog_row.get("schema", "")
        if schema_path.endswith(".json") and not (
            config.data_root / schema_path
        ).is_file():
            errors.append(f"catalog_schema_missing:{path}:{schema_path}")
    field_dictionary = (
        config.data_root / "catalog/field_dictionary.yaml"
    ).read_text(encoding="utf-8")
    if not field_dictionary.startswith(f"version: {config.dataset_version}\n"):
        errors.append("field_dictionary_version_mismatch")
    changelog = (config.data_root / "catalog/CHANGELOG.md").read_text(
        encoding="utf-8"
    )
    if f"## {config.dataset_version}" not in changelog:
        errors.append("catalog_changelog_version_missing")
    data_readme = (config.data_root / "README.md").read_text(encoding="utf-8")
    if config.dataset_version not in data_readme:
        errors.append("data_readme_version_mismatch")
    return errors


def validate_product_expansion_coverage(
    config: PipelineConfig,
) -> dict[str, Any]:
    """Validate canonical and candidate business-chain coverage per product."""

    errors: list[str] = []
    definitions = config.config("product_expansion_candidates")
    candidates = read_json(config.path("product_expansion_candidate_output"))
    supported = config.config("supported_products")
    products = read_json(
        config.data_root / "synthetic" / "fixtures" / "products.json"
    )
    customer_products = read_json(
        config.data_root
        / "synthetic"
        / "fixtures"
        / "customer_products.json"
    )
    subscriptions = read_json(
        config.data_root / "synthetic" / "fixtures" / "subscriptions.json"
    )
    inquiries = read_json(
        config.data_root / "synthetic" / "fixtures" / "inquiries.json"
    )
    evidence_groups = {
        row["evidence_group_id"]: row
        for row in read_jsonl(config.path("rag_expansion_evidence_output"))
    }


    configured_codes = set(definitions["active_product_codes"])
    supported_codes = {
        row["exact_sales_code"] for row in supported["products"]
    }
    fixture_products = {row["product_code"]: row for row in products}
    if configured_codes != EXPECTED_ACTIVE_PRODUCT_CODES:
        errors.append("product_coverage:active_product_codes_mismatch")
    if supported_codes != EXPECTED_ACTIVE_PRODUCT_CODES:
        errors.append("product_coverage:supported_product_codes_mismatch")
    if set(fixture_products) != EXPECTED_ACTIVE_PRODUCT_CODES:
        errors.append("product_coverage:fixture_product_codes_mismatch")
    if "WPU-JCC104 (D)" not in definitions["excluded_manual_aliases"]:
        errors.append("product_coverage:jcc104_alias_not_excluded")
    if "WPU-JCC104 (D)" not in {
        row["alias"] for row in supported["inactive_manual_aliases"]
    }:
        errors.append("product_coverage:jcc104_alias_not_inactive")

    canonical_code = definitions["canonical_coverage"]["exact_sales_code"]
    canonical_product = fixture_products.get(canonical_code)
    canonical_customer_products: list[dict[str, Any]] = []
    canonical_subscriptions: list[dict[str, Any]] = []
    canonical_inquiries: list[dict[str, Any]] = []
    if canonical_product is None:
        errors.append("product_coverage:canonical_product_missing")
    else:
        canonical_customer_products = [
            row
            for row in customer_products
            if row["product_id"] == canonical_product["id"]
        ]
        customer_product_ids = {
            row["id"] for row in canonical_customer_products
        }
        canonical_subscriptions = [
            row
            for row in subscriptions
            if row["customer_product_id"] in customer_product_ids
        ]
        subscription_ids = {row["id"] for row in canonical_subscriptions}
        canonical_inquiries = [
            row
            for row in inquiries
            if row["subscription_id"] in subscription_ids
        ]
        actual_counts = {
            "customer_products": len(canonical_customer_products),
            "subscriptions": len(canonical_subscriptions),
            "inquiries": len(canonical_inquiries),
        }
        for layer, minimum in definitions["canonical_coverage"][
            "minimum_counts"
        ].items():
            if actual_counts[layer] < minimum:
                errors.append(
                    f"product_coverage:canonical_{layer}_missing"
                )

    candidate_codes = set(EXPECTED_PRODUCT_EXPANSION_CASES)
    for code in candidate_codes:
        product = fixture_products.get(code)
        if product is None:
            continue
        if any(
            row["product_id"] == product["id"]
            for row in customer_products
        ):
            errors.append(
                f"product_coverage:candidate_in_canonical_fixture:{code}"
            )

    configured_cases = {
        row["exact_sales_code"]: row for row in definitions["cases"]
    }
    output_cases = {
        row["product"]["exact_sales_code"]: row for row in candidates
    }
    if (
        len(configured_cases) != len(definitions["cases"])
        or set(configured_cases) != candidate_codes
    ):
        errors.append("product_coverage:candidate_config_coverage_mismatch")
    if (
        len(output_cases) != len(candidates)
        or set(output_cases) != candidate_codes
    ):
        errors.append("product_coverage:candidate_output_coverage_mismatch")
    if len(candidates) != config.values["expected_counts"][
        "product_expansion_e2e_candidates"
    ]:
        errors.append("product_coverage:candidate_count_mismatch")

    for code, expected in EXPECTED_PRODUCT_EXPANSION_CASES.items():
        source = configured_cases.get(code)
        candidate = output_cases.get(code)
        if source is None or candidate is None:
            continue
        evidence = evidence_groups.get(source["evidence_group_id"])
        if evidence is None:
            errors.append(f"product_coverage:evidence_missing:{code}")
            continue
        if (
            source["topic_code"] != expected["topic_code"]
            or source["evidence_group_id"]
            != expected["evidence_group_id"]
            or source["expected_resolution_mode"]
            != expected["resolution_mode"]
            or source["expected_handoff_target"]
            != expected["handoff_target"]
        ):
            errors.append(f"product_coverage:case_contract_mismatch:{code}")
        if (
            evidence["exact_sales_code"] != code
            or evidence["topic_code"] != expected["topic_code"]
            or evidence["risk_level"] != expected["risk_level"]
            or evidence["requires_consultation"]
            is not expected["requires_consultation"]
        ):
            errors.append(f"product_coverage:evidence_scope_mismatch:{code}")
        if (
            candidate["scope_status"] != "E2E_CANDIDATE"
            or candidate["backend_import_status"] != "NOT_IMPORTED"
            or candidate["runtime_status"] != "NOT_VERIFIED"
            or candidate["promotion"]["canonical_fixture_included"]
            or candidate["promotion"]["db_handoff_profile_included"]
        ):
            errors.append(f"product_coverage:candidate_status_mismatch:{code}")
        if (
            candidate["customer_product"]["parent_ref"] != code
            or candidate["subscription"]["parent_ref"]
            != candidate["customer_product"]["candidate_ref"]
            or candidate["inquiry"]["subscription_ref"]
            != candidate["subscription"]["candidate_ref"]
        ):
            errors.append(f"product_coverage:chain_reference_mismatch:{code}")
        if (
            candidate["inquiry"]["topic_code"] != evidence["topic_code"]
            or candidate["evidence"]["evidence_group_id"]
            != evidence["evidence_group_id"]
            or candidate["evidence"]["exact_sales_code"] != code
            or candidate["safety"]["risk_level"]
            != evidence["risk_level"]
            or candidate["safety"]["requires_consultation"]
            is not evidence["requires_consultation"]
            or candidate["safety"]["safe_actions"]
            != evidence["safe_actions"]
            or candidate["safety"]["consultation_conditions"]
            != evidence["consultation_conditions"]
        ):
            errors.append(f"product_coverage:grounding_mismatch:{code}")
        if (
            candidate["expected_outcome"]["resolution_mode"]
            != expected["resolution_mode"]
            or candidate["expected_outcome"]["handoff_target"]
            != expected["handoff_target"]
        ):
            errors.append(f"product_coverage:outcome_mismatch:{code}")

    candidate_path = config.values["paths"][
        "product_expansion_candidate_output"
    ]
    handoff = config.config("handoff")
    for profile_name in ("db-smoke", "db-full"):
        if candidate_path in {
            item["path"]
            for item in handoff["profiles"][profile_name]["items"]
        }:
            errors.append(
                f"product_coverage:candidate_in_db_handoff:{profile_name}"
            )

    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "active_product_codes": sorted(configured_codes),
        "excluded_manual_aliases": definitions["excluded_manual_aliases"],
        "canonical": {
            "exact_sales_code": canonical_code,
            "customer_products": len(canonical_customer_products),
            "subscriptions": len(canonical_subscriptions),
            "inquiries": len(canonical_inquiries),
        },
        "candidates": {
            "records": len(candidates),
            "exact_sales_codes": sorted(output_cases),
            "backend_import_status": "NOT_IMPORTED",
            "runtime_status": "NOT_VERIFIED",
        },
    }


def validate_manual_three_model_candidates(
    config: PipelineConfig,
) -> dict[str, Any]:
    """Validate manual candidates without claiming unexecuted Runtime results."""

    errors: list[str] = []
    definitions = config.config("manual_three_model_candidates")
    candidates = read_json(config.path("manual_three_model_candidate_output"))
    configured = {row["scenario_id"]: row for row in definitions["scenarios"]}
    output = {row["scenario_id"]: row for row in candidates}
    if len(configured) != len(definitions["scenarios"]):
        errors.append("manual_candidates:duplicate_config_scenario_id")
    if len(output) != len(candidates):
        errors.append("manual_candidates:duplicate_output_scenario_id")
    if set(configured) != EXPECTED_MANUAL_CANDIDATE_IDS:
        errors.append("manual_candidates:canonical_id_coverage")
    if set(output) != EXPECTED_MANUAL_CANDIDATE_IDS:
        errors.append("manual_candidates:output_id_coverage")
    if len(candidates) != config.values["expected_counts"][
        "manual_three_model_candidates"
    ]:
        errors.append("manual_candidates:count_mismatch")

    evidence_groups = {
        row["evidence_group_id"]: row
        for row in read_jsonl(config.path("rag_expansion_evidence_output"))
    }
    contract_root = config.data_root.parent / "contracts"
    request_schema = read_json(
        contract_root / "ai/requests/SymptomAnalysisRequest.schema.json"
    )
    missing_field_schema = read_json(
        contract_root / "ai/common/MissingField.schema.json"
    )
    followup_schema = read_json(
        contract_root / "ai/common/FollowUpQuestion.schema.json"
    )
    transition_text = (
        contract_root / "state-machine/transition-rules.yaml"
    ).read_text(encoding="utf-8")
    contract_events = set(
        re.findall(
            r"(?m)^\s*event:\s*([A-Z][A-Z0-9_]+)\s*$",
            transition_text,
        )
    )
    inquiry_states = set(config.config("vocabulary")["inquiry_statuses"])
    prohibited_question_patterns = (
        r"분해",
        r"해체",
        r"커버를\s*열",
        r"내부를\s*(?:열|점검|확인)",
    )
    inquiry_ids: set[str] = set()
    correlation_ids: set[str] = set()

    for scenario_id in sorted(EXPECTED_MANUAL_CANDIDATE_IDS):
        source = configured.get(scenario_id)
        candidate = output.get(scenario_id)
        if source is None or candidate is None:
            continue
        if source["source_design_id"] != EXPECTED_MANUAL_SOURCE_ID_MAP[
            scenario_id
        ]:
            errors.append(f"manual_candidates:source_id_map:{scenario_id}")
        if source["candidate_status"] != "CANDIDATE":
            errors.append(f"manual_candidates:not_candidate:{scenario_id}")
        if candidate["promotion"]["golden"] is not False:
            errors.append(f"manual_candidates:golden_claim:{scenario_id}")
        if candidate["request"]["model_code"] != candidate["product"][
            "exact_sales_code"
        ]:
            errors.append(f"manual_candidates:model_request_mismatch:{scenario_id}")

        errors.extend(
            f"manual_candidates:request_contract:{scenario_id}:{detail}"
            for detail in validate_schema(candidate["request"], request_schema)
        )
        inquiry_id = candidate["request"]["inquiry_id"]
        correlation_id = candidate["request"]["correlation_id"]
        if inquiry_id in inquiry_ids:
            errors.append(f"manual_candidates:duplicate_inquiry_id:{scenario_id}")
        if correlation_id in correlation_ids:
            errors.append(f"manual_candidates:duplicate_correlation_id:{scenario_id}")
        inquiry_ids.add(inquiry_id)
        correlation_ids.add(correlation_id)

        questions = candidate["question_expectations"]
        for missing in questions["product_specific_target"]["missing_fields"]:
            errors.extend(
                f"manual_candidates:missing_field_contract:{scenario_id}:{detail}"
                for detail in validate_schema(missing, missing_field_schema)
            )
        all_questions = [
            *questions["common"],
            *questions["product_specific_target"]["followup_questions"],
        ]
        for question in all_questions:
            errors.extend(
                f"manual_candidates:followup_contract:{scenario_id}:{detail}"
                for detail in validate_schema(question, followup_schema)
            )
            if any(
                re.search(pattern, question["question_text"], re.I)
                for pattern in prohibited_question_patterns
            ):
                errors.append(f"manual_candidates:unsafe_question:{scenario_id}")

        retrieval = candidate["retrieval_expectation"]
        if scenario_id in MANUAL_NEGATIVE_SCENARIOS and (
            retrieval["expected_evidence_group_ids"]
            or retrieval["expected_no_evidence"] is not True
        ):
            errors.append(f"manual_candidates:negative_evidence:{scenario_id}")
        for evidence_id in retrieval["expected_evidence_group_ids"]:
            evidence = evidence_groups.get(evidence_id)
            if evidence is None:
                errors.append(
                    f"manual_candidates:evidence_missing:{scenario_id}:{evidence_id}"
                )
            elif evidence["exact_sales_code"] != candidate["product"][
                "exact_sales_code"
            ]:
                errors.append(
                    f"manual_candidates:cross_model_evidence:{scenario_id}:{evidence_id}"
                )
        if candidate["request"]["model_code"] in retrieval[
            "forbidden_model_codes"
        ]:
            errors.append(f"manual_candidates:self_forbidden_model:{scenario_id}")

        for profile_name in ("mvp", "three_model_integration"):
            profile = candidate["runtime_profiles"][profile_name]
            for oracle_name in ("current_runtime", "target_oracle"):
                oracle = profile[oracle_name]
                if oracle["verification_status"] == "RUNTIME_VERIFIED":
                    errors.append(
                        "manual_candidates:unverified_runtime_claim:"
                        f"{scenario_id}:{profile_name}:{oracle_name}"
                    )
                event = oracle["backend"]["event_candidate"]
                if event is not None and event not in contract_events:
                    errors.append(
                        f"manual_candidates:unknown_event:{scenario_id}:{event}"
                    )
                for state in oracle["backend"]["expected_state_path"]:
                    if state not in inquiry_states:
                        errors.append(
                            f"manual_candidates:unknown_state:{scenario_id}:{state}"
                        )

        if candidate["product"]["exact_sales_code"].startswith("WPUIAC"):
            current = candidate["runtime_profiles"]["mvp"]["current_runtime"]
            target = candidate["runtime_profiles"]["mvp"]["target_oracle"]
            current_is_leak = scenario_id in MANUAL_LEAK_DANGER_SCENARIOS
            expected_failure_stage = (
                "VALIDATING" if current_is_leak else "RETRIEVING"
            )
            expected_risk_level = "danger" if current_is_leak else "caution"
            expected_guidance_status = (
                "TOTAL_STOP" if current_is_leak else "PENDING_CONSULTATION"
            )
            if (
                current["ai"]["execution_status"] != "FALLBACK"
                or current["ai"]["failure_stage"] != expected_failure_stage
                or current["ai"]["risk_level"] != expected_risk_level
                or current["ai"]["usage_guidance_status"]
                != expected_guidance_status
                or current["ai"]["requires_consultation"] is not True
                or current["ai"]["internal_issue_codes"]
                != ["RUNTIME_PRODUCT_NOT_APPROVED"]
                or current["rag"]["execution_status"] != "BLOCKED"
                or current["backend"]["event_candidate"] is not None
            ):
                errors.append(f"manual_candidates:mvp_iac_current:{scenario_id}")
            if (
                target["verification_status"] != "HOLD"
                or target["backend"]["event_candidate"]
                != "PRODUCT_VALIDATION_FAILED"
                or target["backend"]["terminal_state"]
                != "CONSULTATION_REQUIRED"
            ):
                errors.append(f"manual_candidates:mvp_iac_target:{scenario_id}")

        target = candidate["runtime_profiles"]["three_model_integration"][
            "target_oracle"
        ]
        if scenario_id in MANUAL_HOT_WATER_DANGER_SCENARIOS and (
            target["verification_status"] != "HOLD"
            or target["ai"]["risk_level"] != "danger"
            or target["ai"]["usage_guidance_status"] != "PARTIAL_STOP"
            or target["ai"]["requires_consultation"] is not True
            or target["backend"]["event_candidate"] != "DANGER_DETECTED"
            or "DANGER_PARTIAL_STOP_BACKEND_CONFLICT" not in target["blockers"]
        ):
            errors.append(f"manual_candidates:hot_water_policy:{scenario_id}")
        if scenario_id in MANUAL_LEAK_DANGER_SCENARIOS and (
            target["ai"]["risk_level"] != "danger"
            or target["ai"]["usage_guidance_status"] != "TOTAL_STOP"
            or target["ai"]["requires_consultation"] is not True
        ):
            errors.append(f"manual_candidates:leak_policy:{scenario_id}")

    long_absence = output.get("SYN-IAC606-109")
    if long_absence is not None:
        target = long_absence["runtime_profiles"]["three_model_integration"][
            "target_oracle"
        ]
        if (
            target["ai"]["risk_level"] != "general"
            or target["ai"]["usage_guidance_status"] != "PARTIAL_STOP"
            or target["ai"]["requires_consultation"] is not False
            or target["backend"]["event_candidate"] is not None
            or long_absence["workflow_kind"] != "SELF_RESOLUTION"
            or long_absence["expected_outcome"]
            != "SELF_RESOLUTION_AFTER_CUSTOMER_CONFIRMATION"
        ):
            errors.append("manual_candidates:long_absence_policy")

    reopened = output.get("SYN-IAC606-103")
    if reopened is not None:
        phase_signatures = [
            (
                phase["phase"],
                phase["success_state"],
                [
                    (
                        step["actor_role"],
                        step["event"],
                        step["from_state"],
                        step["to_state"],
                    )
                    for step in phase["steps"]
                ],
            )
            for phase in reopened["workflow_phases"]
        ]
        if phase_signatures != [
            (
                "BASE_REOPEN",
                "REOPENED",
                [("CUSTOMER", "CUSTOMER_REPORTED_UNRESOLVED", "COMPLETION_PENDING", "REOPENED")],
            ),
            (
                "FOLLOWUP_CONSULTATION_RESTART",
                "CONSULTATION_IN_PROGRESS",
                [
                    ("CONSULTANT", "RESUME_CONSULTATION", "REOPENED", "CONSULTATION_REQUIRED"),
                    ("CONSULTANT", "START_CONSULTATION", "CONSULTATION_REQUIRED", "CONSULTATION_IN_PROGRESS"),
                ],
            ),
        ]:
            errors.append("manual_candidates:reopened_phase_split")

    serialized = json_bytes(candidates).decode("utf-8")
    if re.search(r"C:\\Users\\|C:/Users/|Playdata", serialized, re.I):
        errors.append("manual_candidates:internal_path_exposure")
    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", serialized):
        errors.append("manual_candidates:email_like_value")
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "records": len(candidates),
        "scenario_ids": sorted(output),
    }


def run_data_qa(config: PipelineConfig) -> dict[str, Any]:
    manifest = read_json(config.path("dataset_manifest"))
    errors: list[str] = []
    files_checked = 0
    records_checked = 0
    vocabulary = config.config("vocabulary")
    errors.extend(validate_service_contract_mapping(config))
    errors.extend(validate_contract_alignment_registry(config))
    errors.extend(validate_backend_import_crosswalk(config))
    errors.extend(validate_dataset_catalog(config, manifest))
    product_expansion_coverage = validate_product_expansion_coverage(config)
    errors.extend(product_expansion_coverage["errors"])
    manual_candidate_coverage = validate_manual_three_model_candidates(config)
    errors.extend(manual_candidate_coverage["errors"])
    p1_account_link_coverage = validate_p1_account_link_candidates(config)
    errors.extend(p1_account_link_coverage["errors"])
    risk_vocabulary = vocabulary["risk_levels"]
    usage_vocabulary = vocabulary["usage_guidance_statuses"]
    for name, codes in schema_risk_codes(config.data_root).items():
        if codes != risk_vocabulary:
            errors.append(f"risk_vocabulary_schema_mismatch:{name}")
    for name, codes in schema_usage_codes(config.data_root).items():
        if codes != usage_vocabulary:
            errors.append(f"usage_vocabulary_schema_mismatch:{name}")
    for name, relative in config.values["config_schemas"].items():
        value = config.values if name == "pipeline" else config.config(name)
        schema = read_json(config.data_root / relative)
        errors.extend(
            f"config/{name} {detail}"
            for detail in validate_schema(value, schema)
        )
        files_checked += 1
        records_checked += 1
    for entry in manifest["files"]:
        path = config.data_root / entry["path"]
        if not path.is_file():
            errors.append(f"missing:{entry['path']}")
            continue
        files_checked += 1
        if not entry["schema"].endswith(".json"):
            continue
        data = _load_dataset(path)
        rows = data if isinstance(data, list) else [data]
        schema = read_json(config.data_root / entry["schema"])
        for index, row in enumerate(rows):
            records_checked += 1
            errors.extend(
                f"{entry['path']}[{index}] {detail}"
                for detail in validate_schema(row, schema)
            )

    synthetic = config.config("synthetic")
    outputs = {
        key: read_json(config.data_root / path)
        for key, path in synthetic["outputs"].items()
    }
    id_fields = {
        "users": "id",
        "customer_profiles": "id",
        "products": "id",
        "customer_products": "id",
        "subscriptions": "id",
        "inquiries": "id",
        "consultations": "id",
        "visits": "id",
        "care_histories": "id",
        "followup_confirmations": "id",
        "inquiry_status_histories": "id",
        "audit_events": "id",
    }
    for dataset, key in id_fields.items():
        for duplicate in _duplicates(outputs[dataset], key):
            errors.append(f"duplicate:{dataset}:{duplicate}")
        for duplicate in _duplicates(outputs[dataset], "public_id"):
            errors.append(f"duplicate_public_id:{dataset}:{duplicate}")

    ids = {
        name: {row[key] for row in outputs[name]}
        for name, key in id_fields.items()
    }
    for row in outputs["customer_products"]:
        if row["customer_id"] not in ids["users"] or row["product_id"] not in ids["products"]:
            errors.append(f"broken_fk:customer_product:{row['customer_product_id']}")
    profiles_by_user = {
        row["user_id"]: row for row in outputs["customer_profiles"]
    }
    if len(profiles_by_user) != len(outputs["customer_profiles"]):
        errors.append("customer_profile_user_not_one_to_one")
    customer_user_ids = {
        row["id"] for row in outputs["users"] if row["role"] == "CUSTOMER"
    }
    if set(profiles_by_user) != customer_user_ids:
        errors.append("customer_profile_customer_user_coverage")
    profiles_by_id = {
        row["id"]: row for row in outputs["customer_profiles"]
    }
    customer_products_by_id = {
        row["id"]: row for row in outputs["customer_products"]
    }
    for row in outputs["subscriptions"]:
        if (
            row["customer_profile_id"] not in ids["customer_profiles"]
            or row["customer_product_id"] not in ids["customer_products"]
        ):
            errors.append(f"broken_fk:subscription:{row['subscription_id']}")
            continue
        profile = profiles_by_id[row["customer_profile_id"]]
        customer_product = customer_products_by_id[row["customer_product_id"]]
        if profile["user_id"] != customer_product["customer_id"]:
            errors.append(f"subscription_customer_chain_mismatch:{row['subscription_id']}")
    for name in ("consultations", "visits"):
        for row in outputs[name]:
            if row["inquiry_id"] not in ids["inquiries"]:
                errors.append(f"broken_fk:{name}:{row[id_fields[name]]}")
    target_sets = {
        "QUESTIONNAIRE": set(),
        "INQUIRY": ids["inquiries"],
        "CONSULTATION": ids["consultations"],
        "VISIT": ids["visits"],
    }
    target_fields = {
        "QUESTIONNAIRE": "questionnaire_session_id",
        "INQUIRY": "inquiry_id",
        "CONSULTATION": "consultation_id",
        "VISIT": "visit_id",
    }
    history_versions: set[tuple[str, int, int]] = set()
    versions_by_target: dict[tuple[str, int], list[int]] = {}
    for row in outputs["inquiry_status_histories"]:
        configured_targets = [
            name for name in target_fields.values() if row.get(name) is not None
        ]
        if len(configured_targets) != 1:
            errors.append(f"history_target_count:{row['id']}")
            continue
        target_type = row["target_type_code"]
        expected_field = target_fields[target_type]
        if configured_targets[0] != expected_field:
            errors.append(f"history_target_type_mismatch:{row['id']}")
            continue
        target_id = row[expected_field]
        if target_id not in target_sets[target_type]:
            errors.append(f"broken_fk:inquiry_status_histories:{row['id']}")
        allowed_statuses = (
            vocabulary["inquiry_statuses"]
            if target_type == "INQUIRY"
            else vocabulary["visit_statuses"]
            if target_type == "VISIT"
            else []
        )
        for field in ("from_status_code", "to_status_code"):
            value = row[field]
            if value is not None and value not in allowed_statuses:
                errors.append(
                    f"history_status_set_mismatch:{row['id']}:{target_type}:{field}:{value}"
                )
        version_key = (target_type, target_id, row["state_version"])
        if version_key in history_versions:
            errors.append(
                "duplicate_history_state_version:"
                f"{target_type}:{target_id}:{row['state_version']}"
            )
        history_versions.add(version_key)
        versions_by_target.setdefault((target_type, target_id), []).append(
            row["state_version"]
        )
    for (target_type, target_id), versions in versions_by_target.items():
        expected_versions = list(range(1, max(versions) + 1))
        if sorted(versions) != expected_versions:
            errors.append(
                f"non_contiguous_history_state_version:{target_type}:{target_id}"
            )
    history_audit_keys = {
        (
            row["target_type_code"],
            row[target_fields[row["target_type_code"]]],
            row["event_code"],
            row["state_version"],
            row["idempotency_key"],
            row["correlation_id"],
            row["changed_at"],
        )
        for row in outputs["inquiry_status_histories"]
    }
    audit_keys = {
        (
            row["entity_type"],
            row["entity_id"],
            row["event_type"],
            row["state_version"],
            row["idempotency_key"],
            row["correlation_id"],
            row["occurred_at"],
        )
        for row in outputs["audit_events"]
    }
    if history_audit_keys != audit_keys:
        errors.append("status_history_audit_correspondence_mismatch")
    for row in outputs["care_histories"]:
        broken = row["customer_product_id"] not in ids["customer_products"]
        broken |= bool(row.get("inquiry_id")) and row["inquiry_id"] not in ids["inquiries"]
        broken |= bool(row.get("visit_id")) and row["visit_id"] not in ids["visits"]
        if broken:
            errors.append(f"broken_fk:care_histories:{row['care_history_id']}")
    for row in outputs["followup_confirmations"]:
        broken = row["inquiry_id"] not in ids["inquiries"]
        broken |= bool(row["consultation_id"]) and row["consultation_id"] not in ids["consultations"]
        broken |= bool(row["visit_id"]) and row["visit_id"] not in ids["visits"]
        if broken:
            errors.append(f"broken_fk:followup_confirmations:{row['followup_id']}")

    evidence_ids = {
        row["evidence_id"] for row in read_jsonl(config.path("evidence_output"))
    }
    for row in outputs["inquiries"]:
        if any(item not in evidence_ids for item in row["evidence_ids"]):
            errors.append(f"broken_evidence:{row['inquiry_id']}")
        if row["risk_level"] == "danger" and row["usage_guidance_status"] == "NORMAL":
            errors.append(f"danger_normal:{row['inquiry_id']}")

    configured = {
        row["scenario_id"]: row for row in synthetic["scenario_matrix"]
    }
    materialized = {
        row["scenario_id"]: row
        for row in outputs["demo_scenarios"]["scenarios"]
    }
    if set(configured) != set(materialized):
        errors.append("scenario_matrix_materialization_mismatch")
    registry = {
        row["scenario_id"]: row
        for row in outputs["contract_alignment_registry"]
    }
    active_scenarios = {
        scenario_id
        for scenario_id, row in registry.items()
        if row["include_in_contract_projection"]
    }
    projected_scenarios = {
        row["scenario_id"] for row in outputs["inquiries"]
    }
    if projected_scenarios != active_scenarios:
        errors.append("active_scenario_projection_mismatch")
    if len(active_scenarios) != 22:
        errors.append(f"active_scenario_count:{len(active_scenarios)}!=22")
    if {"SYN-JAC104-012", "SYN-JAC104-016"} & projected_scenarios:
        errors.append("blocked_scenario_materialized")
    if any(
        row["status"] not in vocabulary["inquiry_statuses"]
        for row in outputs["inquiries"]
    ):
        errors.append("noncanonical_inquiry_status")
    if any(
        row["target_type_code"] == "INQUIRY"
        and row["to_status_code"] == "PRODUCT_VALIDATION_FAILED"
        for row in outputs["inquiry_status_histories"]
    ):
        errors.append("product_validation_failed_materialized_as_state")

    idempotency_cases = outputs["api_idempotency_cases"]
    by_outcome = {row["expected_outcome"]: row for row in idempotency_cases}
    if set(by_outcome) != {"PROCESSED", "REPLAY", "CONFLICT"}:
        errors.append("api_idempotency_case_coverage")
    else:
        processed = by_outcome["PROCESSED"]
        replay = by_outcome["REPLAY"]
        conflict = by_outcome["CONFLICT"]
        scope_fields = ("actor", "operation_id", "idempotency_key")
        if any(processed[field] != replay[field] for field in scope_fields):
            errors.append("api_idempotency_replay_scope_mismatch")
        if (
            processed["request_payload_sha256"]
            != replay["request_payload_sha256"]
            or replay["expected_history_rows_created"] != 0
            or not replay["replay"]
        ):
            errors.append("api_idempotency_replay_expectation")
        if (
            processed["idempotency_key"] != conflict["idempotency_key"]
            or processed["request_payload_sha256"]
            == conflict["request_payload_sha256"]
            or conflict["internal_conflict_code"]
            != "IDEMPOTENCY_KEY_REUSE_CONFLICT"
            or conflict["expected_api_error_code"] != "DUPLICATE-EVENT-01"
            or conflict["expected_history_rows_created"] != 0
        ):
            errors.append("api_idempotency_conflict_expectation")
        if any(
            row["internal_conflict_code"] is not None
            or row["expected_api_error_code"] is not None
            for row in (processed, replay)
        ):
            errors.append("api_idempotency_success_error_code_present")
        shared_histories = [
            row
            for row in outputs["inquiry_status_histories"]
            if row["idempotency_key"] == processed["idempotency_key"]
            and row["event_code"] == "CONFIRM_VISIT"
        ]
        if (
            processed["expected_history_rows_created"] != 2
            or {row["target_type_code"] for row in shared_histories}
            != {"INQUIRY", "VISIT"}
            or len({row["correlation_id"] for row in shared_histories}) != 1
        ):
            errors.append("api_idempotency_shared_history_expectation")

    active_text = json_bytes(outputs).decode("utf-8")
    retired_code = "USE_" + "ALLOWED"
    if retired_code in active_text:
        errors.append("retired_usage_code")
    if re.search(r"C:\\Users\\|C:/Users/|Playdata", active_text, re.I):
        errors.append("internal_path_exposure")
    expected = config.values["expected_counts"]
    actual = {
        "manual_pages": len(read_jsonl(config.path("manual_input"))),
        "faq_normalized": len(read_jsonl(config.path("faq_input"))),
        "rag_chunks": len(read_jsonl(config.path("rag_output"))),
        "evidence": len(read_jsonl(config.path("evidence_output"))),
        "synthetic_inquiries": len(outputs["inquiries"]),
        "synthetic_fixture_records": count_synthetic_fixture_records(outputs),
        "product_expansion_e2e_candidates": len(
            read_json(config.path("product_expansion_candidate_output"))
        ),
        "manual_three_model_candidates": len(
            read_json(config.path("manual_three_model_candidate_output"))
        ),
        "p1_account_link_candidates": len(
            read_json(config.path("p1_account_link_candidate_output"))
        ),
    }
    for key, value in actual.items():
        if value != expected[key]:
            errors.append(f"count:{key}:{value}!={expected[key]}")
    representative_e2e = validate_representative_e2e(config)
    errors.extend(representative_e2e["errors"])
    files_checked += representative_e2e["summary"]["documents_checked"]
    return {
        "status": "PASS" if not errors else "FAIL",
        "generated_at": config.generated_at,
        "summary": {
            "errors": len(errors),
            "warnings": 0,
            "files_checked": files_checked,
            "records_checked": records_checked,
        },
        "counts": actual,
        "errors": errors,
        "representative_e2e": representative_e2e,
        "product_expansion_coverage": product_expansion_coverage,
        "manual_three_model_candidate_coverage": manual_candidate_coverage,
        "p1_account_link_candidate_coverage": p1_account_link_coverage,
    }
