"""T-005 reviewed document-chunk model and persistence tests."""

from importlib import import_module
from uuid import UUID, uuid4

import pytest
from django.apps import apps
from django.contrib.postgres.indexes import GinIndex
from django.db import IntegrityError, connection, models, transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import User
from apps.evidence.models import (
    DocumentChunk,
    DocumentPage,
    IngestionBatch,
    SourceDocument,
)


pytestmark = pytest.mark.django_db


def create_operator(sequence: int) -> User:
    return User.objects.create_user(
        username=f"DOC-CHUNK-OP-{sequence:04d}",
        password=None,
        full_name=f"Document chunk operator {sequence}",
        role_code=User.Role.OPERATOR,
        employee_no=f"DOC-CHUNK-EMP-{sequence:04d}",
    )


def create_page(sequence: int) -> DocumentPage:
    operator = create_operator(sequence)
    batch = IngestionBatch.objects.create(
        batch_no=f"DOC-CHUNK-BATCH-{sequence:04d}",
        source_type_code=IngestionBatch.SourceType.LOCAL_FILE,
        idempotency_key=f"doc-chunk-batch-{sequence:04d}",
        correlation_id=uuid4(),
        pipeline_version="doc-chunk-test-v1",
    )
    document = SourceDocument.objects.create(
        ingestion_batch=batch,
        document_code=f"DOC-CHUNK-SOURCE-{sequence:04d}",
        title=f"Document chunk source {sequence}",
        source_org="Official source organization",
        document_type_code="OFFICIAL_GUIDE",
        official_source_url=(
            f"https://example.test/chunk/source/{sequence}"
        ),
        usage_terms_url=(
            f"https://example.test/chunk/terms/{sequence}"
        ),
        license_note="Internal test fixture license.",
        original_file_uri=f"object://doc-chunk/{sequence}.pdf",
        sha256_hash=f"{sequence:064x}",
        collected_by=operator,
    )
    return DocumentPage.objects.create(
        document=document,
        page_no=1,
        extracted_text="Filter inspection and reset procedure.",
        text_sha256=f"{sequence + 10000:064x}",
    )


def chunk_values(
    sequence: int,
    *,
    page: DocumentPage | None = None,
    **overrides,
) -> dict:
    values = {
        "page": page or create_page(sequence),
        "chunk_no": 1,
        "chunk_text": "Inspect the filter and reset the device.",
        "chunk_text_sha256": f"{sequence + 20000:064x}",
        "start_offset": 0,
        "end_offset": 40,
        "token_count": 8,
        "tokenizer_name": "bge-m3-tokenizer",
        "tokenizer_version": "v1",
        "symptom_tags": ["filter", "reset"],
        "metadata": {"language": "ko"},
        "chunking_version": f"chunker-v{sequence}",
    }
    values.update(overrides)
    return values


def create_chunk(
    sequence: int,
    **overrides,
) -> DocumentChunk:
    return DocumentChunk.objects.create(
        **chunk_values(sequence, **overrides)
    )


def test_document_chunk_uses_target_identifiers_and_all_fields():
    chunk = create_chunk(1)
    field_names = {
        field.name for field in DocumentChunk._meta.local_fields
    }

    assert isinstance(chunk.pk, int)
    assert isinstance(chunk.public_id, UUID)
    assert chunk._meta.db_table == "knowledge_document_chunk"
    assert chunk.chunk_type_code == "PARAGRAPH"
    assert chunk.is_active is True
    assert len(field_names) == 20
    assert field_names == {
        "created_at",
        "updated_at",
        "id",
        "public_id",
        "page",
        "chunk_no",
        "chunk_type_code",
        "section_path",
        "chunk_text",
        "chunk_text_sha256",
        "start_offset",
        "end_offset",
        "token_count",
        "tokenizer_name",
        "tokenizer_version",
        "symptom_tags",
        "metadata",
        "search_vector",
        "chunking_version",
        "is_active",
    }


def test_document_chunk_is_exported_and_runtime_registered():
    config = apps.get_app_config("evidence")

    assert config.get_model("DocumentChunk") is DocumentChunk
    assert DocumentChunk._meta.app_label == "evidence"


