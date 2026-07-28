"""T-016 공통 추상 Model의 결정 독립적인 필드 계약을 검증한다."""

from django.db import models

from common.models.base import TimestampedModel
from common.models.soft_delete import SoftDeleteModel


def test_timestamped_model_is_abstract_and_has_only_time_policy():
    assert TimestampedModel._meta.abstract is True

    created_at = TimestampedModel._meta.get_field("created_at")
    updated_at = TimestampedModel._meta.get_field("updated_at")

    assert isinstance(created_at, models.DateTimeField)
    assert created_at.auto_now_add is True
    assert isinstance(updated_at, models.DateTimeField)
    assert updated_at.auto_now is True


def test_soft_delete_model_is_abstract_field_only_contract():
    assert SoftDeleteModel._meta.abstract is True

    deleted_at = SoftDeleteModel._meta.get_field("deleted_at")

    assert isinstance(deleted_at, models.DateTimeField)
    assert deleted_at.null is True
    assert deleted_at.blank is True
    assert deleted_at.db_index is True
    assert SoftDeleteModel.delete is models.Model.delete
