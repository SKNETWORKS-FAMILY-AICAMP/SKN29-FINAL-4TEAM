"""T-005 Wave 5B knowledge data-quality issue contract tests."""

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
    DataQualityIssue,
    DocumentChunk,
    DocumentPage,
    IngestionBatch,
    SourceDocument,
)


pytestmark = pytest.mark.django_db


def create_operator(sequence: int) -> User:
    return User.objects.create_user(
        username=f"QUALITY-ISSUE-OP-{sequence:04d}",
        password=None,
        full_name=f"Quality issue operator {sequence}",
        role_code=User.Role.OPERATOR,
        employee_no=f"QUALITY-ISSUE-EMP-{sequence:04d}",
    )


def create_batch(sequence: int) -> IngestionBatch:
    return IngestionBatch.objects.create(
        batch_no=f"QUALITY-ISSUE-BATCH-{sequence:04d}",
        source_type_code=IngestionBatch.SourceType.LOCAL_FILE,
        idempotency_key=f"quality-issue-batch-{sequence:04d}",
        correlation_id=uuid4(),
        pipeline_version="quality-issue-test-v1",
    )


def create_document(
    sequence: int,
    *,
    batch: IngestionBatch | None = None,
) -> SourceDocument:
    assigned_batch = batch or create_batch(sequence)
    operator = create_operator(sequence + 1000)
    return SourceDocument.objects.create(
        ingestion_batch=assigned_batch,
        document_code=f"QUALITY-ISSUE-DOC-{sequence:04d}",
        title=f"Quality issue source {sequence}",
        source_org="Official source organization",
        document_type_code="OFFICIAL_GUIDE",
        official_source_url=f"https://example.test/docs/{sequence}",
        usage_terms_url=f"https://example.test/terms/{sequence}",
        license_note="Internal test fixture license.",
        original_file_uri=f"object://quality-issue/{sequence}.pdf",
        sha256_hash=f"{sequence:064x}",
        collected_by=operator,
    )


def create_page(
    sequence: int,
    *,
    document: SourceDocument | None = None,
) -> DocumentPage:
    return DocumentPage.objects.create(
        document=document or create_document(sequence),
        page_no=1,
    )


def create_chunk(
    sequence: int,
    *,
    page: DocumentPage | None = None,
) -> DocumentChunk:
    return DocumentChunk.objects.create(
        page=page or create_page(sequence),
        chunk_no=1,
        chunk_text=f"Official chunk text {sequence}",
        chunk_text_sha256=f"{sequence:064x}",
        chunking_version="quality-issue-test-v1",
    )


def create_graph(sequence: int) -> dict:
    batch = create_batch(sequence)
    document = create_document(sequence, batch=batch)
    page = create_page(sequence, document=document)
    chunk = create_chunk(sequence, page=page)
    return {
        "batch": batch,
        "document": document,
        "page": page,
        "chunk": chunk,
    }


def issue_values(sequence: int, **overrides) -> dict:
    values = {
        "document": create_document(sequence),
        "issue_type_code": "CONTRACT_REVIEW_PENDING",
        "issue_message": f"Quality issue {sequence}",
    }
    values.update(overrides)
    return values


def create_issue(sequence: int, **overrides) -> DataQualityIssue:
    return DataQualityIssue.objects.create(
        **issue_values(sequence, **overrides)
    )


def test_data_quality_issue_uses_target_identifiers_fields_and_defaults():
    issue = create_issue(1)
    field_names = {
        field.name for field in DataQualityIssue._meta.local_fields
    }

    assert isinstance(issue.pk, int)
    assert isinstance(issue.public_id, UUID)
    assert issue._meta.db_table == "knowledge_data_quality_issue"
    assert issue.severity_code == "ERROR"
    assert issue.status_code == "OPEN"
    assert issue.details == {}
    assert len(field_names) == 19
    assert field_names == {
        "created_at",
        "updated_at",
        "id",
        "public_id",
        "ingestion_batch",
        "document",
        "page",
        "chunk",
        "issue_type_code",
        "validation_rule_code",
        "validator_version",
        "severity_code",
        "issue_message",
        "details",
        "status_code",
        "detected_at",
        "resolved_by",
        "resolved_at",
        "resolution_note",
    }


def test_data_quality_issue_is_exported_and_runtime_registered():
    config = apps.get_app_config("evidence")

    assert config.get_model("DataQualityIssue") is DataQualityIssue
    assert DataQualityIssue._meta.app_label == "evidence"


