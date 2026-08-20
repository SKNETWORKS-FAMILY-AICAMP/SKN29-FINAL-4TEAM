"""ORM boundary for sanitized AI consultation handoffs."""

from __future__ import annotations

from apps.consultations.models import Consultation, ConsultationHandoff
from apps.inquiries.models import Inquiry


class ConsultationHandoffRepository:
    """Lock, create, and attach one handoff without changing Inquiry state."""

    @staticmethod
    def lock_existing(
        *, inquiry: Inquiry, ai_request_id: str
    ) -> ConsultationHandoff | None:
        return (
            ConsultationHandoff.objects.select_for_update()
            .filter(inquiry=inquiry, ai_request_id=ai_request_id)
            .first()
        )

    @staticmethod
    def create(**values) -> ConsultationHandoff:
        handoff = ConsultationHandoff(**values)
        handoff.full_clean()
        handoff.save(force_insert=True)
        return handoff

    @staticmethod
    def attach_to_latest_consultation(
        *,
        inquiry: Inquiry,
        consultation: Consultation | None = None,
        handoff: ConsultationHandoff | None = None,
    ) -> ConsultationHandoff | None:
        if consultation is None:
            consultation = (
                Consultation.objects.select_for_update()
                .filter(
                    inquiry=inquiry,
                    status__in=[
                        Consultation.Status.WAITING,
                        Consultation.Status.ASSIGNED,
                        Consultation.Status.IN_PROGRESS,
                    ],
                )
                .order_by("-sequence", "-id")
                .first()
            )
        if consultation is None:
            return None

        if handoff is None:
            handoff = (
                ConsultationHandoff.objects.select_for_update()
                .filter(inquiry=inquiry)
                .order_by("-created_at", "-id")
                .first()
            )
        else:
            handoff = (
                ConsultationHandoff.objects.select_for_update()
                .filter(pk=handoff.pk, inquiry=inquiry)
                .first()
            )
        if handoff is None:
            return None
        if handoff.consultation_id not in (None, consultation.id):
            return None

        if handoff.consultation_id != consultation.id:
            handoff.consultation = consultation
            handoff.save(update_fields=["consultation", "updated_at"])
        if consultation.ai_draft_summary != handoff.ai_draft_summary:
            consultation.ai_draft_summary = handoff.ai_draft_summary
            consultation.save(update_fields=["ai_draft_summary", "updated_at"])
        return handoff
