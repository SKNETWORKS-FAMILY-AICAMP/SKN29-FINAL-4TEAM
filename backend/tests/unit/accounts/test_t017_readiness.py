"""T-017 착수 게이트가 실행 증거와 미정 계약을 구분하는지 검증한다."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_DIR.parent
READINESS_SCRIPT = (
    BACKEND_DIR / "apps" / "accounts" / "readiness.py"
)


def load_readiness_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "t017_auth_readiness",
        READINESS_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_t017_owner_implementation_is_ready_for_team_review():
    result = load_readiness_module().audit_readiness(
        auth_test_exit_code=0,
    )

    assert result["status"] == "OWNER_IMPLEMENTATION_READY"
    assert result["evidence"]["runtime_implemented_file_count"] == len(
        load_readiness_module().AUTH_RUNTIME_FILES
    )
    assert result["evidence"]["accounts_app_registered"] is True
    assert result["evidence"]["account_model_class_count"] == 4
    assert result["evidence"]["account_migration_count"] == 5
    assert result["evidence"]["authentication_class_configured"] is True
    assert result["evidence"]["auth_routes_registered"] is True
    assert result["owner_blockers"] == []
    assert result["completion_blockers"] == [
        "TEAM_REVIEWED",
        "DJANGO_MODEL_MIGRATION_PARITY_VERIFIED",
        "POSTGRESQL_VERIFIED",
    ]


def test_readiness_requires_actual_auth_test_execution_evidence():
    result = load_readiness_module().audit_readiness()

    assert result["evidence"]["auth_test_execution_status"] == "NOT_RUN"
    assert result["status"] == "PARTIAL"
    assert result["owner_blockers"] == ["AUTH_TESTS_NOT_EXECUTED"]


def test_completion_evidence_cannot_self_report_postgresql_success():
    evidence = {
        "team_review": {
            "status": "APPROVED",
            "reviewer": "김은진",
            "recorded_at": "2026-07-27T09:00:00+09:00",
        },
        "postgresql": {
            "database_vendor": "PostgreSQL",
            "connection_status": "CONNECTED",
            "migration_status": "PASSED",
            "command": "python manage.py migrate --check",
            "verified_by": "김은진",
            "recorded_at": "2026-07-27T09:10:00+09:00",
        },
    }

    result = load_readiness_module().audit_readiness(
        auth_test_exit_code=0,
        completion_evidence=evidence,
    )

    assert result["status"] == "OWNER_IMPLEMENTATION_READY"
    assert result["completion_blockers"] == [
        "DJANGO_MODEL_MIGRATION_PARITY_VERIFIED",
        "POSTGRESQL_VERIFIED",
    ]

    result = load_readiness_module().audit_readiness(
        auth_test_exit_code=0,
        completion_evidence=evidence,
        postgresql_verification={
            "settings_module": "config.settings.local",
            "database_vendor": "PostgreSQL",
            "connection_status": "CONNECTED",
            "makemigrations_status": "PASSED",
            "migration_status": "PASSED",
        },
    )

    assert result["status"] == "READY"
    assert result["completion_blockers"] == []
    assert result["completion_evidence_supplied"] is True


def test_t017_runtime_verification_forces_local_settings_and_runs_all_checks(
    monkeypatch: pytest.MonkeyPatch,
):
    module = load_readiness_module()
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

    monkeypatch.setattr(module, "_run_verification_command", fake_run)

    result = module.verify_postgresql_runtime()

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


def test_t017_parity_runs_when_postgresql_connection_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    module = load_readiness_module()
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

    monkeypatch.setattr(module, "_run_verification_command", fake_run)

    result = module.verify_postgresql_runtime()

    assert len(calls) == 2
    assert result["connection_status"] == "NOT_CONFIGURED"
    assert result["makemigrations_status"] == "PASSED"
    assert result["migration_status"] == "NOT_RUN"


def test_t017_malformed_completion_evidence_is_safe():
    module = load_readiness_module()

    gates = module._completion_evidence_gates(
        ["not", "an", "object"],
        postgresql_verification={"connection_status": ["bad"]},
    )

    assert not any(gates.values())


def test_owner_cannot_self_approve_completion():
    result = load_readiness_module().audit_readiness(
        auth_test_exit_code=0,
        completion_evidence={
            "team_review": {
                "status": "APPROVED",
                "reviewer": "최지용",
                "recorded_at": "2026-07-27T09:00:00+09:00",
            },
        },
    )

    assert result["status"] == "OWNER_IMPLEMENTATION_READY"
    assert "TEAM_REVIEWED" in result["completion_blockers"]


def test_t017_completion_example_is_safe_and_not_approved():
    example = json.loads(
        (
            REPOSITORY_ROOT
            / "docs"
            / "handoffs"
            / "t017_completion_evidence.example.json"
        ).read_text(encoding="utf-8")
    )

    result = load_readiness_module().audit_readiness(
        auth_test_exit_code=0,
        completion_evidence=example,
    )

    assert result["status"] == "OWNER_IMPLEMENTATION_READY"
    assert result["completion_blockers"] == [
        "TEAM_REVIEWED",
        "DJANGO_MODEL_MIGRATION_PARITY_VERIFIED",
        "POSTGRESQL_VERIFIED",
    ]


def test_yaml_shape_helpers_reject_empty_contract_variants():
    module = load_readiness_module()

    assert module._yaml_list_values("codes: garbage", "codes") == set()
    assert module._yaml_list_values(
        "codes:\n  - CUSTOMER\n  - TECHNICIAN",
        "codes",
    ) == {"CUSTOMER", "TECHNICIAN"}
    assert (
        module._yaml_mapping_has_entries(
            "properties: {}",
            "properties",
        )
        is False
    )
    assert (
        module._yaml_mapping_has_entries(
            "title: Empty",
            "properties",
        )
        is False
    )
    assert module._yaml_mapping_has_entries(
        "properties: garbage",
        "properties",
    ) is False
    assert module._yaml_mapping_has_entries(
        "properties:\n  user_id:\n    type: string",
        "properties",
    ) is True
    assert module._yaml_nested_mapping_has_nonempty_values(
        "roles: {}",
        "roles",
    ) is False
    assert module._yaml_nested_mapping_has_nonempty_values(
        "roles:\n  CUSTOMER: []\n  TECHNICIAN: []",
        "roles",
    ) is False
    assert module._yaml_nested_mapping_has_nonempty_values(
        "roles:\n  CUSTOMER:\n    - READ_OWN",
        "roles",
    ) is True
    assert module._yaml_has_http_operation("{}") is False
    assert module._yaml_has_http_operation(
        "post:\n  summary: login",
    ) is False
    assert module._yaml_has_http_operation(
        "post:\n  responses:\n    '200':\n      description: ok",
    ) is True


def test_readiness_cli_requires_team_and_postgresql_gates():
    readiness_environment = os.environ.copy()
    readiness_environment["DJANGO_SETTINGS_MODULE"] = (
        "config.settings.test"
    )
    readiness_environment["DJANGO_DEMO_LOGIN_ENABLED"] = "false"
    readiness_environment["DJANGO_CORS_ALLOWED_ORIGINS"] = (
        "https://approved.example"
    )
    basic = subprocess.run(
        [sys.executable, str(READINESS_SCRIPT)],
        cwd=REPOSITORY_ROOT,
        env=readiness_environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    strict = subprocess.run(
        [sys.executable, str(READINESS_SCRIPT), "--require-ready"],
        cwd=REPOSITORY_ROOT,
        env=readiness_environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert basic.returncode == 0
    assert strict.returncode == 2
    assert (
        json.loads(basic.stdout)["status"]
        == "OWNER_IMPLEMENTATION_READY"
    )
    assert json.loads(strict.stdout)["completion_blockers"] == [
        "TEAM_REVIEWED",
        "DJANGO_MODEL_MIGRATION_PARITY_VERIFIED",
        "POSTGRESQL_VERIFIED",
    ]
