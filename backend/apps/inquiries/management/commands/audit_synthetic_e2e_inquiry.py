"""Audit one synthetic Mobile-to-Web E2E inquiry without changing DB state."""

from __future__ import annotations

from collections import Counter
import json
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.audit.models import AIRun
from apps.consultations.models import Consultation
from apps.evidence.models import EvidenceLink
from apps.inquiries.models import Guidance, Inquiry, SymptomAssessment
from apps.inquiries.services.synthetic_e2e_assignment_service import (
    DEMO_CONSULTANT_USERNAME,
    DEMO_CUSTOMER_USERNAME,
    SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE,
)
from apps.workflow.models import IdempotencyRecord, TransitionHistory


EXPECTED_MODEL_CODE = "WPUJAC104DWH"
G1_EVENTS = {"SUBMIT_SYMPTOM", "SAFE_GUIDANCE_READY"}
G4_EVENTS = {
    "REQUEST_CONSULTATION",
    "START_CONSULTATION",
    "UPDATE_CONSULTATION_SUMMARY",
    "CONFIRM_CONSULTATION_SUMMARY",
    "CONSULTATION_COMPLETED",
}
G1_OPERATIONS = {"startInquiry", "submitSymptom"}
G3_OPERATIONS = G1_OPERATIONS | {"requestConsultation"}
G4_OPERATIONS = G3_OPERATIONS | {
    "startConsultation",
    "updateConsultationSummary",
    "confirmConsultationSummary",
    "completeConsultation",
}


class Command(BaseCommand):
    help = (
        "한 개의 합성 Mobile→AI→Web E2E 문의를 읽기 전용으로 감사하고 "
        "G1·G3·G4·G5 준비 상태를 공개 식별자 기준 JSON으로 출력합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--inquiry-id",
            required=True,
            type=UUID,
            help="Mobile이 생성한 합성 문의의 public UUID",
        )
        parser.add_argument(
            "--expect-stage",
            required=True,
            choices=("G1", "G3", "G4", "G5"),
            help="현재 검증하려는 E2E Gate",
        )
        parser.add_argument(
            "--require-ready",
            action="store_true",
            help="Blocker가 하나라도 있으면 Exit 1로 종료합니다.",
        )

    def handle(self, *args, **options):
        del args
        inquiry = self._inquiry(options["inquiry_id"])
        snapshot = self._snapshot(inquiry)
        blockers = stage_blockers(snapshot, options["expect_stage"])
        result = {
            "status": "READY" if not blockers else "BLOCKED",
            "scope": "SYNTHETIC_E2E_INQUIRY_AUDIT",
            "expected_stage": options["expect_stage"],
            **snapshot,
            "blockers": blockers,
            "secret_values_printed": False,
            "raw_customer_text_printed": False,
        }
        self.stdout.write(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        )
        if blockers and options["require_ready"]:
            raise CommandError(
                "Synthetic E2E inquiry audit is BLOCKED."
            )

    @staticmethod
    def _inquiry(public_id: UUID) -> Inquiry:
        inquiry = (
            Inquiry.objects.select_related(
                "initiated_by",
                "assigned_user",
                "subscription__customer__user",
                "subscription__product_model",
            )
            .filter(public_id=public_id)
            .first()
        )
        if inquiry is None:
            raise CommandError("지정한 문의를 찾을 수 없습니다.")
        return inquiry

    @staticmethod
    def _snapshot(inquiry: Inquiry) -> dict:
        runs = list(
            AIRun.objects.filter(inquiry=inquiry)
            .order_by("created_at", "id")
            .values(
                "public_id",
                "task_type_code",
                "status_code",
                "schema_validation_status_code",
                "model_provider",
                "model_name",
                "prompt_version",
                "correlation_id",
                "idempotency_key",
                "error_code",
            )
        )
        assessments = list(
            SymptomAssessment.objects.filter(inquiry=inquiry)
            .order_by("assessment_version", "id")
            .values(
                "public_id",
                "assessment_version",
                "risk_level_code",
                "usage_guidance_status",
                "requires_consultation",
                "ai_run_id",
            )
        )
        guidance = list(
            Guidance.objects.filter(inquiry=inquiry)
            .order_by("guidance_version", "id")
            .values(
                "public_id",
                "guidance_version",
                "review_status_code",
                "evidence_sufficiency_code",
                "requires_consultation",
                "generated_by_ai_run__public_id",
            )
        )
        evidence = list(
            EvidenceLink.objects.filter(inquiry=inquiry)
            .order_by("display_order", "id")
            .values(
                "public_id",
                "guidance__public_id",
                "ai_run__public_id",
                "chunk__ai_crosswalk__canonical_chunk_id",
                "display_order",
                "is_verified",
            )
        )
        consultations = list(
            Consultation.objects.filter(inquiry=inquiry)
            .order_by("sequence", "id")
            .values(
                "public_id",
                "sequence",
                "status",
                "outcome",
                "state_version",
                "consultant__username",
                "correlation_id",
                "summary_confirmed_at",
                "confirmed_summary",
                "completed_at",
            )
        )
        histories = list(
            TransitionHistory.objects.filter(inquiry=inquiry)
            .order_by("state_version", "id")
            .values(
                "event_code",
                "from_state",
                "to_state",
                "state_version",
                "correlation_id",
                "idempotency_key",
            )
        )
        resource_ids = [inquiry.public_id]
        resource_ids.extend(row["public_id"] for row in consultations)
        history_keys = [row["idempotency_key"] for row in histories]
        ai_record_ids = []
        for row in runs:
            try:
                ai_record_ids.append(UUID(row["idempotency_key"]))
            except (TypeError, ValueError):
                continue
        idempotency_filter = Q(resource_public_id__in=resource_ids)
        if history_keys:
            idempotency_filter |= Q(idempotency_key__in=history_keys)
        if ai_record_ids:
            idempotency_filter |= Q(public_id__in=ai_record_ids)
        idempotency = list(
            IdempotencyRecord.objects.filter(idempotency_filter)
            .order_by("created_at", "id")
            .values(
                "operation_id",
                "response_status",
                "resource_public_id",
                "completed_at",
            )
        )

        def public_rows(rows):
            return [_json_safe(row) for row in rows]

        return {
            "inquiry": {
                "inquiry_id": str(inquiry.public_id),
                "inquiry_code": inquiry.inquiry_code,
                "channel_code": inquiry.channel_code,
                "status_code": inquiry.status_code,
                "state_version": inquiry.state_version,
                "scenario_code": inquiry.scenario_code,
                "owner_code": inquiry.initiated_by.username,
                "owner_role": inquiry.initiated_by.role_code,
                "owner_is_synthetic": inquiry.initiated_by.is_synthetic,
                "assigned_role_code": inquiry.assigned_role_code,
                "assigned_user_code": (
                    inquiry.assigned_user.username
                    if inquiry.assigned_user_id
                    else None
                ),
                "product_model_code": (
                    inquiry.subscription.product_model.model_code
                ),
            },
            "ai": {
                "run_count": len(runs),
                "runs": public_rows(runs),
                "assessment_count": len(assessments),
                "assessments": public_rows(assessments),
            },
            "guidance": {
                "count": len(guidance),
                "items": public_rows(guidance),
            },
            "evidence": {
                "count": len(evidence),
                "verified_count": sum(
                    1 for row in evidence if row["is_verified"]
                ),
                "items": public_rows(evidence),
            },
            "consultation": {
                "count": len(consultations),
                "items": public_rows(consultations),
            },
            "workflow": {
                "history_count": len(histories),
                "history": public_rows(histories),
                "idempotency_record_count": len(idempotency),
                "idempotency_records": public_rows(idempotency),
            },
        }