def test_open_chunk_type_and_generated_search_vector():
    chunk_type = DocumentChunk._meta.get_field("chunk_type_code")
    search_vector = DocumentChunk._meta.get_field("search_vector")

    assert chunk_type.choices is None
    assert search_vector.generated is True

    chunk = create_chunk(
        2,
        chunk_type_code="TEAM_REVIEW_PENDING",
    )
    chunk.refresh_from_db()
    assert chunk.chunk_type_code == "TEAM_REVIEW_PENDING"
    assert chunk.search_vector is not None


def test_fk_policy_and_migration_dependency():
    page = DocumentChunk._meta.get_field("page")

    assert page.remote_field.model is DocumentPage
    assert page.remote_field.on_delete is models.PROTECT
    assert page.db_column == "page_id"
    assert page.db_index is False

    migration = import_module(
        "apps.evidence.migrations.0005_documentchunk"
    )
    assert migration.Migration.dependencies == [
        ("evidence", "0004_documentpage"),
    ]


def test_indexes_and_constraints_match_contract():
    indexes = {
        index.name: index for index in DocumentChunk._meta.indexes
    }
    constraints = {
        constraint.name
        for constraint in DocumentChunk._meta.constraints
    }

    assert set(indexes) == {
        "ix_document_chunk_active",
        "ix_document_chunk_fts",
    }
    assert isinstance(indexes["ix_document_chunk_fts"], GinIndex)
    assert constraints == {
        "ux_document_chunk_version",
        "ux_document_chunk_id_hash",
        "ux_document_chunk_active_position",
        "ck_document_chunk_no",
        "ck_document_chunk_text",
        "ck_document_chunk_hash",
        "ck_document_chunk_offsets",
        "ck_document_chunk_token_count",
        "ck_document_chunk_json",
    }


def test_chunk_version_and_active_position_are_unique():
    page = create_page(10)
    create_chunk(10, page=page, chunking_version="v1")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_chunk(11, page=page, chunking_version="v1")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_chunk(12, page=page, chunking_version="v2")

    inactive = create_chunk(
        13,
        page=page,
        chunking_version="v2",
        is_active=False,
    )
    assert inactive.is_active is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"chunk_no": 0},
        {"chunk_text": "   "},
        {"chunk_text_sha256": "A" * 64},
        {"start_offset": -1, "end_offset": 10},
        {"start_offset": 5, "end_offset": 5},
        {"start_offset": None, "end_offset": 10},
        {"token_count": -1},
        {"symptom_tags": {"not": "array"}},
        {"metadata": ["not", "object"]},
    ],
)
def test_invalid_chunk_values_are_database_rejected(overrides: dict):
    with pytest.raises(IntegrityError), transaction.atomic():
        create_chunk(
            30 + len(str(overrides)),
            **overrides,
        )


def test_public_id_is_unique_and_page_deletion_is_protected():
    chunk = create_chunk(50)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_chunk(51, public_id=chunk.public_id)

    with pytest.raises(ProtectedError):
        chunk.page.delete()


def test_postgresql_generated_vector_gin_index_and_column_types():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL structural assertion")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name, data_type, is_generated
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'knowledge_document_chunk'
              AND column_name IN (
                  'id',
                  'public_id',
                  'page_id',
                  'symptom_tags',
                  'metadata',
                  'search_vector'
              )
            """
        )
        columns = {
            name: (data_type, generated)
            for name, data_type, generated in cursor.fetchall()
        }
        cursor.execute(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = 'knowledge_document_chunk'
              AND indexname = 'ix_document_chunk_fts'
            """
        )
        gin_index = cursor.fetchone()

    assert columns == {
        "id": ("bigint", "NEVER"),
        "public_id": ("uuid", "NEVER"),
        "page_id": ("bigint", "NEVER"),
        "symptom_tags": ("jsonb", "NEVER"),
        "metadata": ("jsonb", "NEVER"),
        "search_vector": ("tsvector", "ALWAYS"),
    }
    assert gin_index is not None
    assert "USING gin (search_vector)" in gin_index[0]
