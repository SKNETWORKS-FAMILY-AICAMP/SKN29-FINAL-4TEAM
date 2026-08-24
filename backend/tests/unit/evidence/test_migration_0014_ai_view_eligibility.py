"""Regression tests for the AI-only product eligibility view migration."""

from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock, call


def _migration():
    return import_module(
        "apps.evidence.migrations."
        "0014_decouple_ai_view_product_eligibility"
    )


def _schema_editor(vendor: str):
    return SimpleNamespace(
        connection=SimpleNamespace(vendor=vendor),
        execute=Mock(),
    )


def test_forward_replaces_view_without_dropping_grants_or_product_flags():
    migration = _migration()
    schema_editor = _schema_editor("postgresql")

    migration.create_ai_eligible_view(None, schema_editor)

    assert schema_editor.execute.call_args_list == [
        call(migration.CREATE_VIEW_SQL, params=None),
    ]
    assert "CREATE OR REPLACE VIEW" in migration.CREATE_VIEW_SQL
    assert "DROP VIEW" not in migration.CREATE_VIEW_SQL
    assert "product.is_supported_mvp = TRUE" not in migration.CREATE_VIEW_SQL
    assert "UPDATE catalog_product_model" not in migration.CREATE_VIEW_SQL


def test_forward_adds_only_exact_verified_three_model_candidate_identity():
    migration = _migration()
    sql = migration.CREATE_VIEW_SQL

    assert migration.Migration.dependencies == [
        ("evidence", "0013_expand_backend_ai_rag_lineage_metadata"),
    ]
    for model_code in (
        "WPUJAC104DWH",
        "WPUIAC425SNW",
        "WPUIAC606SNW",
    ):
        assert f"'{model_code}'" in sql
    assert "rag_child_chunks_3model/1.0.0" in sql
    assert "'CHILD-' || product.model_code" in sql
    assert "crosswalk.is_active = TRUE" in sql
    assert "crosswalk.is_verified = TRUE" in sql
    assert "TEXT_AND_VISUAL_VERIFIED" in sql
    assert "knowledge_data_quality_issue" in sql
    assert "vector_dims(embedding.embedding) = 1024" in sql
    assert "INSERT" not in sql
    assert "UPDATE" not in sql
    assert "DELETE" not in sql


def test_reverse_restores_0013_filter_without_dropping_view():
    migration = _migration()
    schema_editor = _schema_editor("postgresql")

    migration.restore_public_mvp_view(None, schema_editor)

    assert schema_editor.execute.call_args_list == [
        call(migration.RESTORE_VIEW_SQL, params=None),
    ]
    assert "CREATE OR REPLACE VIEW" in migration.RESTORE_VIEW_SQL
    assert migration.PUBLIC_PRODUCT_FILTER in migration.RESTORE_VIEW_SQL
    assert "rag_child_chunks_3model/1.0.0" in migration.RESTORE_VIEW_SQL
    assert "DROP VIEW" not in migration.RESTORE_VIEW_SQL


def test_non_postgresql_database_does_not_execute_view_sql():
    migration = _migration()
    schema_editor = _schema_editor("sqlite")

    migration.create_ai_eligible_view(None, schema_editor)
    migration.restore_public_mvp_view(None, schema_editor)

    schema_editor.execute.assert_not_called()
