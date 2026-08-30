"""Provision an isolated local PostgreSQL DB and run E11 safely.

This script intentionally does NOT touch the current development database.

Flow
----
1. Read backend/.env only for local connection/environment values.
2. Create or reconcile ONLY:
   - role: waterbridge_p1_migrator
   - database: waterbridge_p1_team_isolated
3. Ensure pgvector extension exists ONLY in the isolated database.
4. Create a temporary clean detached Git worktree at current HEAD.
5. Run repository official migration allowlist:
   profile=p1-team-isolated
   Plan -> Apply -> Verify
   visits.0005 remains HOLD / NOT APPLIED.
6. Run E11 Playwright runner against a fresh random loopback Backend port
   using the isolated database.
7. Remove the temporary Git worktree.

The generated PostgreSQL password is never printed or written to artifacts.

Run from repository root:

    backend\\.venv\\Scripts\\python.exe ai\\scripts\\experiments\\e11_isolated_setup_and_run.py
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"

TARGET_DB = "waterbridge_p1_team_isolated"
TARGET_ROLE = "waterbridge_p1_migrator"
PROFILE = "p1-team-isolated"
HOLD_CONFIRMATION = "visits.0005=P1_HOLD_EXCLUDED"

E11_RUNNER = (
    REPO_ROOT
    / "ai"
    / "scripts"
    / "experiments"
    / "e11_playwright_user_e2e.py"
)

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class SetupBlocked(RuntimeError):
    pass


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise SetupBlocked(
            f"Backend env file not found: {path}"
        )

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


def effective(
    env_file: dict[str, str],
    key: str,
    default: str = "",
) -> str:
    inherited = os.environ.get(key, "").strip()
    if inherited:
        return inherited
    return env_file.get(key, default).strip()


def backend_python() -> str:
    if os.name == "nt":
        candidate = (
            BACKEND_ROOT
            / ".venv"
            / "Scripts"
            / "python.exe"
        )
    else:
        candidate = (
            BACKEND_ROOT
            / ".venv"
            / "bin"
            / "python"
        )

    if not candidate.exists():
        raise SetupBlocked(
            f"Backend Python not found: {candidate}"
        )
    return str(candidate.resolve())


def current_git_sha() -> str:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise SetupBlocked(
            "Cannot resolve current Git SHA."
        ) from exc

    if len(sha) != 40:
        raise SetupBlocked(
            f"Unexpected Git SHA: {sha!r}"
        )
    return sha


def assert_local_server(host: str) -> None:
    if host.lower() not in LOOPBACK_HOSTS:
        raise SetupBlocked(
            "E11 isolated provisioning is local-only. "
            f"POSTGRES_HOST={host!r}"
        )


def admin_connection_values(
    env_file: dict[str, str],
) -> dict[str, Any]:
    host = effective(
        env_file,
        "POSTGRES_HOST",
        "127.0.0.1",
    )
    assert_local_server(host)

    try:
        port = int(
            effective(
                env_file,
                "POSTGRES_PORT",
                "5432",
            )
        )
    except ValueError as exc:
        raise SetupBlocked(
            "POSTGRES_PORT must be an integer."
        ) from exc

    return {
        "host": host,
        "port": port,
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


def connect_admin(
    cfg: dict[str, Any],
    *,
    autocommit: bool = False,
) -> psycopg.Connection[Any]:
    return psycopg.connect(
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        host=cfg["host"],
        port=cfg["port"],
        connect_timeout=5,
        autocommit=autocommit,
    )


def inspect_admin_privileges(
    conn: psycopg.Connection[Any],
) -> dict[str, bool]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rolcreatedb, rolcreaterole, rolsuper
            FROM pg_roles
            WHERE rolname = current_user
            """
        )
        row = cur.fetchone()

    if row is None:
        raise SetupBlocked(
            "Cannot read current PostgreSQL role flags."
        )

    can_createdb, can_createrole, is_superuser = row
    return {
        "create_database": bool(
            can_createdb or is_superuser
        ),
        "create_role": bool(
            can_createrole or is_superuser
        ),
    }