def test_unapproved_code_fields_remain_open_required_codes():
    issue_type = DataQualityIssue._meta.get_field("issue_type_code")
    severity = DataQualityIssue._meta.get_field("severity_code")
    status = DataQualityIssue._meta.get_field("status_code")

    assert issue_type.choices is None
    assert severity.choices is None
    assert status.choices is None

    issue = create_issue(
        2,
        issue_type_code="TEAM_QUALITY_REVIEW_PENDING",
        severity_code="TEAM_SEVERITY_PENDING",
        status_code="TEAM_STATUS_PENDING",
    )
    assert issue.issue_type_code == "TEAM_QUALITY_REVIEW_PENDING"
    assert issue.severity_code == "TEAM_SEVERITY_PENDING"
    assert issue.status_code == "TEAM_STATUS_PENDING"


def test_fk_policy_and_migration_dependency_match_contract():
    expected_fks = {
        "ingestion_batch": ("evidence.IngestionBatch", True),
        "document": ("evidence.SourceDocument", True),
        "page": ("evidence.DocumentPage", True),
        "chunk": ("evidence.DocumentChunk", True),
        "resolved_by": ("accounts.User", True),
    }
    for name, (label, nullable) in expected_fks.items():
        field = DataQualityIssue._meta.get_field(name)
        assert field.remote_field.model._meta.label == label
        assert field.remote_field.on_delete is models.PROTECT
        assert field.null is nullable
        assert field.db_column == f"{name}_id"
        assert field.db_index is False

    migration = import_module(
        "apps.evidence.migrations.0006_dataqualityissue"
    )
    assert migration.Migration.dependencies == [
        ("accounts", "0003_promote_integer_primary_keys"),
        ("evidence", "0005_documentchunk"),
    ]


def test_indexes_and_constraints_match_approved_contract_range():
    indexes = {
        index.name: (tuple(index.fields), index.condition)
        for index in DataQualityIssue._meta.indexes
    }
    constraints = {
        constraint.name
        for constraint in DataQualityIssue._meta.constraints
    }

    assert indexes == {
        "ix_quality_issue_open": (
            ("severity_code", "detected_at"),
            models.Q(status_code__in=["OPEN", "IN_REVIEW"]),
        ),
        "ix_quality_issue_document": (
            ("document", "page"),
            None,
        ),
        "ix_quality_issue_page": (("page",), None),
        "ix_quality_issue_chunk": (("chunk",), None),
    }
    assert constraints == {
        "ck_quality_issue_target",
        "ck_quality_issue_resolution_bundle",
        "ck_quality_issue_details_object",
    }
    assert not any("allowed" in name for name in constraints)


@pytest.mark.parametrize("target_name", ["document", "page", "chunk"])
def test_exactly_one_quality_target_accepts_each_target(
    target_name: str,
):
    sequence = 10 + len(target_name)
    graph = create_graph(sequence)
    issue = create_issue(
        sequence + 100,
        document=graph["document"] if target_name == "document" else None,
        page=graph["page"] if target_name == "page" else None,
        chunk=graph["chunk"] if target_name == "chunk" else None,
    )

    assert getattr(issue, f"{target_name}_id") == graph[target_name].pk


@pytest.mark.parametrize(
    "target_names",
    [
        (),
        ("document", "page"),
        ("document", "chunk"),
        ("page", "chunk"),
        ("document", "page", "chunk"),
    ],
)
def test_zero_or_multiple_quality_targets_are_database_rejected(
    target_names: tuple[str, ...],
):
    sequence = 30 + len(target_names)
    graph = create_graph(sequence)
    overrides = {
        "document": (
            graph["document"] if "document" in target_names else None
        ),
        "page": graph["page"] if "page" in target_names else None,
        "chunk": graph["chunk"] if "chunk" in target_names else None,
    }

    with pytest.raises(IntegrityError), transaction.atomic():
        create_issue(sequence + 100, **overrides)


def test_target_validation_matches_database_constraint():
    invalid = DataQualityIssue(
        document=None,
        page=None,
        chunk=None,
        issue_type_code="TEAM_REVIEW_PENDING",
        issue_message="Missing target.",
    )

    with pytest.raises(ValidationError) as error:
        invalid.full_clean()
    assert "document" in error.value.message_dict


def test_ingestion_batch_is_optional_context_not_a_quality_target():
    graph = create_graph(50)
    issue = create_issue(
        150,
        ingestion_batch=graph["batch"],
        document=graph["document"],
    )
    assert issue.ingestion_batch == graph["batch"]
    assert issue.document == graph["document"]

    with pytest.raises(IntegrityError), transaction.atomic():
        create_issue(
            151,
            ingestion_batch=graph["batch"],
            document=None,
        )


