"""Backend-AI G1-B PostgreSQL 준비 상태를 읽기 전용으로 감사한다.

연결 정보와 원본 예외 메시지는 출력하지 않는다. 기본 실행은 발견한
Blocker를 JSON으로 보고하고 0을 반환한다. ``--require-ready``를 사용한
경우에만 READY가 아니면 1을 반환한다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import psycopg


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPOSITORY_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config.env import (  # noqa: E402
    PostgresConnectionConfigurationError,
    build_postgres_connection_options,
    load_backend_env,
)
from config.pgvector_compatibility import (  # noqa: E402
    PREFERRED_PGVECTOR_VERSION,
    SUPPORTED_PGVECTOR_VERSIONS,
    is_supported_pgvector_version,
)


REQUIRED_ENV_KEYS = (
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
)
REQUIRED_MIGRATIONS = (
    "0009_ai_chunk_crosswalk",
    "0010_backend_ai_rag_chunks_view",
    "0011_cast_chunk_embedding_vector_dimensions",
    "0012_expand_ai_crosswalk_canonical_id",
)
EXPECTED_VIEW = "public.backend_ai_rag_chunks_v1"
EXPECTED_VIEW_COLUMNS = (
    "chunk_id",
    "metadata",
    "content",
    "embedding",
    "model_code",
    "product_generation",
    "verification_status",
    "allowed_use",
)
EXPECTED_CHUNK_COUNT = 7
EXPECTED_CROSSWALK_PAGE_LINK_COUNT = 8
EVIDENCE_PROFILES = {
    "baseline": {
        "chunk_count": EXPECTED_CHUNK_COUNT,
        "page_link_count": EXPECTED_CROSSWALK_PAGE_LINK_COUNT,
    },
    "three-model": {
        "chunk_count": 53,
        "page_link_count": 53,
    },
}
# 이전 Audit 소비자가 참조하는 이름은 우선 버전 Alias로 보존한다.
EXPECTED_PGVECTOR_VERSION = PREFERRED_PGVECTOR_VERSION
EXPECTED_EMBEDDING_MODEL = "BAAI/bge-m3"
EXPECTED_EMBEDDING_REVISION = (
    "5617a9f61b028005a4858fdac845db406aefb181"
)
AI_READONLY_ROLE = "waterbridge_ti_ai_readonly"
TEAM_INTEGRATION_DATABASE = "waterbridge_team_integration"
BASE_TABLES = (
    "public.knowledge_ai_chunk_crosswalk",
    "public.knowledge_document_chunk",
    "public.knowledge_chunk_embedding",
)


class ConfigurationError(ValueError):
    """연결 전에 발견한 환경 설정 오류."""

    def __init__(
        self,
        reason: str,
        *,
        missing_keys: tuple[str, ...] = (),
    ):
        super().__init__(reason)
        self.reason = reason
        self.missing_keys = tuple(sorted(set(missing_keys)))


def load_connection_options(environ: Mapping[str, str]) -> dict[str, Any]:
    """비밀값을 결과에 포함하지 않는 읽기 전용 연결 옵션을 만든다."""

    missing = tuple(
        key for key in REQUIRED_ENV_KEYS if not environ.get(key, "").strip()
    )
    if missing:
        raise ConfigurationError(
            "missing_required_environment",
            missing_keys=missing,
        )

    try:
        port = int(environ["POSTGRES_PORT"])
    except ValueError as exc:
        raise ConfigurationError("invalid_port") from exc
    if not 1 <= port <= 65535:
        raise ConfigurationError("invalid_port")

    try:
        transport_options = build_postgres_connection_options(
            environ,
            base_dir=BACKEND_DIR,
        )
    except PostgresConnectionConfigurationError as exc:
        raise ConfigurationError(
            exc.reason,
            missing_keys=exc.missing_keys,
        ) from None

    return {
        "dbname": environ["POSTGRES_DB"],
        "user": environ["POSTGRES_USER"],
        "password": environ["POSTGRES_PASSWORD"],
        "host": environ["POSTGRES_HOST"],
        "port": port,
        "options": "-c default_transaction_read_only=on",
        **transport_options,
    }


def _scalar(cursor: Any, query: str, parameters: tuple[Any, ...] = ()) -> Any:
    cursor.execute(query, parameters)
    row = cursor.fetchone()
    return None if row is None else row[0]


def _table_privilege(
    cursor: Any,
    role_name: str,
    table_name: str,
    privilege: str,
) -> bool:
    return bool(
        _scalar(
            cursor,
            "SELECT has_table_privilege(%s, %s, %s)",
            (role_name, table_name, privilege),
        )
    )


def collect_snapshot(
    connection_options: dict[str, Any],
    connect: Callable[..., Any],
) -> dict[str, Any]:
    """현재 PostgreSQL의 G1-B 관련 사실만 SELECT로 수집한다."""

    with connect(**connection_options) as connection:
        with connection.cursor() as cursor:
            database_name = _scalar(cursor, "SELECT current_database()")
            server_version = _scalar(cursor, "SHOW server_version")
            pgvector_version = _scalar(
                cursor,
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'",
            )

            migrations_table_exists = bool(
                _scalar(
                    cursor,
                    "SELECT to_regclass('public.django_migrations') "
                    "IS NOT NULL",
                )
            )
            applied_migrations: list[str] = []
            if migrations_table_exists:
                cursor.execute(
                    "SELECT name FROM django_migrations "
                    "WHERE app = 'evidence' AND name = ANY(%s) "
                    "ORDER BY name",
                    (list(REQUIRED_MIGRATIONS),),
                )
                applied_migrations = [row[0] for row in cursor.fetchall()]

            crosswalk_table_exists = bool(
                _scalar(
                    cursor,
                    "SELECT to_regclass("
                    "'public.knowledge_ai_chunk_crosswalk') IS NOT NULL",
                )
            )
            active_verified_count = 0
            baseline_identity_count = 0
            if crosswalk_table_exists:
                cursor.execute(
                    "SELECT "
                    "COUNT(*) FILTER (WHERE is_active AND is_verified "
                    "AND canonical_verification_status = "
                    "'TEXT_AND_VISUAL_VERIFIED'), "
                    "COUNT(*) FILTER (WHERE is_active AND is_verified "
                    "AND canonical_verification_status = "
                    "'TEXT_AND_VISUAL_VERIFIED' "
                    "AND embedding_model = %s "
                    "AND embedding_model_version = %s) "
                    "FROM knowledge_ai_chunk_crosswalk",
                    (EXPECTED_EMBEDDING_MODEL, EXPECTED_EMBEDDING_REVISION),
                )
                row = cursor.fetchone()
                active_verified_count = int(row[0])
                baseline_identity_count = int(row[1])

            crosswalk_page_table_exists = bool(
                _scalar(
                    cursor,
                    "SELECT to_regclass("
                    "'public.knowledge_ai_chunk_crosswalk_page') IS NOT NULL",
                )
            )
            crosswalk_page_link_count = 0
            if crosswalk_table_exists and crosswalk_page_table_exists:
                crosswalk_page_link_count = int(
                    _scalar(
                        cursor,
                        "SELECT COUNT(*) "
                        "FROM knowledge_ai_chunk_crosswalk_page AS page_link "
                        "JOIN knowledge_ai_chunk_crosswalk AS crosswalk "
                        "ON crosswalk.id = page_link.crosswalk_id "
                        "WHERE crosswalk.is_active "
                        "AND crosswalk.is_verified "
                        "AND crosswalk.canonical_verification_status = "
                        "'TEXT_AND_VISUAL_VERIFIED' "
                        "AND crosswalk.embedding_model = %s "
                        "AND crosswalk.embedding_model_version = %s",
                        (
                            EXPECTED_EMBEDDING_MODEL,
                            EXPECTED_EMBEDDING_REVISION,
                        ),
                    )
                    or 0
                )

            view_exists = bool(
                _scalar(
                    cursor,
                    "SELECT to_regclass(%s) IS NOT NULL",
                    (EXPECTED_VIEW,),
                )
            )
            view_columns: list[str] = []
            view_row_count = 0
            view_distinct_chunk_count = 0
            if view_exists:
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' "
                    "AND table_name = 'backend_ai_rag_chunks_v1' "
                    "ORDER BY ordinal_position"
                )
                view_columns = [row[0] for row in cursor.fetchall()]
                cursor.execute(
                    "SELECT COUNT(*), COUNT(DISTINCT chunk_id) "
                    "FROM public.backend_ai_rag_chunks_v1"
                )
                row = cursor.fetchone()
                view_row_count = int(row[0])
                view_distinct_chunk_count = int(row[1])

            cursor.execute(
                "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, "
                "rolreplication, rolbypassrls, "
                "(SELECT COUNT(*) FROM pg_auth_members membership "
                "WHERE membership.member = role_row.oid "
                "OR membership.roleid = role_row.oid) "
                "FROM pg_roles role_row WHERE rolname = %s",
                (AI_READONLY_ROLE,),
            )
            role_row = cursor.fetchone()
            role_exists = role_row is not None
            role_policy_safe = False
            default_transaction_read_only = False
            schema_create = False
            view_select = False
            view_dml = False
            base_table_select = False
            if role_exists:
                role_policy_safe = bool(
                    role_row[0] is True
                    and all(value is False for value in role_row[1:6])
                    and role_row[6] == 0
                )
                default_transaction_read_only = bool(
                    _scalar(
                        cursor,
                        "SELECT EXISTS ("
                        "SELECT 1 FROM pg_db_role_setting setting "
                        "JOIN pg_roles role_row "
                        "ON role_row.oid = setting.setrole "
                        "JOIN pg_database database_row "
                        "ON database_row.oid = setting.setdatabase "
                        "CROSS JOIN LATERAL unnest(setting.setconfig) "
                        "AS config(value) "
                        "WHERE role_row.rolname = %s "
                        "AND database_row.datname = current_database() "
                        "AND config.value = "
                        "'default_transaction_read_only=on')",
                        (AI_READONLY_ROLE,),
                    )
                )
                schema_create = bool(
                    _scalar(
                        cursor,
                        "SELECT has_schema_privilege(%s, 'public', 'CREATE')",
                        (AI_READONLY_ROLE,),
                    )
                )
                if view_exists:
                    view_select = _table_privilege(
                        cursor,
                        AI_READONLY_ROLE,
                        EXPECTED_VIEW,
                        "SELECT",
                    )
                    view_dml = any(
                        _table_privilege(
                            cursor,
                            AI_READONLY_ROLE,
                            EXPECTED_VIEW,
                            privilege,
                        )
                        for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE")
                    )
                if crosswalk_table_exists:
                    base_table_select = any(
                        _table_privilege(
                            cursor,
                            AI_READONLY_ROLE,
                            table_name,
                            "SELECT",
                        )
                        for table_name in BASE_TABLES
                    )

    return {
        "database_name": database_name,
        "server_version": server_version,
        "pgvector_version": pgvector_version,
        "migrations_table_exists": migrations_table_exists,
        "applied_migrations": applied_migrations,
        "crosswalk_table_exists": crosswalk_table_exists,
        "active_verified_count": active_verified_count,
        "baseline_identity_count": baseline_identity_count,
        "crosswalk_page_table_exists": crosswalk_page_table_exists,
        "crosswalk_page_link_count": crosswalk_page_link_count,
        "view_exists": view_exists,
        "view_columns": view_columns,
        "view_row_count": view_row_count,
        "view_distinct_chunk_count": view_distinct_chunk_count,
        "role_exists": role_exists,
        "role_policy_safe": role_policy_safe,
        "default_transaction_read_only": default_transaction_read_only,
        "schema_create": schema_create,
        "view_select": view_select,
        "view_dml": view_dml,
        "base_table_select": base_table_select,
    }


def evaluate_snapshot(
    snapshot: Mapping[str, Any],
    *,
    require_team_database: bool = False,
    evidence_profile: str = "baseline",
) -> dict[str, Any]:
    """수집값을 공개 가능한 READY/BLOCKED 판정으로 바꾼다."""

    if evidence_profile not in EVIDENCE_PROFILES:
        raise ValueError("Unsupported Backend-AI evidence profile.")
    expectations = EVIDENCE_PROFILES[evidence_profile]
    expected_chunk_count = expectations["chunk_count"]
    expected_page_link_count = expectations["page_link_count"]
    blockers: list[str] = []
    pgvector_version = snapshot.get("pgvector_version")
    crosswalk_page_table_exists = bool(
        snapshot.get("crosswalk_page_table_exists", False)
    )
    crosswalk_page_link_count = int(
        snapshot.get("crosswalk_page_link_count", 0)
    )
    if require_team_database and snapshot["database_name"] != TEAM_INTEGRATION_DATABASE:
        blockers.append("TEAM_INTEGRATION_DATABASE_MISMATCH")
    if not pgvector_version:
        blockers.append("PGVECTOR_EXTENSION_MISSING")
    elif not is_supported_pgvector_version(pgvector_version):
        blockers.append("PGVECTOR_VERSION_MISMATCH")
    if not snapshot["migrations_table_exists"]:
        blockers.append("DJANGO_MIGRATIONS_TABLE_MISSING")
    missing_migrations = sorted(
        set(REQUIRED_MIGRATIONS) - set(snapshot["applied_migrations"])
    )
    blockers.extend(f"MIGRATION_MISSING:{name}" for name in missing_migrations)
    if not snapshot["crosswalk_table_exists"]:
        blockers.append("CROSSWALK_TABLE_MISSING")
    if snapshot["active_verified_count"] != expected_chunk_count:
        blockers.append(
            f"ACTIVE_VERIFIED_CROSSWALK_COUNT_NOT_{expected_chunk_count}"
        )
    if snapshot["baseline_identity_count"] != expected_chunk_count:
        blockers.append(
            f"BASELINE_EMBEDDING_IDENTITY_COUNT_NOT_{expected_chunk_count}"
        )
    if not crosswalk_page_table_exists:
        blockers.append("CROSSWALK_PAGE_TABLE_MISSING")
    if crosswalk_page_link_count != expected_page_link_count:
        blockers.append(
            "ACTIVE_VERIFIED_CROSSWALK_PAGE_LINK_COUNT_NOT_"
            f"{expected_page_link_count}"
        )
    if not snapshot["view_exists"]:
        blockers.append("BACKEND_AI_RAG_VIEW_MISSING")
    if tuple(snapshot["view_columns"]) != EXPECTED_VIEW_COLUMNS:
        blockers.append("BACKEND_AI_RAG_VIEW_COLUMNS_MISMATCH")
    if snapshot["view_row_count"] != expected_chunk_count:
        blockers.append(f"BACKEND_AI_RAG_VIEW_ROW_COUNT_NOT_{expected_chunk_count}")
    if snapshot["view_distinct_chunk_count"] != snapshot["view_row_count"]:
        blockers.append("BACKEND_AI_RAG_VIEW_CHUNK_ID_NOT_UNIQUE")
    if not snapshot["role_exists"]:
        blockers.append("AI_READONLY_ROLE_MISSING")
    if not snapshot["role_policy_safe"]:
        blockers.append("AI_READONLY_ROLE_POLICY_MISMATCH")
    if not snapshot["default_transaction_read_only"]:
        blockers.append("AI_READONLY_DEFAULT_TRANSACTION_NOT_READ_ONLY")
    if snapshot["schema_create"]:
        blockers.append("AI_READONLY_SCHEMA_CREATE_ALLOWED")
    if not snapshot["view_select"]:
        blockers.append("AI_READONLY_VIEW_SELECT_DENIED")
    if snapshot["view_dml"]:
        blockers.append("AI_READONLY_VIEW_DML_ALLOWED")
    if snapshot["base_table_select"]:
        blockers.append("AI_READONLY_BASE_TABLE_SELECT_ALLOWED")

    return {
        "status": "READY" if not blockers else "BLOCKED",
        "scope": "BACKEND_AI_G1B_READINESS",
        "evidence_profile": evidence_profile,
        "database": {
            "name": snapshot["database_name"],
            "server_version": snapshot["server_version"],
            "pgvector_version": pgvector_version,
            "expected_pgvector_version": EXPECTED_PGVECTOR_VERSION,
            "preferred_pgvector_version": PREFERRED_PGVECTOR_VERSION,
            "supported_pgvector_versions": list(SUPPORTED_PGVECTOR_VERSIONS),
            "pgvector_version_supported": is_supported_pgvector_version(
                pgvector_version
            ),
            "team_integration_required": require_team_database,
        },
        "migrations": {
            "required": list(REQUIRED_MIGRATIONS),
            "applied": list(snapshot["applied_migrations"]),
            "missing": missing_migrations,
        },
        "crosswalk": {
            "expected": expected_chunk_count,
            "active_verified": snapshot["active_verified_count"],
            "baseline_identity": snapshot["baseline_identity_count"],
            "page_table_exists": crosswalk_page_table_exists,
            "page_links_expected": expected_page_link_count,
            "page_links": crosswalk_page_link_count,
        },
        "view": {
            "name": EXPECTED_VIEW,
            "exists": snapshot["view_exists"],
            "columns": list(snapshot["view_columns"]),
            "expected_columns": list(EXPECTED_VIEW_COLUMNS),
            "rows": snapshot["view_row_count"],
            "distinct_chunk_ids": snapshot["view_distinct_chunk_count"],
        },
        "ai_readonly_role": {
            "name": AI_READONLY_ROLE,
            "exists": snapshot["role_exists"],
            "policy_safe": snapshot["role_policy_safe"],
            "default_transaction_read_only": snapshot[
                "default_transaction_read_only"
            ],
            "schema_create": snapshot["schema_create"],
            "view_select": snapshot["view_select"],
            "view_dml": snapshot["view_dml"],
            "base_table_select": snapshot["base_table_select"],
        },
        "blockers": blockers,
        "secret_values_printed": False,
    }


def run_audit(
    environ: Mapping[str, str],
    *,
    require_ready: bool = False,
    require_team_database: bool = False,
    evidence_profile: str = "baseline",
    connect: Callable[..., Any] = psycopg.connect,
) -> tuple[dict[str, Any], int]:
    """설정·연결 실패도 비밀 없는 구조화 결과로 반환한다."""

    try:
        connection_options = load_connection_options(environ)
    except ConfigurationError as exc:
        return (
            {
                "status": "NOT_CONFIGURED",
                "scope": "BACKEND_AI_G1B_READINESS",
                "reason": exc.reason,
                "missing_keys": list(exc.missing_keys),
                "secret_values_printed": False,
            },
            2,
        )

    try:
        snapshot = collect_snapshot(connection_options, connect)
        result = evaluate_snapshot(
            snapshot,
            require_team_database=require_team_database,
            evidence_profile=evidence_profile,
        )
    except Exception as exc:  # noqa: BLE001 - 비밀 없는 진단 결과로 변환
        return (
            {
                "status": "AUDIT_FAILED",
                "scope": "BACKEND_AI_G1B_READINESS",
                "error_type": type(exc).__name__,
                "message": (
                    "읽기 전용 감사에 실패했습니다. 원본 오류·Host·DSN·"
                    "사용자·비밀번호는 출력하지 않습니다."
                ),
                "secret_values_printed": False,
            },
            1,
        )

    if require_ready and result["status"] != "READY":
        return result, 1
    return result, 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="READY가 아니면 Exit 1을 반환한다.",
    )
    parser.add_argument(
        "--evidence-profile",
        choices=tuple(EVIDENCE_PROFILES),
        default="baseline",
        help=(
            "baseline은 기존 7건, three-model은 15/19/19 합계 53건 "
            "Crosswalk·View를 검증한다."
        ),
    )
    parser.add_argument(
        "--require-team-database",
        action="store_true",
        help=(
            "현재 DB가 waterbridge_team_integration인지도 완료 조건으로 "
            "검증한다."
        ),
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    load_backend_env()
    result, exit_code = run_audit(
        os.environ,
        require_ready=arguments.require_ready,
        require_team_database=arguments.require_team_database,
        evidence_profile=arguments.evidence_profile,
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
