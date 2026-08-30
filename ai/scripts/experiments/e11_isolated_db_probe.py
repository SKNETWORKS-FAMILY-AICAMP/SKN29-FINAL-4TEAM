"""E11 isolated PostgreSQL preflight.

Read-only probe. It never creates, alters, drops, migrates, or seeds anything.
It checks whether the repository's p1-team-isolated database/role already exist
on the same local PostgreSQL server used by backend/.env.

Run from repository root with the backend virtualenv:

    backend\.venv\Scripts\python.exe ai\scripts\experiments\e11_isolated_db_probe.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import psycopg


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"

TARGET_DB = "waterbridge_p1_team_isolated"
TARGET_ROLE = "waterbridge_p1_migrator"
EXPECTED_HOLD = "0005_replace_visit_result_assignment_fk"


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw in path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        line = raw.strip()
        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        values[key] = value

    return values


def setting(
    env_file: dict[str, str],
    name: str,
    default: str,
) -> str:
    return os.environ.get(name, "").strip() or env_file.get(
        name,
        default,
    ).strip()


def connect(
    *,
    dbname: str,
    user: str,
    password: str,
    host: str,
    port: int,
) -> psycopg.Connection[Any]:
    return psycopg.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port,
        connect_timeout=4,
    )


def main() -> int:
    env_file = read_env_file(BACKEND_ROOT / ".env")

    host = setting(env_file, "POSTGRES_HOST", "127.0.0.1")
    port = int(setting(env_file, "POSTGRES_PORT", "5432"))
    source_db = setting(env_file, "POSTGRES_DB", "waterbridge")
    source_user = setting(env_file, "POSTGRES_USER", "watercare")
    password = setting(env_file, "POSTGRES_PASSWORD", "")

    result: dict[str, Any] = {
        "status": "UNKNOWN",
        "server": {
            "host": host,
            "port": port,
        },
        "source_connection": {},
        "isolated_database": {
            "name": TARGET_DB,
            "exists": False,
            "owner": None,
            "connectable_with_current_credentials": False,
        },
        "isolated_migrator_role": {
            "name": TARGET_ROLE,
            "exists": False,
            "can_login": None,
        },
        "current_user_can_create_database": False,
        "current_user_can_create_role": False,
        "migration_state_if_accessible": None,
        "next_action": None,
    }

    with connect(
        dbname=source_db,
        user=source_user,
        password=password,
        host=host,
        port=port,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    current_database(),
                    current_user
                """
            )
            current_database, current_user = cur.fetchone()

            cur.execute(
                """
                SELECT
                    rolcreatedb,
                    rolcreaterole,
                    rolsuper
                FROM pg_roles
                WHERE rolname = current_user
                """
            )
            role_flags = cur.fetchone()
            if role_flags is None:
                raise RuntimeError(
                    "현재 PostgreSQL role metadata를 읽지 못했습니다."
                )
            can_createdb, can_createrole, is_superuser = role_flags

            cur.execute(
                """
                SELECT
                    d.datname,
                    r.rolname
                FROM pg_database d
                JOIN pg_roles r
                  ON r.oid = d.datdba
                WHERE d.datname = %s
                """,
                (TARGET_DB,),
            )
            db_row = cur.fetchone()

            cur.execute(
                """
                SELECT
                    rolname,
                    rolcanlogin
                FROM pg_roles
                WHERE rolname = %s
                """,
                (TARGET_ROLE,),
            )
            target_role_row = cur.fetchone()

    result["source_connection"] = {
        "database": current_database,
        "user": current_user,
        "password_printed": False,
    }
    result["current_user_can_create_database"] = bool(
        can_createdb or is_superuser
    )
    result["current_user_can_create_role"] = bool(
        can_createrole or is_superuser
    )

    if db_row is not None:
        result["isolated_database"]["exists"] = True
        result["isolated_database"]["owner"] = db_row[1]

    if target_role_row is not None:
        result["isolated_migrator_role"]["exists"] = True
        result["isolated_migrator_role"]["can_login"] = bool(
            target_role_row[1]
        )

    if result["isolated_database"]["exists"]:
        try:
            with connect(
                dbname=TARGET_DB,
                user=source_user,
                password=password,
                host=host,
                port=port,
            ) as isolated:
                result["isolated_database"][
                    "connectable_with_current_credentials"
                ] = True

                with isolated.cursor() as cur:
                    cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM information_schema.tables
                            WHERE table_schema = 'public'
                              AND table_name = 'django_migrations'
                        )
                        """
                    )
                    migration_table_exists = bool(
                        cur.fetchone()[0]
                    )

                    state: dict[str, Any] = {
                        "django_migrations_table_exists":
                            migration_table_exists,
                    }

                    if migration_table_exists:
                        cur.execute(
                            """
                            SELECT app, name
                            FROM django_migrations
                            WHERE
                                (app = 'visits' AND name IN (
                                    '0004_visit_runtime_fields',
                                    '0005_replace_visit_result_assignment_fk'
                                ))
                                OR
                                (app = 'accounts'
                                 AND name = '0009_approved_test_contract_email')
                                OR
                                (app = 'evidence'
                                 AND name = '0015_project_child_record_type_in_ai_view')
                                OR
                                (app = 'inquiries'
                                 AND name = '0015_humanreview')
                                OR
                                (app = 'operations'
                                 AND name = '0003_product_expansion_import_profile')
                            ORDER BY app, name
                            """
                        )
                        applied = {
                            f"{app}.{name}"
                            for app, name in cur.fetchall()
                        }

                        state.update(
                            {
                                "accounts_0009_applied":
                                    "accounts.0009_approved_test_contract_email"
                                    in applied,
                                "evidence_0015_applied":
                                    "evidence.0015_project_child_record_type_in_ai_view"
                                    in applied,
                                "inquiries_0015_applied":
                                    "inquiries.0015_humanreview"
                                    in applied,
                                "operations_0003_applied":
                                    "operations.0003_product_expansion_import_profile"
                                    in applied,
                                "visits_0004_applied":
                                    "visits.0004_visit_runtime_fields"
                                    in applied,
                                "visits_0005_applied":
                                    f"visits.{EXPECTED_HOLD}"
                                    in applied,
                            }
                        )

                    result[
                        "migration_state_if_accessible"
                    ] = state

        except psycopg.Error as exc:
            result["isolated_database"][
                "current_credentials_error_type"
            ] = type(exc).__name__

    db_exists = bool(
        result["isolated_database"]["exists"]
    )
    role_exists = bool(
        result["isolated_migrator_role"]["exists"]
    )

    if db_exists and role_exists:
        result["status"] = "ISOLATED_RESOURCES_PRESENT"
        result["next_action"] = (
            "Prepare isolated E11 credentials and verify/apply the "
            "repository migration allowlist before Playwright."
        )
    elif not db_exists and not role_exists:
        result["status"] = "ISOLATED_RESOURCES_MISSING"
        if (
            result["current_user_can_create_database"]
            and result["current_user_can_create_role"]
        ):
            result["next_action"] = (
                "Current local PostgreSQL user has enough privileges "
                "to provision the isolated DB/role safely."
            )
        else:
            result["next_action"] = (
                "Provisioning requires a PostgreSQL admin/owner role."
            )
    else:
        result["status"] = "ISOLATED_RESOURCES_PARTIAL"
        result["next_action"] = (
            "Only part of the isolated DB/role exists; inspect before "
            "creating or modifying anything."
        )

    print("=== E11 Isolated DB Probe ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()
    print(
        "READ_ONLY=true "
        "(no CREATE/ALTER/DROP/MIGRATE/SEED executed)"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
