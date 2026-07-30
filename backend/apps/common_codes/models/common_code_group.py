"""공통코드 그룹 Model."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from common.models.base import TimestampedModel


class ProtectedDeletionQuerySet(models.QuerySet):
    """공통코드 그룹의 QuerySet 삭제·자연키 변경을 차단한다."""

    def delete(self) -> tuple[int, dict[str, int]]:
        raise ValidationError(
            "공통코드 그룹은 물리 삭제하지 않고 is_active=False로 "
            "비활성화해야 합니다."
        )

    def update(self, **kwargs: Any) -> int:
        if {"group_code", "pk"} & kwargs.keys():
            raise ValidationError(
                "group_code는 생성 후 변경할 수 없습니다."
            )
        return super().update(**kwargs)


class CommonCodeGroup(TimestampedModel):
    """업무 공통코드의 변경 불가 자연키 그룹."""

    objects = ProtectedDeletionQuerySet.as_manager()

    group_code = models.CharField(max_length=40, primary_key=True)
    group_name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "common_code_group"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    group_code__regex=r"^[A-Z][A-Z0-9_]*$"
                ),
                name="ck_common_code_group_code_format",
            ),
            models.CheckConstraint(
                condition=models.Q(display_order__gte=0),
                name="ck_common_code_group_order_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["is_active", "display_order"],
                name="ix_common_code_group_active",
            )
        ]

    @classmethod
    def from_db(
        cls,
        db: str,
        field_names: list[str],
        values: list[Any],
    ) -> CommonCodeGroup:
        instance = super().from_db(db, field_names, values)
        instance._loaded_group_code = instance.group_code
        return instance

    def save(self, *args: Any, **kwargs: Any) -> None:
        loaded_group_code = getattr(self, "_loaded_group_code", None)
        if (
            not self._state.adding
            and loaded_group_code is not None
            and self.group_code != loaded_group_code
        ):
            raise ValidationError(
                {"group_code": "group_code는 생성 후 변경할 수 없습니다."}
            )
        super().save(*args, **kwargs)
        self._loaded_group_code = self.group_code

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        del args, kwargs
        raise ValidationError(
            "공통코드 그룹은 물리 삭제하지 않고 is_active=False로 "
            "비활성화해야 합니다."
        )

    def __str__(self) -> str:
        return f"{self.group_code} ({self.group_name})"
