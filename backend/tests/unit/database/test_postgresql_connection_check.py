"""T-016 PostgreSQL 읽기 전용 점검 도구를 검증한다."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[3]
REPOSITORY_ROOT = BACKEND_DIR.parent
TEST_CA_PATH = (
    BACKEND_DIR / "tests" / "fixtures" / "team_integration" / "test-ca.pem"
)
CHECK_SCRIPT = (
    REPOSITORY_ROOT
    / "scripts"
    / "database"
    / "check_postgresql_connection.py"
)
VALID_ENV = {
    "POSTGRES_DB": "waterbridge",
    "POSTGRES_USER": "waterbridge",
    "POSTGRES_PASSWORD": "do-not-print-this",
    "POSTGRES_HOST": "database.internal",
    "POSTGRES_PORT": "5432",
}


def load_check_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "postgresql_connection_check",
        CHECK_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def check_module() -> ModuleType:
    return load_check_module()


class FakeCursor:
    def __init__(self, values: dict[str, Any]):
        self.values = values
        self.executed: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query: str) -> None:
        self.executed.append(query)

    def fetchone(self) -> tuple[Any]:
        return (self.values[self.executed[-1]],)


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self.fake_cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self) -> FakeCursor:
        return self.fake_cursor


def test_missing_environment_stops_before_connection(check_module: ModuleType):
    connect_called = False

    def fail_if_called(**_kwargs):
        nonlocal connect_called
        connect_called = True

    result, exit_code = check_module.run_check({}, fail_if_called)

    assert exit_code == 2
    assert result["status"] == "NOT_CONFIGURED"
    assert set(result["missing_keys"]) == set(check_module.REQUIRED_ENV_KEYS)
    assert connect_called is False


@pytest.mark.parametrize("port", ["not-a-port", "0", "65536"])
def test_invalid_port_stops_before_connection(
    check_module: ModuleType,
    port: str,
):
    result, exit_code = check_module.run_check(
        {**VALID_ENV, "POSTGRES_PORT": port},
        lambda **_kwargs: pytest.fail("connection must not be attempted"),
    )

    assert exit_code == 2
    assert result["status"] == "NOT_CONFIGURED"


def test_success_uses_read_only_option_and_read_only_queries(
    check_module: ModuleType,
):
    query_values = {
        "SELECT 1": 1,
        "SELECT current_database()": "waterbridge",
        "SELECT current_schema()": "public",
        "SHOW server_version": "17.5",
        "SHOW server_version_num": "170005",
        "SHOW TimeZone": "Asia/Seoul",
        "SHOW default_transaction_read_only": "on",
        (
            "SELECT COALESCE((SELECT ssl FROM pg_stat_ssl "
            "WHERE pid = pg_backend_pid()), false)"
        ): True,
    }
    cursor = FakeCursor(query_values)
    received_options: dict[str, Any] = {}

    def connect(**kwargs):
        received_options.update(kwargs)
        return FakeConnection(cursor)

    result, exit_code = check_module.run_check(VALID_ENV, connect)

    assert exit_code == 0
    assert result == {
        "status": "CONNECTED",
        "vendor": "PostgreSQL",
        "select_one": 1,
        "current_database": "waterbridge",
        "current_schema": "public",
        "server_version": "17.5",
        "server_version_num": "170005",
        "database_timezone": "Asia/Seoul",
        "default_transaction_read_only": "on",
        "connection_ssl": True,
    }
    assert received_options["options"] == (
        "-c default_transaction_read_only=on"
    )
    assert cursor.executed == [
        query
        for _key, query in check_module.READ_ONLY_QUERIES
    ]
    assert all(
        query.startswith(("SELECT", "SHOW"))
        for query in cursor.executed
    )


def test_connection_failure_does_not_expose_secret(
    check_module: ModuleType,
):
    def connect(**_kwargs):
        raise RuntimeError(
            "do-not-print-this database.internal "
            "postgresql://waterbridge:do-not-print-this@database.internal"
        )

    result, exit_code = check_module.run_check(VALID_ENV, connect)
    serialized = json.dumps(result, ensure_ascii=False)

    assert exit_code == 1
    assert result["status"] == "CONNECTION_FAILED"
    assert "do-not-print-this" not in serialized
    assert "database.internal" not in serialized
    assert "postgresql://" not in serialized


def test_verify_full_passes_ca_without_exposing_path(
    check_module: ModuleType,
):
    received_options: dict[str, Any] = {}

    def connect(**kwargs):
        received_options.update(kwargs)
        raise RuntimeError(str(TEST_CA_PATH))

    result, exit_code = check_module.run_check(
        {
            **VALID_ENV,
            "POSTGRES_SSLMODE": "verify-full",
            "POSTGRES_SSLROOTCERT": str(TEST_CA_PATH),
        },
        connect,
    )

    assert exit_code == 1
    assert received_options["sslmode"] == "verify-full"
    assert received_options["sslrootcert"] == str(TEST_CA_PATH.resolve())
    assert str(TEST_CA_PATH) not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize(
    "extra_env",
    [
        {"POSTGRES_SSLMODE": "prefer"},
        {"POSTGRES_SSLMODE": "verify-full"},
        {
            "POSTGRES_SSLMODE": "verify-full",
            "POSTGRES_SSLROOTCERT": "must-not-appear.pem",
        },
    ],
)
def test_invalid_tls_stops_before_connection(
    check_module: ModuleType,
    extra_env: dict[str, str],
):
    result, exit_code = check_module.run_check(
        {**VALID_ENV, **extra_env},
        lambda **_kwargs: pytest.fail("connection must not be attempted"),
    )
    serialized = json.dumps(result, ensure_ascii=False)

    assert exit_code == 2
    assert result["status"] == "NOT_CONFIGURED"
    assert "must-not-appear" not in serialized
    assert "database.internal" not in serialized
