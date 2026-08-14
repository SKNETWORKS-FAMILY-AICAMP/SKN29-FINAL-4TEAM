"""T-005 Wave 5C pgvector chunk-embedding contract tests."""

import logging
from importlib import import_module
from importlib.metadata import version
from uuid import UUID, uuid4

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import (
    DatabaseError,
    IntegrityError,
    connection,
    models,
    transaction,
)
from django.db.models.deletion import ProtectedError
from pgvector.django import CosineDistance, VectorField

from apps.accounts.models import User
from apps.evidence.models import (
    ChunkEmbedding,
    DocumentChunk,
    DocumentPage,
    IngestionBatch,
    SourceDocument,
)
from apps.evidence.models.chunk_embedding import EMBEDDING_DIMENSION


pytestmark = pytest.mark.django_db


def unit_vector(axis: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[axis] = 1.0
    return vector


def create_chunk(sequence: int) -> DocumentChunk:
    operator = User.objects.create_user(
        username=f"CHUNK-EMBED-OP-{sequence:04d}",
        password=None,
        full_name=f"Chunk embedding operator {sequence}",
        role_code=User.Role.OPERATOR,
        employee_no=f"CHUNK-EMBED-EMP-{sequence:04d}",
    )
    batch = IngestionBatch.objects.create(
        batch_no=f"CHUNK-EMBED-BATCH-{sequence:04d}",
        source_type_code=IngestionBatch.SourceType.LOCAL_FILE,
        idempotency_key=f"chunk-embedding-batch-{sequence:04d}",
        correlation_id=uuid4(),
        pipeline_version="chunk-embedding-test-v1",
    )
    document = SourceDocument.objects.create(
        ingestion_batch=batch,
        document_code=f"CHUNK-EMBED-DOC-{sequence:04d}",
        title=f"Chunk embedding document {sequence}",
        source_org="Official source organization",
        document_type_code="OFFICIAL_GUIDE",
        official_source_url=(
            f"https://example.test/embedding/source/{sequence}"
        ),
        usage_terms_url=(
            f"https://example.test/embedding/terms/{sequence}"
        ),
        license_note="Internal test fixture license.",
        original_file_uri=f"object://chunk-embedding/{sequence}.pdf",
        sha256_hash=f"{sequence:064x}",
        collected_by=operator,
    )
    page = DocumentPage.objects.create(
        document=document,
        page_no=1,
        extracted_text=f"Official embedding page {sequence}",
        text_sha256=f"{sequence + 10000:064x}",
    )
    return DocumentChunk.objects.create(
        page=page,
        chunk_no=1,
        chunk_text=f"Official embedding chunk {sequence}",
        chunk_text_sha256=f"{sequence + 20000:064x}",
        chunking_version="chunk-embedding-test-v1",
    )


def embedding_values(
    sequence: int,
    *,
    chunk: DocumentChunk | None = None,
    **overrides,
) -> dict:
    assigned_chunk = chunk or create_chunk(sequence)
    values = {
        "chunk": assigned_chunk,
        "embedding_model": "BAAI/bge-m3",
        "embedding_model_version": "upstream-1024-v1",
        "embedding_dimension": EMBEDDING_DIMENSION,
        "source_text_sha256": assigned_chunk.chunk_text_sha256,
        "embedding": unit_vector(sequence % 2),
    }
    values.update(overrides)
    return values


def create_embedding(
    sequence: int,
    **overrides,
) -> ChunkEmbedding:
    return ChunkEmbedding.objects.create(
        **embedding_values(sequence, **overrides)
    )


def test_chunk_embedding_uses_target_identifiers_fields_and_defaults():
    embedding = create_embedding(1)
    field_names = {
        field.name for field in ChunkEmbedding._meta.local_fields
    }

    assert isinstance(embedding.pk, int)
    assert isinstance(embedding.public_id, UUID)
    assert embedding._meta.db_table == "knowledge_chunk_embedding"
    assert embedding.is_active is True
    assert embedding.embedding_dimension == 1024
    assert len(field_names) == 12
    assert field_names == {
        "created_at",
        "updated_at",
        "id",
        "public_id",
        "chunk",
        "embedding_model",
        "embedding_model_version",
        "embedding_dimension",
        "source_text_sha256",
        "embedding",
        "embedded_at",
        "is_active",
    }


def test_chunk_embedding_is_exported_and_runtime_registered():
    config = apps.get_app_config("evidence")

    assert config.get_model("ChunkEmbedding") is ChunkEmbedding
    assert ChunkEmbedding._meta.app_label == "evidence"


def test_vector_field_dependency_and_migration_contract():
    vector_field = ChunkEmbedding._meta.get_field("embedding")
    chunk_field = ChunkEmbedding._meta.get_field("chunk")

    assert isinstance(vector_field, VectorField)
    assert vector_field.dimensions == EMBEDDING_DIMENSION
    assert chunk_field.remote_field.model is DocumentChunk
    assert chunk_field.remote_field.on_delete is models.PROTECT
    assert chunk_field.db_column == "chunk_id"
    assert chunk_field.db_index is False
    assert version("pgvector") == "0.5.0"

    migration = import_module(
        "apps.evidence.migrations.0007_chunkembedding"
    )
    assert migration.Migration.dependencies == [
        ("evidence", "0006_dataqualityissue"),
    ]
    assert isinstance(
        migration.Migration.operations[0],
        migration.PortableVectorExtension,
    )

    cast_migration = import_module(
        "apps.evidence.migrations."
        "0011_cast_chunk_embedding_vector_dimensions"
    )
    assert cast_migration.Migration.dependencies == [
        ("evidence", "0010_backend_ai_rag_chunks_view"),
    ]


def test_indexes_and_constraints_match_contract():
    indexes = {
        index.name: tuple(index.fields)
        for index in ChunkEmbedding._meta.indexes
    }
    constraints = {
        constraint.name
        for constraint in ChunkEmbedding._meta.constraints
    }

    assert indexes == {
        "ix_chunk_embedding_active": (
            "embedding_model",
            "is_active",
        ),
    }
    assert constraints == {
        "ux_chunk_embedding_model",
        "ck_chunk_embedding_dimension",
        "ck_chunk_embedding_source_hash",
        "ck_chunk_embedding_model_name",
        "ck_chunk_embedding_model_version",
    }


def test_embedding_round_trip_keeps_all_1024_values():
    embedding = create_embedding(2)
    embedding.refresh_from_db()

    assert len(embedding.embedding) == EMBEDDING_DIMENSION
    assert embedding.embedding[0] == 1.0
    assert sum(embedding.embedding) == 1.0


def test_model_version_is_unique_per_chunk():
    chunk = create_chunk(10)
    create_embedding(10, chunk=chunk)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_embedding(11, chunk=chunk)

    second_version = create_embedding(
        12,
        chunk=chunk,
        embedding_model_version="upstream-1024-v2",
    )
    assert second_version.pk is not None


@pytest.mark.parametrize(
    "overrides",
    [
        {"embedding_dimension": 0},
        {"embedding_dimension": 768},
        {"source_text_sha256": "A" * 64},
        {"embedding_model": "   "},
        {"embedding_model_version": "   "},
    ],
)
def test_invalid_structural_values_are_database_rejected(
    overrides: dict,
):
    with pytest.raises((DatabaseError, IntegrityError)), transaction.atomic():
        create_embedding(
            30 + len(str(overrides)),
            **overrides,
        )


def test_invalid_vector_length_is_database_rejected():
    with pytest.raises(DatabaseError), transaction.atomic():
        create_embedding(
            50,
            embedding=[1.0] * (EMBEDDING_DIMENSION - 1),
        )


@pytest.mark.parametrize(
    ("overrides", "invalid_field"),
    [
        ({"embedding_dimension": 768}, "embedding_dimension"),
        (
            {"embedding": [1.0] * (EMBEDDING_DIMENSION - 1)},
            "embedding",
        ),
    ],
)
def test_full_clean_rejects_dimension_mismatch(
    overrides: dict,
    invalid_field: str,
):
    candidate = ChunkEmbedding(
        **embedding_values(51 + len(invalid_field), **overrides)
    )

    with pytest.raises(ValidationError) as exc_info:
        candidate.full_clean()

    assert invalid_field in exc_info.value.message_dict


def test_postgresql_full_clean_has_no_database_constraint_warning(caplog):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL constraint-validation assertion")

    candidate = ChunkEmbedding(**embedding_values(59))

    with caplog.at_level(logging.WARNING, logger="django.db.models"):
        candidate.full_clean()

    database_check_warnings = [
        record.getMessage()
        for record in caplog.records
        if "database error calling check" in record.getMessage().lower()
    ]
    assert database_check_warnings == []


def test_source_hash_must_match_referenced_chunk_version():
    chunk = create_chunk(60)
    values = embedding_values(
        60,
        chunk=chunk,
        source_text_sha256="f" * 64,
    )

    if connection.vendor == "postgresql":
        with pytest.raises(IntegrityError), transaction.atomic():
            ChunkEmbedding.objects.create(**values)
        return

    candidate = ChunkEmbedding(**values)
    with pytest.raises(ValidationError):
        candidate.full_clean()


def test_public_id_is_unique_and_chunk_deletion_is_protected():
    embedding = create_embedding(70)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_embedding(71, public_id=embedding.public_id)

    with pytest.raises(ProtectedError):
        embedding.chunk.delete()


def test_postgresql_exact_cosine_search_and_no_ann_index():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL exact-vector search assertion")

    first = create_embedding(80, embedding=unit_vector(0))
    second = create_embedding(81, embedding=unit_vector(1))
    query = [0.0] * EMBEDDING_DIMENSION
    query[0] = 0.9
    query[1] = 0.1

    ranked = list(
        ChunkEmbedding.objects.annotate(
            distance=CosineDistance("embedding", query)
        ).order_by("distance")
    )
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = 'knowledge_chunk_embedding'
            """
        )
        index_definitions = [
            index_definition.lower()
            for (index_definition,) in cursor.fetchall()
        ]

    assert ranked[0].pk == first.pk
    assert ranked[1].pk == second.pk
    assert all(
        "hnsw" not in definition
        and "ivfflat" not in definition
        for definition in index_definitions
    )


def test_postgresql_vector_catalog_and_composite_source_fk():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL pgvector catalog assertion")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT extversion
            FROM pg_extension
            WHERE extname = 'vector'
            """
        )
        extension_version = cursor.fetchone()
        cursor.execute(
            """
            SELECT format_type(a.atttypid, a.atttypmod)
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = current_schema()
              AND c.relname = 'knowledge_chunk_embedding'
              AND a.attname = 'embedding'
              AND NOT a.attisdropped
            """
        )
        vector_type = cursor.fetchone()
        cursor.execute(
            """
            SELECT
                conname,
                pg_get_constraintdef(oid),
                confrelid::regclass::text,
                confdeltype,
                condeferrable,
                condeferred
            FROM pg_constraint
            WHERE conrelid = (
                current_schema() || '.knowledge_chunk_embedding'
            )::regclass
            """
        )
        constraints = {
            name: (
                definition,
                referenced_table,
                delete_action,
                is_deferrable,
                is_deferred,
            )
            for (
                name,
                definition,
                referenced_table,
                delete_action,
                is_deferrable,
                is_deferred,
            ) in cursor.fetchall()
        }

    assert extension_version == ("0.8.6",)
    assert vector_type == ("vector(1024)",)
    assert "ck_chunk_embedding_dimension" in constraints
    assert "vector_dims((embedding)::vector)" in constraints[
        "ck_chunk_embedding_dimension"
    ][0]
    assert "fk_chunk_embedding_source_hash" in constraints
    source_hash_fk = constraints["fk_chunk_embedding_source_hash"]
    assert source_hash_fk[1:] == (
        "knowledge_document_chunk",
        "r",
        False,
        False,
    )
    assert source_hash_fk[0] == (
        "FOREIGN KEY (chunk_id, source_text_sha256) "
        "REFERENCES knowledge_document_chunk(id, chunk_text_sha256) "
        "ON DELETE RESTRICT"
    )
