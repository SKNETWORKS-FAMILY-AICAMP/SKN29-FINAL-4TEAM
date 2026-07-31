"""T-005 document-to-product applicability contract tests."""

from datetime import date
from importlib import import_module
from uuid import UUID, uuid4

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.evidence.models import (
    DocumentModelScope,
    IngestionBatch,
    SourceDocument,
)
from apps.products.models import ProductModel


pytestmark = pytest.mark.django_db


def create_operator(sequence: int) -> User:
    return User.objects.create_user(
        username=f"MODEL-SCOPE-OP-{sequence:03d}",
        password=None,
        full_name=f"Model scope operator {sequence}",
        role_code=User.Role.OPERATOR,
        employee_no=f"MODEL-SCOPE-EMP-{sequence:03d}",
    )


def create_product(sequence: int) -> ProductModel:
    return ProductModel.objects.create(
        model_code=f"MODEL-SCOPE-PRODUCT-{sequence:03d}",
        model_name=f"Model scope product {sequence}",
    )


def create_document(sequence: int) -> SourceDocument:
    operator = create_operator(sequence + 1000)
    batch = IngestionBatch.objects.create(
        batch_no=f"MODEL-SCOPE-BATCH-{sequence:03d}",
        source_type_code=IngestionBatch.SourceType.LOCAL_FILE,
        idempotency_key=f"model-scope-batch-{sequence:03d}",
        correlation_id=uuid4(),
        pipeline_version="model-scope-test-v1",
    )
    return SourceDocument.objects.create(
        ingestion_batch=batch,
        document_code=f"MODEL-SCOPE-DOC-{sequence:03d}",
        title=f"Model scope document {sequence}",
        source_org="Official source organization",
        document_type_code="OFFICIAL_GUIDE",
        official_source_url=f"https://example.test/docs/{sequence}",
        usage_terms_url=f"https://example.test/terms/{sequence}",
        license_note="Internal test fixture license.",
        original_file_uri=f"object://model-scope/{sequence}.pdf",
        sha256_hash=f"{sequence:064x}",
        collected_by=operator,
    )


def create_scope(
    sequence: int,
    *,
    document: SourceDocument | None = None,
    product: ProductModel | None = None,
    **overrides,
) -> DocumentModelScope:
    values = {
        "document": document or create_document(sequence),
        "product_model": product or create_product(sequence),
    }
    values.update(overrides)
    return DocumentModelScope.objects.create(**values)


def test_document_model_scope_uses_target_identifiers_and_fields():
    scope = create_scope(1)
    field_names = {
        field.name for field in DocumentModelScope._meta.local_fields
    }

    assert isinstance(scope.pk, int)
    assert isinstance(scope.public_id, UUID)
    assert scope._meta.db_table == "knowledge_document_model_scope"
    assert scope.is_verified is False
    assert len(field_names) == 12
    assert field_names == {
        "created_at",
        "updated_at",
        "id",
        "public_id",
        "document",
        "product_model",
        "applicable_from",
        "applicable_to",
        "applicability_note",
        "is_verified",
        "verified_by",
        "verified_at",
    }


def test_document_model_scope_is_exported_and_runtime_registered():
    config = apps.get_app_config("evidence")

    assert config.get_model("DocumentModelScope") is DocumentModelScope
    assert DocumentModelScope._meta.app_label == "evidence"


def test_fk_policy_and_migration_dependencies_match_contract():
    expected_fks = {
        "document": (
            "evidence.SourceDocument",
            False,
            "document_id",
        ),
        "product_model": (
            "products.ProductModel",
            False,
            "product_model_id",
        ),
        "verified_by": (
            "accounts.User",
            True,
            "verified_by_id",
        ),
    }
    for name, (label, nullable, db_column) in expected_fks.items():
        field = DocumentModelScope._meta.get_field(name)
        assert field.remote_field.model._meta.label == label
        assert field.remote_field.on_delete is models.PROTECT
        assert field.null is nullable
        assert field.db_column == db_column
        assert field.db_index is False

    migration = import_module(
        "apps.evidence.migrations.0003_documentmodelscope"
    )
    assert migration.Migration.dependencies == [
        ("accounts", "0003_promote_integer_primary_keys"),
        ("evidence", "0002_sourcedocument"),
        ("products", "0001_initial"),
    ]


def test_indexes_and_constraints_match_contract():
    indexes = {
        index.name: tuple(index.fields)
        for index in DocumentModelScope._meta.indexes
    }
    constraints = {
        constraint.name
        for constraint in DocumentModelScope._meta.constraints
    }

    assert indexes == {
        "ix_model_scope_model": (
            "product_model",
            "is_verified",
            "applicable_from",
            "applicable_to",
        ),
    }
    assert constraints == {
        "ux_document_model_scope",
        "ck_model_scope_period",
        "ck_model_scope_verification",
    }


def test_valid_verified_scope_persists_complete_bundle():
    verifier = create_operator(50)
    verified_at = timezone.now()
    scope = create_scope(
        5,
        applicable_from=date(2025, 1, 1),
        applicable_to=date(2025, 12, 31),
        is_verified=True,
        verified_by=verifier,
        verified_at=verified_at,
    )

    assert scope.is_verified is True
    assert scope.verified_by == verifier
    assert scope.verified_at == verified_at


def test_period_order_is_enforced_by_validation_and_database():
    invalid = DocumentModelScope(
        document=create_document(6),
        product_model=create_product(6),
        applicable_from=date(2025, 2, 1),
        applicable_to=date(2025, 1, 31),
    )
    with pytest.raises(ValidationError) as validation_error:
        invalid.full_clean()
    assert "applicable_to" in validation_error.value.message_dict

    with pytest.raises(IntegrityError), transaction.atomic():
        create_scope(
            7,
            applicable_from=date(2025, 2, 1),
            applicable_to=date(2025, 1, 31),
        )


@pytest.mark.parametrize(
    (
        "is_verified",
        "include_verifier",
        "include_verified_at",
    ),
    [
        (True, False, False),
        (True, True, False),
        (True, False, True),
        (False, True, True),
    ],
)
def test_incomplete_verification_bundle_is_database_rejected(
    is_verified: bool,
    include_verifier: bool,
    include_verified_at: bool,
):
    verifier = create_operator(
        70
        + int(is_verified)
        + int(include_verifier) * 2
        + int(include_verified_at) * 4
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        create_scope(
            70
            + int(is_verified)
            + int(include_verifier) * 2
            + int(include_verified_at) * 4,
            is_verified=is_verified,
            verified_by=verifier if include_verifier else None,
            verified_at=(
                timezone.now() if include_verified_at else None
            ),
        )


def test_document_product_pair_and_public_id_are_unique():
    document = create_document(80)
    product = create_product(80)
    first = create_scope(
        80,
        document=document,
        product=product,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_scope(
            81,
            document=document,
            product=product,
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        create_scope(82, public_id=first.public_id)


def test_all_relationships_use_protect():
    verifier = create_operator(90)
    document = create_document(90)
    product = create_product(90)
    create_scope(
        90,
        document=document,
        product=product,
        is_verified=True,
        verified_by=verifier,
        verified_at=timezone.now(),
    )

    with pytest.raises(ProtectedError):
        document.delete()
    with pytest.raises(ProtectedError):
        product.delete()
    with pytest.raises(ProtectedError):
        verifier.delete()
