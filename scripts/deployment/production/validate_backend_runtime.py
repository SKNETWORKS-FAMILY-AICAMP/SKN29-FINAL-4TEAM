"""Read-only production RDS and Django migration boundary validation."""

from __future__ import annotations

import os
import sys


EXPECTED_PENDING = {
    ("visits", "0005_replace_visit_result_assignment_fk"),
}


def main() -> int:
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
        import django

        django.setup()

        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        with connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            if cursor.fetchone() != ("160014",):
                raise RuntimeError("unexpected PostgreSQL version")

            cursor.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            )
            if cursor.fetchone() != ("0.8.6",):
                raise RuntimeError("unexpected pgvector version")

            cursor.execute(
                """
                SELECT app, name
                FROM django_migrations
                WHERE (app = 'evidence' AND name = '0013_expand_backend_ai_rag_lineage_metadata')
                   OR (app = 'visits' AND name = '0005_replace_visit_result_assignment_fk')
                ORDER BY app, name
                """
            )
            applied = set(cursor.fetchall())
            if (
                "evidence",
                "0013_expand_backend_ai_rag_lineage_metadata",
            ) not in applied:
                raise RuntimeError("evidence.0013 is not applied")
            if (
                "visits",
                "0005_replace_visit_result_assignment_fk",
            ) in applied:
                raise RuntimeError("visits.0005 P1 HOLD was applied")

        executor = MigrationExecutor(connection)
        pending = {
            (migration.app_label, migration.name)
            for migration, backwards in executor.migration_plan(
                executor.loader.graph.leaf_nodes()
            )
            if not backwards
        }
        if pending != EXPECTED_PENDING:
            raise RuntimeError("unexpected migration plan")
        connection.close()
    except Exception:
        print("BACKEND_RUNTIME_PREFLIGHT_FAILED", file=sys.stderr)
        return 1

    print("BACKEND_RUNTIME_PREFLIGHT_PASS")
    print("postgresql=16.14")
    print("pgvector=0.8.6")
    print("evidence.0013=APPLIED")
    print("visits.0005=NOT_APPLIED_P1_HOLD")
    print("migration_plan=VISITS_0005_ONLY_HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
