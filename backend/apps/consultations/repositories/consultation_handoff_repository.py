"""ORM boundary for sanitized AI consultation handoffs."""

from __future__ import annotations

from django.db.models import Q

from apps.consultations.models import Consultation, ConsultationHandoff
from apps.inquiries.models import Inquiry


class ConsultationHandoffRepository:
    """Lock, create, and attach one handoff without changing Inquiry state."""

    V2_SCHEMA_VERSION = "2.0.0"
    LEDGER_ONLY_ROUTES = {"HARNESS_ESCALATE"}

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
            candidates = list(
                ConsultationHandoff.objects.select_for_update()
                .select_related("ai_run")
                .filter(inquiry=inquiry)
                .filter(Q(consultation__isnull=True) | Q(consultation=consultation))
                .order_by("-created_at", "-id")
            )
            handoff = max(
                (
                    item
                    for item in candidates
                    if ConsultationHandoffRepository._is_projection_eligible(item)
                ),
                key=ConsultationHandoffRepository._projection_rank,
                default=None,
            )
        else:
            handoff = (
                ConsultationHandoff.objects.select_for_update()
                .select_related("ai_run")
                .filter(pk=handoff.pk, inquiry=inquiry)
                .first()
            )
        if handoff is None:
            return None
        if not ConsultationHandoffRepository._is_projection_eligible(handoff):
            return None
        if handoff.consultation_id not in (None, consultation.id):
            return None

        projected = list(
            ConsultationHandoff.objects.select_for_update()
            .select_related("ai_run")
            .filter(consultation=consultation)
            .exclude(pk=handoff.pk)
        )
        newest_projection = max(
            projected,
            key=ConsultationHandoffRepository._projection_rank,
            default=None,
        )
        if (
            newest_projection is not None
            and ConsultationHandoffRepository._projection_rank(newest_projection)
            > ConsultationHandoffRepository._projection_rank(handoff)
        ):
            return None

        if handoff.consultation_id != consultation.id:
            handoff.consultation = consultation
            handoff.save(update_fields=["consultation", "updated_at"])
        if consultation.ai_draft_summary != handoff.ai_draft_summary:
            consultation.ai_draft_summary = handoff.ai_draft_summary
            consultation.save(update_fields=["ai_draft_summary", "updated_at"])
        return handoff

    @staticmethod
    def _is_projection_eligible(handoff: ConsultationHandoff) -> bool:
        if handoff.schema_version != ConsultationHandoffRepository.V2_SCHEMA_VERSION:
            return True
        route = handoff.sanitized_payload.get("routing_reason")
        return route not in ConsultationHandoffRepository.LEDGER_ONLY_ROUTES

    @staticmethod
    def _projection_rank(handoff: ConsultationHandoff) -> tuple[int, float, int]:
        payload_version = handoff.sanitized_payload.get("state_version")
        input_payload = handoff.ai_run.input_payload
        input_version = (
            input_payload.get("state_version")
            if isinstance(input_payload, dict)
            else None
        )
        source_version = (
            payload_version
            if isinstance(payload_version, int) and not isinstance(payload_version, bool)
            else input_version
        )
        if not isinstance(source_version, int) or isinstance(source_version, bool):
            source_version = 0
        completed_at = handoff.ai_run.completed_at or handoff.created_at
        completed_rank = completed_at.timestamp() if completed_at is not None else 0.0
        return source_version, completed_rank, handoff.id or 0
