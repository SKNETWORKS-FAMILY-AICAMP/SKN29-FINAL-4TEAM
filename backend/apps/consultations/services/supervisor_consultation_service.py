"""Supervisor-only consultation operations built on the canonical workflow."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.supervisor_policy import is_waterbridge_supervisor
from apps.consultations.models import Consultation
from apps.consultations.services.consultation_service import ConsultationService
from apps.inquiries.models import Inquiry
from apps.inquiries.services.inquiry_service import InquiryService


@dataclass(eq=False)
class SupervisorConsultationError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


class SupervisorConsultationService:
    """Keep supervisor overrides synthetic, atomic, and auditable by Admin."""

    editable_fields = {
        "summary",
        "consultation_note",
        "additional_check",
        "customer_guidance",
        "result_code",
        "usage_guidance_status",
    }

    @staticmethod
    def _authorize(actor: User) -> None:
        if not is_waterbridge_supervisor(actor):
            raise SupervisorConsultationError(
                "SUPERVISOR_REQUIRED",
                "등록된 Supervisor 계정만 상담 운영 작업을 수행할 수 있습니다.",
            )

    @staticmethod
    def _lock_consultation(consultation_id: int) -> Consultation:
        consultation = (
            # Lock only the aggregate root row. ``consultant`` is nullable, so
            # PostgreSQL renders that relation as a LEFT OUTER JOIN and rejects
            # an unrestricted FOR UPDATE on the nullable side of the join.
            Consultation.objects.select_for_update(of=("self",))
            .select_related(
                "inquiry__initiated_by",
                "inquiry__subscription__customer",
                "consultant",
            )
            .filter(pk=consultation_id)
            .first()
        )
        if consultation is None:
            raise SupervisorConsultationError(
                "CONSULTATION_NOT_FOUND",
                "상담을 찾을 수 없습니다.",
            )
        SupervisorConsultationService._require_synthetic_latest(
            consultation
        )
        return consultation

    @staticmethod
    def _require_synthetic_latest(consultation: Consultation) -> None:
        """Validate the Admin-only synthetic and latest consultation scope."""

        if not (
            consultation.inquiry.initiated_by.is_synthetic
            and consultation.inquiry.subscription.customer.is_synthetic
            and consultation.data_classification
            == Consultation.DataClassification.SYNTHETIC
        ):
            raise SupervisorConsultationError(
                "SYNTHETIC_CONSULTATION_REQUIRED",
                "합성 상담 데이터만 Admin에서 변경할 수 있습니다.",
            )
        latest_id = (
            Consultation.objects.filter(inquiry=consultation.inquiry)
            .order_by("-sequence", "-id")
            .values_list("id", flat=True)
            .first()
        )
        if latest_id != consultation.id:
            raise SupervisorConsultationError(
                "LATEST_CONSULTATION_REQUIRED",
                "해당 문의의 최신 상담만 변경할 수 있습니다.",
            )

    @staticmethod
    def _require_assigned_consultant(consultation: Consultation) -> User:
        consultant = consultation.consultant
        if not (
            consultant
            and consultant.is_active
            and consultant.is_synthetic
            and consultant.role_code == User.Role.CONSULTANT
        ):
            raise SupervisorConsultationError(
                "ACTIVE_CONSULTANT_REQUIRED",
                "먼저 활성 합성 상담사를 담당자로 지정해 주세요.",
            )
        return consultant

    @classmethod
    @transaction.atomic
    def reassign(
        cls,
        *,
        actor: User,
        consultation_id: int,
        target_consultant_id: int,
        reason: str,
    ) -> Consultation:
        cls._authorize(actor)
        if not str(reason or "").strip():
            raise SupervisorConsultationError(
                "REASON_REQUIRED",
                "담당자 변경 사유가 필요합니다.",
            )
        consultation = cls._lock_consultation(consultation_id)
        if consultation.status in {
            Consultation.Status.COMPLETED,
            Consultation.Status.CANCELLED,
        } or consultation.inquiry.status_code in {
            Inquiry.Status.RESOLVED,
            Inquiry.Status.CANCELLED,
        }:
            raise SupervisorConsultationError(
                "TERMINAL_CONSULTATION",
                "완료 또는 취소된 상담은 담당자를 바꿀 수 없습니다.",
            )
        target = (
            User.objects.select_for_update()
            .filter(pk=target_consultant_id)
            .first()
        )
        if not (
            target
            and target.is_active
            and target.is_synthetic
            and target.role_code == User.Role.CONSULTANT
        ):
            raise SupervisorConsultationError(
                "ACTIVE_CONSULTANT_REQUIRED",
                "활성 합성 상담사만 새 담당자로 지정할 수 있습니다.",
            )

        consultation.consultant = target
        changed_fields = ["consultant"]
        if consultation.status == Consultation.Status.WAITING:
            consultation.status = Consultation.Status.ASSIGNED
            changed_fields.append("status")
        consultation.full_clean()
        consultation.save(update_fields=[*changed_fields, "updated_at"])

        inquiry = Inquiry.objects.select_for_update().get(
            pk=consultation.inquiry_id
        )
        inquiry.assigned_user = target
        inquiry.assigned_role_code = Inquiry.AssignedRole.CONSULTANT
        inquiry.full_clean()
        inquiry.save(
            update_fields=["assigned_user", "assigned_role_code", "updated_at"]
        )
        consultation.refresh_from_db()
        return consultation

    @classmethod
    @transaction.atomic
    def start(
        cls,
        *,
        actor: User,
        consultation_id: int,
    ) -> Consultation:
        cls._authorize(actor)
        consultation = cls._lock_consultation(consultation_id)
        consultant = cls._require_assigned_consultant(consultation)
        ConsultationService.start(
            actor=actor,
            assigned_consultant=consultant,
            inquiry_public_id=consultation.inquiry.public_id,
            validated_data={"state_version": consultation.inquiry.state_version},
            idempotency_key=f"admin-start-{uuid4().hex}",
            correlation_id=uuid4(),
        )
        consultation.refresh_from_db()
        return consultation

    @classmethod
    @transaction.atomic
    def update_details(
        cls,
        *,
        actor: User,
        consultation_id: int,
        values: dict,
    ) -> Consultation:
        cls._authorize(actor)
        consultation = cls._lock_consultation(consultation_id)
        consultant = cls._require_assigned_consultant(consultation)
        safe_values = {
            key: value
            for key, value in values.items()
            if key in cls.editable_fields
        }
        if not safe_values:
            return consultation
        ConsultationService.save_summary(
            actor=actor,
            assigned_consultant=consultant,
            inquiry_public_id=consultation.inquiry.public_id,
            validated_data={
                "state_version": consultation.inquiry.state_version,
                **safe_values,
            },
            idempotency_key=f"admin-update-{uuid4().hex}",
            correlation_id=uuid4(),
        )
        consultation.refresh_from_db()
        return consultation

    @classmethod
    @transaction.atomic
    def confirm(
        cls,
        *,
        actor: User,
        consultation_id: int,
    ) -> Consultation:
        cls._authorize(actor)
        consultation = cls._lock_consultation(consultation_id)
        consultant = cls._require_assigned_consultant(consultation)
        ConsultationService.confirm_summary(
            actor=actor,
            assigned_consultant=consultant,
            inquiry_public_id=consultation.inquiry.public_id,
            validated_data={"state_version": consultation.inquiry.state_version},
            idempotency_key=f"admin-confirm-{uuid4().hex}",
            correlation_id=uuid4(),
        )
        consultation.refresh_from_db()
        return consultation

    @classmethod
    @transaction.atomic
    def complete(
        cls,
        *,
        actor: User,
        consultation_id: int,
    ) -> Consultation:
        cls._authorize(actor)
        consultation = cls._lock_consultation(consultation_id)
        consultant = cls._require_assigned_consultant(consultation)
        ConsultationService.complete(
            actor=actor,
            assigned_consultant=consultant,
            inquiry_public_id=consultation.inquiry.public_id,
            validated_data={"state_version": consultation.inquiry.state_version},
            idempotency_key=f"admin-complete-{uuid4().hex}",
            correlation_id=uuid4(),
        )
        consultation.refresh_from_db()
        return consultation

    @classmethod
    @transaction.atomic
    def cancel_inquiry(
        cls,
        *,
        actor: User,
        inquiry_id: int,
        reason: str,
    ) -> Inquiry:
        cls._authorize(actor)
        normalized_reason = str(reason or "").strip()
        if not normalized_reason:
            raise SupervisorConsultationError(
                "REASON_REQUIRED",
                "상담 취소 사유가 필요합니다.",
            )
        inquiry = (
            Inquiry.objects.select_for_update()
            .select_related("initiated_by", "subscription__customer")
            .filter(pk=inquiry_id)
            .first()
        )
        if inquiry is None or not (
            inquiry.initiated_by.is_synthetic
            and inquiry.subscription.customer.is_synthetic
        ):
            raise SupervisorConsultationError(
                "SYNTHETIC_INQUIRY_REQUIRED",
                "합성 문의만 Admin에서 취소할 수 있습니다.",
            )
        InquiryService.cancel(
            actor=actor,
            inquiry_public_id=inquiry.public_id,
            validated_data={
                "state_version": inquiry.state_version,
                "reason_code": Inquiry.CancellationReason.OTHER,
                "reason_detail": normalized_reason,
            },
            idempotency_key=f"admin-cancel-{uuid4().hex}",
            correlation_id=uuid4(),
        )
        inquiry.refresh_from_db()
        return inquiry

    @classmethod
    @transaction.atomic
    def cancel_consultation(
        cls,
        *,
        actor: User,
        consultation_id: int,
        reason: str,
    ) -> Consultation:
        """Cancel the consultation's whole inquiry via CANCEL_INQUIRY."""

        cls._authorize(actor)
        normalized_reason = str(reason or "").strip()
        if not normalized_reason:
            raise SupervisorConsultationError(
                "REASON_REQUIRED",
                "상담 취소 사유가 필요합니다.",
            )
        consultation = (
            Consultation.objects.select_related(
                "inquiry__initiated_by",
                "inquiry__subscription__customer",
                "consultant",
            )
            .filter(pk=consultation_id)
            .first()
        )
        if consultation is None:
            raise SupervisorConsultationError(
                "CONSULTATION_NOT_FOUND",
                "상담을 찾을 수 없습니다.",
            )
        cls._require_synthetic_latest(consultation)
        if consultation.status not in {
            Consultation.Status.WAITING,
            Consultation.Status.ASSIGNED,
            Consultation.Status.IN_PROGRESS,
        }:
            raise SupervisorConsultationError(
                "CONSULTATION_CANCEL_NOT_ALLOWED",
                "대기·배정·진행 중인 최신 상담만 문의와 함께 취소할 수 있습니다.",
            )
        cls.cancel_inquiry(
            actor=actor,
            inquiry_id=consultation.inquiry_id,
            reason=normalized_reason,
        )
        consultation.refresh_from_db()
        return consultation
