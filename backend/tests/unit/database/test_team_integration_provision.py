"""TEAM_INTEGRATION Provisioning의 비변경 기본값과 보안 Guard 검증."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_DIR.parent
SCRIPT_PATH = (
    REPOSITORY_ROOT
    / "scripts"
    / "database"
    / "provision_team_integration.py"
)
TEST_CA_PATH = (
    BACKEND_DIR / "tests" / "fixtures" / "team_integration" / "test-ca.pem"
)
VALID_ENV = {
    "POSTGRES_USER": "admin",
    "POSTGRES_PASSWORD": "must-not-appear-admin",
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "5432",
    "TEAM_INTEGRATION_MIGRATOR_PASSWORD": "unique-migrator",
    "TEAM_INTEGRATION_RUNTIME_PASSWORD": "unique-runtime",
    "TEAM_INTEGRATION_READONLY_PASSWORD": "unique-readonly",
    "TEAM_INTEGRATION_AI_PASSWORD": "unique-ai",
}


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "team_integration_provision",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys_modules_name = spec.name
    import sys

    sys.modules[sys_modules_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(sys_modules_name, None)
    return module


@pytest.fixture
def provision_module() -> ModuleType:
    return load_module()


def test_default_plan_never_connects_or_mutates(provision_module: ModuleType):
    result, exit_code = provision_module.run(
        VALID_ENV,
        apply=False,
        confirmed_database=None,
        connect=lambda **_kwargs: pytest.fail("plan must not connect"),
    )

    assert exit_code == 0
    assert result["status"] == "PLAN_READY"
    assert result["mutates_database"] is False
    assert result["target_database"] == "waterbridge_team_integration"


def test_apply_requires_exact_database_confirmation(
    provision_module: ModuleType,
):
    result, exit_code = provision_module.run(
        VALID_ENV,
        apply=True,
        confirmed_database="waterbridge",
        connect=lambda **_kwargs: pytest.fail("invalid apply must not connect"),
    )

    assert exit_code == 2
    assert result["reason"] == "database_confirmation_required"


def test_password_rotation_requires_apply(provision_module: ModuleType):
    result, exit_code = provision_module.run(
        VALID_ENV,
        apply=False,
        confirmed_database=None,
        rotate_passwords=True,
        connect=lambda **_kwargs: pytest.fail("invalid plan must not connect"),
    )

    assert exit_code == 2
    assert result["reason"] == "password_rotation_requires_apply"


def test_apply_rejects_missing_or_placeholder_role_passwords(
    provision_module: ModuleType,
):
    invalid_env = {
        **VALID_ENV,
        "TEAM_INTEGRATION_RUNTIME_PASSWORD": "replace-with-password",
    }
    result, exit_code = provision_module.run(
        invalid_env,
        apply=True,
        confirmed_database=provision_module.TARGET_DATABASE,
        connect=lambda **_kwargs: pytest.fail("invalid apply must not connect"),
    )

    assert exit_code == 2
    assert result["reason"] == "missing_role_passwords"
    assert "TEAM_INTEGRATION_RUNTIME_PASSWORD" in result["missing_keys"]


@pytest.mark.parametrize(
    "invalid_env, expected_reason",
    [
        (
            {
                **VALID_ENV,
                "TEAM_INTEGRATION_RUNTIME_PASSWORD": "unique-migrator",
            },
            "duplicate_role_passwords",
        ),
        (
            {
                **VALID_ENV,
                "TEAM_INTEGRATION_RUNTIME_PASSWORD": (
                    VALID_ENV["POSTGRES_PASSWORD"]
                ),
            },
            "role_password_matches_admin",
        ),
    ],
)
def test_apply_rejects_shared_passwords(
    provision_module: ModuleType,
    invalid_env: dict[str, str],
    expected_reason: str,
):
    result, exit_code = provision_module.run(
        invalid_env,
        apply=True,
        confirmed_database=provision_module.TARGET_DATABASE,
        connect=lambda **_kwargs: pytest.fail("invalid apply must not connect"),
    )

    assert exit_code == 2
    assert result["reason"] == expected_reason


def test_existing_role_with_membership_is_blocked(
    provision_module: ModuleType,
):
    existing_role_row = (
        True,
        False,
        False,
        False,
        False,
        False,
        provision_module.OBJECT_MARKER,
        1,
    )

    with pytest.raises(provision_module.ProvisioningError) as exc_info:
        provision_module._assert_existing_role_policy(existing_role_row)

    assert exc_info.value.reason == "existing_role_policy_mismatch"


def test_existing_database_with_wrong_marker_is_blocked(
    provision_module: ModuleType,
):
    with pytest.raises(provision_module.ProvisioningError) as exc_info:
        provision_module._assert_existing_database_policy(
            ("admin", "foreign-marker"),
            "admin",
        )

    assert exc_info.value.reason == "existing_database_policy_mismatch"


def test_remote_plan_requires_verify_full(provision_module: ModuleType):
    result, exit_code = provision_module.run(
        {**VALID_ENV, "POSTGRES_HOST": "database.internal"},
        apply=False,
        confirmed_database=None,
        connect=lambda **_kwargs: pytest.fail("invalid plan must not connect"),
    )

    assert exit_code == 2
    assert result["reason"] == "remote_verify_full_required"


def test_remote_verify_full_plan_is_secret_free(
    provision_module: ModuleType,
):
    result, exit_code = provision_module.run(
        {
            **VALID_ENV,
            "POSTGRES_HOST": "database.internal",
            "POSTGRES_SSLMODE": "verify-full",
            "POSTGRES_SSLROOTCERT": str(TEST_CA_PATH),
        },
        apply=False,
        confirmed_database=None,
        connect=lambda **_kwargs: pytest.fail("plan must not connect"),
    )
    serialized = json.dumps(result, ensure_ascii=False)

    assert exit_code == 0
    assert result["remote"] is True
    assert "database.internal" not in serialized
    assert "must-not-appear" not in serialized
    assert str(TEST_CA_PATH) not in serialized


def test_apply_failure_redacts_connection_values(
    provision_module: ModuleType,
):
    def connect(**_kwargs):
        raise RuntimeError(
            "database.internal must-not-appear-admin unique-runtime"
        )

    result, exit_code = provision_module.run(
        VALID_ENV,
        apply=True,
        confirmed_database=provision_module.TARGET_DATABASE,
        connect=connect,
    )
    serialized = json.dumps(result, ensure_ascii=False)

    assert exit_code == 1
    assert result["status"] == "FAILED"
    assert "must-not-appear" not in serialized
    assert "unique-runtime" not in serialized
    assert "database.internal" not in serialized


def test_source_has_no_destructive_or_secret_cli_path():
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "DROP DATABASE" not in source
    assert "DROP ROLE" not in source
    assert "--password" not in source
    assert "--dsn" not in source
    assert "PASSWORD %s" not in source
    assert "IS %s" not in source
    assert "sql.Identifier" in source
    assert "sql.Literal" in source
    assert "pg_try_advisory_lock" in source
    assert "pg_available_extensions" in source
    assert "pg_auth_members" in source
    assert "REVOKE ALL PRIVILEGES ON ALL TABLES" in source
    assert "REVOKE ALL PRIVILEGES ON DATABASE" in source
    assert 'cursor.execute("BEGIN")' in source
    assert 'cursor.execute("ROLLBACK")' in source


def test_ai_readonly_grant_is_scoped_to_the_verified_rag_view(
    provision_module: ModuleType,
):
    class RecordingCursor:
        def __init__(self):
            self.statements: list[tuple[str, object]] = []
            self.rows = iter([(True,), (False,)])

        def execute(self, statement, parameters=None):
            rendered = (
                statement.as_string()
                if hasattr(statement, "as_string")
                else statement
            )
            self.statements.append((rendered, parameters))

        def fetchone(self):
            return next(self.rows)

    assert provision_module.AI_READONLY_VIEW == "backend_ai_rag_chunks_v1"
    assert (
        provision_module.AI_READONLY_VIEW_REGCLASS
        == "public.backend_ai_rag_chunks_v1"
    )

    cursor = RecordingCursor()
    provision_module._grant_roles(cursor)
    statements = cursor.statements
    ai_role = '"waterbridge_ti_ai_readonly"'

    assert (
        "SELECT to_regclass(%s) IS NOT NULL",
        ("public.backend_ai_rag_chunks_v1",),
    ) in statements
    assert [
        statement
        for statement, _parameters in statements
        if statement.startswith("GRANT SELECT") and ai_role in statement
    ] == [
        'GRANT SELECT ON TABLE "public"."backend_ai_rag_chunks_v1" '
        'TO "waterbridge_ti_ai_readonly"'
    ]
    assert any(
        "REVOKE ALL PRIVILEGES ON ALL TABLES" in statement
        and ai_role in statement
        for statement, _parameters in statements
    )
    assert any(
        "REVOKE ALL PRIVILEGES ON ALL SEQUENCES" in statement
        and ai_role in statement
        for statement, _parameters in statements
    )
