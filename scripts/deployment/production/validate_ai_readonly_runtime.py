"""Validate the production AI RDS role without exposing its protected DSN."""

from __future__ import annotations

import os
import re
import sys

import psycopg
from psycopg import sql


VIEW_NAME = "backend_ai_rag_chunks_v1"
SUPPORTED_PGVECTOR_VERSIONS = ("0.8.2", "0.8.6")
EXPECTED_MODEL_COUNTS = {
    "WPUJAC104DWH": 15,
    "WPUIAC425SNW": 19,
    "WPUIAC606SNW": 19,
}
FORBIDDEN_TABLES = (
    "accounts_user",
    "django_migrations",
    "knowledge_document_chunk",
    "knowledge_chunk_embedding",
    "knowledge_ai_chunk_crosswalk",
)
RELEASE_SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$")


def main() -> int:
    stage = "ENVIRONMENT"
    try:
        if os.environ.get("AI_HUMAN_REVIEW_RESUME_ENABLED", "").strip().lower() != "false":
            raise RuntimeError("AI Resume must start disabled")
        if len(os.environ.get("AI_HUMAN_REVIEW_RESUME_TOKEN", "").encode("utf-8")) < 32:
            raise RuntimeError("AI Resume token is missing")
        if os.environ.get("AI_HANDOFF_BACKEND_ENABLED", "").strip().lower() != "false":
            raise RuntimeError("AI Handoff must start disabled")
        release_sha = os.environ["RELEASE_SHA"].strip().lower()
        if RELEASE_SHA_PATTERN.fullmatch(release_sha) is None:
            raise RuntimeError("invalid AI release SHA")
        dsn = os.environ["AI_VECTOR_DSN"]
        if os.environ.get("AI_VECTOR_TABLE_NAME") != VIEW_NAME:
            raise RuntimeError("unexpected AI view")

        stage = "DATABASE_CONNECTION"
        with (
            psycopg.connect(dsn, connect_timeout=5) as connection,
            connection.cursor() as cursor,
        ):
            stage = "POSTGRES_VERSION"
            cursor.execute("SHOW server_version_num")
            if cursor.fetchone() != ("160014",):
                raise RuntimeError("unexpected PostgreSQL version")
            stage = "PGVECTOR_VERSION"
            cursor.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            )
            pgvector_row = cursor.fetchone()
            pgvector_version = None if pgvector_row is None else pgvector_row[0]
            if pgvector_version not in SUPPORTED_PGVECTOR_VERSIONS:
                raise RuntimeError("unexpected pgvector version")
            stage = "TRANSACTION_READ_ONLY"
            cursor.execute("SHOW default_transaction_read_only")
            if cursor.fetchone() != ("on",):
                raise RuntimeError("AI transaction is not read-only")
            stage = "PUBLIC_SCHEMA_PRIVILEGE"
            cursor.execute(
                "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"
            )
            if cursor.fetchone() != (False,):
                raise RuntimeError("AI role can create in public schema")
            stage = "VIEW_PRIVILEGE_BOUNDARY"
            cursor.execute(
                """
                SELECT c.relkind,
                       has_table_privilege(current_user, c.oid, 'SELECT'),
                       has_table_privilege(current_user, c.oid, 'INSERT'),
                       has_table_privilege(current_user, c.oid, 'UPDATE'),
                       has_table_privilege(current_user, c.oid, 'DELETE'),
                       has_table_privilege(current_user, c.oid, 'TRUNCATE')
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = %s
                """,
                (VIEW_NAME,),
            )
            if cursor.fetchone() != ("v", True, False, False, False, False):
                raise RuntimeError("AI view privilege boundary mismatch")

            stage = "BASE_TABLE_BOUNDARY"
            for table_name in FORBIDDEN_TABLES:
                cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
                if cursor.fetchone()[0] is None:
                    raise RuntimeError("required base relation is missing")
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                    cursor.execute(
                        "SELECT has_table_privilege(current_user, %s, %s)",
                        (f"public.{table_name}", privilege),
                    )
                    if cursor.fetchone() != (False,):
                        raise RuntimeError("AI role can access a base table")

            stage = "VIEW_COUNTS_AND_LINEAGE"
            cursor.execute(
                sql.SQL(
                    """
                    SELECT COUNT(*), COUNT(DISTINCT chunk_id),
                           MIN(vector_dims(embedding)), MAX(vector_dims(embedding)),
                           COUNT(*) FILTER (WHERE
                               NULLIF(metadata ->> 'evidence_group_id', '') IS NOT NULL
                               AND NULLIF(metadata ->> 'source_variant_id', '') IS NOT NULL
                               AND NULLIF(metadata ->> 'parent_id', '') IS NOT NULL
                               AND metadata ->> 'retrieval_role' = 'SEARCH_CANDIDATE'
                           )
                    FROM {}
                    """
                ).format(sql.Identifier(VIEW_NAME))
            )
            if cursor.fetchone() != (53, 53, 1024, 1024, 53):
                raise RuntimeError(
                    "AI view count, vector dimension, or lineage mismatch"
                )
            stage = "MODEL_DISTRIBUTION"
            cursor.execute(
                sql.SQL(
                    "SELECT model_code, COUNT(*) FROM {} GROUP BY model_code ORDER BY model_code"
                ).format(sql.Identifier(VIEW_NAME))
            )
            if dict(cursor.fetchall()) != EXPECTED_MODEL_COUNTS:
                raise RuntimeError("AI view model distribution mismatch")
    except Exception as exc:
        print("AI_READONLY_RUNTIME_PREFLIGHT_FAILED", file=sys.stderr)
        print(
            f"reason={stage} error_type={type(exc).__name__}",
            file=sys.stderr,
        )
        return 1

    print("AI_READONLY_RUNTIME_PREFLIGHT_PASS")
    print(f"release_sha={release_sha}")
    print(f"pgvector={pgvector_version}")
    print("view_select=ONLY_APPROVED_VIEW")
    print("view_rows=53")
    print("complete_lineage=53")
    print("vector_dimensions=1024")
    print("base_table_access=DENIED")
    print("transaction=READ_ONLY")
    print("ai_resume=DISABLED_PROTECTED")
    print("ai_handoff=DISABLED_PROTECTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
