"""결정적 Safety 결과를 보존하는 근거 기반 고객 안내 생성기."""

from __future__ import annotations

import re

from ...common.retry import get_retry_policy
from ...common.timeout import CancellationToken, PipelineCancelledError
from ...integrations.llm import (
    GuidanceLLMClient,
    LLMConfigurationError,
    LLMOutputValidationError,
    LLMProviderTimeoutError,
    LLMRefusalError,
    OpenAIResponsesLLMClient,
)
from ...integrations.llm.token_usage import log_llm_usage
from ...schemas import ModelMetadata, UsageGuidance
from ...validation.safety import GuidanceMessageGuard, UsageGuidanceValidator
from .models import GuidanceGenerationRequest
from .prompt_identity import PROMPT_VERSION


class GuidanceGenerationExecutionError(RuntimeError):
    """HTTP 오류 계약으로 변환할 수 있는 생성 단계 최종 실패."""

    def __init__(
        self,
        message: str,
        *,
        retry_count: int,
        retryable: bool,
        timed_out: bool = False,
    ) -> None:
        self.retry_count = retry_count
        self.retryable = retryable
        self.timed_out = timed_out
        super().__init__(message)


class CustomerGuidanceGenerator:
    """LLM 권한을 message·next_actions로만 제한해 최종 Guidance를 조립한다."""

    _PROVIDER_SYMPTOM_TYPES = frozenset(
        {
            "제품 누수",
            "전기 이상",
            "온도 이상",
            "출수량 저하",
            "물맛/냄새 이상",
            "소음 이상",
            "필터/관리 문의",
            "기타 증상",
        }
    )
    _PROVIDER_WATER_TYPES = frozenset({"냉수", "온수", "정수", "전체"})

    def __init__(self, llm_client: GuidanceLLMClient | None = None) -> None:
        self._llm_client = llm_client

    def generate(
        self,
        *,
        ctx,
        deterministic_guidance: UsageGuidance,
        cancellation_token: CancellationToken | None,
        attempt_timeout_seconds: float,
    ) -> UsageGuidance:
        client = self._llm_client
        if client is None:
            try:
                client = OpenAIResponsesLLMClient.from_environment()
            except LLMConfigurationError as exc:
                raise GuidanceGenerationExecutionError(
                    "실제 LLM Guidance 생성 구성이 완료되지 않았습니다.",
                    retry_count=0,
                    retryable=False,
                ) from exc

        request = self._build_request(ctx, deterministic_guidance)
        retry_policy = get_retry_policy()
        retry_count = 0
        while True:
            try:
                if cancellation_token is not None:
                    cancellation_token.raise_if_cancelled()
                response = client.generate_guidance(
                    request,
                    timeout_seconds=attempt_timeout_seconds,
                )
                break
            except (LLMConfigurationError, LLMOutputValidationError, LLMRefusalError) as exc:
                raise GuidanceGenerationExecutionError(
                    "LLM Guidance 출력을 검증하지 못했습니다.",
                    retry_count=retry_count,
                    retryable=False,
                ) from exc
            except PipelineCancelledError:
                raise
            except Exception as exc:
                if not retry_policy.can_retry(exc, retry_count):
                    raise GuidanceGenerationExecutionError(
                        "LLM Guidance 생성을 완료하지 못했습니다.",
                        retry_count=retry_count,
                        retryable=retry_policy.is_retryable_exception(exc),
                        timed_out=isinstance(exc, LLMProviderTimeoutError),
                    ) from exc
                next_retry_count = retry_count + 1
                backoff_seconds = retry_policy.backoff_seconds(next_retry_count)
                if cancellation_token is not None:
                    cancellation_token.wait(backoff_seconds)
                    cancellation_token.record_retry(next_retry_count)
                retry_count = next_retry_count
                ctx.retry_count = max(ctx.retry_count, retry_count)

        ctx.retry_count = max(ctx.retry_count, retry_count)
        candidate = UsageGuidance(
            guidance_status=deterministic_guidance.guidance_status,
            message=response.output.message,
            restricted_functions=deterministic_guidance.restricted_functions,
            next_actions=response.output.next_actions,
        )
        if any(
            action not in request.allowed_next_actions
            for action in candidate.next_actions
        ):
            raise GuidanceGenerationExecutionError(
                "LLM Guidance가 허용된 다음 행동 범위를 벗어났습니다.",
                retry_count=retry_count,
                retryable=False,
            )
        try:
            GuidanceMessageGuard().validate_grounding(
                candidate.message,
                grounding_texts=request.evidence_summaries,
            )
            accepted_guidance = UsageGuidanceValidator().validate(
                ctx.safety_assessment,
                candidate,
                has_evidence=True,
            )
        except ValueError as exc:
            raise GuidanceGenerationExecutionError(
                "LLM Guidance가 최종 안전 Gate를 통과하지 못했습니다.",
                retry_count=retry_count,
                retryable=False,
            ) from exc

        ctx.model_metadata = ModelMetadata(
            model_name=response.model_name,
            prompt_version=PROMPT_VERSION,
            tokens_used=response.usage.total_tokens,
            latency_ms=response.latency_ms,
        )
        log_llm_usage(
            correlation_id=ctx.trace_context.correlation_id,
            ai_request_id=ctx.trace_context.ai_request_id,
            model_name=response.model_name,
            prompt_version=PROMPT_VERSION,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.total_tokens,
            latency_ms=response.latency_ms,
            retry_count=retry_count,
        )
        return accepted_guidance

    @staticmethod
    def _build_request(ctx, guidance: UsageGuidance) -> GuidanceGenerationRequest:
        symptom = ctx.structured_symptom
        values: list[str] = []
        if symptom is not None:
            symptom_type = (
                symptom.symptom_type
                if symptom.symptom_type in CustomerGuidanceGenerator._PROVIDER_SYMPTOM_TYPES
                else "기타 증상"
            )
            target_water_type = (
                symptom.target_water_type
                if symptom.target_water_type in CustomerGuidanceGenerator._PROVIDER_WATER_TYPES
                else None
            )
            values = [
                symptom_type,
                target_water_type,
                symptom.occurrence_time,
                symptom.occurrence_condition,
                symptom.error_code,
                (
                    ctx.evidence_applicability.provider_label
                    if ctx.evidence_applicability is not None
                    else None
                ),
                *symptom.accompanying_symptoms,
                *symptom.actions_taken,
            ]
        sanitized_values: list[str] = []
        seen_values: set[str] = set()
        for value in values:
            if not value:
                continue
            sanitized = CustomerGuidanceGenerator._redact_provider_text(value)
            normalized = " ".join(sanitized.split()).casefold()
            if not sanitized or normalized in seen_values:
                continue
            seen_values.add(normalized)
            sanitized_values.append(sanitized)
        symptom_summary = " | ".join(sanitized_values)
        if not symptom_summary:
            symptom_summary = "기타 증상"
        sanitized_model_code = CustomerGuidanceGenerator._redact_provider_text(
            ctx.model_code
        )
        if not re.fullmatch(r"[A-Z0-9-]{1,100}", sanitized_model_code):
            sanitized_model_code = "UNKNOWN_MODEL"
        return GuidanceGenerationRequest(
            model_code=sanitized_model_code,
            symptom_summary=symptom_summary,
            risk_level=ctx.safety_assessment.risk_level.value,
            guidance_status=guidance.guidance_status.value,
            safety_reason=ctx.safety_assessment.safety_reason,
            restricted_functions=guidance.restricted_functions,
            allowed_next_actions=guidance.next_actions,
            evidence_summaries=[reference.summary for reference in ctx.evidence_references],
        )

    @staticmethod
    def _redact_provider_text(value: str) -> str:
        """Provider 입력 직전 연락처·식별자·URL을 보수적으로 제거한다."""

        patterns = (
            (
                re.compile(
                    r"(?<!\d)(?:\+?82[-\s]?)?0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"
                ),
                "[REDACTED_PHONE]",
            ),
            (
                re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
                "[REDACTED_EMAIL]",
            ),
            (
                re.compile(r"(?<!\d)\d{6}-?[1-4]\d{6}(?!\d)"),
                "[REDACTED_ID]",
            ),
            (
                re.compile(r"https?://\S+", flags=re.IGNORECASE),
                "[REDACTED_URL]",
            ),
            (
                re.compile(r"(?<!\d)\d{8,}(?!\d)"),
                "[REDACTED_NUMBER]",
            ),
        )
        sanitized = value
        for pattern, replacement in patterns:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized[:500]
