"""Safe version metadata for an already approved readonly evaluation target."""

import psycopg
from psycopg.rows import dict_row

from ai.app.common.protected_database import run_protected_database_operation


def read_database_versions(dsn: str) -> dict:
    def read():
        with psycopg.connect(dsn, connect_timeout=5) as connection:
            connection.read_only = True
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SET LOCAL statement_timeout = '5s'")
                cursor.execute(
                    "SELECT current_setting('server_version') AS postgresql_version, "
                    "extversion AS pgvector_version FROM pg_extension WHERE extname = 'vector'"
                )
                version = cursor.fetchone()
                if version is None:
                    raise ValueError("PGVECTOR_VERSION_NOT_AVAILABLE")
                return version
    return run_protected_database_operation(read, public_message="Readonly version inspection failed.")
