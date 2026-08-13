"""Shared transactional boundary for assigned-consultant workflow writes."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.consultations.models import Consultation
from apps.inquiries.models import Inquiry
from apps.inquiries.repositories.inquiry_repository import InquiryRepository
from apps.workflow.domain.transition import Transition
from apps.workflow.domain.workflow_snapshot import WorkflowSnapshot
from apps.workflow.engine.allowed_action_resolver import (
    AllowedActionContext,
    AllowedActionResolver,
)
from apps.workflow.engine.guard_evaluator import GuardContext, GuardEvaluator
from apps.workflow.engine.state_machine import (
    InvalidStateTransition,
    StateMachine,
)
from apps.workflow.repositories.workflow_repository import WorkflowRepository
from apps.workflow.services.idempotency_service import IdempotencyService
from apps.workflow.services.transition_history_service import (
    TransitionHistoryService,
)
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import INTERNAL_ERROR, STATE_CONFLICT


@dataclass(frozen=True)
class WorkflowActionOutcome:
    """HTTP-independent result returned by consultation and visit views."""

    status_code: int
    data: dict


ContextFactory = Callable[[Inquiry], dict[str, Any]]
DomainResultsFactory = Callable[
    [Inquiry, dict[str, Any]],
    Mapping[str, bool],
]
Mutation = Callable[
    [Inquiry, Transition, dict[str, Any]],
    Any,
]
ResourceBuilder = Callable[[Any, dict[str, Any]], dict | None]


class AssignedConsultantActionService:
    """Apply idempotency, state guards and atomic history once per action."""

    @classmethod
    @transaction.atomic
    def execute(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        path_parameters: Mapping[str, Any],
        validated_data: dict,
        idempotency_key: str,
        correlation_id: UUID,
        operation_id: str,
        event_code: str,
        message: str,
        context_factory: ContextFactory,
        domain_results_factory: DomainResultsFactory,
        mutation: Mutation,
        resource_builder: ResourceBuilder,
    ) -> WorkflowActionOutcome:
        request_hash = IdempotencyService.canonical_request_hash(
            {
                "normalized_path_parameters": dict(path_parameters),
                "normalized_request_body": validated_data,
                "target_public_id": inquiry_public_id,
            }
        )

        inquiry = cls._lock_assigned_or_claimable_inquiry(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
            event_code=event_code,
        )
        if inquiry is None:
            raise NotFound()

        # A concurrent request may have completed while this transaction was
        # waiting for the aggregate lock. Re-check before version validation.
        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return WorkflowActionOutcome(status_code, data)

        context = context_factory(inquiry)
        snapshot = WorkflowSnapshot(
            inquiry_state=inquiry.status_code,
            state_version=inquiry.state_version,
            visit_status=InquiryRepository.latest_visit_status(inquiry),
        )
        try:
            transition = StateMachine().resolve(
                snapshot=snapshot,
                event_code=event_code,
            )
        except InvalidStateTransition as exc:
            if exc.reason in {
                "TERMINAL_STATE",
                "UNLISTED_TRANSITION",
                "VISIT_STATE_MISMATCH",
            }:
                cls._raise_state_conflict(
                    inquiry,
                    actor=actor,
                    action_context=context,
                )
            raise BusinessError(
                INTERNAL_ERROR,
                "요청 처리 중 오류가 발생했습니다.",
                details={},
                status_code=500,
            ) from exc

        domain_results = {
            "G-ASSIGNED-CONSULTANT": True,
            **dict(domain_results_factory(inquiry, context)),
        }
        guard_result = GuardEvaluator().evaluate(
            transition=transition,
            snapshot=snapshot,
            context=GuardContext(
                actor_role=actor.role_code,
                is_authenticated=bool(actor.is_authenticated),
                correlation_id=str(correlation_id),
                idempotency_key=idempotency_key,
                requested_state_version=validated_data["state_version"],
                domain_results=domain_results,
            ),
        )
        cls._raise_guard_failure(
            inquiry=inquiry,
            actor=actor,
            guard_result=guard_result,
            action_context=context,
        )

        try:
            with transaction.atomic():
                idempotency_record = (
                    WorkflowRepository.create_idempotency_record(
                        actor=actor,
                        operation_id=operation_id,
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                    )
                )
        except IntegrityError:
            existing = WorkflowRepository.lock_idempotency_scope(
                actor=actor,
                operation_id=operation_id,
                idempotency_key=idempotency_key,
            )
            if existing is None:
                raise
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return WorkflowActionOutcome(status_code, data)

        resource = mutation(inquiry, transition, context)
        InquiryRepository.apply_state_transition(
            inquiry,
            status_code=transition.inquiry_state_after,
            state_version=transition.state_version_after,
        )
        TransitionHistoryService.record_inquiry_action(
            inquiry=inquiry,
            transition=transition,
            actor=actor,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        if transition.record_visit_state_history:
            if resource is None or not hasattr(resource, "status"):
                raise BusinessError(
                    INTERNAL_ERROR,
                    "요청 처리 중 오류가 발생했습니다.",
                    details={},
                    status_code=500,
                )
            TransitionHistoryService.record_visit_action(
                visit=resource,
                transition=transition,
                actor=actor,
                correlation_id=correlation_id,
                idempotency_key=idempotency_key,
            )

        data = {
            "message": message,
            "inquiry_id": str(inquiry.public_id),
            "status": inquiry.status_code,
            "state_version": inquiry.state_version,
            "allowed_actions": cls._resolve_allowed_actions(
                inquiry=inquiry,
                actor=actor,
                action_context=context,
                resource=resource,
            ),
            "idempotent_replay": False,
            "resource": resource_builder(resource, context),
        }
        resource_public_id = getattr(resource, "public_id", inquiry.public_id)
        WorkflowRepository.complete_idempotency_record(
            idempotency_record,
            response_status=200,
            response_body=data,
            resource_public_id=resource_public_id,
        )
        return WorkflowActionOutcome(status_code=200, data=data)

    @staticmethod
    def _lock_assigned_or_claimable_inquiry(
        *,
        actor: Any,
        inquiry_public_id: UUID,
        event_code: str,
    ) -> Inquiry | None:
        """Lock an assigned inquiry or atomically claim a waiting queue item."""
        inquiry = (
            Inquiry.objects.select_for_update(of=("self",))
            .select_related(
                "initiated_by",
                "subscription__customer",
                "subscription__customer__user",
                "subscription__product_model",
            )
            .filter(
                public_id=inquiry_public_id,
                initiated_by__is_synthetic=True,
                subscription__customer__deleted_at__isnull=True,
                subscription__customer__is_synthetic=True,
                subscription__customer__user__is_synthetic=True,
            )
            .first()
        )
        if inquiry is None:
            return None
        if (
            inquiry.assigned_user_id == actor.pk
            and inquiry.assigned_role_code == Inquiry.AssignedRole.CONSULTANT
        ):
            return inquiry

        claimable = bool(
            event_code == "START_CONSULTATION"
            and getattr(actor, "role_code", None) == "CONSULTANT"
            and inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
            and inquiry.assigned_user_id is None
            and inquiry.assigned_role_code == Inquiry.AssignedRole.NONE
        )
        if not claimable:
            return None

        waiting_consultation_exists = (
            Consultation.objects.select_for_update()
            .filter(
                inquiry=inquiry,
                status=Consultation.Status.WAITING,
                consultant__isnull=True,
            )
            .exists()
        )
        if not waiting_consultation_exists:
            return None

        inquiry.assigned_user = actor
        inquiry.assigned_role_code = Inquiry.AssignedRole.CONSULTANT
        inquiry.save(
            update_fields=[
                "assigned_user",
                "assigned_role_code",
                "updated_at",
            ]
        )
        return inquiry

    @classmethod
    def _raise_guard_failure(
        cls,
        *,
        inquiry: Inquiry,
        actor: Any,
        guard_result: Any,
        action_context: Mapping[str, Any],
    ) -> None:
        if guard_result.allowed:
            return
        failure = guard_result.failure
        if failure is None:
            raise BusinessError(
                INTERNAL_ERROR,
                "요청 처리 중 오류가 발생했습니다.",
                details={},
                status_code=500,
            )
        if failure.guard_id == "G-STATE-VERSION":
            cls._raise_state_conflict(
                inquiry,
                actor=actor,
                action_context=action_context,
            )
        if failure.http_status == 404:
            raise NotFound()
        if failure.http_status == 403:
            raise PermissionDenied()
        if failure.http_status == 422:
            raise BusinessError(
                failure.error_code,
                failure.message,
                details={},
                status_code=422,
            )
        raise BusinessError(
            INTERNAL_ERROR,
            "요청 처리 중 오류가 발생했습니다.",
            details={},
            status_code=500,
        )

    @classmethod
    def _raise_state_conflict(
        cls,
        inquiry: Inquiry,
        *,
        actor: Any,
        action_context: Mapping[str, Any],
    ) -> None:
        allowed_actions = cls._resolve_allowed_actions(
            inquiry=inquiry,
            actor=actor,
            action_context=action_context,
        )
        raise BusinessError(
            STATE_CONFLICT,
            "다른 사용자가 문의 상태를 먼저 변경했습니다.",
            details={
                "current_status": inquiry.status_code,
                "current_state_version": inquiry.state_version,
                "allowed_actions": [
                    action["code"] for action in allowed_actions
                ],
            },
            status_code=409,
        )

    @staticmethod
    def _resolve_allowed_actions(
        *,
        inquiry: Inquiry,
        actor: Any,
        action_context: Mapping[str, Any],
        resource: Any = None,
    ) -> list[dict[str, Any]]:
        """Build the same persisted Snapshot for success and stale 409."""

        model_name = getattr(getattr(resource, "_meta", None), "model_name", None)
        model_kwargs: dict[str, Any] = {}
        if "consultation" in action_context:
            model_kwargs["consultation"] = action_context["consultation"]
        if "latest_visit" in action_context:
            model_kwargs["visit"] = action_context["latest_visit"]
        elif "visit" in action_context:
            model_kwargs["visit"] = action_context["visit"]
        if model_name == "consultation":
            model_kwargs["consultation"] = resource
        if model_name == "visit":
            model_kwargs["visit"] = resource
        return AllowedActionResolver.resolve(
            context=AllowedActionContext.from_models(
                inquiry=inquiry,
                actor=actor,
                **model_kwargs,
            )
        )
