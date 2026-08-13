"""Expose verified Backend evidence through an AI-compatible read-only view."""

from django.db import migrations


VIEW_NAME = "backend_ai_rag_chunks_v1"

CREATE_VIEW_SQL = f"""
CREATE VIEW {VIEW_NAME} WITH (security_barrier = true) AS
SELECT
    crosswalk.canonical_chunk_id AS chunk_id,
    jsonb_build_object(
        'document_id', document.document_code,
        'document_title', document.title,
        'document_version', document.revision_label,
        'page', primary_page.page_no,
        'page_refs', page_bundle.page_refs,
        'manual_model', product.model_name,
        'model_code', product.model_code,
        'product_generation', product.generation_code,
        'official_url', document.official_source_url,
        'verification_status', 'official_verified',
        'allowed_use', TRUE,
        'source_hash', lower(document.sha256_hash),
        'embedding_model', embedding.embedding_model,
        'embedding_model_revision', embedding.embedding_model_version,
        'index_version', crosswalk.index_version,
        'chunk_set_sha256', lower(crosswalk.chunk_set_sha256),
        -- Free-form chunk metadata is not promoted into safety instructions.
        'safe_actions', '[]'::jsonb
    ) AS metadata,
    chunk.chunk_text AS content,
    embedding.embedding AS embedding,
    product.model_code AS model_code,
    product.generation_code AS product_generation,
    'official_verified'::text AS verification_status,
    TRUE AS allowed_use
FROM knowledge_ai_chunk_crosswalk AS crosswalk
JOIN knowledge_document_chunk AS chunk
  ON chunk.id = crosswalk.chunk_id
JOIN knowledge_document_page AS primary_page
  ON primary_page.id = chunk.page_id
JOIN knowledge_source_document AS document
  ON document.id = primary_page.document_id
JOIN knowledge_ingestion_batch AS ingestion
  ON ingestion.id = document.ingestion_batch_id
JOIN knowledge_document_model_scope AS model_scope
  ON model_scope.id = crosswalk.model_scope_id
JOIN catalog_product_model AS product
  ON product.id = model_scope.product_model_id
JOIN knowledge_chunk_embedding AS embedding
  ON embedding.chunk_id = chunk.id
 AND embedding.embedding_model = crosswalk.embedding_model
 AND embedding.embedding_model_version = crosswalk.embedding_model_version
JOIN LATERAL (
    SELECT
        jsonb_agg(source_page.page_no ORDER BY mapping.display_order) AS page_refs,
        count(*) AS page_count,
        bool_and(
            source_page.document_id = document.id
            AND source_page.parse_status_code = 'PARSED'
            AND source_page.review_status_code = 'APPROVED'
            AND source_page.is_rag_eligible = TRUE
            AND source_page.exclusion_reason IS NULL
        ) AS all_pages_usable,
        bool_or(source_page.id = primary_page.id) AS contains_primary_page
    FROM knowledge_ai_chunk_crosswalk_page AS mapping
    JOIN knowledge_document_page AS source_page
      ON source_page.id = mapping.page_id
    WHERE mapping.crosswalk_id = crosswalk.id
) AS page_bundle
  ON TRUE
WHERE crosswalk.is_active = TRUE
  AND crosswalk.is_verified = TRUE
  AND crosswalk.canonical_verification_status = 'TEXT_AND_VISUAL_VERIFIED'
  AND crosswalk.verified_by_id IS NOT NULL
  AND crosswalk.verified_at IS NOT NULL
  AND chunk.is_active = TRUE
  AND primary_page.parse_status_code = 'PARSED'
  AND primary_page.review_status_code = 'APPROVED'
  AND primary_page.is_rag_eligible = TRUE
  AND primary_page.exclusion_reason IS NULL
  AND document.deleted_at IS NULL
  AND document.dataset_scope_code = 'MVP'
  AND document.status_code = 'APPROVED'
  AND ingestion.dataset_scope_code = 'MVP'
  AND ingestion.status_code = 'SUCCEEDED'
  AND NOT EXISTS (
      SELECT 1
      FROM knowledge_source_document AS successor
      WHERE successor.supersedes_document_id = document.id
        AND successor.deleted_at IS NULL
  )
  AND model_scope.document_id = document.id
  AND model_scope.is_verified = TRUE
  AND model_scope.verified_by_id IS NOT NULL
  AND model_scope.verified_at IS NOT NULL
  AND (
      model_scope.applicable_from IS NULL
      OR model_scope.applicable_from <= (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')::date
  )
  AND (
      model_scope.applicable_to IS NULL
      OR model_scope.applicable_to >= (CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Seoul')::date
  )
  AND product.is_active = TRUE
  AND product.is_supported_mvp = TRUE
  AND product.generation_code IS NOT NULL
  AND embedding.is_active = TRUE
  AND embedding.embedding_dimension = 1024
  AND vector_dims(embedding.embedding) = 1024
  AND lower(crosswalk.source_file_sha256) = lower(document.sha256_hash)
  AND lower(crosswalk.chunk_text_sha256) = lower(chunk.chunk_text_sha256)
  AND lower(embedding.source_text_sha256) = lower(chunk.chunk_text_sha256)
  AND page_bundle.page_count > 0
  AND page_bundle.all_pages_usable = TRUE
  AND page_bundle.contains_primary_page = TRUE
  AND NOT EXISTS (
      SELECT 1
      FROM knowledge_data_quality_issue AS issue
      WHERE issue.status_code IN ('OPEN', 'IN_REVIEW')
        AND (
            issue.ingestion_batch_id = ingestion.id
            OR issue.document_id = document.id
            OR issue.chunk_id = chunk.id
            OR issue.page_id IN (
                SELECT mapped_page.page_id
                FROM knowledge_ai_chunk_crosswalk_page AS mapped_page
                WHERE mapped_page.crosswalk_id = crosswalk.id
            )
        )
  )
"""


def create_backend_ai_rag_view(apps, schema_editor):
    """Create the PostgreSQL-only compatibility view without granting roles."""

    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP VIEW IF EXISTS {VIEW_NAME}")
    schema_editor.execute(CREATE_VIEW_SQL)


def drop_backend_ai_rag_view(apps, schema_editor):
    """Drop the compatibility view before rolling back its source models."""

    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP VIEW IF EXISTS {VIEW_NAME}")


class Migration(migrations.Migration):
    dependencies = [
        ("evidence", "0009_ai_chunk_crosswalk"),
    ]

    operations = [
        migrations.RunPython(
            create_backend_ai_rag_view,
            reverse_code=drop_backend_ai_rag_view,
        ),
    ]
