"""ORM boundary for consultant-visible HumanReview rows."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import F, Q, QuerySet

from apps.inquiries.models import HumanReview, Inquiry
from apps.inquiries.p1_team_routing import P1TeamConsultantRouting


class HumanReviewRepository:
    """Apply role, ownership, and synthetic-data masking before reads."""

    @staticmethod
    def visible_to(actor: Any) -> QuerySet[HumanReview]:
        ownership = Q(inquiry__assigned_user=actor) | Q(
            inquiry__assigned_user__isnull=True,
            inquiry__assigned_role_code=Inquiry.AssignedRole.NONE,
        )
        queryset = (
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
                "guidance__evidence_links",
                "published_guidance__items",
            )
        )
        reserved_contracts = P1TeamConsultantRouting.reserved_contracts()
        assigned_contract = P1TeamConsultantRouting.assigned_contract(actor)
        if assigned_contract is None:
            return queryset.exclude(
                inquiry__subscription__contract_no__in=reserved_contracts
            )
        return queryset.filter(
            Q(inquiry__subscription__contract_no=assigned_contract)
            | ~Q(inquiry__subscription__contract_no__in=reserved_contracts)
        )

    @classmethod
    def list_pending(cls, actor: Any) -> QuerySet[HumanReview]:
        return cls.visible_to(actor).filter(
            status_code=HumanReview.Status.PENDING,
            inquiry__status_code=Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS,
            source_inquiry_state_version=F("inquiry__state_version"),
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
            cls._lock_visible_queryset(actor)
            .filter(public_id=review_public_id)
            .first()
        )

    @classmethod
    def _lock_visible_queryset(cls, actor: Any) -> QuerySet[HumanReview]:
        """Lock only the ledger row, not nullable projection joins.

        ``visible_to`` joins the optional published Guidance for the response
        projection. PostgreSQL rejects an unscoped ``FOR UPDATE`` on that
        nullable outer join, so the decision transaction explicitly locks the
        HumanReview row itself.
        """

        return cls.visible_to(actor).select_for_update(of=("self",))
