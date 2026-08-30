"""E11 isolated migration failure diagnostic.

Scope:
- Does NOT apply migrations.
- Does NOT seed data.
- Does NOT alter application tables.
- It rotates ONLY the dedicated isolated migrator password so the diagnostic
  process can reconnect to the isolated database.
- Reads django_migrations / pg_extension state and computes the remaining
  approved migration plan using the repository's current migration graph.
"""

from __future__ import annotations

import importlib.util
import json
import os
import secrets
import sys
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
ALLOWLIST_PATH = (
    REPO_ROOT
    / "scripts"
    / "database"
    / "migrate_team_integration_allowlist.py"
)

TARGET_DB = "waterbridge_p1_team_isolated"
TARGET_ROLE = "waterbridge_p1_migrator"
PROFILE = "p1-team-isolated"


class DiagnosticBlocked(RuntimeError):
    pass


def read_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        raise DiagnosticBlocked(f"missing env file: {path}")

    for raw in path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        result[key.strip()] = value
    return result


def effective(
    env_file: dict[str, str],
    key: str,
    default: str,
) -> str:
    return os.environ.get(key, "").strip() or env_file.get(
        key,
        default,
    ).strip()


def admin_cfg(env_file: dict[str, str]) -> dict[str, Any]:
    return {
        "host": effective(
            env_file,
            "POSTGRES_HOST",
            "127.0.0.1",
        ),
        "port": int(
            effective(
                env_file,
                "POSTGRES_PORT",
                "5432",
            )
        ),
        "dbname": effective(
            env_file,
            "POSTGRES_DB",
            "waterbridge",
        ),
        "user": effective(
            env_file,
            "POSTGRES_USER",
            "watercare",
        ),
        "password": effective(
            env_file,
            "POSTGRES_PASSWORD",
            "",
        ),
    }


def connect(
    cfg: dict[str, Any],
    *,
    dbname: str,
    user: str,
    password: str,
    autocommit: bool = False,
) -> psycopg.Connection[Any]:
    return psycopg.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=cfg["host"],
        port=cfg["port"],
        connect_timeout=5,
        autocommit=autocommit,
    )


