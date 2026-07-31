"""T-005 Evidence Wave source-document model and constraint tests."""

from importlib import import_module
from uuid import UUID, uuid4

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.evidence.models import IngestionBatch, SourceDocument


pytestmark = pytest.mark.django_db


def create_operator(sequence: int) -> User:
    return User.objects.create_user(
        username=f"SOURCE-DOCUMENT-OP-{sequence:03d}",
        password=None,
        full_name=f"Source document operator {sequence}",
        role_code=User.Role.OPERATOR,
        employee_no=f"SOURCE-DOCUMENT-EMP-{sequence:03d}",
    )


def create_batch(
    sequence: int,
    *,
    dataset_scope_code: str = IngestionBatch.DatasetScope.MVP,
) -> IngestionBatch:
    return IngestionBatch.objects.create(
        batch_no=f"SOURCE-DOCUMENT-BATCH-{sequence:03d}",
        dataset_scope_code=dataset_scope_code,
        source_type_code=IngestionBatch.SourceType.LOCAL_FILE,
        idempotency_key=f"source-document-batch-{sequence:03d}",
        correlation_id=uuid4(),
        pipeline_version="source-document-test-v1",
    )


def source_values(
    sequence: int,
    *,
    batch: IngestionBatch | None = None,
    collected_by: User | None = None,
    **overrides,
) -> dict:
    assigned_batch = batch or create_batch(sequence)
    collector = collected_by or create_operator(sequence)
    values = {
        "ingestion_batch": assigned_batch,
        "document_code": f"SOURCE-DOCUMENT-{sequence:03d}",
        "dataset_scope_code": assigned_batch.dataset_scope_code,
        "title": f"Official source document {sequence}",
        "source_org": "Official source organization",
        "document_type_code": "OFFICIAL_GUIDE",
        "official_source_url": (
            f"https://example.test/source/{sequence}"
        ),
        "usage_terms_url": (
            f"https://example.test/terms/{sequence}"
        ),
        "license_note": "Internal test fixture license.",
        "original_file_uri": (
            f"object://official-sources/{sequence}.pdf"
        ),
        "file_name": f"official-source-{sequence}.pdf",
        "mime_type": "application/pdf",
        "file_size_bytes": 1024,
        "sha256_hash": f"{sequence:064x}",
        "revision_label": "v1",
        "collected_by": collector,
        "parser_version": "parser-v1",
    }
    values.update(overrides)
    return values


def create_source_document(
    sequence: int,
    **overrides,
) -> SourceDocument:
    return SourceDocument.objects.create(
        **source_values(sequence, **overrides)
    )


def test_source_document_uses_target_identifiers_and_all_27_fields():
    document = create_source_document(1)
    field_names = {
        field.name for field in SourceDocument._meta.local_fields
    }

    assert isinstance(document.pk, int)
    assert isinstance(document.public_id, UUID)
    assert document._meta.db_table == "knowledge_source_document"
    assert document.status_code == "COLLECTED"
    assert document.dataset_scope_code == SourceDocument.DatasetScope.MVP
    assert len(field_names) == 27
    assert field_names == {
        "created_at",
        "updated_at",
        "deleted_at",
        "id",
        "public_id",
        "ingestion_batch",
        "document_code",
        "dataset_scope_code",
        "supersedes_document",
        "title",
        "source_org",
        "document_type_code",
        "official_source_url",
        "usage_terms_url",
        "license_note",
        "original_file_uri",
        "file_name",
        "mime_type",
        "file_size_bytes",
        "sha256_hash",
        "revision_label",
        "published_on",
        "collected_at",
        "collected_by",
        "status_code",
        "parser_version",
        "deleted_by",
    }


def test_source_document_is_exported_and_runtime_registered():
    config = apps.get_app_config("evidence")

    assert config.get_model("SourceDocument") is SourceDocument
    assert SourceDocument._meta.app_label == "evidence"


