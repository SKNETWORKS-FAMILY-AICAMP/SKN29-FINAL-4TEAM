"""T-005 Wave 3B document-page contract and database tests."""

from importlib import import_module
from uuid import UUID, uuid4

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.evidence.models import (
    DocumentPage,
    IngestionBatch,
    SourceDocument,
)


pytestmark = pytest.mark.django_db


def create_operator(sequence: int) -> User:
    return User.objects.create_user(
        username=f"DOCUMENT-PAGE-OP-{sequence:03d}",
        password=None,
        full_name=f"Document page operator {sequence}",
        role_code=User.Role.OPERATOR,
        employee_no=f"DOCUMENT-PAGE-EMP-{sequence:03d}",
    )


def create_document(sequence: int) -> SourceDocument:
    operator = create_operator(sequence + 1000)
    batch = IngestionBatch.objects.create(
        batch_no=f"DOCUMENT-PAGE-BATCH-{sequence:03d}",
        source_type_code=IngestionBatch.SourceType.LOCAL_FILE,
        idempotency_key=f"document-page-batch-{sequence:03d}",
        correlation_id=uuid4(),
        pipeline_version="document-page-test-v1",
    )
    return SourceDocument.objects.create(
        ingestion_batch=batch,
        document_code=f"DOCUMENT-PAGE-DOC-{sequence:03d}",
        title=f"Document page source {sequence}",
        source_org="Official source organization",
        document_type_code="OFFICIAL_GUIDE",
        official_source_url=f"https://example.test/docs/{sequence}",
        usage_terms_url=f"https://example.test/terms/{sequence}",
        license_note="Internal test fixture license.",
        original_file_uri=f"object://document-page/{sequence}.pdf",
        sha256_hash=f"{sequence:064x}",
        collected_by=operator,
    )


def create_page(
    sequence: int,
    *,
    document: SourceDocument | None = None,
    **overrides,
) -> DocumentPage:
    values = {
        "document": document or create_document(sequence),
        "page_no": sequence,
    }
    values.update(overrides)
    return DocumentPage.objects.create(**values)


def test_document_page_uses_target_identifiers_fields_and_defaults():
    page = create_page(1)
    field_names = {
        field.name for field in DocumentPage._meta.local_fields
    }

    assert isinstance(page.pk, int)
    assert isinstance(page.public_id, UUID)
    assert page._meta.db_table == "knowledge_document_page"
    assert page.parse_status_code == "PENDING"
    assert page.review_status_code == "PENDING"
    assert page.is_rag_eligible is False
    assert len(field_names) == 14
    assert field_names == {
        "created_at",
        "updated_at",
        "id",
        "public_id",
        "document",
        "page_no",
        "extracted_text",
        "text_sha256",
        "parse_status_code",
        "review_status_code",
        "is_rag_eligible",
        "exclusion_reason",
        "reviewer",
        "reviewed_at",
    }


def test_document_page_is_exported_and_runtime_registered():
    config = apps.get_app_config("evidence")

    assert config.get_model("DocumentPage") is DocumentPage
    assert DocumentPage._meta.app_label == "evidence"


def test_status_fields_remain_open_until_canonical_contracts_exist():
    parse_status = DocumentPage._meta.get_field("parse_status_code")
    review_status = DocumentPage._meta.get_field("review_status_code")

    assert parse_status.choices is None
    assert review_status.choices is None

    page = create_page(
        2,
        parse_status_code="TEAM_PARSE_REVIEW_PENDING",
        review_status_code="TEAM_PAGE_REVIEW_PENDING",
        exclusion_reason="Not yet approved for retrieval.",
    )
    assert page.parse_status_code == "TEAM_PARSE_REVIEW_PENDING"
    assert page.review_status_code == "TEAM_PAGE_REVIEW_PENDING"


def test_fk_policy_and_migration_dependency_match_contract():
    document = DocumentPage._meta.get_field("document")
    reviewer = DocumentPage._meta.get_field("reviewer")

    assert document.remote_field.model._meta.label == "evidence.SourceDocument"
    assert document.remote_field.on_delete is models.PROTECT
    assert document.null is False
    assert document.db_column == "document_id"
    assert document.db_index is False

    assert reviewer.remote_field.model._meta.label == "accounts.User"
    assert reviewer.remote_field.on_delete is models.PROTECT
    assert reviewer.null is True
    assert reviewer.db_column == "reviewer_id"
    assert reviewer.db_index is False

    migration = import_module(
        "apps.evidence.migrations.0004_documentpage"
    )
    assert migration.Migration.dependencies == [
        ("accounts", "0003_promote_integer_primary_keys"),
        ("evidence", "0003_documentmodelscope"),
    ]


def test_indexes_and_constraints_match_approved_contract_range():
    indexes = {
        index.name: (tuple(index.fields), index.condition)
        for index in DocumentPage._meta.indexes
    }
    constraints = {
        constraint.name
        for constraint in DocumentPage._meta.constraints
    }

    assert set(indexes) == {"ix_document_page_rag"}
    assert indexes["ix_document_page_rag"][0] == ("document", "page_no")
    assert indexes["ix_document_page_rag"][1] == models.Q(
        is_rag_eligible=True
    )
    assert constraints == {
        "ux_document_page_no",
        "ck_document_page_no",
        "ck_document_page_sha256",
        "ck_document_page_review_bundle",
        "ck_document_page_rag_eligibility",
    }
    assert not any(
        "parse_status_code_allowed" in name
        or "review_status_code_allowed" in name
        for name in constraints
    )


