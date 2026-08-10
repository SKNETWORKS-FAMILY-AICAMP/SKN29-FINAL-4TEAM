"""Visit ORM boundary for creation, schedule and confirmation."""

from __future__ import annotations

from datetime import datetime, time
from uuid import UUID, uuid4

from django.utils import timezone

from apps.accounts.models import User
from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.visits.models import HandoffReport, Visit


class VisitRepository:
    """Lock and persist one active visit and its public schedule."""

    @staticmethod
    def find_inquiry_public_id(visit_public_id: UUID) -> UUID | None:
        return (
            Visit.objects.filter(public_id=visit_public_id)
            .values_list("inquiry__public_id", flat=True)
            .first()
        )

    @staticmethod
    def lock_latest(inquiry: Inquiry) -> Visit | None:
        return (
            Visit.objects.select_for_update(of=("self",))
            .select_related("technician")
            .filter(inquiry=inquiry)
            .order_by("-created_at", "-id")
            .first()
        )

    @staticmethod
    def lock_by_public_id(
        *,
        inquiry: Inquiry,
        visit_public_id: UUID,
    ) -> Visit | None:
        return (
            Visit.objects.select_for_update(of=("self",))
            .select_related("technician")
            .filter(inquiry=inquiry, public_id=visit_public_id)
            .first()
        )

    @staticmethod
    def synthetic_technician(public_id: UUID) -> User | None:
        return (
            User.objects.filter(
                public_id=public_id,
                role_code=User.Role.TECHNICIAN,
                is_active=True,
                is_synthetic=True,
            )
            .first()
        )

    @staticmethod
    def create(
        *,
        inquiry: Inquiry,
        consultation: Consultation,
        actor,
        values: dict,
        state_version: int,
        idempotency_key: str,
        correlation_id,
    ) -> Visit:
        visit = Visit.objects.create(
            visit_code=f"VIS-{uuid4().hex.upper()}",
            inquiry=inquiry,
            technician=None,
            status=Visit.Status.ASSIGNING,
            requested_at=timezone.now(),
            preferred_date=values.get("preferred_date"),
            confirmed_date=None,
            visit_reason=values["visit_reason"],
            usage_guidance_status=values["usage_guidance_status"],
            handoff_payload=values["handoff"],
            state_version=1,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            data_classification=Visit.DataClassification.SYNTHETIC,
        )
        handoff = values["handoff"]
        report_version = (
            HandoffReport.objects.filter(inquiry=inquiry).count() + 1
        )
        HandoffReport.objects.create(
            inquiry=inquiry,
            consultation=consultation,
            report_version=report_version,
            report_status_code="CONFIRMED",
            product_summary=handoff["product_summary"],
            symptom_summary=handoff["symptom_summary"],
            action_summary=handoff["action_summary"],
            risk_summary=handoff["risk_summary"],
            priority_check_items=handoff["priority_check_items"],
            consultant_final=handoff["consultant_final"],
            confirmed_by=actor,
            confirmed_at=timezone.now(),
        )
        return visit

    @staticmethod
    def update_schedule(
        visit: Visit,
        *,
        technician: User,
        preferred_date,
        confirmed_date,
        status: str,
        state_version: int,
        idempotency_key: str,
        correlation_id,
    ) -> Visit:
        visit.technician = technician
        visit.preferred_date = preferred_date
        visit.confirmed_date = confirmed_date
        visit.status = status
        visit.state_version += 1
        visit.idempotency_key = idempotency_key
        visit.correlation_id = correlation_id
        visit.save(
            update_fields=[
                "technician",
                "preferred_date",
                "confirmed_date",
                "status",
                "state_version",
                "idempotency_key",
                "correlation_id",
                "updated_at",
            ]
        )
        return visit

    @staticmethod
    def confirm(
        visit: Visit,
        *,
        status: str,
        state_version: int,
        idempotency_key: str,
        correlation_id,
    ) -> Visit:
        scheduled_at = timezone.make_aware(
            datetime.combine(visit.confirmed_date, time.min),
            timezone.get_current_timezone(),
        )
        visit.status = status
        visit.scheduled_at = scheduled_at
        visit.state_version += 1
        visit.idempotency_key = idempotency_key
        visit.correlation_id = correlation_id
        visit.save(
            update_fields=[
                "status",
                "scheduled_at",
                "state_version",
                "idempotency_key",
                "correlation_id",
                "updated_at",
            ]
        )
        return visit
