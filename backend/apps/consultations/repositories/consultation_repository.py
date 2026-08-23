"""Consultation ORM boundary used by the workflow runtime."""

from __future__ import annotations

from uuid import uuid4

from django.db.models import Max
from django.utils import timezone

from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry


class ConsultationRepository:
    """Lock and persist one inquiry's active consultation."""

    @staticmethod
    def lock_latest(inquiry: Inquiry) -> Consultation | None:
        return (
            Consultation.objects.select_for_update()
            .filter(inquiry=inquiry)
            .order_by("-sequence", "-id")
            .first()
        )

    @staticmethod
    def request(
        *,
        inquiry: Inquiry,
        state_version: int,
        idempotency_key: str,
        correlation_id,
        current: Consultation | None,
    ) -> Consultation:
        """Create or refresh the unassigned waiting consultation."""

        if current is not None and current.status in {
            Consultation.Status.WAITING,
            Consultation.Status.ASSIGNED,
        }:
            current.state_version = state_version
            current.idempotency_key = idempotency_key
            current.correlation_id = correlation_id
            current.save(
                update_fields=[
                    "state_version",
                    "idempotency_key",
                    "correlation_id",
                    "updated_at",
                ]
            )
            return current

        if (
            current is not None
            and current.status == Consultation.Status.IN_PROGRESS
        ):
            raise RuntimeError(
                "An in-progress consultation cannot be replaced by a request."
            )

        last_sequence = (
            Consultation.objects.filter(inquiry=inquiry).aggregate(
                maximum=Max("sequence")
            )["maximum"]
            or 0
        )
        customer = inquiry.subscription.customer
        is_synthetic = bool(
            customer.is_synthetic and customer.user.is_synthetic
        )
        return Consultation.objects.create(
            consultation_code=f"CONS-{uuid4().hex.upper()}",
            inquiry=inquiry,
            sequence=last_sequence + 1,
            consultant=None,
            status=Consultation.Status.WAITING,
            outcome=Consultation.Outcome.PENDING,
            summary="",
            state_version=state_version,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            data_classification=(
                Consultation.DataClassification.SYNTHETIC
                if is_synthetic
                else Consultation.DataClassification.OPERATIONAL
            ),
        )

    @staticmethod
    def claim(
        consultation: Consultation,
        *,
        actor,
        state_version: int,
        idempotency_key: str,
        correlation_id,
    ) -> Consultation:
        """Assign a waiting consultation while leaving started_at unset."""

        if (
            consultation.status != Consultation.Status.WAITING
            or consultation.consultant_id is not None
            or consultation.started_at is not None
        ):
            raise RuntimeError("The consultation is no longer claimable.")
        consultation.consultant = actor
        consultation.status = Consultation.Status.ASSIGNED
        consultation.state_version = state_version
        consultation.idempotency_key = idempotency_key
        consultation.correlation_id = correlation_id
        consultation.save(
            update_fields=[
                "consultant",
                "status",
                "state_version",
                "idempotency_key",
                "correlation_id",
                "updated_at",
            ]
        )
        return consultation

    @staticmethod
    def start(
        *,
        inquiry: Inquiry,
        actor,
        state_version: int,
        idempotency_key: str,
        correlation_id,
        current: Consultation | None,
    ) -> Consultation:
        now = timezone.now()
        if current is None or current.status not in {
            Consultation.Status.WAITING,
            Consultation.Status.ASSIGNED,
        }:
            last_sequence = (
                Consultation.objects.filter(inquiry=inquiry).aggregate(
                    maximum=Max("sequence")
                )["maximum"]
                or 0
            )
            return Consultation.objects.create(
                consultation_code=f"CONS-{uuid4().hex.upper()}",
                inquiry=inquiry,
                sequence=last_sequence + 1,
                consultant=actor,
                status=Consultation.Status.IN_PROGRESS,
                outcome=Consultation.Outcome.PENDING,
                summary="",
                state_version=state_version,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                started_at=now,
                created_at=now,
                data_classification=(
                    Consultation.DataClassification.SYNTHETIC
                ),
            )

        current.consultant = actor
        current.status = Consultation.Status.IN_PROGRESS
        current.state_version = state_version
        current.idempotency_key = idempotency_key
        current.correlation_id = correlation_id
        current.started_at = current.started_at or now
        current.save(
            update_fields=[
                "consultant",
                "status",
                "state_version",
                "idempotency_key",
                "correlation_id",
                "started_at",
                "updated_at",
            ]
        )
        return current

    @staticmethod
    def save_summary(
        consultation: Consultation,
        *,
        values: dict,
        state_version: int,
        idempotency_key: str,
        correlation_id,
    ) -> Consultation:
        mapping = {
            "summary": "summary",
            "consultation_note": "consultation_note",
            "additional_check": "additional_check",
            "customer_guidance": "customer_guidance",
            "result_code": "outcome",
            "usage_guidance_status": "usage_guidance_status",
        }
        changed = []
        for request_name, model_name in mapping.items():
            if request_name not in values:
                continue
            setattr(consultation, model_name, values[request_name])
            changed.append(model_name)
        consultation.state_version = state_version
        consultation.idempotency_key = idempotency_key
        consultation.correlation_id = correlation_id
        changed.extend(
            ["state_version", "idempotency_key", "correlation_id"]
        )
        consultation.save(update_fields=[*changed, "updated_at"])
        return consultation

    @staticmethod
    def confirm_summary(
        consultation: Consultation,
        *,
        state_version: int,
        idempotency_key: str,
        correlation_id,
    ) -> Consultation:
        consultation.confirmed_summary = consultation.summary.strip()
        consultation.summary_confirmed_at = timezone.now()
        consultation.state_version = state_version
        consultation.idempotency_key = idempotency_key
        consultation.correlation_id = correlation_id
        consultation.save(
            update_fields=[
                "confirmed_summary",
                "summary_confirmed_at",
                "state_version",
                "idempotency_key",
                "correlation_id",
                "updated_at",
            ]
        )
        return consultation

    @staticmethod
    def complete(
        consultation: Consultation,
        *,
        state_version: int,
        idempotency_key: str,
        correlation_id,
    ) -> Consultation:
        consultation.status = Consultation.Status.COMPLETED
        consultation.completed_at = timezone.now()
        consultation.state_version = state_version
        consultation.idempotency_key = idempotency_key
        consultation.correlation_id = correlation_id
        consultation.save(
            update_fields=[
                "status",
                "completed_at",
                "state_version",
                "idempotency_key",
                "correlation_id",
                "updated_at",
            ]
        )
        return consultation

    @staticmethod
    def record_visit_review(
        consultation: Consultation,
        *,
        reason_code: str,
        reason_detail: str | None,
        state_version: int,
        idempotency_key: str,
        correlation_id,
    ) -> Consultation:
        consultation.visit_review_reason_code = reason_code
        consultation.visit_review_reason_detail = reason_detail
        consultation.state_version = state_version
        consultation.idempotency_key = idempotency_key
        consultation.correlation_id = correlation_id
        consultation.save(
            update_fields=[
                "visit_review_reason_code",
                "visit_review_reason_detail",
                "state_version",
                "idempotency_key",
                "correlation_id",
                "updated_at",
            ]
        )
        return consultation

    @staticmethod
    def mark_visit_not_needed(
        consultation: Consultation,
        *,
        reason_code: str,
        reason_detail: str | None,
        state_version: int,
        idempotency_key: str,
        correlation_id,
    ) -> Consultation:
        consultation.visit_not_needed_reason_code = reason_code
        consultation.visit_not_needed_reason_detail = reason_detail
        consultation.outcome = Consultation.Outcome.COMPLETED_NO_VISIT
        consultation.status = Consultation.Status.COMPLETED
        consultation.completed_at = timezone.now()
        consultation.state_version = state_version
        consultation.idempotency_key = idempotency_key
        consultation.correlation_id = correlation_id
        consultation.save(
            update_fields=[
                "visit_not_needed_reason_code",
                "visit_not_needed_reason_detail",
                "outcome",
                "status",
                "completed_at",
                "state_version",
                "idempotency_key",
                "correlation_id",
                "updated_at",
            ]
        )
        return consultation
