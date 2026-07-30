"""CommonCode 계약·제약 검증."""

from uuid import UUID

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import PROTECT

from apps.common_codes.models import CommonCode, CommonCodeGroup


pytestmark = pytest.mark.django_db


@pytest.fixture
def group() -> CommonCodeGroup:
    return CommonCodeGroup.objects.create(
        group_code="TEST_STATUS",
        group_name="테스트 상태",
    )


def create_code(
    group: CommonCodeGroup,
    **overrides,
) -> CommonCode:
    sequence = CommonCode.objects.count() + 1
    values = {
        "group": group,
        "code": f"CODE_{sequence}",
        "code_name": f"테스트 코드 {sequence}",
    }
    values.update(overrides)
    return CommonCode.objects.create(**values)


def test_code_is_registered_with_contract_uuid_identifier(
    group: CommonCodeGroup,
):
    code = create_code(group)

    assert apps.get_model("common_codes", "CommonCode") is CommonCode
    assert CommonCode._meta.db_table == "common_code"
    assert isinstance(code.pk, int)
    assert isinstance(code.public_id, UUID)
    assert code.group_id == "TEST_STATUS"
    assert code.metadata == {}


def test_group_foreign_key_uses_contract_column_and_protects_group(
    group: CommonCodeGroup,
):
    create_code(group)
    field = CommonCode._meta.get_field("group")

    assert field.column == "group_code"
    assert field.target_field.name == "group_code"
    assert field.remote_field.on_delete is PROTECT


def test_group_and_code_combination_is_unique(
    group: CommonCodeGroup,
):
    create_code(group, code="ACTIVE")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_code(group, code="ACTIVE")


def test_public_identifier_is_unique(
    group: CommonCodeGroup,
):
    code = create_code(group)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_code(group, public_id=code.public_id)


def test_code_requires_uppercase_contract_format(
    group: CommonCodeGroup,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        create_code(group, code="general")


def test_display_order_cannot_be_negative(
    group: CommonCodeGroup,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        create_code(group, display_order=-1)


def test_metadata_validator_rejects_non_object(
    group: CommonCodeGroup,
):
    code = CommonCode(
        group=group,
        code="ARRAY_METADATA",
        code_name="배열 메타데이터",
        metadata=[{"unexpected": True}],
    )

    with pytest.raises(ValidationError, match="JSON object"):
        code.full_clean()


def test_database_constraint_rejects_non_object_metadata(
    group: CommonCodeGroup,
):
    with pytest.raises(IntegrityError), transaction.atomic():
        create_code(group, metadata=[])


def test_active_index_is_declared_in_contract_order():
    indexes = {
        index.name: tuple(index.fields)
        for index in CommonCode._meta.indexes
    }

    assert indexes["ix_common_code_active"] == (
        "group",
        "is_active",
        "display_order",
    )
