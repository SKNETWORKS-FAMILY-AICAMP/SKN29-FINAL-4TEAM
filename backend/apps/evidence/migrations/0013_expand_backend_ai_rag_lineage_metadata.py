"""Project approved three-model retrieval lineage through the AI read-only view."""

from importlib import import_module

from django.db import migrations


VIEW_NAME = "backend_ai_rag_chunks_v1"
BASE_MIGRATION = import_module(
    "apps.evidence.migrations.0010_backend_ai_rag_chunks_view"
)
BASE_CREATE_VIEW_SQL = BASE_MIGRATION.CREATE_VIEW_SQL

METADATA_MARKER = """        'chunk_set_sha256', lower(crosswalk.chunk_set_sha256),
"""
LINEAGE_METADATA_SQL = """        'evidence_group_id',
            NULLIF(chunk.metadata ->> 'evidence_group_id', ''),
        'source_variant_id',
            NULLIF(chunk.metadata ->> 'source_variant_id', ''),
        'parent_id',
            CASE
                WHEN chunk.chunking_version = 'rag_child_chunks_3model/1.0.0'
                 AND crosswalk.canonical_chunk_id LIKE (
                    'CHILD-' || product.model_code || '-P'
                    || lpad(primary_page.page_no::text, 3, '0') || '-%'
                 )
                THEN COALESCE(
                    NULLIF(chunk.metadata ->> 'parent_id', ''),
                    'PARENT-' || product.model_code || '-P'
                    || lpad(primary_page.page_no::text, 3, '0')
                )
                ELSE NULLIF(chunk.metadata ->> 'parent_id', '')
            END,
        'retrieval_role',
            CASE
                WHEN chunk.chunking_version = 'rag_child_chunks_3model/1.0.0'
                 AND crosswalk.canonical_chunk_id LIKE (
                    'CHILD-' || product.model_code || '-P'
                    || lpad(primary_page.page_no::text, 3, '0') || '-%'
                 )
                THEN COALESCE(
                    NULLIF(chunk.metadata ->> 'retrieval_role', ''),
                    'SEARCH_CANDIDATE'
                )
                ELSE NULLIF(chunk.metadata ->> 'retrieval_role', '')
            END,
"""

FILTER_MARKER = """WHERE crosswalk.is_active = TRUE
"""
LINEAGE_FILTER_SQL = """WHERE (
    crosswalk.canonical_chunk_id !~ '^CHILD-'
    OR (
        chunk.chunking_version = 'rag_child_chunks_3model/1.0.0'
        AND crosswalk.canonical_chunk_id LIKE (
            'CHILD-' || product.model_code || '-P'
            || lpad(primary_page.page_no::text, 3, '0') || '-%'
        )
        AND NULLIF(chunk.metadata ->> 'evidence_group_id', '') IS NOT NULL
        AND NULLIF(chunk.metadata ->> 'source_variant_id', '') IS NOT NULL
        AND (
            NULLIF(chunk.metadata ->> 'parent_id', '') IS NULL
            OR chunk.metadata ->> 'parent_id' = (
                'PARENT-' || product.model_code || '-P'
                || lpad(primary_page.page_no::text, 3, '0')
            )
        )
        AND (
            NULLIF(chunk.metadata ->> 'retrieval_role', '') IS NULL
            OR chunk.metadata ->> 'retrieval_role' = 'SEARCH_CANDIDATE'
        )
    )
)
  AND crosswalk.is_active = TRUE
"""

if METADATA_MARKER not in BASE_CREATE_VIEW_SQL:
    raise RuntimeError("AI read-only view metadata marker is unavailable.")
if FILTER_MARKER not in BASE_CREATE_VIEW_SQL:
    raise RuntimeError("AI read-only view filter marker is unavailable.")

CREATE_VIEW_SQL = BASE_CREATE_VIEW_SQL.replace(
    METADATA_MARKER,
    METADATA_MARKER + LINEAGE_METADATA_SQL,
    1,
).replace(
    FILTER_MARKER,
    LINEAGE_FILTER_SQL,
    1,
)


def create_lineage_view(apps, schema_editor):
    """Replace only the PostgreSQL view; source tables remain unchanged."""

    if schema_editor.connection.vendor != "postgresql":
        return
    # Static DDL contains literal LIKE wildcards. ``params=None`` prevents
    # psycopg from treating those percent signs as client-side placeholders.
    schema_editor.execute(f"DROP VIEW IF EXISTS {VIEW_NAME}", params=None)
    schema_editor.execute(CREATE_VIEW_SQL, params=None)


def restore_previous_view(apps, schema_editor):
    """Restore the evidence.0010 view when rolling this migration back."""

    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP VIEW IF EXISTS {VIEW_NAME}", params=None)
    schema_editor.execute(BASE_CREATE_VIEW_SQL, params=None)


class Migration(migrations.Migration):
    dependencies = [
        ("evidence", "0012_expand_ai_crosswalk_canonical_id"),
    ]

    operations = [
        migrations.RunPython(
            create_lineage_view,
            reverse_code=restore_previous_view,
        ),
    ]
