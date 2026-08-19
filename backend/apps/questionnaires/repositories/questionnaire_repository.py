"""ORM boundary for CARE_PRECHECK sessions."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from apps.questionnaires.models import QuestionnaireSession
from apps.subscriptions.models import CustomerSubscription


class QuestionnaireRepository:
    """Apply ownership masking and row locks in one place."""

    @staticmethod
    def find_active_owned_subscription(
        *,
        subscription_public_id: UUID,
        actor: Any,
    ) -> CustomerSubscription | None:
        return (
            CustomerSubscription.objects.select_related(
                "customer",
                "customer__user",
                "product_model",
            )
            .filter(
                public_id=subscription_public_id,
                customer__user=actor,
                customer__deleted_at__isnull=True,
                status_code=CustomerSubscription.Status.ACTIVE,
            )
            .first()
        )

    @staticmethod
    def get_owned_session(
        *,
        session_public_id: UUID,
        actor: Any,
    ) -> QuestionnaireSession | None:
        return (
            QuestionnaireSession.objects.select_related(
                "subscription",
                "subscription__customer",
                "subscription__customer__user",
                "inquiry",
            )
            .filter(
                public_id=session_public_id,
                subscription__customer__user=actor,
                subscription__customer__deleted_at__isnull=True,
            )
            .first()
        )

    @staticmethod
    def lock_owned_session(
        *,
        session_public_id: UUID,
        actor: Any,
    ) -> QuestionnaireSession | None:
        return (
            QuestionnaireSession.objects.select_for_update(of=("self",))
            .select_related(
                "subscription",
                "subscription__customer",
                "subscription__customer__user",
                "inquiry",
            )
            .filter(
                public_id=session_public_id,
                subscription__customer__user=actor,
                subscription__customer__deleted_at__isnull=True,
            )
            .first()
        )

    @staticmethod
    def lock_link_candidate(
        *,
        session_public_id: UUID,
        actor: Any,
        subscription: CustomerSubscription,
    ) -> QuestionnaireSession | None:
        return (
            QuestionnaireSession.objects.select_for_update(of=("self",))
            .select_related("subscription", "inquiry")
            .filter(
                public_id=session_public_id,
                subscription=subscription,
                subscription__customer__user=actor,
                subscription__customer__deleted_at__isnull=True,
            )
            .first()
        )
