"""Single-attempt Backend-to-AI rejected HumanReview resume integration."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any
from uuid import UUID

import httpx
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.audit.models import AIRun
from apps.evidence.models import AIChunkCrosswalk
from apps.inquiries.models import ConsultationCauseLedger, HumanReview


RESUME_PATH = "/api/v1/internal/ai/human-reviews/resume"
CONTEXT_RESUME_APPROVED_MODEL_CODES = frozenset({"WPUJAC104DWH"})
CONTEXT_RESUME_REQUIRED_RUNTIME_NAME = "multi_agent"
ALLOWED_FALLBACK_REASONS = frozenset(
    {
        "CONFIGURATION",
        "PROVIDER_TIMEOUT",
        "PROVIDER_UNAVAILABLE",
        "OUTPUT_INVALID",
        "REFUSED",
        "DANGER_BYPASS",
        "INPUT_TOO_LARGE",
        "INPUT_NOT_ELIGIBLE",
        "SAFETY_NOT_VERIFIED",
        "RUNTIME_PRODUCT_NOT_APPROVED",
    }
)
RESUME_RESPONSE_KEYS = frozenset(
    {
        "contract_version",
        "backend_review_id",
        "inquiry_id",
        "ai_request_id",
        "source_inquiry_state_version",
        "review_state_version",
        "status",
        "routing_reason",
        "escalation_reason",
        "context_agent_calls",
        "provider_calls",
        "context_synthesis_status",
        "fallback_reason",
        "handoff_created",
        "handoff_delivery_scheduled",
        "idempotent_replay",
    }
)


class HumanReviewResumeFailure(RuntimeError):
    """A bounded failure that never contains an upstream body or exception."""

    def __init__(self, failure_code: str) -> None:
        self.failure_code = failure_code
        super().__init__(failure_code)


@dataclass(frozen=True, slots=True)
class HumanReviewResumeReceipt:
    backend_review_id: UUID
    inquiry_id: UUID
    ai_request_id: str
    review_state_version: int
    context_agent_calls: int
    provider_calls: int
    context_synthesis_status: str
    fallback_reason: str | None
    handoff_created: bool
    handoff_delivery_scheduled: bool
    idempotent_replay: bool


def _checkpoint_thread_id(
    *,
    inquiry_id: UUID,
    ai_request_id: str,
    state_version: int,
) -> str:
    raw = f"{inquiry_id}:{ai_request_id}:{state_version}".encode("utf-8")
    return f"hitl-{sha256(raw).hexdigest()[:32]}"


def _resume_idempotency_key(review: HumanReview) -> str:
    return (
        "human-review-resume:"
        f"{review.public_id}:{review.review_state_version}"
    )


def _load_review(review_public_id: UUID) -> HumanReview:
    review = (
        HumanReview.objects.select_related(
            "inquiry__subscription__product_model",
            "guidance__generated_by_ai_run",
        )
        .filter(public_id=review_public_id)
        .first()
    )
    if review is None:
        raise HumanReviewResumeFailure("AI_RESUME_REVIEW_NOT_FOUND")
    return review


def build_human_review_resume_payload(
    review_public_id: UUID,
) -> tuple[dict[str, Any], str]:
    """Build a fail-closed DTO only from the committed Backend ledger."""

    review = _load_review(review_public_id)
    inquiry = review.inquiry
    run = review.guidance.generated_by_ai_run
    model_code = inquiry.subscription.product_model.model_code.strip().upper()
    if model_code not in CONTEXT_RESUME_APPROVED_MODEL_CODES:
        raise HumanReviewResumeFailure("RUNTIME_PRODUCT_NOT_APPROVED")
    if (
        review.status_code != HumanReview.Status.REJECTED
        or review.decision_code != HumanReview.Decision.REJECT
        or review.decision_correlation_id is None
        or review.review_state_version != 2
    ):
        raise HumanReviewResumeFailure("AI_RESUME_REVIEW_NOT_REJECTED")
    if (
        run is None
        or run.status_code
        not in {AIRun.Status.SUCCEEDED, AIRun.Status.NO_EVIDENCE}
        or run.schema_validation_status_code
        != AIRun.SchemaValidationStatus.PASSED
        or not isinstance(run.validated_output_payload, dict)
    ):
        raise HumanReviewResumeFailure("AI_RESUME_RUN_NOT_VERIFIED")

    analysis = run.validated_output_payload
    required_identifiers = {
        "inquiry_id": str(inquiry.public_id),
        "correlation_id": str(run.correlation_id),
        "ai_request_id": review.source_ai_request_id,
        "state_version": review.source_inquiry_state_version,
        "model_code": inquiry.subscription.product_model.model_code,
    }
    if any(
        str(analysis.get(name)) != str(expected)
        for name, expected in required_identifiers.items()
    ):
        raise HumanReviewResumeFailure("AI_RESUME_OUTPUT_ID_MISMATCH")

    run_input = run.input_payload
    if not isinstance(run_input, dict) or any(
        str(run_input.get(name)) != str(expected)
        for name, expected in required_identifiers.items()
    ):
        raise HumanReviewResumeFailure("AI_RESUME_INPUT_ID_MISMATCH")
    if inquiry.state_version != review.source_inquiry_state_version + 1:
        raise HumanReviewResumeFailure("AI_RESUME_STALE_INQUIRY_VERSION")
    expected_checkpoint = _checkpoint_thread_id(
        inquiry_id=inquiry.public_id,
        ai_request_id=review.source_ai_request_id,
        state_version=review.source_inquiry_state_version,
    )
    if review.checkpoint_thread_id != expected_checkpoint:
        raise HumanReviewResumeFailure("AI_RESUME_CHECKPOINT_MISMATCH")

    evidence = analysis.get("evidence_references")
    if not isinstance(evidence, list):
        raise HumanReviewResumeFailure("AI_RESUME_EVIDENCE_INVALID")
    canonical_ids = []
    for item in evidence:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("chunk_id"), str)
            or not item["chunk_id"].strip()
            or item.get("verification_status") != "official_verified"
        ):
            raise HumanReviewResumeFailure("AI_RESUME_EVIDENCE_NOT_OFFICIAL")
        canonical_ids.append(item["chunk_id"])
    if len(canonical_ids) != len(set(canonical_ids)):
        raise HumanReviewResumeFailure("AI_RESUME_EVIDENCE_DUPLICATE")

    links = list(
        review.guidance.evidence_links.select_related("chunk")
        .order_by("display_order", "id")
    )
    if (
        len(links) != len(canonical_ids)
        or any(not link.is_verified or link.ai_run_id != run.id for link in links)
    ):
        raise HumanReviewResumeFailure("AI_RESUME_EVIDENCE_BINDING_MISMATCH")
    crosswalk_by_chunk_id = {
        item.chunk_id: item.canonical_chunk_id
        for item in AIChunkCrosswalk.objects.filter(
            chunk_id__in=[link.chunk_id for link in links],
            is_active=True,
            is_verified=True,
        )
    }
    persisted_canonical_ids = [
        crosswalk_by_chunk_id.get(link.chunk_id) for link in links
    ]
    if persisted_canonical_ids != canonical_ids:
        raise HumanReviewResumeFailure("AI_RESUME_EVIDENCE_BINDING_MISMATCH")

    try:
        cause_ledger = run.consultation_cause_ledger
    except ConsultationCauseLedger.DoesNotExist as exc:
        raise HumanReviewResumeFailure(
            "AI_RESUME_CAUSE_LEDGER_MISSING"
        ) from exc
    try:
        cause_ledger.full_clean()
    except ValidationError as exc:
        raise HumanReviewResumeFailure(
            "AI_RESUME_CAUSE_LEDGER_INVALID"
        ) from exc
    if (
        cause_ledger.contract_version != "1.0.0"
        or cause_ledger.producer != "AI_HARNESS"
        or cause_ledger.inquiry_id != inquiry.id
        or cause_ledger.ai_run_id != run.id
        or str(cause_ledger.correlation_id) != str(run.correlation_id)
        or cause_ledger.ai_request_id != review.source_ai_request_id
        or cause_ledger.source_inquiry_state_version
        != review.source_inquiry_state_version
        or cause_ledger.model_code
        != inquiry.subscription.product_model.model_code
    ):
        raise HumanReviewResumeFailure("AI_RESUME_CAUSE_LEDGER_MISMATCH")
    execution_identity = cause_ledger.execution_identity
    if (
        not isinstance(execution_identity, dict)
        or execution_identity.get("runtime_name")
        != CONTEXT_RESUME_REQUIRED_RUNTIME_NAME
    ):
        raise HumanReviewResumeFailure("AI_RESUME_RUNTIME_NOT_MULTI_AGENT")

    payload = {
        "contract_version": "1.0.0",
        "backend_review_id": str(review.public_id),
        "review_state_version": review.review_state_version,
        "decision": "REJECT",
        "decision_correlation_id": str(review.decision_correlation_id),
        "source_inquiry_state_version": (
            review.source_inquiry_state_version
        ),
        "current_inquiry_state_version": inquiry.state_version,
        "checkpoint_thread_id": review.checkpoint_thread_id,
        # The validated AI result contains structured facts, not the raw
        # customer inquiry or an internal prompt.
        "analysis_result": analysis,
    }
    return payload, _resume_idempotency_key(review)


class HumanReviewResumeClient:
    """Call the protected AI endpoint exactly once with no automatic retry."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_seconds: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.token = token.strip()
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client
        if not self.base_url or len(self.token.encode("utf-8")) < 32:
            raise HumanReviewResumeFailure("AI_RESUME_CONFIGURATION_MISSING")
        if timeout_seconds != 30.0:
            raise HumanReviewResumeFailure("AI_RESUME_TIMEOUT_INVALID")

    def resume(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> HumanReviewResumeReceipt:
        client = self._http_client or httpx.Client(
            timeout=httpx.Timeout(self.timeout_seconds)
        )
        owns_client = self._http_client is None
        try:
            response = client.post(
                f"{self.base_url}{RESUME_PATH}",
                headers={
                    "X-Backend-Resume-Token": self.token,
                    "Idempotency-Key": idempotency_key,
                    "X-Correlation-ID": payload["decision_correlation_id"],
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise HumanReviewResumeFailure("AI_RESUME_TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise HumanReviewResumeFailure("AI_RESUME_TRANSPORT") from exc
        finally:
            if owns_client:
                client.close()

        if not 200 <= response.status_code < 300:
            raise HumanReviewResumeFailure("AI_RESUME_REJECTED")
        try:
            body = response.json()
        except ValueError as exc:
            raise HumanReviewResumeFailure("AI_RESUME_RESPONSE_INVALID") from exc
        return self._validate_receipt(body, payload)

    @staticmethod
    def _validate_receipt(
        body: Any,
        expected: dict[str, Any],
    ) -> HumanReviewResumeReceipt:
        if not isinstance(body, dict):
            raise HumanReviewResumeFailure("AI_RESUME_RESPONSE_INVALID")
        if frozenset(body) != RESUME_RESPONSE_KEYS:
            raise HumanReviewResumeFailure("AI_RESUME_RESPONSE_INVALID")
        expected_values = {
            "contract_version": "1.0.0",
            "backend_review_id": expected["backend_review_id"],
            "inquiry_id": expected["analysis_result"]["inquiry_id"],
            "ai_request_id": expected["analysis_result"]["ai_request_id"],
            "source_inquiry_state_version": expected[
                "source_inquiry_state_version"
            ],
            "review_state_version": expected["review_state_version"],
            "status": "RESUMED",
            "routing_reason": "FAIL_CLOSED_CONSULTATION",
            "escalation_reason": "HUMAN_REVIEW_REJECTED",
            "context_agent_calls": 1,
            "handoff_created": True,
        }
        if any(
            str(body.get(name)) != str(value)
            for name, value in expected_values.items()
        ):
            raise HumanReviewResumeFailure("AI_RESUME_RESPONSE_MISMATCH")
        provider_calls = body.get("provider_calls")
        if provider_calls not in {0, 1}:
            raise HumanReviewResumeFailure("AI_RESUME_RESPONSE_INVALID")
        synthesis_status = body.get("context_synthesis_status")
        fallback_reason = body.get("fallback_reason")
        if synthesis_status not in {"SUCCEEDED", "FALLBACK", "UNAVAILABLE"}:
            raise HumanReviewResumeFailure("AI_RESUME_RESPONSE_INVALID")
        if (
            synthesis_status == "SUCCEEDED"
            and (provider_calls != 1 or fallback_reason is not None)
        ):
            raise HumanReviewResumeFailure("AI_RESUME_RESPONSE_INVALID")
        if (
            synthesis_status == "FALLBACK"
            and fallback_reason not in ALLOWED_FALLBACK_REASONS
        ):
            raise HumanReviewResumeFailure("AI_RESUME_RESPONSE_INVALID")
        if synthesis_status == "UNAVAILABLE" and (
            provider_calls != 0 or fallback_reason is not None
        ):
            raise HumanReviewResumeFailure("AI_RESUME_RESPONSE_INVALID")
        if not isinstance(body.get("handoff_delivery_scheduled"), bool):
            raise HumanReviewResumeFailure("AI_RESUME_RESPONSE_INVALID")
        if not isinstance(body.get("idempotent_replay"), bool):
            raise HumanReviewResumeFailure("AI_RESUME_RESPONSE_INVALID")
        try:
            backend_review_id = UUID(str(body["backend_review_id"]))
            inquiry_id = UUID(str(body["inquiry_id"]))
        except (TypeError, ValueError) as exc:
            raise HumanReviewResumeFailure(
                "AI_RESUME_RESPONSE_INVALID"
            ) from exc
        return HumanReviewResumeReceipt(
            backend_review_id=backend_review_id,
            inquiry_id=inquiry_id,
            ai_request_id=str(body["ai_request_id"]),
            review_state_version=int(body["review_state_version"]),
            context_agent_calls=1,
            provider_calls=int(provider_calls),
            context_synthesis_status=str(synthesis_status),
            fallback_reason=(
                str(fallback_reason)
                if fallback_reason is not None
                else None
            ),
            handoff_created=True,
            handoff_delivery_scheduled=body[
                "handoff_delivery_scheduled"
            ],
            idempotent_replay=body["idempotent_replay"],
        )


def resume_rejected_human_review(
    review_public_id: UUID,
    *,
    http_client: httpx.Client | None = None,
) -> HumanReviewResumeReceipt:
    payload, idempotency_key = build_human_review_resume_payload(
        review_public_id
    )
    return send_human_review_resume_payload(
        payload,
        idempotency_key=idempotency_key,
        http_client=http_client,
    )


def send_human_review_resume_payload(
    payload: dict[str, Any],
    *,
    idempotency_key: str,
    http_client: httpx.Client | None = None,
) -> HumanReviewResumeReceipt:
    """Send the exact payload that the durable dispatch ledger hashed."""

    client = HumanReviewResumeClient(
        base_url=settings.AI_SERVICE_BASE_URL,
        token=settings.AI_HUMAN_REVIEW_RESUME_TOKEN,
        timeout_seconds=settings.AI_SERVICE_TIMEOUT_SECONDS,
        http_client=http_client,
    )
    return client.resume(payload, idempotency_key=idempotency_key)
