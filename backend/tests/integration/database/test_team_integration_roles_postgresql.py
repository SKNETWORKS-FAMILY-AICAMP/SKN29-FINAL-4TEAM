"""TEAM_INTEGRATION PostgreSQL의 실제 Role 권한 Matrix 검증."""

from __future__ import annotations

import os

import psycopg
import pytest

from config.env import build_postgres_connection_options


TARGET_DATABASE = "waterbridge_team_integration"
ROLE_PASSWORD_KEYS = {
    "waterbridge_ti_migrator": "TEAM_INTEGRATION_MIGRATOR_PASSWORD",
    "waterbridge_ti_runtime": "TEAM_INTEGRATION_RUNTIME_PASSWORD",
    "waterbridge_ti_readonly": "TEAM_INTEGRATION_READONLY_PASSWORD",
    "waterbridge_ti_ai_readonly": "TEAM_INTEGRATION_AI_PASSWORD",
}


pytestmark = pytest.mark.skipif(
    os.getenv("TEAM_INTEGRATION_POSTGRES_TEST") != "1",
    reason="TEAM_INTEGRATION PostgreSQL Role 검증을 명시적으로 요청하지 않음",
)


def connect_as(role_name: str):
    password_key = ROLE_PASSWORD_KEYS[role_name]
    password = os.getenv(password_key, "")
    assert password, f"필수 환경변수가 없습니다: {password_key}"
    return psycopg.connect(
        dbname=TARGET_DATABASE,
        user=role_name,
        password=password,
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        **build_postgres_connection_options(os.environ),
    )


def scalar(connection, query: str, parameters=()):
    with connection.cursor() as cursor:
        cursor.execute(query, parameters)
        return cursor.fetchone()[0]


def has_table_privilege(connection, table: str, privilege: str) -> bool:
    return scalar(
        connection,
        "SELECT has_table_privilege(current_user, %s, %s)",
        (table, privilege),
    )


def test_team_integration_role_matrix_postgresql():
    with connect_as("waterbridge_ti_migrator") as connection:
        assert scalar(connection, "SELECT current_database()") == TARGET_DATABASE
        assert scalar(
            connection,
            "SELECT has_schema_privilege(current_user, 'public', 'CREATE')",
        ) is True

    with connect_as("waterbridge_ti_runtime") as connection:
        assert scalar(
            connection,
            "SELECT has_schema_privilege(current_user, 'public', 'CREATE')",
        ) is False
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert has_table_privilege(
                connection,
                "public.accounts_user",
                privilege,
            ) is True
        assert has_table_privilege(
            connection,
            "public.django_migrations",
            "INSERT",
        ) is False

    with connect_as("waterbridge_ti_readonly") as connection:
        assert scalar(
            connection,
            "SHOW default_transaction_read_only",
        ) == "on"
        assert has_table_privilege(
            connection,
            "public.accounts_user",
            "SELECT",
        ) is True
        assert has_table_privilege(
            connection,
            "public.accounts_user",
            "INSERT",
        ) is False

    with connect_as("waterbridge_ti_ai_readonly") as connection:
        assert scalar(
            connection,
            "SHOW default_transaction_read_only",
        ) == "on"
        assert scalar(
            connection,
            "SELECT has_schema_privilege(current_user, 'public', 'CREATE')",
        ) is False
        assert has_table_privilege(
            connection,
            "public.accounts_user",
            "SELECT",
        ) is False
        assert has_table_privilege(
            connection,
            "public.backend_ai_rag_chunks_v1",
            "SELECT",
        ) is True
        for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
            assert has_table_privilege(
                connection,
                "public.backend_ai_rag_chunks_v1",
                privilege,
            ) is False
