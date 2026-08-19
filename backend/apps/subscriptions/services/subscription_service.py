"""T-018 list/detail projection service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timezone as datetime_timezone
import json
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.care.models import CareRecord
from apps.care.services.approved_care_cycle_rule_loader import (
    load_approved_care_cycle_rule_registry,
)
from apps.care.services.care_schedule_service import CareScheduleService
from apps.subscriptions.models import CustomerSubscription
from apps.subscriptions.repositories.subscription_repository import (
    SUPPORTED_PRODUCT_MODEL_CODES,
    SubscriptionRepository,
)
from common.api.pagination import build_page_data
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import (
    PRODUCT_NOT_SUPPORTED,
    SUBSCRIPTION_ALREADY_ACTIVE,
)
from apps.workflow.repositories.workflow_repository import WorkflowRepository
from apps.workflow.services.idempotency_service import IdempotencyService


BUSINESS_TIMEZONE = ZoneInfo("Asia/Seoul")
CREATE_OPERATION_ID = "createMySubscription"
UPDATE_OPERATION_ID = "updateMySubscription"


@dataclass(frozen=True)
class SubscriptionMutationOutcome:
    status_code: int
    data: dict[str, Any]


class SubscriptionService:
    """Return allowlisted values without leaking internal subscription data."""

    @classmethod
    def list_for_customer(
        cls,
        *,
        actor: Any,
        page: int,
        size: int,
    ) -> dict[str, Any]:
        subscriptions, total = SubscriptionRepository.list_page(
            actor=actor,
            offset=(page - 1) * size,
            limit=size,
        )
        return build_page_data(
            [cls._summary(subscription) for subscription in subscriptions],
            page=page,
            size=size,
            total=total,
        )

    @classmethod
    def detail_for_customer(
        cls,
        *,
        actor: Any,
        subscription_public_id: UUID,
    ) -> dict[str, Any]:
        subscription = SubscriptionRepository.find_detail(
            actor=actor,
            subscription_public_id=subscription_public_id,
        )
        if subscription is None:
            raise NotFound()
        return {
            **cls._summary(subscription),
            "ended_on": subscription.ended_on,
        }

    @classmethod
    @transaction.atomic
    def create_for_customer(
        cls,
        *,
        actor: Any,
        validated_data: dict[str, Any],
        idempotency_key: str,
    ) -> SubscriptionMutationOutcome:
        customer = SubscriptionRepository.lock_synthetic_customer(actor)
        if customer is None or not getattr(actor, "is_synthetic", False):
            raise PermissionDenied()

        normalized_request = {
            "normalized_path_parameters": {},
            "normalized_request_body": validated_data,
            "target_public_id": customer.public_id,
        }
        request_hash = IdempotencyService.canonical_request_hash(
            normalized_request
        )
        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=CREATE_OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return SubscriptionMutationOutcome(status_code, data)

        product = SubscriptionRepository.find_supported_product(
            validated_data["model_code"]
        )
        if (
            product is None
            or product.model_code not in SUPPORTED_PRODUCT_MODEL_CODES
        ):
            raise BusinessError(
                PRODUCT_NOT_SUPPORTED,
                "지원하는 제품 모델을 선택해 주세요.",
                details={"model_code": validated_data["model_code"]},
                status_code=422,
            )
        duplicate = SubscriptionRepository.find_active_product_subscription(
            customer=customer,
            product=product,
        )
        if duplicate is not None:
            raise BusinessError(
                SUBSCRIPTION_ALREADY_ACTIVE,
                "동일 제품의 활성 구독이 이미 등록되어 있습니다.",
                details={"subscription_id": str(duplicate.public_id)},
                status_code=409,
            )

        idempotency_record = cls._create_idempotency_record(
            actor=actor,
            operation_id=CREATE_OPERATION_ID,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        subscription = SubscriptionRepository.create_synthetic_subscription(
            public_id=uuid4(),
            customer=customer,
            product=product,
            started_on=validated_data["started_on"],
            management_type_code=validated_data["management_type_code"],
        )
        last_care_on = validated_data.get("last_care_on")
        if last_care_on is not None:
            SubscriptionRepository.set_registration_care_baseline(
                subscription,
                performed_on=last_care_on,
            )
        cls._align_approved_filter_schedule(
            subscription=subscription,
            change_reason="SUBSCRIPTION_CREATED",
        )
        subscription.refresh_from_db()
        data = cls._mutation_data(subscription, idempotent_replay=False)
        cls._complete_idempotency(
            idempotency_record,
            status_code=201,
            data=data,
            resource_public_id=subscription.public_id,
        )
        return SubscriptionMutationOutcome(201, data)

    @classmethod
    @transaction.atomic
    def update_for_customer(
        cls,
        *,
        actor: Any,
        subscription_public_id: UUID,
        validated_data: dict[str, Any],
        idempotency_key: str,
    ) -> SubscriptionMutationOutcome:
        if not getattr(actor, "is_synthetic", False):
            raise PermissionDenied()
        customer = SubscriptionRepository.lock_synthetic_customer(actor)
        if customer is None:
            raise PermissionDenied()
        subscription = SubscriptionRepository.lock_owned_active_subscription(
            actor=actor,
            subscription_public_id=subscription_public_id,
        )
        if subscription is None:
            raise NotFound()

        normalized_request = {
            "normalized_path_parameters": {
                "subscription_id": subscription_public_id,
            },
            "normalized_request_body": validated_data,
            "target_public_id": subscription_public_id,
        }
        request_hash = IdempotencyService.canonical_request_hash(
            normalized_request
        )
        existing = WorkflowRepository.lock_idempotency_scope(
            actor=actor,
            operation_id=UPDATE_OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return SubscriptionMutationOutcome(status_code, data)

        started_on = validated_data.get(
            "started_on",
            subscription.started_on,
        )
        last_care_on = validated_data.get("last_care_on")
        if last_care_on is not None and last_care_on < started_on:
            raise ValidationError(
                {"last_care_on": ["사용 시작일보다 빠를 수 없습니다."]}
            )
        for care_on in cls._completed_care_dates(subscription):
            if care_on < started_on:
                raise ValidationError(
                    {
                        "started_on": [
                            "기존 완료 관리일보다 늦출 수 없습니다."
                        ]
                    }
                )

        idempotency_record = cls._create_idempotency_record(
            actor=actor,
            operation_id=UPDATE_OPERATION_ID,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        SubscriptionRepository.save_allowed_updates(
            subscription,
            started_on=validated_data.get("started_on"),
            management_type_code=validated_data.get(
                "management_type_code"
            ),
        )
        if last_care_on is not None:
            SubscriptionRepository.set_registration_care_baseline(
                subscription,
                performed_on=last_care_on,
            )
        cls._align_approved_filter_schedule(
            subscription=subscription,
            change_reason="SUBSCRIPTION_SCOPE_OR_BASELINE_CHANGED",
        )
        subscription.refresh_from_db()
        data = cls._mutation_data(subscription, idempotent_replay=False)
        cls._complete_idempotency(
            idempotency_record,
            status_code=200,
            data=data,
            resource_public_id=subscription.public_id,
        )
        return SubscriptionMutationOutcome(200, data)

    @classmethod
    def _summary(
        cls,
        subscription: CustomerSubscription,
    ) -> dict[str, Any]:
        product = subscription.product_model
        return {
            "subscription_id": subscription.public_id,
            "status_code": subscription.status_code,
            "management_type_code": subscription.management_type_code,
            "started_on": subscription.started_on,
            "last_care_on": cls._last_care_on(subscription),
            "next_care_on": subscription.next_care_on,
            "product": {
                "product_model_id": product.public_id,
                "model_code": product.model_code,
                "model_name": product.model_name,
                "generation_code": product.generation_code,
                "manufacturer": product.manufacturer,
            },
        }

    @staticmethod
    def _last_care_on(subscription: CustomerSubscription) -> date | None:
        care_dates: list[date] = []
        care_records = getattr(
            subscription,
            "t018_completed_care_records",
            None,
        )
        if care_records is None:
            care_records = SubscriptionRepository.completed_care_rows(
                subscription
            )
        for care_record in care_records:
            if care_record.performed_on is not None:
                care_dates.append(care_record.performed_on)
                continue
            if care_record.completed_at is None:
                continue
            completed_at = care_record.completed_at
            if timezone.is_naive(completed_at):
                completed_at = completed_at.replace(
                    tzinfo=datetime_timezone.utc
                )
            care_dates.append(
                timezone.localtime(completed_at, BUSINESS_TIMEZONE).date()
            )
        return max(care_dates, default=None)

    @classmethod
    def _mutation_data(
        cls,
        subscription: CustomerSubscription,
        *,
        idempotent_replay: bool,
    ) -> dict[str, Any]:
        return {
            **cls._summary(subscription),
            "ended_on": subscription.ended_on,
            "idempotent_replay": idempotent_replay,
        }

    @staticmethod
    def _align_approved_filter_schedule(
        *,
        subscription: CustomerSubscription,
        change_reason: str,
    ) -> None:
        CareScheduleService.recalculate_from_registry(
            subscription_public_id=subscription.public_id,
            care_type_code=CareRecord.CareType.FILTER_REPLACEMENT,
            registry=load_approved_care_cycle_rule_registry(),
            change_reason=change_reason,
            invalidate_official_on_miss=True,
        )

    @classmethod
    def _completed_care_dates(
        cls,
        subscription: CustomerSubscription,
    ) -> list[date]:
        dates: list[date] = []
        for care in SubscriptionRepository.completed_care_rows(subscription):
            if care.performed_on is not None:
                dates.append(care.performed_on)
            elif care.completed_at is not None:
                completed_at = care.completed_at
                if timezone.is_naive(completed_at):
                    completed_at = completed_at.replace(
                        tzinfo=datetime_timezone.utc
                    )
                dates.append(
                    timezone.localtime(
                        completed_at,
                        BUSINESS_TIMEZONE,
                    ).date()
                )
        return dates

    @staticmethod
    def _create_idempotency_record(
        *,
        actor: Any,
        operation_id: str,
        idempotency_key: str,
        request_hash: str,
    ):
        return WorkflowRepository.create_idempotency_record(
            actor=actor,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )

    @staticmethod
    def _complete_idempotency(
        record,
        *,
        status_code: int,
        data: dict[str, Any],
        resource_public_id: UUID,
    ) -> None:
        serializable = json.loads(json.dumps(data, cls=DjangoJSONEncoder))
        WorkflowRepository.complete_idempotency_record(
            record,
            response_status=status_code,
            response_body=serializable,
            resource_public_id=resource_public_id,
        )