def resource_state(
    conn: psycopg.Connection[Any],
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT rolname, rolcanlogin
            FROM pg_roles
            WHERE rolname = %s
            """,
            (TARGET_ROLE,),
        )
        role_row = cur.fetchone()

        cur.execute(
            """
            SELECT d.datname, r.rolname
            FROM pg_database d
            JOIN pg_roles r
              ON r.oid = d.datdba
            WHERE d.datname = %s
            """,
            (TARGET_DB,),
        )
        db_row = cur.fetchone()

    return {
        "role_exists": role_row is not None,
        "role_can_login": (
            bool(role_row[1])
            if role_row is not None
            else None
        ),
        "database_exists": db_row is not None,
        "database_owner": (
            db_row[1]
            if db_row is not None
            else None
        ),
    }


def provision_isolated_resources(
    cfg: dict[str, Any],
    generated_password: str,
) -> dict[str, Any]:
    # CREATE DATABASE cannot run inside a transaction.
    with connect_admin(
        cfg,
        autocommit=True,
    ) as conn:
        privileges = inspect_admin_privileges(conn)
        if not (
            privileges["create_database"]
            and privileges["create_role"]
        ):
            raise SetupBlocked(
                "Current PostgreSQL user lacks CREATE DATABASE "
                "or CREATE ROLE privilege."
            )

        before = resource_state(conn)

        if (
            before["database_exists"]
            and before["database_owner"] != TARGET_ROLE
        ):
            raise SetupBlocked(
                "Isolated database already exists with an "
                "unexpected owner; refusing to alter it."
            )

        with conn.cursor() as cur:
            if before["role_exists"]:
                cur.execute(
                    sql.SQL(
                        "ALTER ROLE {} WITH LOGIN PASSWORD {}"
                    ).format(
                        sql.Identifier(TARGET_ROLE),
                        sql.Literal(generated_password),
                    )
                )
            else:
                cur.execute(
                    sql.SQL(
                        "CREATE ROLE {} WITH LOGIN PASSWORD {}"
                    ).format(
                        sql.Identifier(TARGET_ROLE),
                        sql.Literal(generated_password),
                    )
                )

            if not before["database_exists"]:
                cur.execute(
                    sql.SQL(
                        "CREATE DATABASE {} OWNER {}"
                    ).format(
                        sql.Identifier(TARGET_DB),
                        sql.Identifier(TARGET_ROLE),
                    )
                )

        after = resource_state(conn)

    if not (
        after["role_exists"]
        and after["role_can_login"] is True
        and after["database_exists"]
        and after["database_owner"] == TARGET_ROLE
    ):
        raise SetupBlocked(
            "Isolated DB/role provisioning verification failed."
        )

    return {
        "before": before,
        "after": after,
        "admin_privileges": privileges,
        "password_printed": False,
        "password_persisted": False,
    }


def ensure_vector_extension(
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Install pgvector only in the isolated E11 database.

    This is the single intentional schema-level bootstrap mutation outside
    Django migrations. It is necessary because evidence.0007 itself depends
    on the vector extension being available to create VectorField objects.
    The operation is restricted to TARGET_DB and uses the existing local
    PostgreSQL admin credentials. The development database is never touched.
    """

    with psycopg.connect(
        dbname=TARGET_DB,
        user=cfg["user"],
        password=cfg["password"],
        host=cfg["host"],
        port=cfg["port"],
        connect_timeout=5,
        autocommit=True,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT extversion
                FROM pg_extension
                WHERE extname = 'vector'
                """
            )
            before = cur.fetchone()

            cur.execute(
                """
                SELECT default_version
                FROM pg_available_extensions
                WHERE name = 'vector'
                """
            )
            available = cur.fetchone()

            if available is None:
                raise SetupBlocked(
                    "pgvector extension is not available on the local "
                    "PostgreSQL server."
                )

            if before is None:
                cur.execute(
                    "CREATE EXTENSION vector"
                )

            cur.execute(
                """
                SELECT extversion
                FROM pg_extension
                WHERE extname = 'vector'
                """
            )
            after = cur.fetchone()

    if after is None:
        raise SetupBlocked(
            "pgvector extension installation verification failed."
        )

    return {
        "database": TARGET_DB,
        "available_default_version": available[0],
        "installed_before": before is not None,
        "installed_after": True,
        "installed_version": after[0],
        "development_database_modified": False,
    }


def build_target_environment(
    env_file: dict[str, str],
    cfg: dict[str, Any],
    password: str,
) -> dict[str, str]:
    child = os.environ.copy()

    # Reuse non-secret/non-DB local settings from backend/.env while
    # allowing already-exported shell values to take precedence.
    for key, value in env_file.items():
        child.setdefault(key, value)

    child["POSTGRES_HOST"] = str(cfg["host"])
    child["POSTGRES_PORT"] = str(cfg["port"])
    child["POSTGRES_DB"] = TARGET_DB
    child["POSTGRES_USER"] = TARGET_ROLE
    child["POSTGRES_PASSWORD"] = password
    child["DJANGO_SETTINGS_MODULE"] = (
        "config.settings.local"
    )

    return child


def run_json_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )

    stdout = result.stdout.strip()
    if not stdout:
        raise SetupBlocked(
            "Official migration runner returned no JSON. "
            f"exit_code={result.returncode}"
        )

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        safe_tail = stdout[-2000:]
        raise SetupBlocked(
            "Official migration runner output was not JSON. "
            f"exit_code={result.returncode}, tail={safe_tail}"
        ) from exc

    if result.returncode != 0:
        raise SetupBlocked(
            "Official migration runner blocked/failed: "
            + json.dumps(
                {
                    "status": payload.get("status"),
                    "reason": payload.get("reason"),
                    "nodes": payload.get("nodes"),
                    "error_type": payload.get(
                        "error_type"
                    ),
                },
                ensure_ascii=False,
            )
        )

    return payload


def add_clean_worktree(
    sha: str,
) -> tuple[Path, Path]:
    parent = Path(
        tempfile.mkdtemp(
            prefix="waterbridge-e11-"
        )
    )
    worktree = parent / "repo"

    result = subprocess.run(
        [
            "git",
            "worktree",
            "add",
            "--detach",
            str(worktree),
            sha,
        ],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode != 0:
        shutil.rmtree(
            parent,
            ignore_errors=True,
        )
        raise SetupBlocked(
            "Could not create temporary clean Git worktree: "
            + (result.stderr or result.stdout)[-2000:]
        )

    return parent, worktree


def remove_clean_worktree(
    parent: Path,
    worktree: Path,
) -> None:
    subprocess.run(
        [
            "git",
            "worktree",
            "remove",
            "--force",
            str(worktree),
        ],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    shutil.rmtree(
        parent,
        ignore_errors=True,
    )


def run_official_allowlist(
    *,
    sha: str,
    env: dict[str, str],
) -> dict[str, Any]:
    parent, worktree = add_clean_worktree(sha)
    try:
        runner = (
            worktree
            / "scripts"
            / "database"
            / "migrate_team_integration_allowlist.py"
        )
        if not runner.exists():
            raise SetupBlocked(
                "Official migration allowlist runner is absent "
                f"at SHA {sha}."
            )

        python = backend_python()

        plan = run_json_command(
            [
                python,
                str(runner),
                "--profile",
                PROFILE,
                "--settings",
                "config.settings.local",
                "--verbosity",
                "0",
            ],
            cwd=worktree,
            env=env,
        )

        if plan.get("status") not in {
            "PLAN_READY",
            "ALREADY_APPLIED",
        }:
            raise SetupBlocked(
                "Unexpected allowlist plan status: "
                f"{plan.get('status')!r}"
            )

        print(
            "[E11-ISO] Migration Plan: "
            f"{plan.get('status')}"
        )
        print(
            "[E11-ISO] Remaining approved migrations: "
            f"{len(plan.get('remaining_plan', []))}"
        )
        print(
            "[E11-ISO] Forbidden migration: "
            f"{plan.get('forbidden_migration')}"
        )
        print(
            "[E11-ISO] Hold: "
            f"{plan.get('hold')}"
        )

        apply_result = run_json_command(
            [
                python,
                str(runner),
                "--profile",
                PROFILE,
                "--apply",
                "--confirm-database",
                TARGET_DB,
                "--confirm-source-sha",
                sha,
                "--confirm-hold",
                HOLD_CONFIRMATION,
                "--settings",
                "config.settings.local",
                "--verbosity",
                "0",
            ],
            cwd=worktree,
            env=env,
        )

        verification = apply_result.get(
            "verification",
            {},
        )

        required = {
            "status": verification.get(
                "status"
            ) == "VERIFIED",
            "accounts_0009": verification.get(
                "accounts.0009"
            ) == "APPLIED",
            "evidence_0015": verification.get(
                "evidence.0015"
            ) == "APPLIED",
            "inquiries_0015": verification.get(
                "inquiries.0015"
            ) == "APPLIED",
            "operations_0003": verification.get(
                "operations.0003"
            ) == "APPLIED",
            "visits_0004": verification.get(
                "visits.0004"
            ) == "APPLIED",
            "visits_0005_hold": verification.get(
                "visits.0005"
            ) == "NOT_APPLIED_P1_HOLD",
            "remaining_plan_zero": verification.get(
                "remaining_plan_count"
            ) == 0,
            "blockers_zero": verification.get(
                "blockers"
            ) == [],
        }

        if not all(required.values()):
            raise SetupBlocked(
                "Post-apply migration verification failed: "
                + json.dumps(
                    required,
                    ensure_ascii=False,
                )
            )

        print(
            "[E11-ISO] Migration verification: VERIFIED"
        )
        print(
            "[E11-ISO] visits.0005: "
            "NOT_APPLIED_P1_HOLD"
        )

        return {
            "plan_status": plan.get("status"),
            "apply_status": apply_result.get(
                "status"
            ),
            "verification": verification,
        }

    finally:
        remove_clean_worktree(
            parent,
            worktree,
        )


def random_loopback_port() -> int:
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    ) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(
            sock.getsockname()[1]
        )


def run_e11(
    *,
    env: dict[str, str],
) -> int:
    if not E11_RUNNER.exists():
        raise SetupBlocked(
            f"E11 runner not found: {E11_RUNNER}"
        )

    port = random_loopback_port()
    env = env.copy()
    env["E2E_BACKEND_BASE_URL"] = (
        f"http://127.0.0.1:{port}"
    )
    env["E2E_BACKEND_PYTHON"] = backend_python()

    print(
        "[E11-ISO] Starting E11 against isolated DB "
        f"on Backend port {port}."
    )
    print(
        "[E11-ISO] Consultant password prompt may appear next."
    )

    result = subprocess.run(
        [
            sys.executable,
            str(E11_RUNNER),
        ],
        cwd=REPO_ROOT,
        env=env,
    )
    return int(result.returncode)


def main() -> int:
    print(
        "=== E11 Isolated Setup + Official Migration "
        "Allowlist + Playwright ==="
    )

    env_file = read_env_file(
        BACKEND_ROOT / ".env"
    )
    cfg = admin_connection_values(
        env_file
    )

    print(
        f"[E11-ISO] PostgreSQL server: "
        f"{cfg['host']}:{cfg['port']}"
    )
    print(
        f"[E11-ISO] Existing development DB will NOT "
        f"be modified: {cfg['dbname']}"
    )
    print(
        f"[E11-ISO] Target isolated DB: {TARGET_DB}"
    )
    print(
        f"[E11-ISO] Target migrator role: {TARGET_ROLE}"
    )

    generated_password = secrets.token_urlsafe(48)

    try:
        resource_result = provision_isolated_resources(
            cfg,
            generated_password,
        )
        print(
            "[E11-ISO] Isolated DB/Role: READY "
            f"(db_created_now="
            f"{not resource_result['before']['database_exists']}, "
            f"role_created_now="
            f"{not resource_result['before']['role_exists']})"
        )

        print(
            "[E11-ISO] Ensuring pgvector extension exists "
            "ONLY in the isolated database."
        )
        vector_result = ensure_vector_extension(cfg)
        print(
            "[E11-ISO] pgvector: "
            f"{vector_result['installed_version']} "
            f"(installed_before="
            f"{vector_result['installed_before']})"
        )

        target_env = build_target_environment(
            env_file,
            cfg,
            generated_password,
        )

        sha = current_git_sha()
        print(
            f"[E11-ISO] Source SHA: {sha}"
        )
        print(
            "[E11-ISO] Creating temporary clean worktree "
            "for official migration allowlist."
        )

        migration_result = run_official_allowlist(
            sha=sha,
            env=target_env,
        )

        print(
            "[E11-ISO] Official migration allowlist complete: "
            f"{migration_result['apply_status']}"
        )

        e11_code = run_e11(
            env=target_env,
        )

        print()
        print("=" * 88)
        print("[E11-ISO] FINAL")
        print(
            json.dumps(
                {
                    "isolated_database": TARGET_DB,
                    "isolated_role": TARGET_ROLE,
                    "development_database_modified": False,
                    "pgvector": {
                        "database": TARGET_DB,
                        "installed": True,
                        "version": vector_result[
                            "installed_version"
                        ],
                    },
                    "migration_allowlist_verified": True,
                    "visits_0005": (
                        "NOT_APPLIED_P1_HOLD"
                    ),
                    "e11_exit_code": e11_code,
                    "password_printed": False,
                    "password_persisted": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        return e11_code

    except SetupBlocked as exc:
        print()
        print("=" * 88)
        print("[E11-ISO] BLOCKED")
        print(str(exc))
        return 2
    finally:
        generated_password = ""


if __name__ == "__main__":
    raise SystemExit(main())
