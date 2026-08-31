"""공개 계약 4.0.0 필드 조합을 고객 전달 경로로 축소한다."""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from ...schemas import (
    AiExecutionStatus,
    AiStage,
    FallbackReasonCode,
    RiskLevel,
    SafetyPriority,
    SymptomAnalysisResult,
    UsageGuidance,
    UsageGuidanceStatus,
)


class ResponseRoutingDisposition(str, Enum):
    """Backend가 같은 공개 필드 조합으로 재현해야 하는 전달 판정."""

    DANGER_HANDOFF = "DANGER_HANDOFF"
    PRE_SEND_HUMAN_REVIEW = "PRE_SEND_HUMAN_REVIEW"
    AUTO_GUIDANCE = "AUTO_GUIDANCE"
    FAIL_CLOSED_CONSULTATION = "FAIL_CLOSED_CONSULTATION"
    CUSTOMER_INPUT_PENDING = "CUSTOMER_INPUT_PENDING"


class ResponseRoutingPolicy:
    """응답 Schema를 바꾸지 않고 Routing 의미와 Fail-closed 조건을 강제한다."""

    def apply(
        self,
        response: SymptomAnalysisResult,
        *,
        accepted_evidence_chunk_ids: Iterable[str] | None = None,
    ) -> tuple[SymptomAnalysisResult, ResponseRoutingDisposition]:
        """검증된 공개 응답과 내부 Routing 판정을 함께 반환한다."""

        if response.status == AiExecutionStatus.FALLBACK:
            return (
                self._normalize_existing_fallback(response),
                ResponseRoutingDisposition.FAIL_CLOSED_CONSULTATION,
            )

        safety = response.safety_assessment
        guidance = response.usage_guidance

        if safety.risk_level == RiskLevel.DANGER:
            if (
                safety.requires_consultation
                and safety.matched_safety_rule_ids
                and not response.missing_fields
                and not response.followup_questions
                and guidance.guidance_status
                not in {
                    UsageGuidanceStatus.NORMAL,
                    UsageGuidanceStatus.PENDING_CONSULTATION,
                }
            ):
                return response, ResponseRoutingDisposition.DANGER_HANDOFF
            return self._invalid_success_fallback(response)

        if response.followup_questions:
            # OPEN-18: clarification is Evidence-driven and may be requested
            # even when candidate evidence has already been retrieved.
            if (
                safety.risk_level == RiskLevel.CAUTION
                and safety.requires_consultation
                and guidance.guidance_status
                == UsageGuidanceStatus.PENDING_CONSULTATION
            ):
                return (
                    response,
                    ResponseRoutingDisposition.CUSTOMER_INPUT_PENDING,
                )
            return self._invalid_success_fallback(response)

        # OPEN-19: Runtime PRE_SEND HITL is removed. A validated non-danger
        # result that explicitly requests consultation should remain a normal
        # contract response and let Backend transition it to consultation.
        if safety.requires_consultation:
            return (
                response,
                ResponseRoutingDisposition.FAIL_CLOSED_CONSULTATION,
            )

        if safety.risk_level == RiskLevel.CAUTION:
            if (
                response.evidence_references
                and guidance.guidance_status == UsageGuidanceStatus.PARTIAL_STOP
                and self._accepted_evidence_matches(
                    response,
                    accepted_evidence_chunk_ids,
                )
            ):
                return (
                    response,
                    ResponseRoutingDisposition.AUTO_GUIDANCE,
                )
            return self._invalid_success_fallback(response)

        if safety.risk_level == RiskLevel.GENERAL:
            if (
                response.evidence_references
                and not safety.requires_consultation
                and not safety.matched_safety_rule_ids
                and not response.followup_questions
                and guidance.guidance_status == UsageGuidanceStatus.NORMAL
                and self._accepted_evidence_matches(
                    response,
                    accepted_evidence_chunk_ids,
                )
            ):
                return response, ResponseRoutingDisposition.AUTO_GUIDANCE
            return self._invalid_success_fallback(response)

        return self._invalid_success_fallback(response)

    @staticmethod
    def _accepted_evidence_matches(
        response: SymptomAnalysisResult,
        accepted_evidence_chunk_ids: Iterable[str] | None,
    ) -> bool:
        if accepted_evidence_chunk_ids is None:
            return True
        public_ids = [item.chunk_id for item in response.evidence_references]
        accepted_ids = list(accepted_evidence_chunk_ids)
        return (
            len(public_ids) == len(set(public_ids))
            and len(accepted_ids) == len(set(accepted_ids))
            and set(public_ids) == set(accepted_ids)
        )

    def _invalid_success_fallback(
        self,
        response: SymptomAnalysisResult,
    ) -> tuple[SymptomAnalysisResult, ResponseRoutingDisposition]:
        safety = response.safety_assessment
        if safety.risk_level != RiskLevel.DANGER:
            safety = safety.model_copy(
                update={
                    "risk_level": RiskLevel.CAUTION,
                    "priority": SafetyPriority.CONSULTATION_RECOMMENDED,
                    "requires_consultation": True,
                    "safety_reason": (
                        "자동 안내 Routing 조건을 충족하지 못해 상담 연결이 필요합니다."
                    ),
                }
            )
            guidance = self._blocking_guidance()
        else:
            safety = safety.model_copy(update={"requires_consultation": True})
            guidance = response.usage_guidance

        fallback = response.model_copy(
            update={
                "status": AiExecutionStatus.FALLBACK,
                "fallback_reason_code": FallbackReasonCode.UNSPECIFIED_FALLBACK,
                "failure_stage": AiStage.VALIDATING,
                "safety_assessment": safety,
                "usage_guidance": guidance,
                "evidence_references": [],
            }
        )
        return fallback, ResponseRoutingDisposition.FAIL_CLOSED_CONSULTATION

    def _normalize_existing_fallback(
        self,
        response: SymptomAnalysisResult,
    ) -> SymptomAnalysisResult:
        safety = response.safety_assessment
        guidance = response.usage_guidance
        if not safety.requires_consultation:
            safety = safety.model_copy(update={"requires_consultation": True})
        if (
            safety.risk_level != RiskLevel.DANGER
            and guidance.guidance_status
            != UsageGuidanceStatus.PENDING_CONSULTATION
        ):
            guidance = self._blocking_guidance()
        return response.model_copy(
            update={
                "failure_stage": response.failure_stage or AiStage.VALIDATING,
                "safety_assessment": safety,
                "usage_guidance": guidance,
            }
        )

    @staticmethod
    def _blocking_guidance() -> UsageGuidance:
        return UsageGuidance(
            guidance_status=UsageGuidanceStatus.PENDING_CONSULTATION,
            message="자동 안내를 확정하지 못해 전문 상담 연결이 필요합니다.",
            restricted_functions=["상담 전 자가조치 안내"],
            next_actions=["전문 상담 연결을 요청해 주세요."],
        )
