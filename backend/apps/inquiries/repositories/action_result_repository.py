"""ORM boundary for append-only T-022 customer action results."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import Max

from apps.inquiries.models import (
    CustomerActionResult,
    GuidanceItem,
    Inquiry,
)


class ActionResultRepository:
    """Keep guidance ownership and attempt numbering inside one aggregate."""

    @staticmethod
    def lock_guidance_item(
        *,
        inquiry: Inquiry,
        guidance_item_public_id: UUID,
    ) -> GuidanceItem | None:
        return (
            GuidanceItem.objects.select_for_update()
            .select_related("guidance")
            .filter(
                public_id=guidance_item_public_id,
                guidance__inquiry=inquiry,
            )
            .first()
        )

    @staticmethod
    def next_attempt_no(*, guidance_item: GuidanceItem) -> int:
        latest = guidance_item.action_results.aggregate(
            value=Max("attempt_no")
        )["value"]
        return (latest or 0) + 1

    @staticmethod
    def create(
        *,
        guidance_item: GuidanceItem,
        actor: Any,
        attempt_no: int,
        validated_data: dict,
        request_token: UUID,
    ) -> CustomerActionResult:
        result = CustomerActionResult(
            guidance_item=guidance_item,
            attempt_no=attempt_no,
            result_code=validated_data["result_code"],
            result_text=validated_data.get("result_text"),
            performed_at=validated_data.get("performed_at"),
            customer_comment=validated_data.get("customer_comment"),
            submitted_by=actor,
            # The canonical actor/operation/key value is stored by
            # IdempotencyRecord. This legacy globally-unique column keeps a
            # non-secret request token so different actors may reuse a key.
            idempotency_key=str(request_token),
        )
        result.full_clean()
        result.save()
        return result
