"""CommonCodeGroup 계약·제약 검증."""

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.common_codes.models import CommonCodeGroup


pytestmark = pytest.mark.django_db


def create_group(**overrides) -> CommonCodeGroup:
    sequence = CommonCodeGroup.objects.count() + 1
    values = {
        "group_code": f"TEST_GROUP_{sequence}",
        "group_name": f"테스트 그룹 {sequence}",
    }
    values.update(overrides)
    return CommonCodeGroup.objects.create(**values)


def test_group_is_registered_as_natural_key_model():
    group = create_group()

    assert (
        apps.get_model("common_codes", "CommonCodeGroup")
        is CommonCodeGroup
    )
    assert CommonCodeGroup._meta.db_table == "common_code_group"
    assert group.pk == "TEST_GROUP_1"
    assert group.display_order == 0
    assert group.is_active is True


def test_group_code_requires_uppercase_contract_format():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_group(group_code="risk_level")

    with pytest.raises(IntegrityError), transaction.atomic():
        create_group(group_code="1INVALID")


def test_display_order_cannot_be_negative():
    with pytest.raises(IntegrityError), transaction.atomic():
        create_group(display_order=-1)


def test_group_code_cannot_change_after_creation():
    group = create_group()
    group.group_code = "RENAMED_GROUP"

    with pytest.raises(ValidationError, match="생성 후 변경"):
        group.save()


def test_group_cannot_be_physically_deleted_through_model():
    group = create_group()

    with pytest.raises(ValidationError, match="비활성화"):
        group.delete()

    assert CommonCodeGroup.objects.filter(pk=group.pk).exists()


def test_group_cannot_be_physically_deleted_through_queryset():
    group = create_group()

    with pytest.raises(ValidationError, match="비활성화"):
        CommonCodeGroup.objects.filter(pk=group.pk).delete()

    assert CommonCodeGroup.objects.filter(pk=group.pk).exists()


def test_group_code_cannot_change_through_queryset_update():
    group = create_group()

    with pytest.raises(ValidationError, match="생성 후 변경"):
        CommonCodeGroup.objects.filter(pk=group.pk).update(
            group_code="RENAMED_GROUP"
        )

    assert CommonCodeGroup.objects.filter(pk=group.pk).exists()


def test_active_index_is_declared_in_contract_order():
    indexes = {
        index.name: tuple(index.fields)
        for index in CommonCodeGroup._meta.indexes
    }

    assert indexes["ix_common_code_group_active"] == (
        "is_active",
        "display_order",
    )
