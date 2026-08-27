"""상담사에게 전달할 맥락을 출처 보존형 브리프로 가공하는 독립 후보 Agent."""

from __future__ import annotations

from ...common.timeout import PipelineCancelledError
from ...generation.consultation_summary.context_synthesizer import (
    ConsultationContextSynthesizer,
    PreparedContextSynthesis,
)
from ...generation.consultation_summary.prompt_identity import PROMPT_VERSION
from ...integrations.llm.consultation_summary_client import (
    ConsultationContextLLMClient,
)
from ...integrations.llm.llm_client import (
    LLMConfigurationError,
    LLMOutputValidationError,
    LLMProviderConnectionError,
    LLMProviderTimeoutError,
    LLMRefusalError,
)
from ...validation.consultation_context import (
    ContextBriefValidationError,
    CounselorContextBriefValidator,
)
from .context_synthesis_contracts import (
    ConsultationContextSynthesisAgentOutput,
    ConsultationContextSynthesisInput,
    ContextSynthesisFallbackReason,
    ContextSynthesisStatus,
)


class ConsultationContextSynthesisAgent:
    """상담 분기 이후 구조화 사실을 압축하되 진단·업무 상태는 결정하지 않는다."""

    role = "CONSULTATION_CONTEXT_SYNTHESIS_CANDIDATE"
    allowed_tools = (
        "ConsultationContextLLMClient",
        "CounselorContextBriefValidator",
        "DeterministicContextBriefBuilder",
    )
    completion_condition = (
        "모든 입력 사실 범주가 보존되고 생성 문장 출처·비식별·금지표현 검증을 통과"
    )
    failure_policy = (
        "재시도 없이 비식별 결정론적 브리프를 반환하며 상담 이관 자체를 차단하지 않음"
    )

    def __init__(
        self,
        *,
        llm_client: ConsultationContextLLMClient | None = None,
        synthesizer: ConsultationContextSynthesizer | None = None,
        validator: CounselorContextBriefValidator | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._synthesizer = synthesizer or ConsultationContextSynthesizer()
        self._validator = validator or CounselorContextBriefValidator()

    def run(
        self,
        synthesis_input: ConsultationContextSynthesisInput,
        *,
        timeout_seconds: float = 5.0,
    ) -> ConsultationContextSynthesisAgentOutput:
        """공유 Pipeline을 변경하지 않고 독립 계약 한 건을 합성한다."""

        synthesis_input = ConsultationContextSynthesisInput.model_validate(
            synthesis_input.model_dump(mode="python")
        )
        prepared = self._synthesizer.prepare(synthesis_input)
        if prepared.request is None:
            reason_by_bypass = {
                "DANGER": ContextSynthesisFallbackReason.DANGER_BYPASS,
                "INPUT_TOO_LARGE": ContextSynthesisFallbackReason.INPUT_TOO_LARGE,
                "INPUT_NOT_ELIGIBLE": (
                    ContextSynthesisFallbackReason.INPUT_NOT_ELIGIBLE
                ),
                "RUNTIME_PRODUCT_NOT_APPROVED": (
                    ContextSynthesisFallbackReason.RUNTIME_PRODUCT_NOT_APPROVED
                ),
                "SAFETY_NOT_VERIFIED": (
                    ContextSynthesisFallbackReason.SAFETY_NOT_VERIFIED
                ),
            }
            reason = reason_by_bypass[prepared.provider_bypass_reason]
            return self._fallback(
                synthesis_input,
                prepared,
                reason=reason,
                provider_called=False,
            )
        if self._llm_client is None:
            return self._fallback(
                synthesis_input,
                prepared,
                reason=ContextSynthesisFallbackReason.CONFIGURATION,
                provider_called=False,
            )
        if timeout_seconds <= 0:
            return self._fallback(
                synthesis_input,
                prepared,
                reason=ContextSynthesisFallbackReason.PROVIDER_TIMEOUT,
                provider_called=False,
            )

        try:
            response = self._llm_client.synthesize_context(
                prepared.request,
                timeout_seconds=timeout_seconds,
            )
            brief = self._validator.validate_and_build(
                candidate=response.output,
                sources_by_id=prepared.sources_by_id,
                evidence_chunk_ids_by_source_id=(
                    prepared.evidence_chunk_ids_by_source_id
                ),
                provider_source_ids=prepared.provider_source_ids,
            )
            success_output = ConsultationContextSynthesisAgentOutput(
                inquiry_id=synthesis_input.inquiry_id,
                correlation_id=synthesis_input.correlation_id,
                ai_request_id=synthesis_input.ai_request_id,
                state_version=synthesis_input.state_version,
                model_code=synthesis_input.model_code,
                routing_reason=synthesis_input.routing_reason,
                status=ContextSynthesisStatus.SUCCEEDED,
                brief=brief,
                fallback_reason=None,
                should_use_deterministic_handoff=False,
                provider_called=True,
                retry_count=0,
                model_name=response.model_name,
                prompt_version=PROMPT_VERSION,
                tokens_used=response.usage.total_tokens,
                latency_ms=response.latency_ms,
            )
        except PipelineCancelledError:
            raise
        except LLMProviderTimeoutError:
            return self._fallback(
                synthesis_input,
                prepared,
                reason=ContextSynthesisFallbackReason.PROVIDER_TIMEOUT,
                provider_called=True,
            )
        except LLMProviderConnectionError:
            return self._fallback(
                synthesis_input,
                prepared,
                reason=ContextSynthesisFallbackReason.PROVIDER_UNAVAILABLE,
                provider_called=True,
            )
        except LLMConfigurationError:
            return self._fallback(
                synthesis_input,
                prepared,
                reason=ContextSynthesisFallbackReason.CONFIGURATION,
                provider_called=True,
            )
        except LLMRefusalError:
            return self._fallback(
                synthesis_input,
                prepared,
                reason=ContextSynthesisFallbackReason.REFUSED,
                provider_called=True,
            )
        except (LLMOutputValidationError, ContextBriefValidationError, ValueError):
            return self._fallback(
                synthesis_input,
                prepared,
                reason=ContextSynthesisFallbackReason.OUTPUT_INVALID,
                provider_called=True,
            )
        except Exception:
            return self._fallback(
                synthesis_input,
                prepared,
                reason=ContextSynthesisFallbackReason.PROVIDER_UNAVAILABLE,
                provider_called=True,
            )

        return success_output

    @staticmethod
    def _fallback(
        synthesis_input: ConsultationContextSynthesisInput,
        prepared: PreparedContextSynthesis,
        *,
        reason: ContextSynthesisFallbackReason,
        provider_called: bool,
    ) -> ConsultationContextSynthesisAgentOutput:
        return ConsultationContextSynthesisAgentOutput(
            inquiry_id=synthesis_input.inquiry_id,
            correlation_id=synthesis_input.correlation_id,
            ai_request_id=synthesis_input.ai_request_id,
            state_version=synthesis_input.state_version,
            model_code=synthesis_input.model_code,
            routing_reason=synthesis_input.routing_reason,
            status=ContextSynthesisStatus.FALLBACK,
            brief=prepared.deterministic_brief,
            fallback_reason=reason,
            should_use_deterministic_handoff=True,
            provider_called=provider_called,
            retry_count=0,
            model_name=None,
            prompt_version=PROMPT_VERSION,
            tokens_used=None,
            latency_ms=None,
        )
