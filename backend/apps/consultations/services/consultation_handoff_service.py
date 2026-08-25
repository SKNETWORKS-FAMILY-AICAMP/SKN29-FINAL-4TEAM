"""Validate and persist sanitized AI consultation handoffs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import transaction

from apps.audit.models import AIRun
from apps.consultations.models import ConsultationHandoff
from apps.consultations.repositories import ConsultationHandoffRepository
from apps.evidence.models import AIChunkCrosswalk
from apps.inquiries.models import Inquiry
from apps.workflow.services.idempotency_service import IdempotencyService
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import DUPLICATE_EVENT, STATE_CONFLICT


ALLOWED_AI_TASKS = {
    AIRun.TaskType.ANALYZE_SYMPTOM,
    AIRun.TaskType.DRAFT_HANDOFF,
}
TERMINAL_AI_STATUSES = {
    AIRun.Status.SUCCEEDED,
    AIRun.Status.NO_EVIDENCE,
    AIRun.Status.FAILED,
    AIRun.Status.TIMED_OUT,
}


@dataclass(frozen=True)
class ConsultationHandoffOutcome:
    status_code: int
    data: dict[str, Any]


class ConsultationHandoffService:
    """Persist one immutable handoff and materialize its consultant draft."""

    @classmethod
    @transaction.atomic
    def persist(
        cls,
        *,
        inquiry_public_id: UUID,
        validated_data: dict[str, Any],
        idempotency_key: str,
        correlation_id: UUID,
    ) -> ConsultationHandoffOutcome:
        inquiry = (
            Inquiry.objects.select_for_update(of=("self",))
            .select_related(
                "subscription__product_model",
                "subscription__customer__user",
            )
            .filter(public_id=inquiry_public_id)
            .first()
        )
        if inquiry is None:
            cls._conflict("동일 Inquiry를 확인할 수 없습니다.")

        payload = IdempotencyService._json_value(validated_data)
        payload_sha256 = IdempotencyService.canonical_request_hash(payload)
        ai_request_id = validated_data["ai_request_id"]
        if idempotency_key != ai_request_id:
            cls._conflict("Idempotency Key와 AI Request가 일치하지 않습니다.")

        existing = ConsultationHandoffRepository.lock_existing(
            inquiry=inquiry,
            ai_request_id=ai_request_id,
        )
        if existing is not None:
            if existing.payload_sha256 != payload_sha256:
                raise BusinessError(
                    DUPLICATE_EVENT,
                    "동일 AI Request가 다른 Handoff Payload에 재사용되었습니다.",
                    details={},
                    status_code=409,
                )
            ConsultationHandoffRepository.attach_to_latest_consultation(
                inquiry=inquiry,
                handoff=existing,
            )
            existing.refresh_from_db()
            return cls._outcome(existing, replay=True, status_code=200)

        ai_run = (
            AIRun.objects.select_for_update()
            .filter(
                inquiry=inquiry,
                idempotency_key=ai_request_id,
                correlation_id=correlation_id,
                task_type_code__in=ALLOWED_AI_TASKS,
                status_code__in=TERMINAL_AI_STATUSES,
            )
            .first()
        )
        if ai_run is None:
            cls._conflict(
                "Inquiry·Correlation·AI Request가 같은 AI 실행을 확인할 수 없습니다."
            )

        expected_model = inquiry.subscription.product_model.model_code
        if validated_data["model_code"] != expected_model:
            cls._conflict("상담 인계 모델이 문의 구독 제품과 일치하지 않습니다.")

        cls._validate_evidence(
            inquiry=inquiry,
            evidence=validated_data["evidence"],
        )
        ai_draft_summary = cls._build_ai_draft_summary(validated_data)
        customer = inquiry.subscription.customer
        is_synthetic = bool(
            customer.is_synthetic
            and customer.user_id is not None
            and customer.user.is_synthetic
        )
        handoff = ConsultationHandoffRepository.create(
            inquiry=inquiry,
            ai_run=ai_run,
            ai_request_id=ai_request_id,
            correlation_id=correlation_id,
            model_code_snapshot=expected_model,
            product_family_snapshot=validated_data["product_family"],
            schema_version=validated_data.get("schema_version", "1.0.0"),
            sanitized_payload=payload,
            payload_sha256=payload_sha256,
            ai_draft_summary=ai_draft_summary,
            data_classification=(
                ConsultationHandoff.DataClassification.SYNTHETIC
                if is_synthetic
                else ConsultationHandoff.DataClassification.OPERATIONAL
            ),
        )
        ConsultationHandoffRepository.attach_to_latest_consultation(
            inquiry=inquiry,
            handoff=handoff,
        )
        handoff.refresh_from_db()
        return cls._outcome(handoff, replay=False, status_code=201)

    @staticmethod
    def _validate_evidence(*, inquiry: Inquiry, evidence: list[dict]) -> None:
        if not evidence:
            return
        canonical_ids = [item["chunk_id"] for item in evidence]
        mappings = {
            item.canonical_chunk_id: item
            for item in AIChunkCrosswalk.objects.filter(
                canonical_chunk_id__in=canonical_ids,
                is_active=True,
                is_verified=True,
            )
            .select_related(
                "chunk__page__document",
                "model_scope__product_model",
            )
            .prefetch_related("source_pages__page")
        }
        if set(mappings) != set(canonical_ids):
            ConsultationHandoffService._conflict(
                "검증되지 않은 AI Evidence는 상담 인계에 저장할 수 없습니다."
            )

        product_id = inquiry.subscription.product_model_id
        for supplied in evidence:
            mapping = mappings[supplied["chunk_id"]]
            source_pages = [item.page for item in mapping.source_pages.all()]
            if (
                mapping.model_scope.product_model_id != product_id
                or mapping.chunk.page.document.title != supplied["document_title"]
                or (
                    supplied.get("page") is not None
                    and supplied["page"]
                    not in {page.page_no for page in source_pages}
                )
            ):
                ConsultationHandoffService._conflict(
                    "AI Evidence가 문의 제품·공식 문서와 일치하지 않습니다."
                )

    @staticmethod
    def _build_ai_draft_summary(payload: dict[str, Any]) -> str:
        lines = [
            f"증상 요약: {payload['customer_symptom_summary']}",
            f"상담 전환 사유: {payload['escalation_reason']}",
            f"안전 수준: {payload['safety_level']}",
        ]
        if payload["consultant_priority_checks"]:
            lines.append(
                "우선 확인: "
                + " / ".join(payload["consultant_priority_checks"])
            )
        if payload["safety_notes"]:
            lines.append("안전 메모: " + " / ".join(payload["safety_notes"]))
        return "\n".join(lines)

    @staticmethod
    def _outcome(
        handoff: ConsultationHandoff,
        *,
        replay: bool,
        status_code: int,
    ) -> ConsultationHandoffOutcome:
        return ConsultationHandoffOutcome(
            status_code=status_code,
            data={
                "handoff_id": str(handoff.public_id),
                "inquiry_id": str(handoff.inquiry.public_id),
                "ai_request_id": handoff.ai_request_id,
                "consultation_id": (
                    str(handoff.consultation.public_id)
                    if handoff.consultation_id is not None
                    else None
                ),
                "idempotent_replay": replay,
            },
        )

    @staticmethod
    def _conflict(message: str) -> None:
        raise BusinessError(
            STATE_CONFLICT,
            message,
            details={},
            status_code=409,
        )
