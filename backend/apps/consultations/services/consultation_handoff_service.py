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
from apps.inquiries.models import HumanReview, Inquiry
from apps.inquiries.services.safety_rule_registry import (
    danger_assessment_is_valid,
)
from apps.workflow.models import TransitionHistory
from apps.workflow.services.idempotency_service import IdempotencyService
from common.exceptions.business import BusinessError
from common.exceptions.error_codes import (
    AI_HANDOFF_EVIDENCE_REJECTED,
    AI_HANDOFF_NOT_READY,
    AI_HANDOFF_STALE,
    DUPLICATE_EVENT,
    STATE_CONFLICT,
)


V2_SCHEMA_VERSION = "2.0.0"
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
TRANSIENT_AI_STATUSES = {
    AIRun.Status.QUEUED,
    AIRun.Status.RUNNING,
    AIRun.Status.RETRYING,
}
HARNESS_ALLOWED_PAIRS = {
    ("MCP_TOOL_FAILURE", "VALIDATING"),
    ("OUTPUT_SCHEMA_INVALID", "VALIDATING"),
    ("UNSPECIFIED_FALLBACK", "VALIDATING"),
}
FAIL_CLOSED_EVENT_BY_REASON = {
    "NO_EVIDENCE": "NO_EVIDENCE",
    "RUNTIME_PRODUCT_NOT_APPROVED": "PRODUCT_VALIDATION_FAILED",
}
FALLBACK_REASON_CODES = {
    "RUNTIME_PRODUCT_NOT_APPROVED",
    "NO_EVIDENCE",
    "MCP_TOOL_FAILURE",
    "OUTPUT_SCHEMA_INVALID",
    "UNSPECIFIED_FALLBACK",
}
REASON_LABELS = {
    "DANGER_PRIORITY": "즉시 안전 확인과 전문 상담이 필요한 위험 상황",
    "NO_EVIDENCE": "공식 안내 근거를 확인하지 못해 전문 상담이 필요한 상황",
    "RUNTIME_PRODUCT_NOT_APPROVED": "현재 자동 안내 대상 제품으로 확정되지 않은 상황",
    "AI_PROCESSING_TIMEOUT": "자동 분석을 제한 시간 안에 확정하지 못한 상황",
    "HUMAN_REVIEW_REJECTED": "검토에서 자동 안내가 승인되지 않은 상황",
    "MCP_TOOL_FAILURE": "자동 검증 도구 결과를 확정하지 못한 상황",
    "OUTPUT_SCHEMA_INVALID": "자동 분석 결과의 안전한 형식을 확정하지 못한 상황",
    "UNSPECIFIED_FALLBACK": "자동 안내를 안전하게 확정하지 못한 상황",
}
SAFETY_LEVEL_LABELS = {
    "general": "일반 확인",
    "caution": "주의 필요",
    "danger": "즉시 안전 조치 필요",
    "unknown": "추가 확인 필요",
}


@dataclass(frozen=True)
class ConsultationHandoffOutcome:
    status_code: int
    data: dict[str, Any]


