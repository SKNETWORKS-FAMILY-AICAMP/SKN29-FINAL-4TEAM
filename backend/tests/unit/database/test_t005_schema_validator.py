"""T-005 Snapshot·결정 목록·구현 준비도 회귀 검증."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml


BACKEND_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_DIR.parent
ARTIFACT_DIR = REPOSITORY_ROOT / "docs" / "database" / "t-005"
VALIDATOR_PATH = (
    REPOSITORY_ROOT / "scripts" / "database" / "validate_t005_schema.py"
)
READINESS_PATH = (
    REPOSITORY_ROOT
    / "scripts"
    / "database"
    / "audit_t005_implementation_readiness.py"
)
EXPECTED_BLOCKER_IDS = {
    "T005_PRIMARY_KEY_POLICY",
    "T005_USAGE_GUIDANCE_PHYSICAL_MAPPING",
    "T005_USAGE_GUIDANCE_CODESET",
    "T005_VISIT_STORAGE_MAPPING",
    "T005_VISIT_STATUS_CODESET",
    "T005_ENUM_SEED_POLICY",
    "T005_STATUS_HISTORY_IDEMPOTENCY_SCOPE",
}


def load_script(path: Path, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def validator_module() -> ModuleType:
    return load_script(VALIDATOR_PATH, "t005_schema_validator")


@pytest.fixture
def baseline_data() -> dict[str, dict[str, Any]]:
    return {
        "manifest": json.loads(
            (ARTIFACT_DIR / "manifest.json").read_text(encoding="utf-8")
        ),
        "schema": json.loads(
            (ARTIFACT_DIR / "watercare_schema_v3.json").read_text(
                encoding="utf-8"
            )
        ),
        "logical_contract": json.loads(
            (
                ARTIFACT_DIR / "t005_logical_contract_v0.3.json"
            ).read_text(encoding="utf-8")
        ),
        "decision_register": json.loads(
            (
                ARTIFACT_DIR / "t005_decision_register_v0.3.json"
            ).read_text(encoding="utf-8")
        ),
        "physical_contract": json.loads(
            (
                ARTIFACT_DIR / "t005_physical_contract_v1.2.json"
            ).read_text(encoding="utf-8")
        ),
    }


def test_current_snapshot_keeps_seven_legacy_gaps_but_owner_baseline_resolves_them(
    validator_module: ModuleType,
):
    result = validator_module.audit_snapshot()

    assert result["errors"] == []
    assert result["decision_alignment"]["matches"] is True
    assert result["decision_register"]["valid"] is True
    assert result["decision_register"]["accepted_count"] == 7
    assert (
        result["owner_baseline"]["status"]
        == "OWNER_BASELINE_CONFIRMED"
    )
    assert result["owner_baseline"]["confirmation_status"] == "CONFIRMED"
    assert result["owner_baseline"]["completion_review_status"] == "PENDING"
    assert result["blocker_alignment"]["matches"] is True
    assert {
        gap["id"]
        for gap in result["legacy_snapshot_gaps"]
    } == EXPECTED_BLOCKER_IDS
    assert result["gaps"] == []
    assert result["completion_gates"]["owner_baseline_confirmed"] is True
    assert result["completion_gates"]["non_author_review_confirmed"] is False
    assert (
        result["completion_gates"][
            "three_layer_identifier_runtime_complete"
        ]
        is False
    )
    assert (
        "three_layer_identifier_runtime_complete"
        in result["wbs_completion_gaps"]
    )
    assert "postgresql_migration_verified" in result[
        "wbs_completion_gaps"
    ]


def test_validator_cli_separates_owner_baseline_and_wbs_completion():
    basic = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    strict = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            "--require-wbs-complete",
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert basic.returncode == 0
    assert strict.returncode == 2
    assert json.loads(basic.stdout)["structure_valid"] is True
    assert json.loads(strict.stdout)["gaps"] == []
    assert json.loads(strict.stdout)["wbs_completion_gaps"]
    assert (
        json.loads(strict.stdout)["owner_baseline"]["status"]
        == "OWNER_BASELINE_CONFIRMED"
    )


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_manifest_decision_mutation_is_detected(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
    mutation: str,
):
    manifest = baseline_data["manifest"]
    if mutation == "missing":
        manifest["blocking_decisions"].pop()
    else:
        manifest["blocking_decisions"].append(
            manifest["blocking_decisions"][0]
        )

    result = validator_module.audit_snapshot(
        manifest=manifest,
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        verify_artifact_hashes=False,
    )

    assert result["blocker_alignment"]["matches"] is False
    assert any(
        error["id"] == "T005_BLOCKER_MANIFEST_MISMATCH"
        for error in result["errors"]
    )


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_logical_contract_decision_mutation_is_detected(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
    mutation: str,
):
    contract = baseline_data["logical_contract"]
    if mutation == "missing":
        contract["decisions_required"].pop()
    else:
        contract["decisions_required"].append(
            contract["decisions_required"][0]
        )

    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=contract,
        decision_register=baseline_data["decision_register"],
        verify_artifact_hashes=False,
    )

    assert result["decision_alignment"]["matches"] is False
    assert result["logical_contract_checks"]["decision_ids_aligned"] is False


def test_snapshot_hash_mutation_is_detected(
    validator_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        validator_module,
        "sha256",
        lambda _path: "0" * 64,
    )

    result = validator_module.audit_snapshot()

    assert any(
        error["id"] == "T005_ARTIFACT_HASH_MISMATCH"
        for error in result["errors"]
    )


def test_missing_fk_target_is_detected(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
):
    schema = baseline_data["schema"]
    physical_fk = next(
        column
        for table in schema["tables"].values()
        for column in table["columns"]
        if column.get("referenceKind") == "physical_fk"
    )
    physical_fk["reference"] = "missing_table.missing_column"

    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=schema,
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        verify_artifact_hashes=False,
    )

    assert any(
        error["id"] == "T005_MISSING_FK_TARGET"
        for error in result["errors"]
    )


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_decision_register_id_mutation_is_detected(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
    mutation: str,
):
    register = baseline_data["decision_register"]
    if mutation == "missing":
        register["decisions"].pop()
    else:
        register["decisions"].append(register["decisions"][0])

    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=register,
        verify_artifact_hashes=False,
    )

    assert result["decision_register"]["valid"] is False
    assert any(
        error["id"] == "T005_DECISION_REGISTER_INVALID"
        for error in result["errors"]
    )


def test_accepted_decision_requires_traceability_fields(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
):
    register = baseline_data["decision_register"]
    for field in (
        "selected_option",
        "decided_by",
        "decided_at",
        "rationale",
        "effective_from",
    ):
        register["decisions"][0][field] = None

    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=register,
        verify_artifact_hashes=False,
    )

    assert result["decision_register"]["valid"] is False
    invalid = result["decision_register"]["invalid_decisions"][0]
    assert invalid["id"] == "T005_PRIMARY_KEY_POLICY"
    assert set(invalid["missing_fields"]) == {
        "selected_option",
        "decided_by",
        "decided_at",
        "rationale",
        "effective_from",
    }


@pytest.mark.parametrize("status", ["REJECTED", "DEFERRED"])
def test_nonpending_decision_requires_audit_trace(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
    status: str,
):
    register = baseline_data["decision_register"]
    register["decisions"][0]["status"] = status
    register["decisions"][0]["decided_by"] = None
    register["decisions"][0]["decided_at"] = None
    register["decisions"][0]["rationale"] = None

    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=register,
        verify_artifact_hashes=False,
    )

    assert result["decision_register"]["valid"] is False
    invalid = result["decision_register"]["invalid_decisions"][0]
    assert invalid["id"] == "T005_PRIMARY_KEY_POLICY"
    assert set(invalid["missing_fields"]) == {
        "decided_by",
        "decided_at",
        "rationale",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("version", "unexpected"),
        ("status", "GARBAGE"),
        ("status", "PENDING"),
    ],
)
def test_decision_register_header_mutation_is_detected(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
    field: str,
    value: str,
):
    register = baseline_data["decision_register"]
    register[field] = value

    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=register,
        verify_artifact_hashes=False,
    )

    assert result["decision_register"]["valid"] is False
    assert any(
        error["id"] == "T005_DECISION_REGISTER_INVALID"
        for error in result["errors"]
    )


def test_implementation_readiness_stays_separate_from_design_completion():
    readiness_module = load_script(
        READINESS_PATH,
        "t005_implementation_readiness",
    )

    result = readiness_module.audit_readiness()

    assert result["status"] == "NOT_READY"
    assert result["evidence"]["app_skeleton_count"] == 12
    assert result["evidence"]["postgres_env_complete"] is False
    assert result["evidence"]["docker_compose_configured"] is True
    assert "DOCKER_COMPOSE_NOT_CONFIGURED" not in result["blockers"]
    assert "POSTGRES_ENV_INCOMPLETE" in result["blockers"]


def test_owner_baseline_rejects_code_contract_drift(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
):
    usage_codes = {
        "codes": [
            "NORMAL",
            "PARTIAL_STOP",
            "TOTAL_STOP",
        ],
        "legacy_import_aliases": {"USE_ALLOWED": "NORMAL"},
    }

    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        usage_code_contract=usage_codes,
        verify_artifact_hashes=False,
    )

    assert result["owner_baseline"]["valid"] is False
    assert result["gaps"]
    assert any(
        error["id"] == "T005_OWNER_BASELINE_INVALID"
        for error in result["errors"]
    )


def test_historical_contract_generations_remain_frozen():
    logical_v02 = json.loads(
        (
            ARTIFACT_DIR / "t005_logical_contract_v0.2.json"
        ).read_text(encoding="utf-8")
    )
    decision_v02 = json.loads(
        (
            ARTIFACT_DIR / "t005_decision_register_v0.2.json"
        ).read_text(encoding="utf-8")
    )
    physical_v11 = json.loads(
        (
            ARTIFACT_DIR / "t005_physical_contract_v1.1.json"
        ).read_text(encoding="utf-8")
    )

    assert logical_v02["status"] == "HISTORICAL_SNAPSHOT"
    assert len(logical_v02["decisions_required"]) == 6
    assert len(decision_v02["decisions"]) == 6
    assert "T005_STATUS_HISTORY_IDEMPOTENCY_SCOPE" not in {
        decision["id"] for decision in logical_v02["decisions_required"]
    }
    assert "support_inquiry_status_history" not in (
        physical_v11["physical_overrides"]
    )


def test_manifest_points_to_active_contract_generation(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
):
    assert validator_module.audit_snapshot()[
        "active_contract_alignment"
    ]["matches"] is True

    manifest = baseline_data["manifest"]
    manifest["active_physical_contract"] = (
        "t005_physical_contract_v1.1.json"
    )
    result = validator_module.audit_snapshot(
        manifest=manifest,
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        physical_contract=baseline_data["physical_contract"],
        verify_artifact_hashes=False,
    )

    assert result["active_contract_alignment"]["matches"] is False
    assert any(
        error["id"] == "T005_ACTIVE_CONTRACT_POINTER_MISMATCH"
        for error in result["errors"]
    )


def test_status_history_idempotency_uses_request_ledger_and_trace_indexes(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
):
    physical_contract = baseline_data["physical_contract"]
    history = physical_contract["physical_overrides"][
        "support_inquiry_status_history"
    ]

    assert history["idempotency_key"]["global_unique"] is False
    assert history["idempotency_key"]["request_scope_owner"] == (
        "workflow_idempotency_record"
    )
    assert history["idempotency_key"]["request_scope_fields"] == [
        "actor",
        "operation_id",
        "idempotency_key",
    ]
    assert history["idempotency_key"]["history_unique"] is False
    assert history["idempotency_key"]["trace_only"] is True
    assert "postgresql_partial_unique_constraints" not in history
    assert {
        index["target_type_code"]
        for index in history["postgresql_partial_idempotency_indexes"]
    } == {"QUESTIONNAIRE", "INQUIRY", "CONSULTATION", "VISIT"}
    assert all(
        index["unique"] is False
        for index in history["postgresql_partial_idempotency_indexes"]
    )

    history["postgresql_partial_idempotency_indexes"][0]["unique"] = True
    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        physical_contract=physical_contract,
        verify_artifact_hashes=False,
    )

    assert result["owner_baseline"]["valid"] is False
    assert (
        result["owner_baseline"]["checks"][
            "status_history_idempotency_scope"
        ]
        is False
    )

    physical_contract = copy.deepcopy(baseline_data["physical_contract"])
    physical_contract["physical_overrides"][
        "support_inquiry_status_history"
    ]["idempotency_key"]["history_unique"] = True
    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        physical_contract=physical_contract,
        verify_artifact_hashes=False,
    )
    assert result["owner_baseline"]["checks"][
        "status_history_idempotency_scope"
    ] is False


def test_status_history_check_constraint_expression_drift_is_rejected(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
):
    physical_contract = baseline_data["physical_contract"]
    checks = physical_contract["physical_overrides"][
        "support_inquiry_status_history"
    ]["target_integrity"]["check_constraints"]
    checks[0]["expression"] = "num_nonnulls(inquiry_id, visit_id) <= 1"

    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        physical_contract=physical_contract,
        verify_artifact_hashes=False,
    )

    assert result["owner_baseline"]["checks"][
        "status_history_target_integrity"
    ] is False


def test_status_history_state_version_constraint_must_be_unique(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
):
    physical_contract = baseline_data["physical_contract"]
    constraints = physical_contract["physical_overrides"][
        "support_inquiry_status_history"
    ]["postgresql_partial_version_constraints"]
    constraints[0]["unique"] = False

    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        physical_contract=physical_contract,
        verify_artifact_hashes=False,
    )

    assert result["owner_baseline"]["checks"][
        "status_history_state_version_scope"
    ] is False


def test_request_ledger_runtime_constraint_matches_contract_scope():
    from apps.workflow.models import IdempotencyRecord

    constraint = next(
        constraint
        for constraint in IdempotencyRecord._meta.constraints
        if constraint.name == "ux_workflow_idempotency_scope"
    )

    assert tuple(constraint.fields) == (
        "actor",
        "operation_id",
        "idempotency_key",
    )


def test_owner_baseline_accepts_transitional_and_complete_gate_states(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
):
    transitional = validator_module.audit_snapshot(
        manifest=copy.deepcopy(baseline_data["manifest"]),
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        physical_contract=copy.deepcopy(baseline_data["physical_contract"]),
        verify_artifact_hashes=False,
    )
    assert transitional["owner_baseline"]["checks"][
        "implementation_gate_valid"
    ] is True

    complete_manifest = copy.deepcopy(baseline_data["manifest"])
    complete_manifest["implementation_gate"].update(
        {
            "status": "COMPLETE",
            "completion_claim_allowed": True,
        }
    )
    complete_contract = copy.deepcopy(baseline_data["physical_contract"])
    complete_contract["identifier_policy"]["compatibility_bridge"][
        "status"
    ] = "COMPLETE"
    complete_contract["implementation_gate"] = {
        "status": "COMPLETE",
        "completion_claim_allowed": True,
        "incomplete_items": [],
    }
    complete = validator_module.audit_snapshot(
        manifest=complete_manifest,
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        physical_contract=complete_contract,
        verify_artifact_hashes=False,
    )
    assert complete["owner_baseline"]["checks"][
        "implementation_gate_valid"
    ] is True
    assert complete["completion_gates"][
        "three_layer_identifier_runtime_complete"
    ] is True

    hybrid_contract = copy.deepcopy(complete_contract)
    hybrid_contract["identifier_policy"]["compatibility_bridge"][
        "status"
    ] = "TRANSITIONAL"
    hybrid = validator_module.audit_snapshot(
        manifest=complete_manifest,
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        physical_contract=hybrid_contract,
        verify_artifact_hashes=False,
    )
    assert hybrid["owner_baseline"]["checks"][
        "implementation_gate_valid"
    ] is False


def test_identifier_and_role_contract_parity_rejects_counselor_alias(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
):
    physical_contract = baseline_data["physical_contract"]
    physical_contract["physical_overrides"]["accounts_user"]["role_code"][
        "codes"
    ][1] = "COUNSELOR"

    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        physical_contract=physical_contract,
        verify_artifact_hashes=False,
    )

    assert result["owner_baseline"]["checks"][
        "user_role_code_parity"
    ] is False


def test_physical_identifier_parity_rejects_public_id_type_drift(
    validator_module: ModuleType,
    baseline_data: dict[str, dict[str, Any]],
):
    physical_contract = baseline_data["physical_contract"]
    physical_contract["physical_overrides"]["support_inquiry"][
        "public_id"
    ]["type"] = "varchar(48)"

    result = validator_module.audit_snapshot(
        manifest=baseline_data["manifest"],
        schema=baseline_data["schema"],
        logical_contract=baseline_data["logical_contract"],
        decision_register=baseline_data["decision_register"],
        physical_contract=physical_contract,
        verify_artifact_hashes=False,
    )

    assert result["owner_baseline"]["checks"][
        "physical_identifier_parity"
    ] is False


def test_api_schemas_use_owner_baseline_field_names_and_codes():
    inquiry = yaml.safe_load(
        (
            REPOSITORY_ROOT
            / "contracts"
            / "api"
            / "components"
            / "schemas"
            / "inquiry"
            / "InquiryDetail.yaml"
        ).read_text(encoding="utf-8")
    )
    visit = yaml.safe_load(
        (
            REPOSITORY_ROOT
            / "contracts"
            / "api"
            / "components"
            / "schemas"
            / "visit"
            / "VisitSchedule.yaml"
        ).read_text(encoding="utf-8")
    )

    assert {
        "usage_guidance_status",
        "usage_guidance_message",
        "restricted_functions",
        "evidence",
        "next_action",
        "requires_consultation",
    } <= set(inquiry["properties"])
    assert {
        value
        for value in inquiry["properties"]["usage_guidance_status"]["enum"]
        if value is not None
    } == validator_codes(
        REPOSITORY_ROOT
        / "contracts"
        / "codes"
        / "usage-guidance-statuses.yaml"
    )
    assert {
        "preferred_date",
        "confirmed_date",
        "schedule_status",
        "synthetic_technician_id",
    } == set(visit["properties"])
    assert set(
        visit["properties"]["schedule_status"]["enum"]
    ) == validator_codes(
        REPOSITORY_ROOT
        / "contracts"
        / "codes"
        / "visit-statuses.yaml"
    )


def validator_codes(path: Path) -> set[str]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return set(document["codes"])


def test_t005_completion_evidence_cannot_self_report_runtime_gates(
    validator_module: ModuleType,
):
    evidence = {
        "non_author_review": {
            "status": "CONFIRMED",
            "reviewer": "윤승혁(PM)",
            "recorded_at": "2026-07-27T09:00:00+09:00",
        },
        "django_model_migration_parity": {
            "status": "VERIFIED",
            "command": "python manage.py makemigrations --check --dry-run",
            "verified_by": "김은진",
            "recorded_at": "2026-07-27T09:05:00+09:00",
        },
        "postgresql_migration": {
            "status": "VERIFIED",
            "database_vendor": "PostgreSQL",
            "command": "python manage.py migrate --check",
            "verified_by": "김은진",
            "recorded_at": "2026-07-27T09:10:00+09:00",
        },
        "seed_idempotency": {
            "status": "VERIFIED",
            "database_vendor": "PostgreSQL",
            "run_count": 2,
            "command": "python manage.py seed_demo_accounts",
            "verified_by": "김은진",
            "recorded_at": "2026-07-27T09:15:00+09:00",
        },
        "external_review": {
            "status": "CONFIRMED",
            "reviewer": "김은진",
            "recorded_at": "2026-07-27T09:20:00+09:00",
        },
    }

    gates = validator_module.completion_evidence_gates(evidence)

    assert gates["non_author_review_confirmed"] is True
    assert gates["seed_idempotency_verified_on_postgresql"] is True
    assert gates["external_review_verified"] is True
    assert gates["django_model_migration_parity_verified"] is False
    assert gates["postgresql_migration_verified"] is False

    gates = validator_module.completion_evidence_gates(
        evidence,
        postgresql_verification={
            "settings_module": "config.settings.local",
            "database_vendor": "PostgreSQL",
            "connection_status": "CONNECTED",
            "makemigrations_status": "PASSED",
            "migration_status": "PASSED",
        },
    )

    assert all(gates.values())


def test_t005_runtime_verification_forces_local_settings_and_runs_all_checks(
    validator_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[list[str], Path, dict[str, str]]] = []

    def fake_run(command, *, cwd, environ):
        calls.append((command, cwd, environ))
        stdout = (
            json.dumps(
                {
                    "status": "CONNECTED",
                    "vendor": "PostgreSQL",
                }
            )
            if command[-1].endswith("check_postgresql_connection.py")
            else ""
        )
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr(
        validator_module,
        "_run_verification_command",
        fake_run,
    )

    result = validator_module.verify_postgresql_runtime()

    assert result == {
        "settings_module": "config.settings.local",
        "database_vendor": "PostgreSQL",
        "connection_status": "CONNECTED",
        "makemigrations_status": "PASSED",
        "migration_status": "PASSED",
    }
    assert len(calls) == 3
    assert calls[1][0][-4:] == [
        "makemigrations",
        "--check",
        "--dry-run",
        "--settings=config.settings.local",
    ]
    assert calls[2][0][-4:] == [
        "migrate",
        "--check",
        "--noinput",
        "--settings=config.settings.local",
    ]
    assert all(
        environ["DJANGO_SETTINGS_MODULE"] == "config.settings.local"
        for _, _, environ in calls
    )


def test_t005_parity_runs_when_postgresql_connection_is_unavailable(
    validator_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[list[str]] = []

    def fake_run(command, *, cwd, environ):
        del cwd, environ
        calls.append(command)
        if command[-1].endswith("check_postgresql_connection.py"):
            return subprocess.CompletedProcess(
                command,
                2,
                json.dumps({"status": "NOT_CONFIGURED"}),
                "",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        validator_module,
        "_run_verification_command",
        fake_run,
    )

    result = validator_module.verify_postgresql_runtime()

    assert len(calls) == 2
    assert result["connection_status"] == "NOT_CONFIGURED"
    assert result["makemigrations_status"] == "PASSED"
    assert result["migration_status"] == "NOT_RUN"


def test_t005_malformed_completion_evidence_is_safe(
    validator_module: ModuleType,
):
    gates = validator_module.completion_evidence_gates(
        ["not", "an", "object"],
        postgresql_verification={"connection_status": ["bad"]},
    )

    assert not any(gates.values())


def test_t005_owner_cannot_self_confirm_non_author_review(
    validator_module: ModuleType,
):
    gates = validator_module.completion_evidence_gates(
        {
            "non_author_review": {
                "status": "CONFIRMED",
                "reviewer": "최지용",
                "recorded_at": "2026-07-27T09:00:00+09:00",
            },
        }
    )

    assert gates["non_author_review_confirmed"] is False


def test_t005_legacy_completion_review_aliases_remain_supported(
    validator_module: ModuleType,
):
    gates = validator_module.completion_evidence_gates(
        {
            "team_review": {
                "status": "APPROVED",
                "reviewer": "김은진",
                "recorded_at": "2026-07-27T09:00:00+09:00",
            },
        }
    )

    assert gates["non_author_review_confirmed"] is True


def test_t005_completion_example_is_safe_and_not_confirmed(
    validator_module: ModuleType,
):
    example = json.loads(
        (
            REPOSITORY_ROOT
            / "docs"
            / "handoffs"
            / "t005_completion_evidence.example.json"
        ).read_text(encoding="utf-8")
    )

    gates = validator_module.completion_evidence_gates(example)

    assert not any(gates.values())
