"""T-019 owner-only care history application service."""

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
from rest_framework.exceptions import NotFound, ValidationError

from apps.care.models import CareRecord
from apps.care.repositories.care_history_repository import (
    CareHistoryRepository,
)
from apps.care.services.approved_care_cycle_rule_loader import (
    load_approved_care_cycle_rule_registry,
)
from apps.care.services.care_schedule_service import CareScheduleService
from apps.subscriptions.models import CustomerSubscription
from apps.workflow.repositories.workflow_repository import WorkflowRepository
from apps.workflow.services.idempotency_service import IdempotencyService
from common.api.pagination import build_page_data


CREATE_OPERATION_ID = "createMyCareRecord"
BUSINESS_TIMEZONE = ZoneInfo("Asia/Seoul")
SELF_CARE_RESULT = {
    CareRecord.CareType.FILTER_REPLACEMENT: CareRecord.Result.FILTER_REPLACED,
    CareRecord.CareType.CLEANING: CareRecord.Result.NORMAL,
}


@dataclass(frozen=True)
class CareHistoryMutationOutcome:
    status_code: int
    data: dict[str, Any]


class CareHistoryService:
    @classmethod
    def list_for_customer(
        cls,
        *,
        actor: Any,
        subscription_public_id: UUID,
        page: int,
        size: int,
    ) -> dict[str, Any]:
        subscription = cls._visible_subscription(
            actor=actor,
            subscription_public_id=subscription_public_id,
        )
        records, total = CareHistoryRepository.list_page(
            subscription=subscription,
            offset=(page - 1) * size,
            limit=size,
        )
        return build_page_data(
            [cls._item(record) for record in records],
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
        care_record_public_id: UUID,
    ) -> dict[str, Any]:
        subscription = cls._visible_subscription(
            actor=actor,
            subscription_public_id=subscription_public_id,
        )
        record = CareHistoryRepository.find_detail(
            subscription=subscription,
            care_record_public_id=care_record_public_id,
        )
        if record is None:
            raise NotFound()
        return cls._item(record)

    @classmethod
    @transaction.atomic
    def create_for_customer(
        cls,
        *,
        actor: Any,
        subscription_public_id: UUID,
        validated_data: dict[str, Any],
        idempotency_key: str,
    ) -> CareHistoryMutationOutcome:
        customer = CareHistoryRepository.lock_customer(actor)
        if customer is None:
            raise NotFound()
        subscription = CareHistoryRepository.visible_subscription(
            actor=actor,
            subscription_public_id=subscription_public_id,
            for_update=True,
        )
        if subscription is None:
            raise NotFound()

        performed_on = validated_data["performed_on"]
        if performed_on < subscription.started_on:
            raise ValidationError(
                {"performed_on": ["구독 시작일보다 빠를 수 없습니다."]}
            )
        care_type = validated_data["care_type_code"]
        result_code = SELF_CARE_RESULT[care_type]
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
            operation_id=CREATE_OPERATION_ID,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            status_code, data = IdempotencyService.replay_or_conflict(
                existing,
                request_hash=request_hash,
            )
            return CareHistoryMutationOutcome(status_code, data)

        idempotency_record = WorkflowRepository.create_idempotency_record(
            actor=actor,
            operation_id=CREATE_OPERATION_ID,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        record = CareHistoryRepository.create_customer_completed(
            public_id=uuid4(),
            subscription=subscription,
            actor=actor,
            care_type_code=care_type,
            performed_on=performed_on,
            result_code=result_code,
            completed_at=timezone.now(),
        )
        if care_type == CareRecord.CareType.FILTER_REPLACEMENT:
            CareScheduleService.recalculate_from_registry(
                subscription_public_id=subscription.public_id,
                care_type_code=care_type,
                registry=load_approved_care_cycle_rule_registry(),
                change_reason="CUSTOMER_FILTER_REPLACEMENT_COMPLETED",
                invalidate_official_on_miss=True,
            )
        data = {**cls._item(record), "idempotent_replay": False}
        serializable = json.loads(json.dumps(data, cls=DjangoJSONEncoder))
        WorkflowRepository.complete_idempotency_record(
            idempotency_record,
            response_status=201,
            response_body=serializable,
            resource_public_id=record.public_id,
        )
        return CareHistoryMutationOutcome(201, data)

    @classmethod
    def recent_completed_context(
        cls,
        *,
        subscription: CustomerSubscription,
        limit: int = 5,
    ) -> list[dict[str, str | None]]:
        safe_limit = max(1, min(limit, 5))
        return [
            {
                "care_type_code": record.care_type_code,
                "performed_on": cls._business_date(record).isoformat(),
                "result_code": record.result_code,
            }
            for record in CareHistoryRepository.recent_completed(
                subscription=subscription,
                limit=safe_limit,
            )
        ]

    @classmethod
    def assigned_inquiry_context(
        cls,
        *,
        actor: Any,
        inquiry_public_id: UUID,
        limit: int = 5,
    ) -> list[dict[str, str | None]]:
        subscription = CareHistoryRepository.assigned_subscription(
            actor=actor,
            inquiry_public_id=inquiry_public_id,
        )
        if subscription is None:
            raise NotFound()
        return cls.recent_completed_context(
            subscription=subscription,
            limit=limit,
        )

    @staticmethod
    def _visible_subscription(
        *,
        actor: Any,
        subscription_public_id: UUID,
    ) -> CustomerSubscription:
        subscription = CareHistoryRepository.visible_subscription(
            actor=actor,
            subscription_public_id=subscription_public_id,
        )
        if subscription is None:
            raise NotFound()
        return subscription

    @classmethod
    def _item(cls, record: CareRecord) -> dict[str, Any]:
        return {
            "care_record_id": record.public_id,
            "subscription_id": record.subscription.public_id,
            "care_type_code": record.care_type_code,
            "status_code": CareRecord.Status.COMPLETED,
            "performed_on": cls._business_date(record),
            "result_code": record.result_code,
            "source_code": record.source_code,
        }

    @staticmethod
    def _business_date(record: CareRecord) -> date:
        if record.performed_on is not None:
            return record.performed_on
        completed_at = record.completed_at
        if completed_at is None:
            raise ValueError("COMPLETED CareRecord에 업무 날짜가 없습니다.")
        if timezone.is_naive(completed_at):
            completed_at = completed_at.replace(tzinfo=datetime_timezone.utc)
        return timezone.localtime(completed_at, BUSINESS_TIMEZONE).date()
