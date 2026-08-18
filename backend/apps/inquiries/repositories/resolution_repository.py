"""ORM boundary for T-023 completion feedback and finalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from django.utils import timezone

from apps.consultations.models import Consultation
from apps.inquiries.models import FollowupConfirmation, Inquiry
from apps.visits.models import Visit


@dataclass(frozen=True)
class CompletedHandling:
    source_code: str
    completed_at: Any
    handler: Any
    consultation: Consultation | None = None
    visit: Visit | None = None


class ResolutionRepository:
    """Lock one completion aggregate and preserve its source lineage."""

    @staticmethod
    def lock_staff_inquiry(*, inquiry_public_id: UUID) -> Inquiry | None:
        return (
            Inquiry.objects.select_for_update()
            .select_related(
                "subscription__customer__user",
                "assigned_user",
            )
            .filter(public_id=inquiry_public_id)
            .first()
        )

    @staticmethod
    def lock_assigned_consultant_inquiry(
        *,
        inquiry_public_id: UUID,
        actor: Any,
    ) -> Inquiry | None:
        return (
            Inquiry.objects.select_for_update()
            .select_related(
                "subscription__customer__user",
                "assigned_user",
            )
            .filter(
                public_id=inquiry_public_id,
                assigned_user=actor,
                assigned_role_code=Inquiry.AssignedRole.CONSULTANT,
            )
            .first()
        )

    @staticmethod
    def lock_completed_handling(inquiry: Inquiry) -> CompletedHandling | None:
        consultation = (
            Consultation.objects.select_for_update()
            .select_related("consultant")
            .filter(
                inquiry=inquiry,
                status=Consultation.Status.COMPLETED,
                completed_at__isnull=False,
            )
            .order_by("-completed_at", "-id")
            .first()
        )
        visit = (
            Visit.objects.select_for_update()
            .select_related("technician")
            .filter(
                inquiry=inquiry,
                status=Visit.Status.COMPLETED,
                completed_at__isnull=False,
            )
            .order_by("-completed_at", "-id")
            .first()
        )
        if consultation is None and visit is None:
            return None
        if visit is not None and (
            consultation is None
            or visit.completed_at >= consultation.completed_at
        ):
            return CompletedHandling(
                source_code="VISIT",
                completed_at=visit.completed_at,
                handler=visit.technician,
                visit=visit,
            )
        return CompletedHandling(
            source_code="CONSULTATION",
            completed_at=consultation.completed_at,
            handler=consultation.consultant,
            consultation=consultation,
        )

    @staticmethod
    def create_resolved_feedback(
        *,
        inquiry: Inquiry,
        handling: CompletedHandling,
        state_version: int,
        comment: str | None,
    ) -> FollowupConfirmation:
        now = timezone.now()
        followup = FollowupConfirmation(
            followup_code=f"FUP-{uuid4().hex.upper()}",
            inquiry=inquiry,
            consultation=handling.consultation,
            visit=handling.visit,
            channel_code=ResolutionRepository._channel(inquiry),
            resolution_status_code=(
                FollowupConfirmation.ResolutionStatus.RESOLVED
            ),
            state_version=state_version,
            customer_response=comment,
            next_action=FollowupConfirmation.NextAction.FINALIZE_INQUIRY,
            requested_at=handling.completed_at,
            responded_at=now,
            confirmed_at=now,
        )
        followup.full_clean()
        followup.save()
        return followup

    @staticmethod
    def create_unresolved_feedback(
        *,
        inquiry: Inquiry,
        handling: CompletedHandling,
        state_version: int,
        reason_code: str | None,
        comment: str | None,
    ) -> FollowupConfirmation:
        followup = FollowupConfirmation(
            followup_code=f"FUP-{uuid4().hex.upper()}",
            inquiry=inquiry,
            consultation=handling.consultation,
            visit=handling.visit,
            channel_code=ResolutionRepository._channel(inquiry),
            resolution_status_code=(
                FollowupConfirmation.ResolutionStatus.REOPENED
            ),
            state_version=state_version,
            customer_response=comment,
            unresolved_reason=reason_code or "",
            next_action=(
                FollowupConfirmation.NextAction.RESUME_CONSULTATION
            ),
            requested_at=handling.completed_at,
            responded_at=timezone.now(),
        )
        followup.full_clean()
        followup.save()
        return followup

    @staticmethod
    def fresh_resolved_feedback_exists(
        *,
        inquiry: Inquiry,
        handling: CompletedHandling,
    ) -> bool:
        return inquiry.followup_confirmations.filter(
            resolution_status_code=(
                FollowupConfirmation.ResolutionStatus.RESOLVED
            ),
            created_at__gt=handling.completed_at,
        ).exists()

    @staticmethod
    def _channel(inquiry: Inquiry) -> str:
        mapping = {
            Inquiry.Channel.WEB: FollowupConfirmation.Channel.WEB,
            Inquiry.Channel.MOBILE: FollowupConfirmation.Channel.APP,
            Inquiry.Channel.PHONE: FollowupConfirmation.Channel.PHONE,
        }
        try:
            return mapping[inquiry.channel_code]
        except KeyError as exc:
            raise ValueError(
                "A confirmed customer channel is required for feedback."
            ) from exc
