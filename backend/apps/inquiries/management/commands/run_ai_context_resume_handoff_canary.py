"""Run one guarded JAC104 Resume -> Context -> Handoff production Canary."""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid5

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.accounts.models import User
from apps.audit.models import AIRun
from apps.consultations.models import Consultation, ConsultationHandoff
from apps.evidence.models import EvidenceLink
from apps.inquiries.models import (
    ConsultationCauseLedger,
    Guidance,
    HumanReview,
    HumanReviewResumeDispatch,
    Inquiry,
    SymptomEntry,
)
from apps.inquiries.services.human_review_service import HumanReviewService
from apps.inquiries.services.inquiry_transition_service import (
    InquiryTransitionService,
)


CANONICAL_CONTRACT_NO = "SUB-SYN-0001"
CANONICAL_MODEL_CODE = "WPUJAC104DWH"
CANONICAL_CONSULTANT_USERNAME = "DEMO-CONSULTANT-001"
FIXTURE_SCENARIO_PREFIX = "SYN-AI-CONTEXT-"
FIXTURE_IDEMPOTENCY_PREFIX = "ai-context-e2e-"
CANARY_NAMESPACE = UUID("a5f63dbd-e125-4f0e-95b8-846ec2cc2607")
RELEASE_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:01[016789])[- ]?\d{3,4}[- ]?\d{4}(?!\d)"
)
EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
FORBIDDEN_KEY_PARTS = ("api_key", "secret", "token", "prompt")
HANDOFF_WAIT_SECONDS = 20.0


