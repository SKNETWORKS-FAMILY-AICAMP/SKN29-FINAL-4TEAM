"""공통 생성·수정 시각 필드를 제공하는 추상 Model."""

from django.db import models


class TimestampedModel(models.Model):
    """구체 Model에 생성·수정 시각 필드만 상속한다."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