def test_page_number_is_enforced_by_validation_and_database():
    document = create_document(3)
    invalid = DocumentPage(document=document, page_no=0)
    with pytest.raises(ValidationError) as validation_error:
        invalid.full_clean()
    assert "page_no" in validation_error.value.message_dict

    with pytest.raises(IntegrityError), transaction.atomic():
        create_page(3, document=document, page_no=0)


def test_document_page_number_and_public_id_are_unique():
    document = create_document(4)
    first = create_page(4, document=document, page_no=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_page(5, document=document, page_no=1)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_page(6, public_id=first.public_id)


def test_nullable_sha256_accepts_null_and_lowercase_digest():
    without_hash = create_page(7, text_sha256=None)
    with_hash = create_page(8, text_sha256="a" * 64)

    assert without_hash.text_sha256 is None
    assert with_hash.text_sha256 == "a" * 64


@pytest.mark.parametrize(
    "invalid_hash",
    [
        "a" * 63,
        "A" * 64,
        "g" * 64,
        "",
    ],
)
def test_sha256_format_is_enforced_by_validation_and_database(
    invalid_hash: str,
):
    invalid = DocumentPage(
        document=create_document(20 + len(invalid_hash)),
        page_no=1,
        text_sha256=invalid_hash,
    )
    with pytest.raises(ValidationError) as validation_error:
        invalid.full_clean()
    assert "text_sha256" in validation_error.value.message_dict

    with pytest.raises(IntegrityError), transaction.atomic():
        create_page(
            30 + len(invalid_hash),
            text_sha256=invalid_hash,
        )


@pytest.mark.parametrize(
    ("include_reviewer", "include_reviewed_at"),
    [(True, False), (False, True)],
)
def test_incomplete_review_bundle_is_database_rejected(
    include_reviewer: bool,
    include_reviewed_at: bool,
):
    reviewer = create_operator(
        100 + int(include_reviewer) + int(include_reviewed_at) * 2
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        create_page(
            100 + int(include_reviewer) + int(include_reviewed_at) * 2,
            reviewer=reviewer if include_reviewer else None,
            reviewed_at=timezone.now() if include_reviewed_at else None,
        )


def test_valid_review_bundle_and_rag_eligible_page_persist():
    reviewer = create_operator(110)
    page = create_page(
        110,
        extracted_text="Approved official page text.",
        text_sha256="b" * 64,
        parse_status_code="PARSED",
        review_status_code="APPROVED",
        is_rag_eligible=True,
        reviewer=reviewer,
        reviewed_at=timezone.now(),
    )

    assert page.is_rag_eligible is True
    assert page.reviewer == reviewer
    assert page.exclusion_reason is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"parse_status_code": "PENDING"},
        {"review_status_code": "PENDING"},
        {"extracted_text": None},
        {"text_sha256": None},
        {"reviewer": None, "reviewed_at": None},
        {"exclusion_reason": "Excluded by quality review."},
    ],
)
def test_rag_eligibility_requires_only_the_approved_positive_gate(
    overrides: dict,
):
    sequence = 120 + len(str(overrides))
    reviewer = create_operator(sequence)
    values = {
        "extracted_text": "Approved official page text.",
        "text_sha256": "c" * 64,
        "parse_status_code": "PARSED",
        "review_status_code": "APPROVED",
        "is_rag_eligible": True,
        "reviewer": reviewer,
        "reviewed_at": timezone.now(),
    }
    values.update(overrides)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_page(sequence, **values)


def test_document_and_reviewer_foreign_keys_block_parent_deletion():
    document = create_document(200)
    reviewer = create_operator(200)
    create_page(
        200,
        document=document,
        reviewer=reviewer,
        reviewed_at=timezone.now(),
    )

    with pytest.raises(ProtectedError):
        document.delete()
    with pytest.raises(ProtectedError):
        reviewer.delete()


def test_postgresql_catalog_contains_target_types_constraints_and_index():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL catalog assertion")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'knowledge_document_page'
              AND column_name IN (
                  'id', 'public_id', 'document_id', 'reviewer_id'
              )
            """
        )
        column_types = dict(cursor.fetchall())
        cursor.execute(
            """
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'knowledge_document_page'::regclass
            ORDER BY conname
            """
        )
        constraints = dict(cursor.fetchall())
        cursor.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = 'knowledge_document_page'
              AND indexname = 'ix_document_page_rag'
            """
        )
        indexes = dict(cursor.fetchall())

    assert column_types == {
        "id": "bigint",
        "public_id": "uuid",
        "document_id": "bigint",
        "reviewer_id": "bigint",
    }
    assert {
        "ux_document_page_no",
        "ck_document_page_no",
        "ck_document_page_sha256",
        "ck_document_page_review_bundle",
        "ck_document_page_rag_eligibility",
    } <= set(constraints)
    assert "ix_document_page_rag" in indexes
    assert "WHERE is_rag_eligible" in indexes["ix_document_page_rag"]