def rotate_isolated_password(
    cfg: dict[str, Any],
    password: str,
) -> dict[str, Any]:
    with connect(
        cfg,
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        autocommit=True,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    current_user,
                    rolcreatedb,
                    rolcreaterole,
                    rolsuper
                FROM pg_roles
                WHERE rolname = current_user
                """
            )
            row = cur.fetchone()
            if row is None:
                raise DiagnosticBlocked(
                    "cannot read admin role metadata"
                )

            (
                current_user,
                can_createdb,
                can_createrole,
                is_superuser,
            ) = row

            cur.execute(
                """
                SELECT rolcanlogin
                FROM pg_roles
                WHERE rolname = %s
                """,
                (TARGET_ROLE,),
            )
            target = cur.fetchone()
            if target is None:
                raise DiagnosticBlocked(
                    f"isolated role missing: {TARGET_ROLE}"
                )

            cur.execute(
                """
                SELECT 1
                FROM pg_database
                WHERE datname = %s
                """,
                (TARGET_DB,),
            )
            if cur.fetchone() is None:
                raise DiagnosticBlocked(
                    f"isolated database missing: {TARGET_DB}"
                )

            # Credential-only mutation on the dedicated isolated role.
            cur.execute(
                sql.SQL(
                    "ALTER ROLE {} WITH LOGIN PASSWORD {}"
                ).format(
                    sql.Identifier(TARGET_ROLE),
                    sql.Literal(password),
                )
            )

    return {
        "admin_user": current_user,
        "admin_createdb": bool(can_createdb),
        "admin_createrole": bool(can_createrole),
        "admin_superuser": bool(is_superuser),
        "isolated_password_rotated": True,
        "password_printed": False,
        "password_persisted": False,
    }


def read_database_state(
    cfg: dict[str, Any],
    password: str,
) -> dict[str, Any]:
    with connect(
        cfg,
        dbname=TARGET_DB,
        user=TARGET_ROLE,
        password=password,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT current_database(), current_user
                """
            )
            dbname, user = cur.fetchone()

            cur.execute(
                """
                SELECT extname, extversion
                FROM pg_extension
                ORDER BY extname
                """
            )
            extensions = {
                name: version
                for name, version in cur.fetchall()
            }

            cur.execute(
                """
                SELECT
                    name,
                    default_version,
                    installed_version
                FROM pg_available_extensions
                WHERE name = 'vector'
                """
            )
            vector_available = cur.fetchone()

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
            migration_table = bool(cur.fetchone()[0])

            applied: list[tuple[str, str]] = []
            if migration_table:
                cur.execute(
                    """
                    SELECT app, name
                    FROM django_migrations
                    ORDER BY id
                    """
                )
                applied = list(cur.fetchall())

            cur.execute(
                """
                SELECT
                    table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
            tables = [
                row[0] for row in cur.fetchall()
            ]

    return {
        "database": dbname,
        "user": user,
        "vector_extension": {
            "installed": "vector" in extensions,
            "installed_version": extensions.get("vector"),
            "available": vector_available is not None,
            "default_version": (
                vector_available[1]
                if vector_available is not None
                else None
            ),
            "available_installed_version": (
                vector_available[2]
                if vector_available is not None
                else None
            ),
        },
        "django_migrations_table_exists": migration_table,
        "applied_migration_count": len(applied),
        "last_20_applied": [
            f"{app}.{name}"
            for app, name in applied[-20:]
        ],
        "public_table_count": len(tables),
        "evidence_tables": [
            name
            for name in tables
            if name.startswith("knowledge_")
        ],
    }


def load_allowlist_module():
    if not ALLOWLIST_PATH.exists():
        raise DiagnosticBlocked(
            f"allowlist runner missing: {ALLOWLIST_PATH}"
        )
    spec = importlib.util.spec_from_file_location(
        "e11_allowlist_diag",
        ALLOWLIST_PATH,
    )
    if spec is None or spec.loader is None:
        raise DiagnosticBlocked(
            "cannot load migration allowlist module"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compute_remaining_plan(
    env_file: dict[str, str],
    cfg: dict[str, Any],
    password: str,
) -> dict[str, Any]:
    # Ensure current repo backend imports work.
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))

    child_values = dict(env_file)
    child_values.update(
        {
            "POSTGRES_HOST": str(cfg["host"]),
            "POSTGRES_PORT": str(cfg["port"]),
            "POSTGRES_DB": TARGET_DB,
            "POSTGRES_USER": TARGET_ROLE,
            "POSTGRES_PASSWORD": password,
            "DJANGO_SETTINGS_MODULE": "config.settings.local",
        }
    )
    for key, value in child_values.items():
        os.environ[key] = value

    import django

    django.setup()

    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    allowlist = load_allowlist_module()
    profile = allowlist.MIGRATION_PROFILES[PROFILE]
    executor = MigrationExecutor(connection)

    raw_plan = executor.migration_plan(
        list(allowlist.APPROVED_TARGETS)
    )
    remaining = [
        f"{migration.app_label}.{migration.name}"
        for migration, backwards in raw_plan
        if not backwards
    ]

    applied = set(executor.loader.applied_migrations)

    special = {
        "evidence.0007_chunkembedding_applied": (
            "evidence",
            "0007_chunkembedding",
        )
        in applied,
        "evidence.0007_chunkembedding_pending": (
            "evidence.0007_chunkembedding" in remaining
        ),
        "visits.0004_applied": (
            "visits",
            "0004_visit_runtime_fields",
        )
        in applied,
        "visits.0005_applied": (
            "visits",
            "0005_replace_visit_result_assignment_fk",
        )
        in applied,
    }

    return {
        "remaining_approved_count": len(remaining),
        "next_20_remaining": remaining[:20],
        "special": special,
    }


def infer_likely_blocker(
    state: dict[str, Any],
    plan: dict[str, Any],
    admin: dict[str, Any],
) -> dict[str, Any]:
    vector = state["vector_extension"]
    special = plan["special"]

    if (
        vector["available"]
        and not vector["installed"]
        and special["evidence.0007_chunkembedding_pending"]
    ):
        return {
            "code": "VECTOR_EXTENSION_NOT_INSTALLED",
            "confidence": "HIGH",
            "reason": (
                "evidence.0007_chunkembedding is still pending and "
                "declares pgvector VectorExtension(), while the fresh "
                "isolated database has no installed vector extension."
            ),
            "admin_superuser": admin["admin_superuser"],
            "recommended_next_step": (
                "Install vector once in the isolated database using "
                "an authorized extension-capable admin, then rerun the "
                "official migration allowlist."
            ),
        }

    return {
        "code": "NEEDS_NEXT_MIGRATION_INSPECTION",
        "confidence": "MEDIUM",
        "reason": (
            "Current metadata does not uniquely identify the SQL error."
        ),
        "admin_superuser": admin["admin_superuser"],
        "recommended_next_step": (
            "Inspect the first remaining migration and execute a "
            "targeted non-destructive SQL/permission check."
        ),
    }


def main() -> int:
    print("=== E11 Isolated Migration Diagnostic ===")

    env_file = read_env_file(BACKEND_ROOT / ".env")
    cfg = admin_cfg(env_file)
    password = secrets.token_urlsafe(48)

    try:
        admin = rotate_isolated_password(
            cfg,
            password,
        )
        state = read_database_state(
            cfg,
            password,
        )
        plan = compute_remaining_plan(
            env_file,
            cfg,
            password,
        )
        inference = infer_likely_blocker(
            state,
            plan,
            admin,
        )

        result = {
            "status": "DIAGNOSTIC_COMPLETE",
            "server": {
                "host": cfg["host"],
                "port": cfg["port"],
            },
            "admin": admin,
            "isolated_database_state": state,
            "remaining_plan": plan,
            "inference": inference,
            "schema_mutation_performed": False,
            "migration_applied": False,
            "seed_performed": False,
        }

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "DIAGNOSTIC_BLOCKED",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "password_printed": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    finally:
        password = ""


if __name__ == "__main__":
    raise SystemExit(main())
