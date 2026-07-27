"""T-005 ERD Snapshot의 구조와 미해결 WBS 충돌을 감사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPOSITORY_ROOT / "backend"
MANAGE_PATH = BACKEND_DIR / "manage.py"
POSTGRESQL_CHECK_PATH = (
    REPOSITORY_ROOT
    / "scripts"
    / "database"
    / "check_postgresql_connection.py"
)
ARTIFACT_DIR = REPOSITORY_ROOT / "docs" / "database" / "t-005"
MANIFEST_PATH = ARTIFACT_DIR / "manifest.json"
SCHEMA_PATH = ARTIFACT_DIR / "watercare_schema_v3.json"
LOGICAL_CONTRACT_PATH = ARTIFACT_DIR / "t005_logical_contract_v0.2.json"
DECISION_REGISTER_PATH = ARTIFACT_DIR / "t005_decision_register_v0.1.json"
PHYSICAL_CONTRACT_PATH = ARTIFACT_DIR / "t005_physical_contract_v1.0.json"
USAGE_CODE_CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "codes"
    / "usage-guidance-statuses.yaml"
)
VISIT_CODE_CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "codes"
    / "visit-statuses.yaml"
)
DECISION_STATUSES = {"PENDING", "ACCEPTED", "REJECTED", "DEFERRED"}
DECISION_REGISTER_STATUSES = DECISION_STATUSES | {"PARTIAL"}
DECISION_REGISTER_VERSION = "0.1"
ACCEPTED_DECISION_FIELDS = {
    "selected_option",
    "decided_by",
    "decided_at",
    "rationale",
    "effective_from",
}
DECIDED_DECISION_FIELDS = {
    "decided_by",
    "decided_at",
    "rationale",
}
COMPLETION_EVIDENCE_FIELDS = {
    "reviewer",
    "recorded_at",
}
LEGACY_COMPLETION_EVIDENCE_FIELD_ALIASES = {
    "team_review": "non_author_review",
}
LEGACY_COMPLETION_EVIDENCE_STATUS_ALIASES = {
    "APPROVED": "CONFIRMED",
}

EXPECTED_USAGE_GUIDANCE_FIELDS = {
    "usage_guidance_status",
    "usage_guidance_message",
    "restricted_functions",
    "evidence",
    "next_action",
    "requires_consultation",
}
EXPECTED_VISIT_SCHEDULE_FIELDS = {
    "preferred_date",
    "synthetic_technician_id",
    "schedule_status",
    "confirmed_date",
}
EXPECTED_RISK_LEVELS = {"general", "caution", "danger"}
EXPECTED_USAGE_GUIDANCE_CODES = {
    "NORMAL",
    "PARTIAL_STOP",
    "TOTAL_STOP",
    "PENDING_CONSULTATION",
}
EXPECTED_VISIT_STATUS_CODES = {
    "ASSIGNING",
    "SCHEDULING",
    "CONFIRMED",
    "IN_PROGRESS",
    "COMPLETED",
    "FOLLOW_UP_REQUIRED",
    "CANCELLED",
}


def _confirmation_record_valid(value: Any) -> bool:
    status = value.get("status") if isinstance(value, dict) else None
    canonical_status = LEGACY_COMPLETION_EVIDENCE_STATUS_ALIASES.get(
        status,
        status,
    )
    return (
        isinstance(value, dict)
        and canonical_status == "CONFIRMED"
        and all(
            isinstance(value.get(field), str)
            and bool(value[field].strip())
            for field in COMPLETION_EVIDENCE_FIELDS
        )
        and value["reviewer"].strip() != "최지용"
    )


def completion_evidence_gates(
    evidence: dict[str, Any] | None,
    *,
    postgresql_verification: dict[str, Any] | None = None,
) -> dict[str, bool]:
    """완료 증거를 평가한다.

    canonical 입력은 ``non_author_review.status=CONFIRMED``이다.
    기존 산출물 호환을 위해 ``team_review``와 ``APPROVED``는 입력
    alias로만 허용하며 반환 gate 이름에는 사용하지 않는다.
    """

    evidence = evidence if isinstance(evidence, dict) else {}
    postgresql_verification = (
        postgresql_verification
        if isinstance(postgresql_verification, dict)
        else {}
    )
    seed = evidence.get("seed_idempotency")
    non_author_review = evidence.get("non_author_review")
    if non_author_review is None:
        legacy_key = next(
            legacy
            for legacy, canonical in (
                LEGACY_COMPLETION_EVIDENCE_FIELD_ALIASES.items()
            )
            if canonical == "non_author_review"
        )
        non_author_review = evidence.get(legacy_key)
    return {
        "non_author_review_confirmed": _confirmation_record_valid(
            non_author_review
        ),
        "django_model_migration_parity_verified": (
            postgresql_verification.get("settings_module")
            == "config.settings.local"
            and postgresql_verification.get("makemigrations_status")
            == "PASSED"
        ),
        "postgresql_migration_verified": (
            postgresql_verification.get("settings_module")
            == "config.settings.local"
            and postgresql_verification.get("database_vendor")
            == "PostgreSQL"
            and postgresql_verification.get("connection_status")
            == "CONNECTED"
            and postgresql_verification.get("migration_status")
            == "PASSED"
        ),
        "seed_idempotency_verified_on_postgresql": (
            isinstance(seed, dict)
            and seed.get("status") == "VERIFIED"
            and seed.get("database_vendor") == "PostgreSQL"
            and isinstance(seed.get("run_count"), int)
            and seed["run_count"] >= 2
            and all(
                isinstance(seed.get(field), str)
                and bool(seed[field].strip())
                for field in ("command", "verified_by", "recorded_at")
            )
        ),
        "external_review_verified": _confirmation_record_valid(
            evidence.get("external_review")
        ),
    }


def _run_verification_command(
    command: list[str],
    *,
    cwd: Path,
    environ: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=environ,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def verify_postgresql_runtime() -> dict[str, Any]:
    """실제 로컬 Django 설정과 PostgreSQL로 Migration 상태를 검증한다."""

    environ = os.environ.copy()
    environ["DJANGO_SETTINGS_MODULE"] = "config.settings.local"
    connection = _run_verification_command(
        [sys.executable, str(POSTGRESQL_CHECK_PATH)],
        cwd=REPOSITORY_ROOT,
        environ=environ,
    )
    connection_payload: dict[str, Any] = {}
    if connection.stdout:
        try:
            parsed = json.loads(connection.stdout)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            connection_payload = parsed

    result: dict[str, Any] = {
        "settings_module": "config.settings.local",
        "database_vendor": connection_payload.get("vendor"),
        "connection_status": (
            "CONNECTED"
            if (
                connection.returncode == 0
                and connection_payload.get("status") == "CONNECTED"
                and connection_payload.get("vendor") == "PostgreSQL"
            )
            else (
                "NOT_CONFIGURED"
                if connection.returncode == 2
                else "FAILED"
            )
        ),
        "makemigrations_status": "NOT_RUN",
        "migration_status": "NOT_RUN",
    }

    parity = _run_verification_command(
        [
            sys.executable,
            str(MANAGE_PATH),
            "makemigrations",
            "--check",
            "--dry-run",
            "--settings=config.settings.local",
        ],
        cwd=BACKEND_DIR,
        environ=environ,
    )
    result["makemigrations_status"] = (
        "PASSED" if parity.returncode == 0 else "FAILED"
    )
    if result["connection_status"] != "CONNECTED":
        return result

    migration = _run_verification_command(
        [
            sys.executable,
            str(MANAGE_PATH),
            "migrate",
            "--check",
            "--noinput",
            "--settings=config.settings.local",
        ],
        cwd=BACKEND_DIR,
        environ=environ,
    )
    result["migration_status"] = (
        "PASSED" if migration.returncode == 0 else "FAILED"
    )
    return result


EXPECTED_DECISIONS = {
    "T005_PRIMARY_KEY_POLICY": "DOMAIN_PREFIX_UUID4_WITH_DEMO_SEQUENCE",
    "T005_USAGE_GUIDANCE_PHYSICAL_MAPPING": (
        "CANONICAL_STATUS_RENAME_NO_DUAL_WRITE"
    ),
    "T005_USAGE_GUIDANCE_CODESET": (
        "NORMAL_CANONICAL_USE_ALLOWED_IMPORT_ALIAS"
    ),
    "T005_VISIT_STORAGE_MAPPING": "DATE_FIELDS_PLUS_SCHEDULE_STATUS",
    "T005_VISIT_STATUS_CODESET": (
        "SEVEN_VISIT_STATUSES_WITH_FOLLOW_UP"
    ),
    "T005_ENUM_SEED_POLICY": "CONTRACT_YAML_TEXTCHOICES_UPSERT",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def table_columns(
    schema: dict[str, Any],
    table_name: str,
) -> dict[str, dict[str, Any]]:
    table = schema["tables"].get(table_name)
    if table is None:
        return {}
    return {column["name"]: column for column in table["columns"]}


def code_values(document: dict[str, Any]) -> set[str]:
    values = document.get("codes", [])
    if not isinstance(values, list):
        return set()
    return {
        value
        for value in values
        if isinstance(value, str)
    }


def audit_owner_baseline(
    *,
    physical_contract: dict[str, Any],
    decision_register: dict[str, Any],
    usage_code_contract: dict[str, Any],
    visit_code_contract: dict[str, Any],
) -> dict[str, Any]:
    """별도 물리 계약이 v3 Snapshot의 여섯 gap을 모두 해소하는지 검사한다."""

    physical_overrides = physical_contract.get("physical_overrides", {})
    inquiry_fields = set(
        physical_overrides.get("support_inquiry", {})
    )
    assessment_fields = set(
        physical_overrides.get("support_symptom_assessment", {})
    )
    visit_fields = set(
        physical_overrides.get("field_service_visit", {})
    )
    standard_codes = physical_contract.get("standard_codes", {})
    registered_decisions = {
        decision.get("id"): decision.get("selected_option")
        for decision in decision_register.get("decisions", [])
        if decision.get("status") == "ACCEPTED"
    }
    legacy_aliases = usage_code_contract.get(
        "legacy_import_aliases",
        {},
    )
    enum_seed_policy = physical_contract.get(
        "enum_and_seed_policy",
        {},
    )

    checks = {
        "contract_version": (
            physical_contract.get("contract_version") == "1.0.0"
        ),
        "owner_status": (
            physical_contract.get("status") == "OWNER_BASELINE"
        ),
        "owner_confirmation": (
            physical_contract.get("confirmation_status") == "CONFIRMED"
        ),
        "immutable_snapshot": (
            physical_contract.get("inherits", {}).get(
                "immutable_snapshot"
            )
            is True
        ),
        "accepted_decisions": (
            registered_decisions == EXPECTED_DECISIONS
        ),
        "identifier_policy": (
            physical_contract.get("identifier_policy", {}).get("option")
            == EXPECTED_DECISIONS["T005_PRIMARY_KEY_POLICY"]
            and physical_contract.get("identifier_policy", {}).get(
                "database_type"
            )
            == "varchar(48)"
        ),
        "usage_guidance_fields": (
            EXPECTED_USAGE_GUIDANCE_FIELDS <= inquiry_fields
            and "usage_guidance_status" in assessment_fields
        ),
        "visit_schedule_fields": (
            EXPECTED_VISIT_SCHEDULE_FIELDS <= visit_fields
        ),
        "usage_guidance_codes": (
            code_values(usage_code_contract)
            == EXPECTED_USAGE_GUIDANCE_CODES
            and set(standard_codes.get("usage_guidance_status", []))
            == EXPECTED_USAGE_GUIDANCE_CODES
        ),
        "legacy_usage_alias": (
            legacy_aliases == {"USE_ALLOWED": "NORMAL"}
        ),
        "visit_status_codes": (
            code_values(visit_code_contract)
            == EXPECTED_VISIT_STATUS_CODES
            and set(standard_codes.get("visit_schedule_status", []))
            == EXPECTED_VISIT_STATUS_CODES
        ),
        "visit_default": (
            physical_overrides.get("field_service_visit", {})
            .get("schedule_status", {})
            .get("default")
            == "ASSIGNING"
        ),
        "enum_seed_policy": (
            enum_seed_policy.get("django_representation")
            == "TextChoices with contract parity tests"
            and enum_seed_policy.get("database_enum") is False
            and enum_seed_policy.get("manual_insert") is False
        ),
    }
    return {
        "status": (
            "OWNER_BASELINE_CONFIRMED"
            if all(checks.values())
            else "OWNER_BASELINE_INVALID"
        ),
        "confirmation_scope": "T005_OWNER_BASELINE",
        "confirmation_status": physical_contract.get(
            "confirmation_status",
            "UNCONFIRMED",
        ),
        "completion_review_status": physical_contract.get(
            "completion_review_status",
            "PENDING",
        ),
        "checks": checks,
        "valid": all(checks.values()),
    }


def audit_snapshot(
    *,
    manifest: dict[str, Any] | None = None,
    schema: dict[str, Any] | None = None,
    logical_contract: dict[str, Any] | None = None,
    decision_register: dict[str, Any] | None = None,
    physical_contract: dict[str, Any] | None = None,
    usage_code_contract: dict[str, Any] | None = None,
    visit_code_contract: dict[str, Any] | None = None,
    completion_evidence: dict[str, Any] | None = None,
    postgresql_verification: dict[str, Any] | None = None,
    verify_artifact_hashes: bool = True,
) -> dict[str, Any]:
    if manifest is None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if schema is None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if logical_contract is None:
        logical_contract = json.loads(
            LOGICAL_CONTRACT_PATH.read_text(encoding="utf-8")
        )
    if decision_register is None:
        decision_register = json.loads(
            DECISION_REGISTER_PATH.read_text(encoding="utf-8")
        )
    if physical_contract is None:
        physical_contract = json.loads(
            PHYSICAL_CONTRACT_PATH.read_text(encoding="utf-8")
        )
    if usage_code_contract is None:
        usage_code_contract = yaml.safe_load(
            USAGE_CODE_CONTRACT_PATH.read_text(encoding="utf-8")
        )
    if visit_code_contract is None:
        visit_code_contract = yaml.safe_load(
            VISIT_CODE_CONTRACT_PATH.read_text(encoding="utf-8")
        )
    tables = schema.get("tables", {})
    columns = [
        (table_name, column)
        for table_name, table in tables.items()
        for column in table.get("columns", [])
    ]
    physical_fks = [
        (table_name, column)
        for table_name, column in columns
        if column.get("referenceKind") == "physical_fk"
    ]
    logical_codes = [
        (table_name, column)
        for table_name, column in columns
        if column.get("referenceKind") == "logical_code"
    ]
    counts = {
        "tables": len(tables),
        "columns": len(columns),
        "physical_fks": len(physical_fks),
        "logical_codes": len(logical_codes),
    }
    errors: list[dict[str, str]] = []

    contract_usage_fields = set(
        logical_contract["canonical_fields"]["usage_guidance"]
    )
    contract_visit_fields = set(
        logical_contract["canonical_fields"]["visit_schedule"]
    )
    contract_risk_levels = set(
        logical_contract["confirmed_code_sets"]["risk_level"]
    )
    manifest_blocker_ids = list(manifest.get("blocking_decisions", []))
    contract_decision_ids = [
        decision.get("id")
        for decision in logical_contract.get("decisions_required", [])
    ]
    manifest_blocker_set = set(manifest_blocker_ids)
    contract_decision_set = set(contract_decision_ids)
    register_decisions = decision_register.get("decisions", [])
    register_ids = [
        decision.get("id")
        for decision in register_decisions
    ]
    register_id_set = set(register_ids)
    manifest_duplicates = sorted(
        {
            blocker_id
            for blocker_id in manifest_blocker_ids
            if manifest_blocker_ids.count(blocker_id) > 1
        }
    )
    contract_decision_duplicates = sorted(
        {
            decision_id
            for decision_id in contract_decision_ids
            if contract_decision_ids.count(decision_id) > 1
        }
    )
    register_duplicates = sorted(
        {
            decision_id
            for decision_id in register_ids
            if register_ids.count(decision_id) > 1
        }
    )
    decision_alignment = {
        "manifest_ids": sorted(manifest_blocker_set),
        "logical_contract_ids": sorted(contract_decision_set),
        "missing_in_logical_contract": sorted(
            manifest_blocker_set - contract_decision_set
        ),
        "stale_in_logical_contract": sorted(
            contract_decision_set - manifest_blocker_set
        ),
        "manifest_duplicates": manifest_duplicates,
        "logical_contract_duplicates": contract_decision_duplicates,
        "matches": (
            manifest_blocker_set == contract_decision_set
            and not manifest_duplicates
            and not contract_decision_duplicates
            and None not in contract_decision_set
        ),
    }
    invalid_register_decisions = []
    for decision in register_decisions:
        status = decision.get("status")
        missing_fields = []
        if status == "ACCEPTED":
            missing_fields = sorted(
                field
                for field in ACCEPTED_DECISION_FIELDS
                if not decision.get(field)
            )
        elif status in {"REJECTED", "DEFERRED"}:
            missing_fields = sorted(
                field
                for field in DECIDED_DECISION_FIELDS
                if not decision.get(field)
            )
        if status not in DECISION_STATUSES or missing_fields:
            invalid_register_decisions.append(
                {
                    "id": decision.get("id"),
                    "status": status,
                    "missing_fields": missing_fields,
                }
            )
    individual_statuses = [
        decision.get("status")
        for decision in register_decisions
    ]
    expected_register_status = "PARTIAL"
    if (
        individual_statuses
        and len(set(individual_statuses)) == 1
        and individual_statuses[0] in DECISION_STATUSES
    ):
        expected_register_status = individual_statuses[0]
    register_status = decision_register.get("status")
    register_version = decision_register.get("version")
    decision_register_check = {
        "version": register_version,
        "version_valid": register_version == DECISION_REGISTER_VERSION,
        "status": register_status,
        "expected_status": expected_register_status,
        "status_valid": (
            register_status in DECISION_REGISTER_STATUSES
            and register_status == expected_register_status
        ),
        "ids": sorted(register_id_set),
        "missing_ids": sorted(
            manifest_blocker_set - register_id_set
        ),
        "stale_ids": sorted(
            register_id_set - manifest_blocker_set
        ),
        "duplicates": register_duplicates,
        "invalid_decisions": invalid_register_decisions,
        "accepted_count": sum(
            decision.get("status") == "ACCEPTED"
            for decision in register_decisions
        ),
        "valid": (
            register_id_set == manifest_blocker_set
            and not register_duplicates
            and None not in register_id_set
            and not invalid_register_decisions
            and register_version == DECISION_REGISTER_VERSION
            and register_status in DECISION_REGISTER_STATUSES
            and register_status == expected_register_status
        ),
    }
    if not decision_register_check["valid"]:
        errors.append(
            {
                "id": "T005_DECISION_REGISTER_INVALID",
                "message": json.dumps(
                    decision_register_check,
                    ensure_ascii=False,
                ),
            }
        )
    owner_baseline = audit_owner_baseline(
        physical_contract=physical_contract,
        decision_register=decision_register,
        usage_code_contract=usage_code_contract,
        visit_code_contract=visit_code_contract,
    )
    if not owner_baseline["valid"]:
        errors.append(
            {
                "id": "T005_OWNER_BASELINE_INVALID",
                "message": json.dumps(
                    owner_baseline["checks"],
                    ensure_ascii=False,
                ),
            }
        )
    logical_contract_checks = {
        "usage_guidance_fields": (
            contract_usage_fields == EXPECTED_USAGE_GUIDANCE_FIELDS
        ),
        "visit_schedule_fields": (
            contract_visit_fields == EXPECTED_VISIT_SCHEDULE_FIELDS
        ),
        "risk_levels": contract_risk_levels == EXPECTED_RISK_LEVELS,
        "open_decisions_visible": bool(
            logical_contract.get("decisions_required")
        ),
        "decision_ids_aligned": decision_alignment["matches"],
    }
    if not all(logical_contract_checks.values()):
        errors.append(
            {
                "id": "T005_LOGICAL_CONTRACT_INVALID",
                "message": json.dumps(
                    logical_contract_checks,
                    ensure_ascii=False,
                ),
            }
        )

    if counts != manifest["expected_counts"]:
        errors.append(
            {
                "id": "T005_COUNT_MISMATCH",
                "message": (
                    f"expected={manifest['expected_counts']}, actual={counts}"
                ),
            }
        )
    if schema.get("counts") != manifest["expected_counts"]:
        errors.append(
            {
                "id": "T005_SCHEMA_METADATA_MISMATCH",
                "message": "schema counts and manifest counts differ",
            }
        )

    if verify_artifact_hashes:
        for relative_path, expected_hash in manifest["files"].items():
            artifact_path = ARTIFACT_DIR / relative_path
            if not artifact_path.is_file():
                errors.append(
                    {
                        "id": "T005_ARTIFACT_MISSING",
                        "message": relative_path,
                    }
                )
                continue
            actual_hash = sha256(artifact_path)
            if actual_hash != expected_hash:
                errors.append(
                    {
                        "id": "T005_ARTIFACT_HASH_MISMATCH",
                        "message": (
                            f"{relative_path}: expected={expected_hash}, "
                            f"actual={actual_hash}"
                        ),
                    }
                )

    columns_by_table = {
        table_name: {
            column["name"]
            for column in table.get("columns", [])
        }
        for table_name, table in tables.items()
    }
    for child_table, column in physical_fks:
        reference = column.get("reference", "")
        if "." not in reference:
            errors.append(
                {
                    "id": "T005_INVALID_FK_REFERENCE",
                    "message": f"{child_table}.{column['name']} -> {reference}",
                }
            )
            continue
        parent_table, parent_column = reference.rsplit(".", 1)
        if parent_column not in columns_by_table.get(parent_table, set()):
            errors.append(
                {
                    "id": "T005_MISSING_FK_TARGET",
                    "message": f"{child_table}.{column['name']} -> {reference}",
                }
            )

    legacy_snapshot_gaps: list[dict[str, Any]] = []
    uuid_primary_keys = [
        f"{table_name}.{column['name']}"
        for table_name, column in columns
        if column.get("pk") is True
        and str(column.get("type", "")).lower() == "uuid"
    ]
    if uuid_primary_keys:
        legacy_snapshot_gaps.append(
            {
                "id": "T005_PRIMARY_KEY_POLICY",
                "message": (
                    "UUID PK Snapshot과 도메인형 문자열 ID 공통 규칙이 충돌한다."
                ),
                "examples": uuid_primary_keys[:5],
                "count": len(uuid_primary_keys),
            }
        )

    inquiry_columns = table_columns(schema, "support_inquiry")
    if "usage_guidance_status" not in inquiry_columns:
        legacy_snapshot_gaps.append(
            {
                "id": "T005_USAGE_GUIDANCE_PHYSICAL_MAPPING",
                "message": (
                    "canonical 이름은 usage_guidance_status로 확정됐지만 "
                    "ERD v3 물리 필드는 아직 usage_guidance_code다."
                ),
            }
        )

    visit_columns = table_columns(schema, "field_service_visit")
    required_visit_fields = {
        "preferred_date",
        "confirmed_date",
        "schedule_status",
    }
    missing_visit_fields = sorted(required_visit_fields - set(visit_columns))
    if missing_visit_fields:
        legacy_snapshot_gaps.append(
            {
                "id": "T005_VISIT_STORAGE_MAPPING",
                "message": (
                    "화면 계약의 방문 희망일·확정일·일정 상태 필드가 "
                    "동일 이름으로 ERD에 없다."
                ),
                "missing": missing_visit_fields,
                "current": [
                    field
                    for field in (
                        "scheduled_start_at",
                        "scheduled_end_at",
                        "visit_status_code",
                    )
                    if field in visit_columns
                ],
            }
        )

    legacy_snapshot_gaps.append(
        {
            "id": "T005_ENUM_SEED_POLICY",
            "message": (
                "Enum 관리와 Seed 운영 방식은 공통 개발 규칙에서 보류 상태다."
            ),
        }
    )

    for decision in logical_contract["decisions_required"]:
        decision_id = decision["id"]
        if decision_id in {
            "T005_PRIMARY_KEY_POLICY",
            "T005_USAGE_GUIDANCE_PHYSICAL_MAPPING",
            "T005_VISIT_STORAGE_MAPPING",
            "T005_ENUM_SEED_POLICY",
        }:
            continue
        legacy_snapshot_gaps.append(
            {
                "id": decision_id,
                "message": decision["decision"],
            }
        )

    gap_ids = [gap["id"] for gap in legacy_snapshot_gaps]
    gap_id_set = set(gap_ids)
    gap_duplicates = sorted(
        {
            gap_id
            for gap_id in gap_ids
            if gap_ids.count(gap_id) > 1
        }
    )
    blocker_alignment = {
        "manifest_ids": sorted(manifest_blocker_set),
        "gap_ids": sorted(gap_id_set),
        "missing_in_manifest": sorted(gap_id_set - manifest_blocker_set),
        "stale_in_manifest": sorted(manifest_blocker_set - gap_id_set),
        "manifest_duplicates": manifest_duplicates,
        "gap_duplicates": gap_duplicates,
        "matches": (
            manifest_blocker_set == gap_id_set
            and not manifest_duplicates
            and not gap_duplicates
        ),
    }
    if not blocker_alignment["matches"]:
        errors.append(
            {
                "id": "T005_BLOCKER_MANIFEST_MISMATCH",
                "message": json.dumps(
                    blocker_alignment,
                    ensure_ascii=False,
                ),
            }
        )

    gaps = [] if owner_baseline["valid"] else legacy_snapshot_gaps
    evidence_gates = completion_evidence_gates(
        completion_evidence,
        postgresql_verification=postgresql_verification,
    )
    completion_gates = {
        "owner_baseline_confirmed": (
            owner_baseline["valid"]
            and owner_baseline["confirmation_status"] == "CONFIRMED"
        ),
        "non_author_review_confirmed": evidence_gates[
            "non_author_review_confirmed"
        ],
        "django_model_migration_parity_verified": evidence_gates[
            "django_model_migration_parity_verified"
        ],
        "postgresql_migration_verified": evidence_gates[
            "postgresql_migration_verified"
        ],
        "seed_idempotency_verified_on_postgresql": evidence_gates[
            "seed_idempotency_verified_on_postgresql"
        ],
        "external_review_verified": evidence_gates[
            "external_review_verified"
        ],
    }
    wbs_completion_gaps = [
        gate
        for gate, complete in completion_gates.items()
        if not complete
    ]

    coverage = {
        "current_owner": all(
            field in inquiry_columns
            for field in ("current_owner_id", "current_owner_role_code")
        ),
        "usage_guidance": all(
            field in inquiry_columns
            for field in (
                "usage_guidance_message",
                "restricted_functions",
            )
        ),
        "customer_action_required": (
            "customer_action_required" in inquiry_columns
        ),
        "evidence_structure": (
            "knowledge_evidence_link" in tables
            and "support_guidance" in tables
        ),
    }
    if not all(coverage.values()):
        errors.append(
            {
                "id": "T005_WBS_BASE_FIELDS_MISSING",
                "message": json.dumps(coverage, ensure_ascii=False),
            }
        )

    return {
        "artifact_version": manifest["artifact_version"],
        "snapshot_status": manifest["snapshot_status"],
        "structure_valid": not errors,
        "counts": counts,
        "coverage": coverage,
        "logical_contract_checks": logical_contract_checks,
        "decision_alignment": decision_alignment,
        "decision_register": decision_register_check,
        "owner_baseline": owner_baseline,
        "blocker_alignment": blocker_alignment,
        "errors": errors,
        "legacy_snapshot_gaps": legacy_snapshot_gaps,
        "gaps": gaps,
        "completion_gates": completion_gates,
        "completion_evidence_supplied": (
            isinstance(completion_evidence, dict)
            and bool(completion_evidence)
        ),
        "postgresql_verification": (
            postgresql_verification
            if isinstance(postgresql_verification, dict)
            else {
                "settings_module": "config.settings.local",
                "database_vendor": None,
                "connection_status": "NOT_RUN",
                "makemigrations_status": "NOT_RUN",
                "migration_status": "NOT_RUN",
            }
        ),
        "wbs_completion_gaps": wbs_completion_gaps,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-wbs-complete",
        action="store_true",
        help="미해결 WBS 충돌이 있으면 exit code 2를 반환한다.",
    )
    parser.add_argument(
        "--completion-evidence",
        type=Path,
        help="팀·외부 리뷰와 Seed 검증 기록 JSON 경로",
    )
    parser.add_argument(
        "--verify-postgresql",
        action="store_true",
        help=(
            "config.settings.local로 실제 PostgreSQL 연결, "
            "Model/Migration parity, 미적용 Migration을 검증한다."
        ),
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    completion_evidence = None
    if arguments.completion_evidence is not None:
        try:
            completion_evidence = json.loads(
                arguments.completion_evidence.read_text(encoding="utf-8")
            )
            if not isinstance(completion_evidence, dict):
                raise ValueError("completion evidence must be an object")
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            print(
                json.dumps(
                    {
                        "status": "INVALID_COMPLETION_EVIDENCE",
                        "path": str(arguments.completion_evidence),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 1
    result = audit_snapshot(
        completion_evidence=completion_evidence,
        postgresql_verification=(
            verify_postgresql_runtime()
            if arguments.verify_postgresql
            else None
        ),
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["errors"]:
        return 1
    if (
        arguments.require_wbs_complete
        and result["wbs_completion_gaps"]
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