def test_details_requires_a_json_object_in_validation_and_database():
    valid = create_issue(
        60,
        details={"rule": "PAGE_HASH", "expected": "sha256"},
    )
    assert valid.details["rule"] == "PAGE_HASH"

    invalid = DataQualityIssue(
        document=create_document(61),
        issue_type_code="TEAM_REVIEW_PENDING",
        issue_message="Invalid details.",
        details=["not", "an", "object"],
    )
    with pytest.raises(ValidationError) as error:
        invalid.full_clean()
    assert "details" in error.value.message_dict

    with pytest.raises(IntegrityError), transaction.atomic():
        create_issue(62, details=["not", "an", "object"])


def test_resolution_bundle_is_independent_from_open_status_codes():
    resolver = create_operator(70)
    resolved_at = timezone.now()

    open_with_bundle = create_issue(
        70,
        status_code="OPEN",
        resolved_by=resolver,
        resolved_at=resolved_at,
        resolution_note="Corrected source metadata.",
    )
    resolved_without_bundle = create_issue(
        71,
        status_code="RESOLVED",
    )

    assert open_with_bundle.resolved_by == resolver
    assert resolved_without_bundle.resolved_by is None


@pytest.mark.parametrize(
    ("include_resolver", "include_resolved_at", "include_note"),
    [
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, False),
        (True, False, True),
        (False, True, True),
    ],
)
def test_partial_resolution_bundle_is_database_rejected(
    include_resolver: bool,
    include_resolved_at: bool,
    include_note: bool,
):
    sequence = (
        80
        + int(include_resolver)
        + int(include_resolved_at) * 2
        + int(include_note) * 4
    )
    resolver = create_operator(sequence)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_issue(
            sequence,
            status_code="TEAM_STATUS_PENDING",
            resolved_by=resolver if include_resolver else None,
            resolved_at=timezone.now() if include_resolved_at else None,
            resolution_note="Resolution." if include_note else None,
        )


def test_public_id_is_unique():
    first = create_issue(100)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_issue(101, public_id=first.public_id)


def test_all_quality_issue_relationships_use_protect():
    context_batch = create_batch(200)
    document_target = create_document(201)
    page_target = create_page(202)
    chunk_target = create_chunk(203)
    resolver = create_operator(204)

    create_issue(
        210,
        ingestion_batch=context_batch,
        document=document_target,
    )
    create_issue(211, document=None, page=page_target)
    create_issue(212, document=None, chunk=chunk_target)
    create_issue(
        213,
        resolved_by=resolver,
        resolved_at=timezone.now(),
        resolution_note="Resolved by operator.",
    )

    with pytest.raises(ProtectedError):
        context_batch.delete()
    with pytest.raises(ProtectedError):
        document_target.delete()
    with pytest.raises(ProtectedError):
        page_target.delete()
    with pytest.raises(ProtectedError):
        chunk_target.delete()
    with pytest.raises(ProtectedError):
        resolver.delete()


def test_postgresql_catalog_contains_target_types_constraints_and_indexes():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL catalog assertion")

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'knowledge_data_quality_issue'
              AND column_name IN (
                  'id',
                  'public_id',
                  'ingestion_batch_id',
                  'document_id',
                  'page_id',
                  'chunk_id',
                  'resolved_by_id'
              )
            """
        )
        column_types = dict(cursor.fetchall())
        cursor.execute(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'knowledge_data_quality_issue'::regclass
            ORDER BY conname
            """
        )
        constraints = {row[0] for row in cursor.fetchall()}
        cursor.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = 'knowledge_data_quality_issue'
              AND indexname IN (
                  'ix_quality_issue_open',
                  'ix_quality_issue_document',
                  'ix_quality_issue_page',
                  'ix_quality_issue_chunk'
              )
            """
        )
        indexes = dict(cursor.fetchall())

    assert column_types == {
        "id": "bigint",
        "public_id": "uuid",
        "ingestion_batch_id": "bigint",
        "document_id": "bigint",
        "page_id": "bigint",
        "chunk_id": "bigint",
        "resolved_by_id": "bigint",
    }
    assert {
        "ck_quality_issue_target",
        "ck_quality_issue_resolution_bundle",
        "ck_quality_issue_details_object",
    } <= constraints
    assert set(indexes) == {
        "ix_quality_issue_open",
        "ix_quality_issue_document",
        "ix_quality_issue_page",
        "ix_quality_issue_chunk",
    }
    assert "status_code" in indexes["ix_quality_issue_open"]
    assert "OPEN" in indexes["ix_quality_issue_open"]
    assert "IN_REVIEW" in indexes["ix_quality_issue_open"]