class Command(BaseCommand):
    help = (
        "승인된 신규 JAC104 합성 문의 한 건으로 공식 거절, AI Resume, "
        "맥락 Agent, Handoff와 Replay를 한 번만 검증합니다."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--inquiry-id", required=True)
        parser.add_argument("--expected-release-sha", required=True)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="검증된 합성 문의를 실제로 소비합니다.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
        )

    def handle(self, *args, **options) -> None:
        del args
        inquiry_id = self._uuid(options["inquiry_id"], "inquiry_id")
        expected_sha = self._release_sha(options["expected_release_sha"])
        self._assert_runtime(expected_sha=expected_sha)
        inquiry = self._load_target(inquiry_id)
        self._assert_baseline(inquiry)

        if not options["apply"]:
            self._render(
                {
                    "canary_scope": "JAC104_RESUME_CONTEXT_HANDOFF_REPLAY",
                    "inquiry_id": str(inquiry.public_id),
                    "overall_status": "READY_FOR_APPLY",
                    "release_sha": expected_sha,
                    "writes_performed": False,
                },
                json_output=options["json_output"],
            )
            return

        self._require_postgresql()
        consultant = self._canonical_consultant()
        identities = self._identities(inquiry)
        submit = InquiryTransitionService.submit_symptom(
            actor=inquiry.initiated_by,
            inquiry_public_id=inquiry.public_id,
            validated_data={"state_version": 1},
            idempotency_key=identities["submit_key"],
            correlation_id=identities["submit_correlation"],
        )
        if (
            submit.status_code != 200
            or submit.data.get("idempotent_replay") is not False
        ):
            raise CommandError("최초 증상 제출이 새 실행으로 확정되지 않았습니다.")

        run, review, initial_evidence_count = self._assert_initial_review(
            inquiry.public_id
        )
        decision_data = {
            "decision": HumanReview.Decision.REJECT,
            "review_state_version": 1,
            "reason_code": "CANARY_CONTEXT_REJECT",
            "consultation_disposition": (
                HumanReview.ConsultationDisposition.PRESERVE
            ),
            "consultation_evidence_ids": [],
        }
        decision = HumanReviewService.decide(
            actor=consultant,
            review_public_id=review.public_id,
            validated_data=decision_data,
            idempotency_key=identities["decision_key"],
            correlation_id=identities["decision_correlation"],
        )
        if (
            decision.status_code != 200
            or decision.data.get("idempotent_replay") is not False
        ):
            raise CommandError("공식 HumanReview 거절이 새 결정으로 확정되지 않았습니다.")

        dispatch, handoff, consultation = self._assert_automatic_result(
            inquiry_id=inquiry.public_id,
            run=run,
            review_id=review.public_id,
        )
        counts_before_replay = self._counts(inquiry.public_id)

        decision_replay = HumanReviewService.decide(
            actor=consultant,
            review_public_id=review.public_id,
            validated_data=decision_data,
            idempotency_key=identities["decision_key"],
            correlation_id=identities["decision_correlation"],
        )
        if (
            decision_replay.status_code != 200
            or decision_replay.data.get("idempotent_replay") is not True
        ):
            raise CommandError("HumanReview 결정 Replay가 멱등 응답이 아닙니다.")
        self._assert_counts_unchanged(
            inquiry.public_id,
            expected=counts_before_replay,
            stage="decision_replay",
        )

        handoff_replay = self._replay_handoff_http(handoff)
        if (
            handoff_replay.get("handoff_id") != str(handoff.public_id)
            or handoff_replay.get("idempotent_replay") is not True
        ):
            raise CommandError("Handoff HTTP Replay가 기존 원장을 반환하지 않았습니다.")
        self._assert_counts_unchanged(
            inquiry.public_id,
            expected=counts_before_replay,
            stage="handoff_replay",
        )
        dispatch.refresh_from_db()
        if dispatch.attempt_count != 1 or dispatch.provider_calls != 1:
            raise CommandError("Replay 이후 Provider 호출 원장이 증가했습니다.")

        self._render(
            {
                "ai_run_count": counts_before_replay["ai_runs"],
                "canary_scope": "JAC104_RESUME_CONTEXT_HANDOFF_REPLAY",
                "consultation_count": counts_before_replay["consultations"],
                "consultation_id": str(consultation.public_id),
                "context_agent_calls": 1,
                "context_synthesis_status": dispatch.context_synthesis_status,
                "decision_replay_idempotent": True,
                "fallback_reason": dispatch.fallback_reason,
                "handoff_count": counts_before_replay["handoffs"],
                "handoff_http_replay_idempotent": True,
                "handoff_payload_sha256": handoff.payload_sha256,
                "inquiry_id": str(inquiry.public_id),
                "initial_context_agent_calls": 0,
                "initial_context_provider_calls": 0,
                "initial_evidence_count": initial_evidence_count,
                "overall_status": "AWS_AUTO_CONTEXT_HANDOFF_PASS",
                "provider_calls": dispatch.provider_calls,
                "release_sha": expected_sha,
                "resume_attempt_count": dispatch.attempt_count,
                "resume_dispatch_count": counts_before_replay[
                    "resume_dispatches"
                ],
                "sensitive_data_exposure": "NONE_DETECTED",
            },
            json_output=options["json_output"],
        )

    @staticmethod
    def _uuid(value: str, label: str) -> UUID:
        try:
            return UUID(str(value))
        except (TypeError, ValueError, AttributeError) as exc:
            raise CommandError(f"{label} 형식이 UUID가 아닙니다.") from exc

    @staticmethod
    def _release_sha(value: str) -> str:
        normalized = str(value).strip().lower()
        if RELEASE_SHA_PATTERN.fullmatch(normalized) is None:
            raise CommandError("expected_release_sha는 40자리 Git SHA여야 합니다.")
        return normalized

    @staticmethod
    def _assert_runtime(*, expected_sha: str) -> None:
        actual_sha = os.getenv("RELEASE_SHA", "").strip().lower()
        if actual_sha != expected_sha:
            raise CommandError("실행 Container Release SHA가 승인값과 다릅니다.")
        if settings.AI_SERVICE_MODE != "local":
            raise CommandError(
                "Backend가 실제 AI HTTP 모드(local)가 아닙니다."
            )
        ai_endpoint = urlsplit(settings.AI_SERVICE_BASE_URL)
        try:
            ai_port = ai_endpoint.port
        except ValueError as exc:
            raise CommandError(
                "Backend AI HTTP 대상 주소가 올바르지 않습니다."
            ) from exc
        if not (
            ai_endpoint.scheme == "http"
            and ai_endpoint.hostname == "ai"
            and ai_port == 8001
            and ai_endpoint.username is None
            and ai_endpoint.password is None
            and ai_endpoint.path in {"", "/"}
            and not ai_endpoint.query
            and not ai_endpoint.fragment
        ):
            raise CommandError(
                "Backend AI HTTP 대상이 보호된 내부 Runtime이 아닙니다."
            )
        if not settings.AI_HUMAN_REVIEW_RESUME_ENABLED:
            raise CommandError("Backend HumanReview Resume가 비활성 상태입니다.")
        if len(settings.AI_HUMAN_REVIEW_RESUME_TOKEN.encode("utf-8")) < 32:
            raise CommandError("Backend Resume 보호 토큰이 준비되지 않았습니다.")
        if len(settings.AI_HANDOFF_INTERNAL_TOKEN.encode("utf-8")) < 32:
            raise CommandError("Backend Handoff 보호 토큰이 준비되지 않았습니다.")

    @staticmethod
    def _require_postgresql() -> None:
        if connection.vendor != "postgresql":
            raise CommandError("운영 Canary apply는 PostgreSQL에서만 허용합니다.")

    @staticmethod
    def _load_target(inquiry_id: UUID) -> Inquiry:
        inquiry = (
            Inquiry.objects.select_related(
                "initiated_by",
                "subscription__customer__user",
                "subscription__product_model",
            )
            .filter(public_id=inquiry_id)
            .first()
        )
        if inquiry is None:
            raise CommandError("Canary Inquiry를 찾을 수 없습니다.")
        owner = inquiry.initiated_by
        customer = inquiry.subscription.customer
        product = inquiry.subscription.product_model
        if not (
            owner.is_synthetic
            and owner.is_active
            and owner.role_code == User.Role.CUSTOMER
            and customer.is_synthetic
            and customer.user_id == owner.pk
            and customer.deleted_at is None
            and inquiry.subscription.status_code == "ACTIVE"
            and inquiry.subscription.contract_no == CANONICAL_CONTRACT_NO
            and product.model_code == CANONICAL_MODEL_CODE
            and product.is_active
            and product.is_supported_mvp
            and inquiry.channel_code == Inquiry.Channel.MOBILE
            and str(inquiry.scenario_code or "").startswith(
                FIXTURE_SCENARIO_PREFIX
            )
            and str(inquiry.source_idempotency_key or "").startswith(
                FIXTURE_IDEMPOTENCY_PREFIX
            )
            and inquiry.source_correlation_id is not None
        ):
            raise CommandError("승인된 신규 JAC104 합성 Fixture 경계가 아닙니다.")
        return inquiry

    @staticmethod
    def _assert_baseline(inquiry: Inquiry) -> None:
        confirmed_low_flow = SymptomEntry.objects.filter(
            inquiry=inquiry,
            symptom_type_code="LOW_FLOW",
            is_customer_confirmed=True,
        ).count()
        counts = Command._counts(inquiry.public_id)
        if not (
            inquiry.status_code == Inquiry.Status.DRAFT
            and inquiry.state_version == 1
            and confirmed_low_flow == 1
            and all(value == 0 for value in counts.values())
        ):
            raise CommandError(
                "이미 소비됐거나 원장이 존재하는 Inquiry는 Canary에 사용할 수 없습니다."
            )

    @staticmethod
    def _canonical_consultant() -> User:
        consultant = User.objects.filter(
            username=CANONICAL_CONSULTANT_USERNAME,
            role_code=User.Role.CONSULTANT,
            is_active=True,
            is_synthetic=True,
        ).first()
        if consultant is None:
            raise CommandError("승인된 합성 상담사 계정이 준비되지 않았습니다.")
        return consultant

    @staticmethod
    def _identities(inquiry: Inquiry) -> dict[str, Any]:
        base = str(inquiry.public_id)
        return {
            "submit_key": f"aws-context-auto-submit:{base}",
            "submit_correlation": uuid5(
                CANARY_NAMESPACE,
                f"submit/{base}",
            ),
            "decision_key": f"aws-context-auto-reject:{base}",
            "decision_correlation": uuid5(
                CANARY_NAMESPACE,
                f"reject/{base}",
            ),
        }

    @staticmethod
    def _assert_initial_review(
        inquiry_id: UUID,
    ) -> tuple[AIRun, HumanReview, int]:
        inquiry = Inquiry.objects.get(public_id=inquiry_id)
        runs = AIRun.objects.filter(inquiry=inquiry)
        guidances = Guidance.objects.filter(inquiry=inquiry)
        reviews = HumanReview.objects.filter(inquiry=inquiry)
        if not (
            inquiry.status_code == Inquiry.Status.QUESTIONNAIRE_IN_PROGRESS
            and inquiry.state_version == 2
            and runs.count() == 1
            and guidances.count() == 1
            and reviews.count() == 1
            and ConsultationCauseLedger.objects.filter(inquiry=inquiry).count()
            == 1
            and HumanReviewResumeDispatch.objects.filter(
                human_review__in=reviews
            ).count()
            == 0
            and ConsultationHandoff.objects.filter(inquiry=inquiry).count()
            == 0
            and Consultation.objects.filter(inquiry=inquiry).count() == 0
        ):
            raise CommandError("최초 분석·검토 대기 원장이 예상 계약과 다릅니다.")
        run = runs.get()
        review = reviews.select_related("guidance").get()
        if not (
            run.status_code == AIRun.Status.SUCCEEDED
            and run.schema_validation_status_code
            == AIRun.SchemaValidationStatus.PASSED
            and run.completed_at is not None
            and review.status_code == HumanReview.Status.PENDING
            and review.review_state_version == 1
            and review.source_ai_request_id == run.idempotency_key
            and review.source_inquiry_state_version == 2
            and review.guidance_id == guidances.get().pk
        ):
            raise CommandError("AI Run과 초기 HumanReview 결속이 올바르지 않습니다.")
        payload = run.validated_output_payload
        references = (
            payload.get("evidence_references")
            if isinstance(payload, dict)
            else None
        )
        if (
            not isinstance(references, list)
            or not references
            or any(
                not isinstance(item, dict)
                or item.get("verification_status") != "official_verified"
                or not item.get("chunk_id")
                for item in references
            )
        ):
            raise CommandError("최초 AI 실행 Evidence가 official_verified가 아닙니다.")
        links = EvidenceLink.objects.filter(
            inquiry=inquiry,
            guidance=review.guidance,
            ai_run=run,
        )
        if links.count() != len(references) or links.filter(
            is_verified=False
        ).exists():
            raise CommandError("Backend 공식 Evidence 원장 결속이 불완전합니다.")
        return run, review, len(references)

    @classmethod
    def _assert_automatic_result(
        cls,
        *,
        inquiry_id: UUID,
        run: AIRun,
        review_id: UUID,
    ) -> tuple[HumanReviewResumeDispatch, ConsultationHandoff, Consultation]:
        review = HumanReview.objects.get(public_id=review_id)
        inquiry = Inquiry.objects.get(public_id=inquiry_id)
        if not (
            review.status_code == HumanReview.Status.REJECTED
            and review.decision_code == HumanReview.Decision.REJECT
            and review.review_state_version == 2
            and inquiry.status_code == Inquiry.Status.CONSULTATION_REQUIRED
        ):
            raise CommandError("공식 거절과 Inquiry 상담 전환이 확정되지 않았습니다.")
        dispatches = HumanReviewResumeDispatch.objects.filter(
            human_review=review
        )
        if dispatches.count() != 1:
            raise CommandError("Resume Dispatch가 정확히 한 건이 아닙니다.")
        dispatch = dispatches.get()
        if not (
            dispatch.status == HumanReviewResumeDispatch.Status.SUCCEEDED
            and dispatch.attempt_count == 1
            and dispatch.provider_calls == 1
            and dispatch.context_synthesis_status == "SUCCEEDED"
            and dispatch.fallback_reason is None
            and dispatch.handoff_delivery_scheduled is True
            and dispatch.idempotent_replay is False
            and SHA256_PATTERN.fullmatch(dispatch.payload_sha256 or "")
        ):
            raise CommandError("맥락 Agent Resume 성공 원장이 PASS 기준과 다릅니다.")

        deadline = time.monotonic() + HANDOFF_WAIT_SECONDS
        while time.monotonic() < deadline:
            if ConsultationHandoff.objects.filter(inquiry=inquiry).count() == 1:
                break
            time.sleep(0.25)
        handoffs = ConsultationHandoff.objects.filter(inquiry=inquiry)
        consultations = Consultation.objects.filter(inquiry=inquiry)
        if handoffs.count() != 1 or consultations.count() != 1:
            raise CommandError("Handoff 또는 Consultation 원장이 정확히 한 건이 아닙니다.")
        handoff = handoffs.select_related("consultation", "ai_run").get()
        consultation = consultations.get()
        if not (
            handoff.ai_run_id == run.pk
            and handoff.consultation_id == consultation.pk
            and handoff.schema_version == "2.0.0"
            and handoff.ai_request_id == run.idempotency_key
            and SHA256_PATTERN.fullmatch(handoff.payload_sha256 or "")
        ):
            raise CommandError("Handoff 식별자와 Backend 원장 결속이 다릅니다.")
        cls._assert_safe_handoff_payload(
            handoff.sanitized_payload,
            customer_raw_text=inquiry.raw_text,
        )
        return dispatch, handoff, consultation

    @staticmethod
    def _iter_strings(value: Any):
        if isinstance(value, str):
            yield value
        elif isinstance(value, Mapping):
            for item in value.values():
                yield from Command._iter_strings(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from Command._iter_strings(item)

    @staticmethod
    def _iter_keys(value: Any):
        if isinstance(value, Mapping):
            for key, item in value.items():
                yield str(key).casefold()
                yield from Command._iter_keys(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from Command._iter_keys(item)

    @classmethod
    def _assert_safe_handoff_payload(
        cls,
        payload: Any,
        *,
        customer_raw_text: str,
    ) -> None:
        if not isinstance(payload, dict):
            raise CommandError("Handoff 저장 Payload가 JSON Object가 아닙니다.")
        context = payload.get("context_synthesis")
        evidence = payload.get("evidence")
        source_ids = payload.get("source_chunk_ids")
        if not (
            payload.get("routing_reason") == "FAIL_CLOSED_CONSULTATION"
            and payload.get("escalation_reason") == "HUMAN_REVIEW_REJECTED"
            and isinstance(context, dict)
            and context.get("status") == "SUCCEEDED"
            and context.get("fallback_reason") is None
            and isinstance(evidence, list)
            and isinstance(source_ids, list)
            and source_ids
            == [item.get("chunk_id") for item in evidence if isinstance(item, dict)]
        ):
            raise CommandError("저장된 맥락 Handoff 계약이 PASS 기준과 다릅니다.")
        nested_ids = {
            chunk_id
            for finding in context.get("brief", {}).get(
                "evidence_based_findings", []
            )
            if isinstance(finding, dict)
            for chunk_id in finding.get("source_chunk_ids", [])
        }
        if not nested_ids.issubset(set(source_ids)):
            raise CommandError("맥락 Agent Evidence가 승인 Evidence 범위를 벗어났습니다.")
        keys = tuple(cls._iter_keys(payload))
        strings = tuple(cls._iter_strings(payload))
        if any(part in key for key in keys for part in FORBIDDEN_KEY_PARTS):
            raise CommandError("Handoff에 보호 필드 이름이 포함됐습니다.")
        if customer_raw_text and customer_raw_text in strings:
            raise CommandError("Handoff에 고객 원문이 그대로 포함됐습니다.")
        if any(
            PHONE_PATTERN.search(value) or EMAIL_PATTERN.search(value)
            for value in strings
        ):
            raise CommandError("Handoff에 직접 연락처 형식이 포함됐습니다.")

    @staticmethod
    def _replay_handoff_http(handoff: ConsultationHandoff) -> dict[str, Any]:
        allowed_host = next(
            (
                host
                for host in settings.ALLOWED_HOSTS
                if host and host != "*" and not host.startswith(".")
            ),
            None,
        )
        if allowed_host is None:
            raise CommandError("내부 Replay에 사용할 명시적 Backend Host가 없습니다.")
        url = (
            "http://127.0.0.1:8000/api/v1/internal/ai/inquiries/"
            f"{handoff.inquiry.public_id}/consultation-handoffs"
        )
        headers = {
            "Host": allowed_host,
            "X-AI-Handoff-Token": settings.AI_HANDOFF_INTERNAL_TOKEN,
            "Idempotency-Key": handoff.ai_request_id,
            "X-Correlation-ID": str(handoff.correlation_id),
        }
        try:
            with httpx.Client(timeout=5.0, trust_env=False) as client:
                response = client.post(
                    url,
                    json=handoff.sanitized_payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise CommandError("Handoff HTTP Replay 전송에 실패했습니다.") from exc
        if response.status_code != 200:
            raise CommandError(
                "Handoff HTTP Replay 응답이 200이 아닙니다. "
                f"status={response.status_code}"
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise CommandError("Handoff HTTP Replay 응답이 JSON이 아닙니다.") from exc
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            raise CommandError("Handoff HTTP Replay 응답 계약이 다릅니다.")
        return data

    @staticmethod
    def _counts(inquiry_id: UUID) -> dict[str, int]:
        inquiry = Inquiry.objects.get(public_id=inquiry_id)
        reviews = HumanReview.objects.filter(inquiry=inquiry)
        return {
            "ai_runs": AIRun.objects.filter(inquiry=inquiry).count(),
            "consultations": Consultation.objects.filter(inquiry=inquiry).count(),
            "handoffs": ConsultationHandoff.objects.filter(inquiry=inquiry).count(),
            "human_reviews": reviews.count(),
            "resume_dispatches": HumanReviewResumeDispatch.objects.filter(
                human_review__in=reviews
            ).count(),
        }

    @classmethod
    def _assert_counts_unchanged(
        cls,
        inquiry_id: UUID,
        *,
        expected: dict[str, int],
        stage: str,
    ) -> None:
        if cls._counts(inquiry_id) != expected:
            raise CommandError(f"{stage} 중 원장 건수가 증가했습니다.")

    def _render(self, payload: dict[str, Any], *, json_output: bool) -> None:
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if json_output:
            self.stdout.write(rendered)
            return
        self.stdout.write(self.style.SUCCESS(payload["overall_status"]))
        self.stdout.write(f"AI_CONTEXT_AUTO_CANARY={rendered}")