def test_only_canonical_dataset_scope_is_frozen_as_choices():
    dataset_scope = SourceDocument._meta.get_field(
        "dataset_scope_code"
    )
    document_type = SourceDocument._meta.get_field(
        "document_type_code"
    )
    status = SourceDocument._meta.get_field("status_code")

    assert list(dataset_scope.choices) == [
        ("MVP", "MVP"),
        ("EXPANSION", "Expansion"),
    ]
    assert document_type.choices is None
    assert status.choices is None

    document = create_source_document(
        2,
        document_type_code="TEAM_REVIEW_PENDING",
        status_code="CANONICAL_REVIEW_PENDING",
    )
    assert document.document_type_code == "TEAM_REVIEW_PENDING"
    assert document.status_code == "CANONICAL_REVIEW_PENDING"


def test_source_document_fk_policy_and_migration_dependencies():
    expected_fks = {
        "ingestion_batch": (
            "evidence.IngestionBatch",
            False,
            "ingestion_batch_id",
        ),
        "supersedes_document": (
            "evidence.SourceDocument",
            True,
            "supersedes_document_id",
        ),
        "collected_by": (
            "accounts.User",
            False,
            "collected_by_id",
        ),
        "deleted_by": (
            "accounts.User",
            True,
            "deleted_by_id",
        ),
    }
    for name, (label, nullable, db_column) in expected_fks.items():
        field = SourceDocument._meta.get_field(name)
        assert field.remote_field.model._meta.label == label
        assert field.remote_field.on_delete is models.PROTECT
        assert field.null is nullable
        assert field.db_column == db_column
        assert field.db_index is False

    migration = import_module(
        "apps.evidence.migrations.0002_sourcedocument"
    )
    assert migration.Migration.dependencies == [
        ("accounts", "0003_promote_integer_primary_keys"),
        ("evidence", "0001_initial"),
    ]


def test_source_document_indexes_and_constraints_match_contract():
    indexes = {
        index.name: tuple(index.fields)
        for index in SourceDocument._meta.indexes
    }
    constraints = {
        constraint.name for constraint in SourceDocument._meta.constraints
    }

    assert indexes == {
        "ix_source_document_status": (
            "document_type_code",
            "status_code",
            "-collected_at",
        ),
        "ix_source_document_revision": (
            "official_source_url",
            "revision_label",
        ),
        "ix_source_document_supersedes": (
            "supersedes_document",
        ),
        "ix_source_doc_active_status": (
            "status_code",
            "-collected_at",
        ),
        "ix_source_document_batch": ("ingestion_batch",),
    }
    assert constraints == {
        "ux_source_document_code",
        "ux_source_document_sha256",
        "ux_source_document_id_scope",
        "ck_source_document_file_size",
        "ck_source_document_sha256",
        "ck_source_document_not_self_supersede",
        "ck_source_document_deleted_pair",
        "ck_knowledge_source_document_dataset_scope_code_allowed",
    }


