"""Equivalence and declarative dataset validation."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import PipelineConfig
from .e2e_validation import validate_representative_e2e
from .io import ensure_within, json_bytes, read_json, read_jsonl, sha256_bytes, sha256_file


def validate_service_contract_mapping(config: PipelineConfig) -> list[str]:
    mapping = config.config("contract_mapping")
    vocabulary = config.config("vocabulary")
    repo_root = config.data_root.parent.resolve()
    errors: list[str] = []

    for source_name, source in mapping["contract_sources"].items():
        try:
            path = ensure_within(repo_root, repo_root / source["path"])
        except ValueError:
            errors.append(f"contract_source_path_escape:{source_name}")
            continue
        if not path.is_file():
            errors.append(f"contract_source_missing:{source_name}:{source['path']}")
            continue
        actual_hash = sha256_file(path)
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
    for source_name, source in crosswalk["backend_sources"].items():
        try:
            path = ensure_within(repo_root, repo_root / source["path"])
        except ValueError:
            errors.append(f"backend_source_path_escape:{source_name}")
            continue
        if not path.is_file():
            errors.append(f"backend_source_missing:{source_name}:{source['path']}")
            continue
        actual_hash = sha256_file(path)
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
    care_mapping = crosswalk["code_mappings"]["care_type"]
    if care_mapping.get("VISIT_SERVICE") is not None:
        errors.append("unconfirmed_care_mapping_enabled")
    blocked = {
        row["id"]: row["treatment"] for row in crosswalk["blocked_mappings"]
    }
    if blocked.get("CARE-VISIT-SERVICE-TYPE") != "EXCLUDE_FROM_DIRECT_LOAD":
        errors.append("unconfirmed_care_mapping_not_excluded")
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
        else "lookup_bridge_and_blocked_mappings_verified",
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
    }
