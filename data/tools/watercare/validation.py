"""Equivalence and declarative dataset validation."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import PipelineConfig
from .e2e_validation import validate_representative_e2e
from .io import json_bytes, read_json, read_jsonl, sha256_bytes


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
        len(synthetic["scenario_matrix"]) == expected["synthetic_inquiries"],
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


def run_data_qa(config: PipelineConfig) -> dict[str, Any]:
    manifest = read_json(config.path("dataset_manifest"))
    errors: list[str] = []
    files_checked = 0
    records_checked = 0
    vocabulary = config.config("vocabulary")
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
        "users": "user_id",
        "products": "product_id",
        "customer_products": "customer_product_id",
        "subscriptions": "subscription_id",
        "inquiries": "inquiry_id",
        "consultations": "consultation_id",
        "visits": "visit_id",
        "care_histories": "care_history_id",
        "followup_confirmations": "followup_id",
        "inquiry_status_histories": "history_id",
        "audit_events": "audit_event_id",
    }
    for dataset, key in id_fields.items():
        for duplicate in _duplicates(outputs[dataset], key):
            errors.append(f"duplicate:{dataset}:{duplicate}")

    ids = {
        name: {row[key] for row in outputs[name]}
        for name, key in id_fields.items()
    }
    for row in outputs["customer_products"]:
        if row["customer_id"] not in ids["users"] or row["product_id"] not in ids["products"]:
            errors.append(f"broken_fk:customer_product:{row['customer_product_id']}")
    for row in outputs["subscriptions"]:
        if row["customer_id"] not in ids["users"] or row["customer_product_id"] not in ids["customer_products"]:
            errors.append(f"broken_fk:subscription:{row['subscription_id']}")
    for name in ("consultations", "visits", "inquiry_status_histories"):
        for row in outputs[name]:
            if row["inquiry_id"] not in ids["inquiries"]:
                errors.append(f"broken_fk:{name}:{row[id_fields[name]]}")
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
    if any(
        row["status"] not in vocabulary["inquiry_statuses"]
        for row in outputs["inquiries"]
    ):
        errors.append("noncanonical_inquiry_status")

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