def stage_blockers(snapshot: dict, expected_stage: str) -> list[str]:
    """Return stable public blocker codes for one expected E2E stage."""

    blockers: list[str] = []
    inquiry = snapshot["inquiry"]
    ai = snapshot["ai"]
    guidance = snapshot["guidance"]
    evidence = snapshot["evidence"]
    consultation = snapshot["consultation"]
    workflow = snapshot["workflow"]
    histories = workflow["history"]
    events = [row["event_code"] for row in histories]
    operation_counts = Counter(
        row["operation_id"] for row in workflow["idempotency_records"]
    )

    if inquiry["owner_code"] != DEMO_CUSTOMER_USERNAME:
        blockers.append("OWNER_IS_NOT_DEMO_CUSTOMER")
    if inquiry["owner_role"] != "CUSTOMER" or not inquiry["owner_is_synthetic"]:
        blockers.append("OWNER_IS_NOT_SYNTHETIC_CUSTOMER")
    if inquiry["channel_code"] != Inquiry.Channel.MOBILE:
        blockers.append("CHANNEL_IS_NOT_MOBILE")
    if inquiry["product_model_code"] != EXPECTED_MODEL_CODE:
        blockers.append("PRODUCT_MODEL_IS_NOT_P0_TARGET")

    if ai["run_count"] != 1:
        blockers.append("AI_RUN_COUNT_NOT_1")
    else:
        run = ai["runs"][-1]
        if run["status_code"] != AIRun.Status.SUCCEEDED:
            blockers.append("AI_RUN_NOT_SUCCEEDED")
        if (
            run["schema_validation_status_code"]
            != AIRun.SchemaValidationStatus.PASSED
        ):
            blockers.append("AI_SCHEMA_NOT_PASSED")
        if run["task_type_code"] != AIRun.TaskType.ANALYZE_SYMPTOM:
            blockers.append("AI_TASK_IS_NOT_ANALYZE_SYMPTOM")
        history_correlations = {
            row["correlation_id"] for row in histories
        }
        if run["correlation_id"] not in history_correlations:
            blockers.append("AI_CORRELATION_NOT_IN_HISTORY")

    if ai["assessment_count"] < 1:
        blockers.append("SYMPTOM_ASSESSMENT_MISSING")
    if guidance["count"] < 1:
        blockers.append("GUIDANCE_MISSING")
    if evidence["count"] < 1:
        blockers.append("EVIDENCE_LINK_MISSING")
    if evidence["verified_count"] != evidence["count"]:
        blockers.append("EVIDENCE_LINK_NOT_ALL_VERIFIED")
    missing_g1_events = sorted(G1_EVENTS - set(events))
    blockers.extend(f"EVENT_MISSING:{event}" for event in missing_g1_events)
    _append_operation_blockers(blockers, operation_counts, G1_OPERATIONS)

    history_versions = [row["state_version"] for row in histories]
    if history_versions != sorted(set(history_versions)):
        blockers.append("INQUIRY_HISTORY_VERSION_NOT_MONOTONIC")
    if histories and history_versions[-1] != inquiry["state_version"]:
        blockers.append("INQUIRY_VERSION_DIFFERS_FROM_HISTORY")

    if expected_stage == "G1":
        if inquiry["status_code"] != Inquiry.Status.AI_GUIDANCE:
            blockers.append("G1_STATUS_IS_NOT_AI_GUIDANCE")
        if inquiry["assigned_user_code"] is not None:
            blockers.append("G1_INQUIRY_ALREADY_ASSIGNED")
        if consultation["count"] != 0:
            blockers.append("G1_CONSULTATION_ALREADY_EXISTS")
        return blockers

    if inquiry["scenario_code"] != SYNTHETIC_E2E_RUNTIME_SCENARIO_CODE:
        blockers.append("SYNTHETIC_E2E_MARKER_MISSING")
    if inquiry["assigned_user_code"] != DEMO_CONSULTANT_USERNAME:
        blockers.append("DEMO_CONSULTANT_ASSIGNMENT_MISSING")
    if inquiry["assigned_role_code"] != Inquiry.AssignedRole.CONSULTANT:
        blockers.append("ASSIGNED_ROLE_IS_NOT_CONSULTANT")
    if consultation["count"] != 1:
        blockers.append("CONSULTATION_COUNT_NOT_1")

    if expected_stage == "G3":
        _append_operation_blockers(
            blockers,
            operation_counts,
            G3_OPERATIONS - G1_OPERATIONS,
        )
        if inquiry["status_code"] != Inquiry.Status.CONSULTATION_REQUIRED:
            blockers.append("G3_STATUS_IS_NOT_CONSULTATION_REQUIRED")
        if consultation["count"] == 1:
            current = consultation["items"][0]
            if current["status"] != Consultation.Status.WAITING:
                blockers.append("G3_CONSULTATION_IS_NOT_WAITING")
            if current["consultant__username"] is not None:
                blockers.append("G3_CONSULTATION_ALREADY_STARTED")
        if "REQUEST_CONSULTATION" not in events:
            blockers.append("EVENT_MISSING:REQUEST_CONSULTATION")
        return blockers

    if inquiry["status_code"] != Inquiry.Status.COMPLETION_PENDING:
        blockers.append("G4_STATUS_IS_NOT_COMPLETION_PENDING")
    _append_operation_blockers(
        blockers,
        operation_counts,
        G4_OPERATIONS - G1_OPERATIONS,
    )
    missing_g4_events = sorted(G4_EVENTS - set(events))
    blockers.extend(f"EVENT_MISSING:{event}" for event in missing_g4_events)
    if consultation["count"] == 1:
        current = consultation["items"][0]
        if current["status"] != Consultation.Status.COMPLETED:
            blockers.append("G4_CONSULTATION_IS_NOT_COMPLETED")
        if current["consultant__username"] != DEMO_CONSULTANT_USERNAME:
            blockers.append("G4_CONSULTANT_MISMATCH")
        if not current.get("confirmed_summary"):
            blockers.append("G4_CONFIRMED_SUMMARY_MISSING")
        if current.get("summary_confirmed_at") is None:
            blockers.append("G4_SUMMARY_CONFIRMATION_TIME_MISSING")
        if current.get("completed_at") is None:
            blockers.append("G4_COMPLETION_TIME_MISSING")
    return blockers


def _append_operation_blockers(
    blockers: list[str],
    operation_counts: Counter,
    expected_operations: set[str],
) -> None:
    for operation in sorted(expected_operations):
        count = operation_counts[operation]
        if count == 0:
            blockers.append(f"IDEMPOTENCY_OPERATION_MISSING:{operation}")
        elif count != 1:
            blockers.append(
                f"IDEMPOTENCY_OPERATION_COUNT_NOT_1:{operation}:{count}"
            )


def _json_safe(row: dict) -> dict:
    safe: dict = {}
    for key, value in row.items():
        if isinstance(value, UUID):
            safe[key] = str(value)
        elif hasattr(value, "isoformat"):
            safe[key] = value.isoformat()
        else:
            safe[key] = value
    return safe
