"""Separate verified AI retrieval eligibility from public MVP support."""

from importlib import import_module

from django.db import migrations


VIEW_NAME = "backend_ai_rag_chunks_v1"
BASE_MIGRATION = import_module(
    "apps.evidence.migrations.0013_expand_backend_ai_rag_lineage_metadata"
)
BASE_CREATE_VIEW_SQL = BASE_MIGRATION.CREATE_VIEW_SQL

PUBLIC_PRODUCT_FILTER = "  AND product.is_supported_mvp = TRUE\n"
THREE_MODEL_AI_ELIGIBILITY_FILTER = """  AND product.model_code IN (
      'WPUJAC104DWH',
      'WPUIAC425SNW',
      'WPUIAC606SNW'
  )
  AND chunk.chunking_version = 'rag_child_chunks_3model/1.0.0'
  AND crosswalk.canonical_chunk_id LIKE (
      'CHILD-' || product.model_code || '-P'
      || lpad(primary_page.page_no::text, 3, '0') || '-%'
  )
"""


def _as_create_or_replace(sql: str) -> str:
    marker = f"CREATE VIEW {VIEW_NAME}"
    if marker not in sql:
        raise RuntimeError("AI read-only view CREATE marker is unavailable.")
    return sql.replace(
        marker,
        f"CREATE OR REPLACE VIEW {VIEW_NAME}",
        1,
    )


if PUBLIC_PRODUCT_FILTER not in BASE_CREATE_VIEW_SQL:
    raise RuntimeError("AI read-only view product filter marker is unavailable.")

CREATE_VIEW_SQL = _as_create_or_replace(
    BASE_CREATE_VIEW_SQL.replace(
        PUBLIC_PRODUCT_FILTER,
        THREE_MODEL_AI_ELIGIBILITY_FILTER,
        1,
    )
)
RESTORE_VIEW_SQL = _as_create_or_replace(BASE_CREATE_VIEW_SQL)


def create_ai_eligible_view(apps, schema_editor):
    """Replace the view without changing product flags or existing grants."""

    if schema_editor.connection.vendor != "postgresql":
        return
    # Static DDL contains literal LIKE wildcards. ``params=None`` prevents
    # psycopg from treating those percent signs as client-side placeholders.
    schema_editor.execute(CREATE_VIEW_SQL, params=None)


def restore_public_mvp_view(apps, schema_editor):
    """Restore the evidence.0013 public-MVP eligibility filter on rollback."""

    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RESTORE_VIEW_SQL, params=None)


class Migration(migrations.Migration):
    dependencies = [
        ("evidence", "0013_expand_backend_ai_rag_lineage_metadata"),
    ]

    operations = [
        migrations.RunPython(
            create_ai_eligible_view,
            reverse_code=restore_public_mvp_view,
        ),
    ]