def test_document_code_sha256_and_public_id_are_unique():
    first = create_source_document(3)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_source_document(
            4,
            document_code=first.document_code,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_source_document(
            5,
            sha256_hash=first.sha256_hash,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_source_document(
            6,
            public_id=first.public_id,
        )


def test_hash_file_size_and_dataset_scope_are_database_constrained():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_source_document(
            7,
            sha256_hash="A" * 64,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_source_document(
            8,
            file_size_bytes=-1,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_source_document(
            9,
            dataset_scope_code="UNAPPROVED",
        )


def test_soft_delete_pair_and_self_supersede_are_database_constrained():
    deleter = create_operator(100)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_source_document(
            10,
            deleted_at=timezone.now(),
            deleted_by=None,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_source_document(
            11,
            deleted_at=None,
            deleted_by=deleter,
        )

    document = create_source_document(
        12,
        deleted_at=timezone.now(),
        deleted_by=deleter,
    )
    assert document.deleted_by == deleter

    with pytest.raises(IntegrityError), transaction.atomic():
        SourceDocument.objects.filter(pk=document.pk).update(
            supersedes_document_id=document.pk,
        )


def test_clean_rejects_batch_and_superseded_revision_scope_mismatches():
    mvp_batch = create_batch(13)
    mismatched_batch = SourceDocument(
        **source_values(
            13,
            batch=mvp_batch,
            dataset_scope_code=SourceDocument.DatasetScope.EXPANSION,
        )
    )

    with pytest.raises(ValidationError) as batch_error:
        mismatched_batch.full_clean()
    assert "dataset_scope_code" in batch_error.value.message_dict

    original = create_source_document(14)
    expansion_batch = create_batch(
        15,
        dataset_scope_code=IngestionBatch.DatasetScope.EXPANSION,
    )
    mismatched_revision = SourceDocument(
        **source_values(
            15,
            batch=expansion_batch,
            supersedes_document=original,
        )
    )

    with pytest.raises(ValidationError) as revision_error:
        mismatched_revision.full_clean()
    assert "supersedes_document" in revision_error.value.message_dict


def test_all_source_document_relationships_use_protect():
    collector = create_operator(16)
    batch = create_batch(16)
    original = create_source_document(
        16,
        batch=batch,
        collected_by=collector,
    )
    deleter = create_operator(17)
    replacement = create_source_document(
        17,
        batch=batch,
        collected_by=collector,
        supersedes_document=original,
        deleted_at=timezone.now(),
        deleted_by=deleter,
    )

    with pytest.raises(ProtectedError):
        batch.delete()
    with pytest.raises(ProtectedError):
        collector.delete()
    with pytest.raises(ProtectedError):
        deleter.delete()
    with pytest.raises(ProtectedError):
        original.delete()

    assert replacement.supersedes_document == original


def test_postgresql_composite_scope_fks_and_column_types_exist():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL structural assertion")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'knowledge_source_document'::regclass
              AND conname IN (
                  'fk_source_document_batch_scope',
                  'fk_source_document_supersedes_scope'
              )
            ORDER BY conname
            """
        )
        definitions = dict(cursor.fetchall())
        cursor.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'knowledge_source_document'
              AND column_name IN (
                  'id',
                  'public_id',
                  'ingestion_batch_id',
                  'supersedes_document_id'
              )
            """
        )
        column_types = dict(cursor.fetchall())

    assert set(definitions) == {
        "fk_source_document_batch_scope",
        "fk_source_document_supersedes_scope",
    }
    assert (
        "FOREIGN KEY (ingestion_batch_id, dataset_scope_code)"
        in definitions["fk_source_document_batch_scope"]
    )
    assert (
        "REFERENCES knowledge_ingestion_batch"
        "(id, dataset_scope_code)"
        in definitions["fk_source_document_batch_scope"]
    )
    assert (
        "FOREIGN KEY (supersedes_document_id, dataset_scope_code)"
        in definitions["fk_source_document_supersedes_scope"]
    )
    assert (
        "REFERENCES knowledge_source_document"
        "(id, dataset_scope_code)"
        in definitions["fk_source_document_supersedes_scope"]
    )
    assert column_types == {
        "id": "bigint",
        "public_id": "uuid",
        "ingestion_batch_id": "bigint",
        "supersedes_document_id": "bigint",
    }


def test_postgresql_rejects_batch_scope_mismatch_at_database_boundary():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL composite FK assertion")

    batch = create_batch(18)
    with pytest.raises(IntegrityError) as error:
        with transaction.atomic():
            SourceDocument.objects.create(
                **source_values(
                    18,
                    batch=batch,
                    dataset_scope_code=(
                        SourceDocument.DatasetScope.EXPANSION
                    ),
                )
            )

    assert (
        error.value.__cause__.diag.constraint_name
        == "fk_source_document_batch_scope"
    )


def test_postgresql_rejects_cross_scope_superseded_revision():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL composite FK assertion")

    original = create_source_document(19)
    expansion_batch = create_batch(
        20,
        dataset_scope_code=IngestionBatch.DatasetScope.EXPANSION,
    )
    with pytest.raises(IntegrityError) as error:
        with transaction.atomic():
            SourceDocument.objects.create(
                **source_values(
                    20,
                    batch=expansion_batch,
                    supersedes_document=original,
                )
            )

    assert (
        error.value.__cause__.diag.constraint_name
        == "fk_source_document_supersedes_scope"
    )