class ConsultationHandoffService:
    """Persist one immutable handoff and safely materialize its draft."""

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
        is_v2 = validated_data.get("schema_version") == V2_SCHEMA_VERSION
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
            if is_v2:
                cls._stale("동일 Inquiry를 확인할 수 없습니다.")
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
            # v2 replay must be read-only. Legacy v1 keeps its existing late-attach
            # behavior for consultations created after the first delivery.
            if not is_v2:
                ConsultationHandoffRepository.attach_to_latest_consultation(
                    inquiry=inquiry,
                    handoff=existing,
                )
                existing.refresh_from_db()
            return cls._outcome(existing, replay=True, status_code=200)

        ai_run = (
            cls._lock_v2_ai_run(
                inquiry=inquiry,
                validated_data=validated_data,
                correlation_id=correlation_id,
            )
            if is_v2
            else cls._lock_v1_ai_run(
                inquiry=inquiry,
                ai_request_id=ai_request_id,
                correlation_id=correlation_id,
            )
        )

        expected_model = inquiry.subscription.product_model.model_code
        if validated_data["model_code"] != expected_model:
            if is_v2:
                cls._stale("상담 인계 모델이 문의 구독 제품과 일치하지 않습니다.")
            cls._conflict("상담 인계 모델이 문의 구독 제품과 일치하지 않습니다.")

        if is_v2:
            cls._validate_v2_route_authority(
                inquiry=inquiry,
                ai_run=ai_run,
                payload=validated_data,
            )
        cls._validate_evidence(
            inquiry=inquiry,
            ai_run=ai_run,
            evidence=validated_data["evidence"],
            is_v2=is_v2,
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

    @classmethod
    def _lock_v1_ai_run(
        cls,
        *,
        inquiry: Inquiry,
        ai_request_id: str,
        correlation_id: UUID,
    ) -> AIRun:
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
        return ai_run

    @classmethod
    def _lock_v2_ai_run(
        cls,
        *,
        inquiry: Inquiry,
        validated_data: dict[str, Any],
        correlation_id: UUID,
    ) -> AIRun:
        ai_request_id = validated_data["ai_request_id"]
        ai_run = (
            AIRun.objects.select_for_update()
            .filter(idempotency_key=ai_request_id)
            .first()
        )
        if ai_run is None:
            cls._not_ready("원래 AI 실행 기록이 아직 준비되지 않았습니다.")
        if (
            ai_run.inquiry_id != inquiry.id
            or ai_run.correlation_id != correlation_id
            or ai_run.task_type_code not in ALLOWED_AI_TASKS
        ):
            cls._stale("Handoff 식별자가 원래 AI 실행과 일치하지 않습니다.")
        if ai_run.status_code in TRANSIENT_AI_STATUSES or ai_run.completed_at is None:
            cls._not_ready("AI 실행 결과가 아직 확정되지 않았습니다.")
        if ai_run.status_code not in TERMINAL_AI_STATUSES:
            cls._stale("AI 실행이 Handoff에 사용할 수 없는 상태입니다.")

        cls._validate_original_run_identity(
            inquiry=inquiry,
            ai_run=ai_run,
            payload=validated_data,
        )
        return ai_run

    @classmethod
    def _validate_original_run_identity(
        cls,
        *,
        inquiry: Inquiry,
        ai_run: AIRun,
        payload: dict[str, Any],
    ) -> None:
        original = ai_run.input_payload
        if not isinstance(original, dict):
            cls._stale("AI 실행의 원래 입력 기록을 확인할 수 없습니다.")
        expected = {
            "inquiry_id": str(inquiry.public_id),
            "correlation_id": str(ai_run.correlation_id),
            "ai_request_id": ai_run.idempotency_key,
            "state_version": payload["state_version"],
            "model_code": payload["model_code"],
        }
        if any(original.get(key) != value for key, value in expected.items()):
            cls._stale("Handoff가 원래 AI 입력 상태와 일치하지 않습니다.")

        output = ai_run.validated_output_payload
        if not isinstance(output, dict):
            return
        output_expected = {
            "inquiry_id": str(inquiry.public_id),
            "correlation_id": str(ai_run.correlation_id),
            "ai_request_id": ai_run.idempotency_key,
            "state_version": payload["state_version"],
        }
        if output.get("success") is not False:
            output_expected["model_code"] = payload["model_code"]
        if any(output.get(key) != value for key, value in output_expected.items()):
            cls._stale("Handoff가 확정된 AI 출력 식별자와 일치하지 않습니다.")

    @classmethod
    def _validate_v2_route_authority(
        cls,
        *,
        inquiry: Inquiry,
        ai_run: AIRun,
        payload: dict[str, Any],
    ) -> None:
        route = payload["routing_reason"]
        if route == "DANGER_HANDOFF":
            output = cls._validated_output(ai_run)
            if (
                not danger_assessment_is_valid(output)
                or payload["safety_level"] != "danger"
                or payload["safety_requires_consultation"] is not True
            ):
                cls._stale("위험 Handoff가 확정된 위험 판정과 일치하지 않습니다.")
            cls._require_transition(
                inquiry=inquiry,
                ai_run=ai_run,
                event_code="DANGER_DETECTED",
            )
            return

        if route == "HARNESS_ESCALATE":
            output = cls._validated_output(ai_run)
            pair = (
                output.get("fallback_reason_code"),
                output.get("failure_stage"),
            )
            if (
                pair not in HARNESS_ALLOWED_PAIRS
                or payload["escalation_reason"] != pair[0]
            ):
                cls._stale("Harness Handoff 승인 조합을 확인할 수 없습니다.")
            return

        cls._validate_fail_closed_authority(
            inquiry=inquiry,
            ai_run=ai_run,
            payload=payload,
        )

    @classmethod
    def _validate_fail_closed_authority(
        cls,
        *,
        inquiry: Inquiry,
        ai_run: AIRun,
        payload: dict[str, Any],
    ) -> None:
        reason = payload["escalation_reason"]
        if reason == "HUMAN_REVIEW_REJECTED":
            cls._validated_output(ai_run)
            review_exists = (
                HumanReview.objects.select_for_update()
                .filter(
                    inquiry=inquiry,
                    guidance__inquiry=inquiry,
                    source_ai_request_id=ai_run.idempotency_key,
                    source_inquiry_state_version=payload["state_version"],
                    status_code=HumanReview.Status.REJECTED,
                    decision_code=HumanReview.Decision.REJECT,
                )
                .exists()
            )
            if not review_exists:
                cls._stale("거절된 Human Review 결속을 확인할 수 없습니다.")
            return

        if reason == "AI_PROCESSING_TIMEOUT":
            if (
                ai_run.status_code != AIRun.Status.TIMED_OUT
                or ai_run.error_code != "AI-TIMEOUT-01"
            ):
                cls._stale("AI 시간 초과 실행 기록을 확인할 수 없습니다.")
            cls._require_transition(
                inquiry=inquiry,
                ai_run=ai_run,
                event_code="AI_PROCESSING_TIMEOUT",
            )
            return

        output = cls._validated_output(ai_run)
        fallback_reason = output.get("fallback_reason_code")
        failure_stage = output.get("failure_stage")
        if (
            fallback_reason not in FALLBACK_REASON_CODES
            or reason != fallback_reason
            or (fallback_reason, failure_stage) in HARNESS_ALLOWED_PAIRS
        ):
            cls._stale("안전 종료 Handoff의 확정 사유가 AI 실행과 다릅니다.")

        expected_event = FAIL_CLOSED_EVENT_BY_REASON.get(reason)
        if expected_event is not None:
            if reason == "NO_EVIDENCE" and ai_run.status_code != AIRun.Status.NO_EVIDENCE:
                cls._stale("근거 없음 Handoff의 AI 실행 상태가 일치하지 않습니다.")
            cls._require_transition(
                inquiry=inquiry,
                ai_run=ai_run,
                event_code=expected_event,
            )

    @classmethod
    def _validated_output(cls, ai_run: AIRun) -> dict[str, Any]:
        output = ai_run.validated_output_payload
        if (
            ai_run.schema_validation_status_code
            != AIRun.SchemaValidationStatus.PASSED
            or not isinstance(output, dict)
        ):
            cls._stale("계약 검증을 통과한 AI 실행 결과를 확인할 수 없습니다.")
        if output.get("success") is False:
            cls._stale("성공 계약으로 확정된 AI 실행 결과를 확인할 수 없습니다.")
        return output

    @classmethod
    def _require_transition(
        cls,
        *,
        inquiry: Inquiry,
        ai_run: AIRun,
        event_code: str,
    ) -> None:
        exists = TransitionHistory.objects.filter(
            target_type_code=TransitionHistory.TargetType.INQUIRY,
            inquiry=inquiry,
            event_code=event_code,
            correlation_id=ai_run.correlation_id,
            idempotency_key=ai_run.idempotency_key,
            changed_by_type_code=TransitionHistory.ChangedByType.SYSTEM,
        ).exists()
        if not exists:
            cls._stale("Handoff 사유와 일치하는 Backend 상태 이력이 없습니다.")

    @classmethod
    def _validate_evidence(
        cls,
        *,
        inquiry: Inquiry,
        ai_run: AIRun,
        evidence: list[dict],
        is_v2: bool,
    ) -> None:
        canonical_ids = [item["chunk_id"] for item in evidence]
        if is_v2:
            output = ai_run.validated_output_payload
            references = (
                output.get("evidence_references", [])
                if isinstance(output, dict)
                else []
            )
            if not isinstance(references, list) or any(
                not isinstance(item, dict) for item in references
            ):
                cls._evidence_error("AI 실행의 Evidence 기록 형식이 올바르지 않습니다.")
            approved_ids = [item.get("chunk_id") for item in references]
            if canonical_ids != approved_ids or any(
                item.get("verification_status") != "official_verified"
                for item in references
            ):
                cls._evidence_error(
                    "Handoff Evidence가 같은 AI 실행의 승인 근거와 일치하지 않습니다."
                )
            for supplied, reference in zip(evidence, references, strict=True):
                reference_pages = reference.get("page_refs")
                page_matches = (
                    supplied.get("page") is None
                    or supplied.get("page") == reference.get("page")
                    or (
                        isinstance(reference_pages, list)
                        and supplied.get("page") in reference_pages
                    )
                )
                if (
                    supplied["document_title"] != reference.get("document_title")
                    or not page_matches
                ):
                    cls._evidence_error(
                        "Handoff Evidence의 공식 문서·페이지가 AI 실행 기록과 다릅니다."
                    )

        if not evidence:
            return
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
            if is_v2:
                cls._evidence_error(
                    "활성·검증된 AI Evidence Crosswalk를 확인할 수 없습니다."
                )
            cls._conflict("검증되지 않은 AI Evidence는 상담 인계에 저장할 수 없습니다.")

        product_id = inquiry.subscription.product_model_id
        for supplied in evidence:
            mapping = mappings[supplied["chunk_id"]]
            source_pages = [item.page for item in mapping.source_pages.all()]
            valid_page_ids = {page.id for page in source_pages}
            valid_page_numbers = {page.page_no for page in source_pages}
            if (
                mapping.model_scope.product_model_id != product_id
                or not source_pages
                or mapping.chunk.page_id not in valid_page_ids
                or mapping.chunk.page.document.title != supplied["document_title"]
                or (
                    supplied.get("page") is not None
                    and supplied["page"] not in valid_page_numbers
                )
            ):
                if is_v2:
                    cls._evidence_error(
                        "AI Evidence가 문의 제품·공식 문서·페이지와 일치하지 않습니다."
                    )
                cls._conflict("AI Evidence가 문의 제품·공식 문서와 일치하지 않습니다.")

    @classmethod
    def _build_ai_draft_summary(cls, payload: dict[str, Any]) -> str:
        if payload.get("schema_version") != V2_SCHEMA_VERSION:
            return cls._build_v1_ai_draft_summary(payload)
        return cls._build_v2_ai_draft_summary(payload)

    @staticmethod
    def _build_v1_ai_draft_summary(payload: dict[str, Any]) -> str:
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

    @classmethod
    def _build_v2_ai_draft_summary(cls, payload: dict[str, Any]) -> str:
        reason = REASON_LABELS.get(
            payload["escalation_reason"],
            "자동 안내를 확정하지 못해 전문 상담이 필요한 상황",
        )
        safety = SAFETY_LEVEL_LABELS[payload["safety_level"]]
        lines = [
            f"증상 요약: {payload['customer_symptom_summary']}",
            f"상담 필요 사유: {reason}",
            f"안전 수준: {safety}",
        ]
        cls._append_text_list(lines, "안전 확인", payload["safety_notes"])
        cls._append_text_list(lines, "이미 시도한 조치", payload["self_help_actions"])

        context = payload.get("context_synthesis")
        if isinstance(context, dict):
            brief = context["brief"]
            lines.append(f"문제 정리: {brief['issue_summary']['text']}")
            sections = (
                ("안전 제약", brief["safety_constraints"]),
                ("고객 확인 사실", brief["customer_reported_facts"]),
                ("조치 결과", brief["attempted_actions_and_outcomes"]),
                ("미확인 사항", brief["unresolved_questions"]),
                ("공식 근거 확인", brief["evidence_based_findings"]),
                ("상담사 우선 확인", brief["consultant_priority_checks"]),
                ("불확실성", brief["uncertainty_notes"]),
            )
            for label, items in sections:
                cls._append_text_list(
                    lines,
                    label,
                    [item["text"] for item in items],
                )
        else:
            cls._append_text_list(
                lines,
                "공식 근거 확인",
                [item["summary"] for item in payload["evidence"]],
            )
            cls._append_text_list(
                lines,
                "상담사 우선 확인",
                payload["consultant_priority_checks"],
            )

        summary = "\n".join(lines)
        return summary if len(summary) <= 4000 else summary[:3999] + "…"

    @staticmethod
    def _append_text_list(lines: list[str], label: str, values: list[str]) -> None:
        if values:
            lines.append(f"{label}: " + " / ".join(values))

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
    def _not_ready(message: str) -> None:
        raise BusinessError(
            AI_HANDOFF_NOT_READY,
            message,
            details={},
            status_code=409,
        )

    @staticmethod
    def _stale(message: str) -> None:
        raise BusinessError(
            AI_HANDOFF_STALE,
            message,
            details={},
            status_code=409,
        )

    @staticmethod
    def _evidence_error(message: str) -> None:
        raise BusinessError(
            AI_HANDOFF_EVIDENCE_REJECTED,
            message,
            details={},
            status_code=422,
        )

    @staticmethod
    def _conflict(message: str) -> None:
        raise BusinessError(
            STATE_CONFLICT,
            message,
            details={},
            status_code=409,
        )
