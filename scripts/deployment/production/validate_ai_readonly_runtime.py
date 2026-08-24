"""Validate the production AI RDS role without exposing its protected DSN."""

from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql


VIEW_NAME = "backend_ai_rag_chunks_v1"
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


def main() -> int:
    try:
        dsn = os.environ["AI_VECTOR_DSN"]
        if os.environ.get("AI_VECTOR_TABLE_NAME") != VIEW_NAME:
            raise RuntimeError("unexpected AI view")

        with (
            psycopg.connect(dsn, connect_timeout=5) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SHOW server_version_num")
            if cursor.fetchone() != ("160014",):
                raise RuntimeError("unexpected PostgreSQL version")
            cursor.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            )
            if cursor.fetchone() != ("0.8.2",):
                raise RuntimeError("unexpected pgvector version")
            cursor.execute("SHOW default_transaction_read_only")
            if cursor.fetchone() != ("on",):
                raise RuntimeError("AI transaction is not read-only")
            cursor.execute(
                "SELECT has_schema_privilege(current_user, 'public', 'CREATE')"
            )
            if cursor.fetchone() != (False,):
                raise RuntimeError("AI role can create in public schema")
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

            cursor.execute(
                sql.SQL(
                    """
                    SELECT COUNT(*), COUNT(DISTINCT chunk_id),
                           MIN(vector_dims(embedding)), MAX(vector_dims(embedding))
                    FROM {}
                    """
                ).format(sql.Identifier(VIEW_NAME))
            )
            if cursor.fetchone() != (53, 53, 1024, 1024):
                raise RuntimeError("AI view count or vector dimension mismatch")
            cursor.execute(
                sql.SQL(
                    "SELECT model_code, COUNT(*) FROM {} GROUP BY model_code ORDER BY model_code"
                ).format(sql.Identifier(VIEW_NAME))
            )
            if dict(cursor.fetchall()) != EXPECTED_MODEL_COUNTS:
                raise RuntimeError("AI view model distribution mismatch")
    except Exception:
        print("AI_READONLY_RUNTIME_PREFLIGHT_FAILED", file=sys.stderr)
        return 1

    print("AI_READONLY_RUNTIME_PREFLIGHT_PASS")
    print("view_select=ONLY_APPROVED_VIEW")
    print("view_rows=53")
    print("vector_dimensions=1024")
    print("base_table_access=DENIED")
    print("transaction=READ_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
