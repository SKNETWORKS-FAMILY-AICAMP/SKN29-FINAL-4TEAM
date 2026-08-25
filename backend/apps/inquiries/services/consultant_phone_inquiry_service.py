"""Application service for CR-001 consultant phone intake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound

from apps.inquiries.repositories.consultant_phone_inquiry_repository import (
    ConsultantPhoneInquiryRepository,
)
from apps.workflow.domain.workflow_snapshot import WorkflowSnapshot
from apps.workflow.engine.allowed_action_resolver import (
    AllowedActionContext,
    AllowedActionResolver,
)
from apps.workflow.engine.guard_evaluator import GuardContext, GuardEvaluator
from apps.workflow.engine.state_machine import StateMachine
from apps.workflow.repositories.workflow_repository import WorkflowRepository
from apps.workflow.services.idempotency_service import IdempotencyService
from apps.workflow.services.transition_history_service import (
    TransitionHistoryService,
)
from common.exceptions.business import BusinessError
from common.privacy import mask_person_name, mask_phone


REGISTER_PHONE_INQUIRY_OPERATION_ID = "registerConsultantPhoneInquiry"
REGISTER_PHONE_INQUIRY_EVENT_CODE = "REGISTER_PHONE_INQUIRY"


@dataclass(frozen=True)
class RegisterPhoneInquiryOutcome:
    status_code: int
    data: dict


class ConsultantPhoneInquiryService:
    """Keep search projection and write transaction independent of Web code."""

    @classmethod
    def search(cls, *, query: str, limit: int) -> dict:
        subscriptions = (
            ConsultantPhoneInquiryRepository
            .search_active_synthetic_subscriptions(
                query=query,
                limit=limit,
            )
        )
        items = [cls._search_item(subscription) for subscription in subscriptions]
        return {
            "items": items,
            "returned_count": len(items),
        }

    @classmethod
    @transaction.atomic
    def register(
        cls,
        *,
        actor: Any,
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
    ) -> RegisterPhoneInquiryOutcome:
        subscription = (
            ConsultantPhoneInquiryRepository
            .lock_active_synthetic_subscription(
                subscription_public_id=validated_data["subscription_id"],
            )
        )
        if subscription is None:
            raise NotFound()

        normalized_request = {
            "normalized_path_parameters": {},
            "normalized_request_body": {
                "subscription_id": validated_data["subscription_id"],
                "raw_text": validated_data["raw_text"],
                "representative_symptom_code": validated_data[
                    "representative_symptom_code"
                ],
                "priority_code": validated_data["priority_code"],
            },
            "target_public_id": subscription.public_id,
        }
        request_hash = IdempotencyService.canonical_request_hash(
            normalized_request
        )

        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=REGISTER_PHONE_INQUIRY_OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return RegisterPhoneInquiryOutcome(status_code, data)

        transition = StateMachine().resolve(
            snapshot=WorkflowSnapshot(
                inquiry_state=None,
                state_version=None,
                visit_status=None,
            ),
            event_code=REGISTER_PHONE_INQUIRY_EVENT_CODE,
        )
        guard_result = GuardEvaluator().evaluate(
            transition=transition,
            snapshot=WorkflowSnapshot(
                inquiry_state=None,
                state_version=None,
                visit_status=None,
            ),
            context=GuardContext(
                actor_role=getattr(actor, "role_code", None),
                is_authenticated=bool(actor.is_authenticated),
                correlation_id=str(correlation_id),
                idempotency_key=idempotency_key,
                requested_state_version=None,
                domain_results={
                    "G-CONSULTANT-PHONE-SUBSCRIPTION": True,
                },
            ),
        )
        if not guard_result.allowed:
            failure = guard_result.failure
            if failure is None:
                raise RuntimeError("Phone inquiry guard failed without detail")
            raise BusinessError(
                failure.error_code,
                failure.message,
                details={},
                status_code=failure.http_status,
            )

        try:
            with transaction.atomic():
                idempotency_record = WorkflowRepository.create_idempotency_record(
                    actor=actor,
                    operation_id=REGISTER_PHONE_INQUIRY_OPERATION_ID,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                )
        except IntegrityError:
            existing = WorkflowRepository.lock_idempotency_scope(
                actor=actor,
                operation_id=REGISTER_PHONE_INQUIRY_OPERATION_ID,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return RegisterPhoneInquiryOutcome(status_code, data)

        inquiry = ConsultantPhoneInquiryRepository.create_phone_inquiry(
            subscription=subscription,
            actor=actor,
            raw_text=validated_data["raw_text"],
            priority_code=validated_data["priority_code"],
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            status_code=transition.inquiry_state_after,
            state_version=transition.state_version_after,
        )
        ConsultantPhoneInquiryRepository.create_representative_symptom(
            inquiry=inquiry,
            symptom_code=validated_data["representative_symptom_code"],
        )
        allowed_actions = AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=actor,
                consultation=None,
                visit=None,
            )
        )
        data = {
            "inquiry_id": str(inquiry.public_id),
            "inquiry_code": inquiry.inquiry_code,
            "status_code": inquiry.status_code,
            "state_version": inquiry.state_version,
            "idempotent_replay": False,
            "allowed_actions": allowed_actions,
        }
        TransitionHistoryService.record_inquiry_action(
            inquiry=inquiry,
            transition=transition,
            actor=actor,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        WorkflowRepository.complete_idempotency_record(
            idempotency_record,
            response_status=201,
            response_body=data,
            resource_public_id=inquiry.public_id,
        )
        return RegisterPhoneInquiryOutcome(201, data)

    @staticmethod
    def _search_item(subscription) -> dict:
        customer = subscription.customer
        product = subscription.product_model
        return {
            "customer_id": customer.public_id,
            "customer_display_name": mask_person_name(customer.customer_name),
            "phone_masked": mask_phone(customer.phone),
            "subscription_id": subscription.public_id,
            "subscription_status": subscription.status_code,
            "management_type_code": subscription.management_type_code,
            "product_id": product.public_id,
            "product_model_code": product.model_code,
            "product_name": product.model_name,
        }

    @staticmethod
    def _mask_phone(value: str) -> str:
        return mask_phone(value)
