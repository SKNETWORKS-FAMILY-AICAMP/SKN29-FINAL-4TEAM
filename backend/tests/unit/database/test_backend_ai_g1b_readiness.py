"""Backend-AI G1-B 읽기 전용 감사의 판정·비밀 보호 검증."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_DIR.parent
SCRIPT_PATH = (
    REPOSITORY_ROOT
    / "scripts"
    / "database"
    / "audit_backend_ai_g1b_readiness.py"
)
VALID_ENV = {
    "POSTGRES_DB": "waterbridge_team_integration",
    "POSTGRES_USER": "audit-user-must-not-appear",
    "POSTGRES_PASSWORD": "audit-password-must-not-appear",
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "5432",
}


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "backend_ai_g1b_readiness",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


@pytest.fixture
def audit_module() -> ModuleType:
    return load_module()


def ready_snapshot(module: ModuleType) -> dict[str, object]:
    return {
        "database_name": module.TEAM_INTEGRATION_DATABASE,
        "server_version": "16.14",
        "migrations_table_exists": True,
        "applied_migrations": list(module.REQUIRED_MIGRATIONS),
        "crosswalk_table_exists": True,
        "active_verified_count": 7,
        "baseline_identity_count": 7,
        "view_exists": True,
        "view_columns": list(module.EXPECTED_VIEW_COLUMNS),
        "view_row_count": 7,
        "view_distinct_chunk_count": 7,
        "role_exists": True,
        "role_policy_safe": True,
        "default_transaction_read_only": True,
        "schema_create": False,
        "view_select": True,
        "view_dml": False,
        "base_table_select": False,
    }


def test_ready_requires_all_crosswalk_view_and_role_gates(
    audit_module: ModuleType,
):
    result = audit_module.evaluate_snapshot(
        ready_snapshot(audit_module),
        require_team_database=True,
    )

    assert result["status"] == "READY"
    assert result["blockers"] == []
    assert result["crosswalk"] == {
        "expected": 7,
        "active_verified": 7,
        "baseline_identity": 7,
    }
    assert result["ai_readonly_role"]["view_select"] is True
    assert result["ai_readonly_role"]["base_table_select"] is False


@pytest.mark.parametrize(
    "field, invalid_value, expected_blocker",
    [
        (
            "active_verified_count",
            6,
            "ACTIVE_VERIFIED_CROSSWALK_COUNT_NOT_7",
        ),
        (
            "baseline_identity_count",
            6,
            "BASELINE_EMBEDDING_IDENTITY_COUNT_NOT_7",
        ),
        ("view_row_count", 0, "BACKEND_AI_RAG_VIEW_ROW_COUNT_NOT_7"),
        ("view_select", False, "AI_READONLY_VIEW_SELECT_DENIED"),
        ("view_dml", True, "AI_READONLY_VIEW_DML_ALLOWED"),
        (
            "base_table_select",
            True,
            "AI_READONLY_BASE_TABLE_SELECT_ALLOWED",
        ),
        (
            "default_transaction_read_only",
            False,
            "AI_READONLY_DEFAULT_TRANSACTION_NOT_READ_ONLY",
        ),
    ],
)
def test_each_data_or_privilege_gap_blocks_ready(
    audit_module: ModuleType,
    field: str,
    invalid_value: object,
    expected_blocker: str,
):
    snapshot = ready_snapshot(audit_module)
    snapshot[field] = invalid_value

    result = audit_module.evaluate_snapshot(snapshot)

    assert result["status"] == "BLOCKED"
    assert expected_blocker in result["blockers"]


def test_view_column_order_and_team_database_are_explicit_gates(
    audit_module: ModuleType,
):
    snapshot = ready_snapshot(audit_module)
    snapshot["database_name"] = "author_local_database"
    snapshot["view_columns"] = list(reversed(snapshot["view_columns"]))

    result = audit_module.evaluate_snapshot(
        snapshot,
        require_team_database=True,
    )

    assert result["status"] == "BLOCKED"
    assert "TEAM_INTEGRATION_DATABASE_MISMATCH" in result["blockers"]
    assert "BACKEND_AI_RAG_VIEW_COLUMNS_MISMATCH" in result["blockers"]


def test_connection_is_forced_read_only_and_result_does_not_expose_secrets(
    audit_module: ModuleType,
):
    options = audit_module.load_connection_options(VALID_ENV)

    assert options["options"] == "-c default_transaction_read_only=on"

    def failing_connect(**_kwargs):
        raise RuntimeError(
            "127.0.0.1 audit-user-must-not-appear "
            "audit-password-must-not-appear"
        )

    result, exit_code = audit_module.run_audit(
        VALID_ENV,
        connect=failing_connect,
    )
    serialized = json.dumps(result, ensure_ascii=False)

    assert exit_code == 1
    assert result["status"] == "AUDIT_FAILED"
    assert "audit-user-must-not-appear" not in serialized
    assert "audit-password-must-not-appear" not in serialized
    assert "127.0.0.1" not in serialized


def test_require_ready_changes_exit_code_without_mutating_result(
    audit_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
):
    blocked = ready_snapshot(audit_module)
    blocked["view_row_count"] = 0
    blocked["view_distinct_chunk_count"] = 0
    monkeypatch.setattr(
        audit_module,
        "collect_snapshot",
        lambda _options, _connect: blocked,
    )

    report, report_exit = audit_module.run_audit(
        VALID_ENV,
        require_ready=False,
    )
    gate, gate_exit = audit_module.run_audit(
        VALID_ENV,
        require_ready=True,
    )

    assert report == gate
    assert report["status"] == "BLOCKED"
    assert report_exit == 0
    assert gate_exit == 1


def test_missing_environment_fails_before_connecting(
    audit_module: ModuleType,
):
    result, exit_code = audit_module.run_audit(
        {},
        connect=lambda **_kwargs: pytest.fail("must not connect"),
    )

    assert exit_code == 2
    assert result["status"] == "NOT_CONFIGURED"
    assert set(result["missing_keys"]) == set(audit_module.REQUIRED_ENV_KEYS)
