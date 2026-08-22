"""Regression tests for the PostgreSQL lineage view migration."""

from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock, call


def _migration():
    return import_module(
        "apps.evidence.migrations.0013_expand_backend_ai_rag_lineage_metadata"
    )


def _schema_editor(vendor: str):
    return SimpleNamespace(
        connection=SimpleNamespace(vendor=vendor),
        execute=Mock(),
    )


def test_forward_postgresql_static_view_sql_disables_parameter_composition():
    migration = _migration()
    schema_editor = _schema_editor("postgresql")

    migration.create_lineage_view(None, schema_editor)

    assert migration.CREATE_VIEW_SQL.count("'-%'") == 3
    assert schema_editor.execute.call_args_list == [
        call(f"DROP VIEW IF EXISTS {migration.VIEW_NAME}", params=None),
        call(migration.CREATE_VIEW_SQL, params=None),
    ]


def test_reverse_postgresql_static_view_sql_disables_parameter_composition():
    migration = _migration()
    schema_editor = _schema_editor("postgresql")

    migration.restore_previous_view(None, schema_editor)

    assert schema_editor.execute.call_args_list == [
        call(f"DROP VIEW IF EXISTS {migration.VIEW_NAME}", params=None),
        call(migration.BASE_CREATE_VIEW_SQL, params=None),
    ]


def test_non_postgresql_database_does_not_execute_view_sql():
    migration = _migration()
    schema_editor = _schema_editor("sqlite")

    migration.create_lineage_view(None, schema_editor)
    migration.restore_previous_view(None, schema_editor)

    schema_editor.execute.assert_not_called()
