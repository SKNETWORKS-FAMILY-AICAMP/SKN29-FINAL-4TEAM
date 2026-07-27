"""논리 삭제 시각 필드를 제공하는 추상 Model."""

from django.db import models


class SoftDeleteModel(models.Model):
    """삭제 동작·Manager 정책을 정하지 않고 deleted_at 필드만 제공한다."""

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    class Meta:
        abstract = True
