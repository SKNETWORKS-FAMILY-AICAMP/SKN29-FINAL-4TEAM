"""ORM boundary for consultant-visible HumanReview rows."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import Q, QuerySet

from apps.inquiries.models import HumanReview, Inquiry


class HumanReviewRepository:
    """Apply role, ownership, and synthetic-data masking before reads."""

    @staticmethod
    def visible_to(actor: Any) -> QuerySet[HumanReview]:
        ownership = Q(inquiry__assigned_user=actor) | Q(
            inquiry__assigned_user__isnull=True,
            inquiry__assigned_role_code=Inquiry.AssignedRole.NONE,
        )
        return (
            HumanReview.objects.filter(
                ownership,
                inquiry__initiated_by__is_synthetic=True,
            )
            .select_related(
                "inquiry__subscription__product_model",
                "guidance",
                "published_guidance",
            )
            .prefetch_related(
                "guidance__items",
                "published_guidance__items",
            )
        )

    @classmethod
    def list_pending(cls, actor: Any) -> QuerySet[HumanReview]:
        return cls.visible_to(actor).filter(
            status_code=HumanReview.Status.PENDING
        ).order_by("created_at", "public_id")

    @classmethod
    def retrieve_visible(
        cls,
        *,
        actor: Any,
        review_public_id: UUID,
    ) -> HumanReview | None:
        return cls.visible_to(actor).filter(public_id=review_public_id).first()

    @classmethod
    def lock_visible(
        cls,
        *,
        actor: Any,
        review_public_id: UUID,
    ) -> HumanReview | None:
        return (
            cls.visible_to(actor)
            .select_for_update()
            .filter(public_id=review_public_id)
            .first()
        )
