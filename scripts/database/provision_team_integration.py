"""TEAM_INTEGRATION PostgreSQL DB·Role·권한을 안전하게 구성한다.

기본 실행은 비변경 Plan이다. 실제 변경은 ``--apply``와 정확한 DB명
확인을 함께 제공한 경우에만 수행한다. 비밀번호·Host·DSN은 어떤 JSON
결과나 오류에도 포함하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPOSITORY_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config.env import (  # noqa: E402
    PostgresConnectionConfigurationError,
    build_postgres_connection_options,
    load_backend_env,
    load_env_file,
)


TARGET_DATABASE = "waterbridge_team_integration"
ADMIN_DATABASE = "postgres"
OBJECT_MARKER = "waterbridge:team-integration:v1"
AI_READONLY_VIEW = "backend_ai_rag_chunks_v1"
AI_READONLY_VIEW_REGCLASS = f"public.{AI_READONLY_VIEW}"
ADVISORY_LOCK_KEY = 870_429_001
TEAM_ENV_PATH = BACKEND_DIR / ".env.team-integration"
PROTECTED_DATABASES = frozenset(
    {"waterbridge", "watercare", "postgres", "template0", "template1"}
)
REQUIRED_ADMIN_KEYS = (
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
)


@dataclass(frozen=True)
class RoleSpec:
    label: str
    name: str
    password_key: str


ROLE_SPECS = (
    RoleSpec(
        "migrator",
        "waterbridge_ti_migrator",
        "TEAM_INTEGRATION_MIGRATOR_PASSWORD",
    ),
    RoleSpec(
        "runtime",
        "waterbridge_ti_runtime",
        "TEAM_INTEGRATION_RUNTIME_PASSWORD",
    ),
    RoleSpec(
        "readonly",
        "waterbridge_ti_readonly",
        "TEAM_INTEGRATION_READONLY_PASSWORD",
    ),
    RoleSpec(
        "ai_readonly",
        "waterbridge_ti_ai_readonly",
        "TEAM_INTEGRATION_AI_PASSWORD",
    ),
)


class ProvisioningError(RuntimeError):
    """입력값을 노출하지 않는 Provisioning 오류."""

    def __init__(
        self,
        reason: str,
        *,
        missing_keys: tuple[str, ...] = (),
    ):
        super().__init__(f"TEAM_INTEGRATION provisioning error: {reason}")
        self.reason = reason
        self.missing_keys = tuple(sorted(set(missing_keys)))


def _is_local_host(host: str) -> bool:
    return host.strip().lower() in {"127.0.0.1", "localhost", "::1"}


def _is_placeholder(value: str) -> bool:
    return value.strip().lower().startswith("replace-with-")


def _validated_port(environ: Mapping[str, str]) -> int:
    try:
        port = int(environ.get("POSTGRES_PORT", ""))
    except ValueError as exc:
        raise ProvisioningError("invalid_port") from exc
    if not 1 <= port <= 65535:
        raise ProvisioningError("invalid_port")
    return port


def build_configuration(
    environ: Mapping[str, str],
    *,
    apply: bool,
    confirmed_database: str | None,
    rotate_passwords: bool,
) -> dict[str, Any]:
    missing_admin = tuple(
        key for key in REQUIRED_ADMIN_KEYS if not environ.get(key, "").strip()
    )
    if missing_admin:
        raise ProvisioningError(
            "missing_admin_environment",
            missing_keys=missing_admin,
        )

    if TARGET_DATABASE in PROTECTED_DATABASES:
        raise ProvisioningError("protected_target_database")

    if apply and confirmed_database != TARGET_DATABASE:
        raise ProvisioningError("database_confirmation_required")
    if rotate_passwords and not apply:
        raise ProvisioningError("password_rotation_requires_apply")

    if apply:
        missing_passwords = tuple(
            role.password_key
            for role in ROLE_SPECS
            if not environ.get(role.password_key, "").strip()
            or _is_placeholder(environ.get(role.password_key, ""))
        )
        if missing_passwords:
            raise ProvisioningError(
                "missing_role_passwords",
                missing_keys=missing_passwords,
            )
        role_password_values = tuple(
            environ[role.password_key] for role in ROLE_SPECS
        )
        if len(set(role_password_values)) != len(role_password_values):
            raise ProvisioningError("duplicate_role_passwords")
        if environ["POSTGRES_PASSWORD"] in role_password_values:
            raise ProvisioningError("role_password_matches_admin")

    try:
        connection_options = build_postgres_connection_options(
            environ,
            base_dir=BACKEND_DIR,
        )
    except PostgresConnectionConfigurationError as exc:
        raise ProvisioningError(
            exc.reason,
            missing_keys=exc.missing_keys,
        ) from None

    host = environ["POSTGRES_HOST"].strip()
    if not _is_local_host(host):
        if connection_options.get("sslmode") != "verify-full":
            raise ProvisioningError("remote_verify_full_required")
        if "sslrootcert" not in connection_options:
            raise ProvisioningError(
                "remote_sslrootcert_required",
                missing_keys=("POSTGRES_SSLROOTCERT",),
            )

    return {
        "admin_connection": {
            "dbname": ADMIN_DATABASE,
            "user": environ["POSTGRES_USER"],
            "password": environ["POSTGRES_PASSWORD"],
            "host": host,
            "port": _validated_port(environ),
            **connection_options,
        },
        "role_passwords": {
            role.name: environ.get(role.password_key, "")
            for role in ROLE_SPECS
        },
        "remote": not _is_local_host(host),
        "rotate_passwords": rotate_passwords,
    }


def _role_row(cursor: Any, role_name: str) -> tuple[Any, ...] | None:
    cursor.execute(
        """
        SELECT
            rolcanlogin,
            rolsuper,
            rolcreatedb,
            rolcreaterole,
            rolreplication,
            rolbypassrls,
            shobj_description(oid, 'pg_authid'),
            (
                SELECT COUNT(*)
                FROM pg_auth_members membership
                WHERE membership.member = role_row.oid
                   OR membership.roleid = role_row.oid
            )
        FROM pg_roles role_row
        WHERE rolname = %s
        """,
        (role_name,),
    )
    return cursor.fetchone()


def _ensure_role(
    cursor: Any,
    role: RoleSpec,
    password: str,
    *,
    rotate_password: bool,
) -> str:
    row = _role_row(cursor, role.name)
    if row is not None:
        _assert_existing_role_policy(row)
        if rotate_password:
            cursor.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(role.name),
                    sql.Literal(password),
                )
            )
            return "ROTATED"
        return "EXISTS"

    cursor.execute(
        sql.SQL(
            "CREATE ROLE {} LOGIN PASSWORD {} "
            "NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOREPLICATION NOBYPASSRLS"
        ).format(
            sql.Identifier(role.name),
            sql.Literal(password),
        )
    )
    cursor.execute(
        sql.SQL("COMMENT ON ROLE {} IS {}").format(
            sql.Identifier(role.name),
            sql.Literal(OBJECT_MARKER),
        )
    )
    return "CREATED"


def _assert_existing_role_policy(row: tuple[Any, ...]) -> None:
    safe_attributes = (
        row[0] is True
        and all(value is False for value in row[1:6])
    )
    no_memberships = row[7] == 0
    if (
        not safe_attributes
        or row[6] != OBJECT_MARKER
        or not no_memberships
    ):
        raise ProvisioningError("existing_role_policy_mismatch")


def _database_row(cursor: Any) -> tuple[Any, ...] | None:
    cursor.execute(
        """
        SELECT
            pg_get_userbyid(datdba),
            shobj_description(oid, 'pg_database')
        FROM pg_database
        WHERE datname = %s
        """,
        (TARGET_DATABASE,),
    )
    return cursor.fetchone()


def _preflight_admin(cursor: Any) -> str:
    """변경 전에 관리자 capability와 pgvector 가용성을 확인한다."""

    cursor.execute(
        """
        SELECT current_user, rolsuper, rolcreatedb, rolcreaterole
        FROM pg_roles
        WHERE rolname = current_user
        """
    )
    row = cursor.fetchone()
    if row is None:
        raise ProvisioningError("admin_role_not_found")
    owner, is_superuser, can_create_db, can_create_role = row
    if not is_superuser and not (can_create_db and can_create_role):
        raise ProvisioningError("insufficient_admin_capabilities")

    cursor.execute(
        "SELECT EXISTS ("
        "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
        ")"
    )
    if cursor.fetchone()[0] is not True:
        raise ProvisioningError("vector_extension_unavailable")
    return owner


def _ensure_database(cursor: Any, owner: str) -> str:
    row = _database_row(cursor)
    if row is not None:
        _assert_existing_database_policy(row, owner)
        return "EXISTS"

    cursor.execute(
        sql.SQL(
            "CREATE DATABASE {} WITH OWNER {} TEMPLATE template0 "
            "ENCODING 'UTF8'"
        ).format(
            sql.Identifier(TARGET_DATABASE),
            sql.Identifier(owner),
        )
    )
    cursor.execute(
        sql.SQL("COMMENT ON DATABASE {} IS {}").format(
            sql.Identifier(TARGET_DATABASE),
            sql.Literal(OBJECT_MARKER),
        )
    )
    return "CREATED"


def _assert_existing_database_policy(
    row: tuple[Any, ...],
    owner: str,
) -> None:
    if row[0] != owner or row[1] != OBJECT_MARKER:
        raise ProvisioningError("existing_database_policy_mismatch")


def _preflight_existing_objects(cursor: Any, owner: str) -> None:
    """Mutation 전에 모든 동명 객체의 표식·정책을 한 번에 검증한다."""

    for role in ROLE_SPECS:
        row = _role_row(cursor, role.name)
        if row is not None:
            _assert_existing_role_policy(row)
    database_row = _database_row(cursor)
    if database_row is not None:
        _assert_existing_database_policy(database_row, owner)


def _grant_default_privileges(cursor: Any) -> None:
    """Migrator 자신의 향후 객체에 최소권한 Default ACL을 설정한다."""

    roles = {role.label: role.name for role in ROLE_SPECS}
    default_statements = (
        (
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}",
            roles["runtime"],
        ),
        (
            "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {}",
            roles["runtime"],
        ),
        ("GRANT SELECT ON TABLES TO {}", roles["readonly"]),
        ("GRANT SELECT ON SEQUENCES TO {}", roles["readonly"]),
    )
    for statement, target_role in default_statements:
        cursor.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public " + statement)
            .format(sql.Identifier(target_role))
        )

    default_revoke_statements = (
        (
            "REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
            "ON TABLES FROM {}",
            roles["readonly"],
        ),
        (
            "REVOKE USAGE, UPDATE ON SEQUENCES FROM {}",
            roles["readonly"],
        ),
        ("REVOKE ALL PRIVILEGES ON TABLES FROM {}", roles["ai_readonly"]),
        (
            "REVOKE ALL PRIVILEGES ON SEQUENCES FROM {}",
            roles["ai_readonly"],
        ),
    )
    for statement, target_role in default_revoke_statements:
        cursor.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public " + statement)
            .format(sql.Identifier(target_role))
        )


def _grant_roles(cursor: Any) -> None:
    roles = {role.label: role.name for role in ROLE_SPECS}

    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cursor.execute(
        sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
            sql.Identifier(TARGET_DATABASE)
        )
    )
    cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")

    for role_name in roles.values():
        cursor.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON DATABASE {} FROM {}").format(
                sql.Identifier(TARGET_DATABASE),
                sql.Identifier(role_name),
            )
        )
        cursor.execute(
            sql.SQL("REVOKE ALL PRIVILEGES ON SCHEMA public FROM {}").format(
                sql.Identifier(role_name)
            )
        )
        cursor.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(TARGET_DATABASE),
                sql.Identifier(role_name),
            )
        )
        cursor.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                sql.Identifier(role_name)
            )
        )

    cursor.execute(
        sql.SQL("GRANT CREATE ON SCHEMA public TO {}").format(
            sql.Identifier(roles["migrator"])
        )
    )
    cursor.execute(
        sql.SQL(
            "REVOKE TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES "
            "IN SCHEMA public FROM {}"
        ).format(sql.Identifier(roles["runtime"]))
    )
    cursor.execute(
        sql.SQL(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
            "IN SCHEMA public TO {}"
        ).format(sql.Identifier(roles["runtime"]))
    )
    cursor.execute(
        sql.SQL(
            "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES "
            "IN SCHEMA public TO {}"
        ).format(sql.Identifier(roles["runtime"]))
    )
    cursor.execute(
        sql.SQL(
            "REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER "
            "ON ALL TABLES IN SCHEMA public FROM {}"
        ).format(sql.Identifier(roles["readonly"]))
    )
    cursor.execute(
        sql.SQL(
            "REVOKE USAGE, UPDATE ON ALL SEQUENCES "
            "IN SCHEMA public FROM {}"
        ).format(sql.Identifier(roles["readonly"]))
    )
    cursor.execute(
        sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(
            sql.Identifier(roles["readonly"])
        )
    )
    cursor.execute(
        sql.SQL(
            "GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {}"
        ).format(sql.Identifier(roles["readonly"]))
    )
    cursor.execute(
        sql.SQL(
            "REVOKE ALL PRIVILEGES ON ALL TABLES "
            "IN SCHEMA public FROM {}"
        ).format(sql.Identifier(roles["ai_readonly"]))
    )
    cursor.execute(
        sql.SQL(
            "REVOKE ALL PRIVILEGES ON ALL SEQUENCES "
            "IN SCHEMA public FROM {}"
        ).format(sql.Identifier(roles["ai_readonly"]))
    )
    cursor.execute(
        "SELECT to_regclass(%s) IS NOT NULL",
        (AI_READONLY_VIEW_REGCLASS,),
    )
    if cursor.fetchone()[0]:
        cursor.execute(
            sql.SQL("GRANT SELECT ON TABLE {} TO {}").format(
                sql.Identifier("public", AI_READONLY_VIEW),
                sql.Identifier(roles["ai_readonly"]),
            )
        )

    cursor.execute(
        "SELECT to_regclass('public.django_migrations') IS NOT NULL"
    )
    if cursor.fetchone()[0]:
        cursor.execute(
            sql.SQL(
                "REVOKE INSERT, UPDATE, DELETE ON TABLE "
                "public.django_migrations FROM {}"
            ).format(sql.Identifier(roles["runtime"]))
        )

    for readonly_role in (roles["readonly"], roles["ai_readonly"]):
        cursor.execute(
            sql.SQL(
                "ALTER ROLE {} IN DATABASE {} "
                "SET default_transaction_read_only TO 'on'"
            ).format(
                sql.Identifier(readonly_role),
                sql.Identifier(TARGET_DATABASE),
            )
        )


def provision(
    configuration: dict[str, Any],
    *,
    connect: Callable[..., Any] = psycopg.connect,
) -> dict[str, Any]:
    admin_options = configuration["admin_connection"]
    role_passwords = configuration["role_passwords"]
    role_status: dict[str, str] = {}

    with connect(**admin_options, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_lock(%s)",
                (ADVISORY_LOCK_KEY,),
            )
            if cursor.fetchone()[0] is not True:
                raise ProvisioningError("provisioning_lock_unavailable")
            try:
                owner = _preflight_admin(cursor)
                _preflight_existing_objects(cursor, owner)
                cursor.execute("BEGIN")
                try:
                    for role in ROLE_SPECS:
                        role_status[role.label] = _ensure_role(
                            cursor,
                            role,
                            role_passwords[role.name],
                            rotate_password=configuration["rotate_passwords"],
                        )
                except Exception:
                    cursor.execute("ROLLBACK")
                    raise
                else:
                    cursor.execute("COMMIT")
                database_status = _ensure_database(cursor, owner)
            finally:
                cursor.execute(
                    "SELECT pg_advisory_unlock(%s)",
                    (ADVISORY_LOCK_KEY,),
                )

    target_options = {**admin_options, "dbname": TARGET_DATABASE}
    with connect(**target_options) as connection:
        with connection.cursor() as cursor:
            _grant_roles(cursor)

    migrator = next(role for role in ROLE_SPECS if role.label == "migrator")
    migrator_options = {
        **target_options,
        "user": migrator.name,
        "password": role_passwords[migrator.name],
    }
    with connect(**migrator_options) as connection:
        with connection.cursor() as cursor:
            _grant_default_privileges(cursor)

    return {
        "status": "APPLIED",
        "scope": "TEAM_INTEGRATION",
        "target_database": TARGET_DATABASE,
        "database": database_status,
        "roles": role_status,
        "next_action": (
            "Run Django migrations with the migrator role, then rerun "
            "this command to reconcile grants."
        ),
    }


def run(
    environ: Mapping[str, str],
    *,
    apply: bool,
    confirmed_database: str | None,
    rotate_passwords: bool = False,
    connect: Callable[..., Any] = psycopg.connect,
) -> tuple[dict[str, Any], int]:
    try:
        configuration = build_configuration(
            environ,
            apply=apply,
            confirmed_database=confirmed_database,
            rotate_passwords=rotate_passwords,
        )
    except ProvisioningError as exc:
        return (
            {
                "status": "NOT_CONFIGURED",
                "reason": exc.reason,
                "missing_keys": list(exc.missing_keys),
                "message": "비밀값·Host·DSN은 출력하지 않습니다.",
            },
            2,
        )

    if not apply:
        return (
            {
                "status": "PLAN_READY",
                "scope": "TEAM_INTEGRATION",
                "target_database": TARGET_DATABASE,
                "remote": configuration["remote"],
                "roles": {
                    role.label: role.name for role in ROLE_SPECS
                },
                "mutates_database": False,
                "apply_requirement": (
                    f"--apply --confirm-database {TARGET_DATABASE}"
                ),
            },
            0,
        )

    try:
        return provision(configuration, connect=connect), 0
    except ProvisioningError as exc:
        return (
            {
                "status": "BLOCKED",
                "reason": exc.reason,
                "message": "기존 DB·Role을 변경하지 않았거나 중단했습니다.",
            },
            3,
        )
    except Exception as exc:  # noqa: BLE001 - 비밀 없는 CLI 결과로 변환
        return (
            {
                "status": "FAILED",
                "error_type": type(exc).__name__,
                "message": (
                    "Provisioning에 실패했습니다. 비밀번호·Host·DSN·"
                    "원본 오류 메시지는 출력하지 않습니다."
                ),
            },
            1,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="DB·Role·Grant를 실제 적용한다. 기본은 Plan이다.",
    )
    parser.add_argument(
        "--rotate-passwords",
        action="store_true",
        help=(
            "표식이 일치하는 기존 Role 비밀번호만 명시적으로 교체한다. "
            "--apply와 정확한 DB 확인이 함께 필요하다."
        ),
    )
    parser.add_argument(
        "--confirm-database",
        help="적용 대상 DB명을 정확히 다시 입력한다.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    load_backend_env()
    load_env_file(TEAM_ENV_PATH)
    result, exit_code = run(
        os.environ,
        apply=arguments.apply,
        confirmed_database=arguments.confirm_database,
        rotate_passwords=arguments.rotate_passwords,
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
