"""Deterministic consultant assignment for the approved synthetic E2E run."""

from __future__ import annotations

from apps.accounts.models import User
from apps.inquiries.models import Inquiry, SymptomEntry
from apps.subscriptions.models import CustomerSubscription
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import INTERNAL_ERROR, STATE_CONFLICT


DEMO_CONSULTANT_USERNAME = "DEMO-CONSULTANT-001"
DEMO_CUSTOMER_USERNAME = "DEMO-CUSTOMER-001"
DEMO_CUSTOMER_NO = "DEMO-CUSTOMER-001"
SYNTHETIC_E2E_ASSIGNMENT_MODE = "SYNTHETIC_E2E_ASSIGNMENT"
SYNTHETIC_E2E_SCENARIO_REFERENCE = "SYN-JAC104-002"
SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE = "SYN-JAC104-002-RUNTIME-E2E"
SYNTHETIC_E2E_TARGET_MODEL_CODE = "WPUJAC104DWH"
SYNTHETIC_E2E_TARGET_SYMPTOM_CODE = "LOW_FLOW"


class SyntheticE2EAssignmentValidationError(ValueError):
    """Raised when an inquiry is outside the approved synthetic boundary."""


class SyntheticE2EAssignmentService:
    """Assign only the explicitly marked synthetic inquiry to the demo agent."""

    @classmethod
    def validate_preparation_candidate(cls, inquiry: Inquiry) -> None:
        """Validate the exact inquiry before the operator marks it for E2E."""

        cls._validate_common_boundary(inquiry)
        if inquiry.status_code != Inquiry.Status.AI_GUIDANCE:
            raise SyntheticE2EAssignmentValidationError(
                "문의 상태가 AI_GUIDANCE일 때만 합성 E2E 배정을 준비할 수 있습니다."
            )
        if inquiry.assigned_user_id is not None or (
            inquiry.assigned_role_code != Inquiry.AssignedRole.NONE
        ):
            raise SyntheticE2EAssignmentValidationError(
                "이미 담당자가 있는 문의는 합성 E2E 대상으로 표시할 수 없습니다."
            )
        if inquiry.consultations.exists():
            raise SyntheticE2EAssignmentValidationError(
                "이미 상담 요청이 생성된 문의는 합성 E2E 대상으로 표시할 수 없습니다."
            )
        if inquiry.scenario_code not in {
            None,
            "",
            SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE,
        }:
            raise SyntheticE2EAssignmentValidationError(
                "다른 시나리오 코드가 있는 문의는 합성 E2E 대상으로 바꿀 수 없습니다."
            )

    @classmethod
    def require_active_demo_consultant(cls) -> User:
        """Lock and return the one approved synthetic consultant account."""

        consultant = (
            User.objects.select_for_update(of=("self",))
            .filter(
                username=DEMO_CONSULTANT_USERNAME,
                role_code=User.Role.CONSULTANT,
                is_active=True,
                is_synthetic=True,
            )
            .first()
        )
        if consultant is None:
            raise SyntheticE2EAssignmentValidationError(
                "활성 합성 상담사 DEMO-CONSULTANT-001이 필요합니다."
            )
        return consultant

    @classmethod
    def assign_if_marked(cls, inquiry: Inquiry) -> bool:
        """Assign a marked inquiry in the caller's existing transaction.

        The method deliberately does nothing for every unmarked inquiry.  It
        never creates the demo account and never overwrites another assignee.
        """

        if inquiry.scenario_code != SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE:
            return False

        try:
            cls._validate_common_boundary(inquiry)
        except SyntheticE2EAssignmentValidationError as exc:
            raise BusinessError(
                INTERNAL_ERROR,
                "합성 E2E 상담사 배정 조건을 확인할 수 없습니다.",
                details={},
                status_code=500,
            ) from exc

        if inquiry.assigned_user_id is not None or (
            inquiry.assigned_role_code != Inquiry.AssignedRole.NONE
        ):
            existing = inquiry.assigned_user
            if (
                existing is not None
                and existing.username == DEMO_CONSULTANT_USERNAME
                and inquiry.assigned_role_code
                == Inquiry.AssignedRole.CONSULTANT
            ):
                return False
            raise BusinessError(
                STATE_CONFLICT,
                "이미 다른 담당자에게 배정된 문의입니다.",
                details={
                    "current_status": inquiry.status_code,
                    "current_state_version": inquiry.state_version,
                },
                status_code=409,
            )

        try:
            consultant = cls.require_active_demo_consultant()
        except SyntheticE2EAssignmentValidationError as exc:
            raise BusinessError(
                INTERNAL_ERROR,
                "합성 E2E 상담사 배정 계정을 확인할 수 없습니다.",
                details={},
                status_code=500,
            ) from exc

        inquiry.assigned_user = consultant
        inquiry.assigned_role_code = Inquiry.AssignedRole.CONSULTANT
        inquiry.clean()
        inquiry.save(
            update_fields=[
                "assigned_user",
                "assigned_role_code",
                "updated_at",
            ]
        )
        return True

    @staticmethod
    def _validate_common_boundary(inquiry: Inquiry) -> None:
        subscription = inquiry.subscription
        customer = subscription.customer
        owner = customer.user
        product = subscription.product_model

        if (
            inquiry.initiated_by_id != owner.pk
            or owner.username != DEMO_CUSTOMER_USERNAME
            or owner.role_code != User.Role.CUSTOMER
            or not owner.is_active
            or not owner.is_synthetic
            or not customer.is_synthetic
            or customer.customer_no != DEMO_CUSTOMER_NO
            or customer.deleted_at is not None
        ):
            raise SyntheticE2EAssignmentValidationError(
                "공식 합성 고객 DEMO-CUSTOMER-001의 활성 문의만 준비할 수 있습니다."
            )
        if inquiry.channel_code != Inquiry.Channel.MOBILE:
            raise SyntheticE2EAssignmentValidationError(
                "Mobile 채널 문의만 합성 E2E 대상으로 준비할 수 있습니다."
            )
        if subscription.status_code != CustomerSubscription.Status.ACTIVE:
            raise SyntheticE2EAssignmentValidationError(
                "활성 구독 문의만 합성 E2E 대상으로 준비할 수 있습니다."
            )
        if (
            product.model_code != SYNTHETIC_E2E_TARGET_MODEL_CODE
            or not product.is_active
            or not product.is_supported_mvp
        ):
            raise SyntheticE2EAssignmentValidationError(
                "지원 제품 WPUJAC104DWH 문의만 합성 E2E 대상으로 준비할 수 있습니다."
            )
        symptom_matches = SymptomEntry.objects.filter(
            inquiry=inquiry,
            symptom_type_code=SYNTHETIC_E2E_TARGET_SYMPTOM_CODE,
            is_customer_confirmed=True,
        ).exists()
        if not symptom_matches:
            raise SyntheticE2EAssignmentValidationError(
                "고객이 확인한 출수량 저하(LOW_FLOW) 문의만 준비할 수 있습니다."
            )


__all__ = [
    "DEMO_CONSULTANT_USERNAME",
    "DEMO_CUSTOMER_NO",
    "DEMO_CUSTOMER_USERNAME",
    "SYNTHETIC_E2E_ASSIGNMENT_MODE",
    "SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE",
    "SYNTHETIC_E2E_SCENARIO_REFERENCE",
    "SYNTHETIC_E2E_TARGET_MODEL_CODE",
    "SYNTHETIC_E2E_TARGET_SYMPTOM_CODE",
    "SyntheticE2EAssignmentService",
    "SyntheticE2EAssignmentValidationError",
]
