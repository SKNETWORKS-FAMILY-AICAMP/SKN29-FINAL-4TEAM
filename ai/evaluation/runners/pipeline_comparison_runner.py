"""Single RAG와 후보 Multi-Agent를 같은 입력에서 비교하는 실행기."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _ComparisonModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PipelineRuntimeMeasurement(_ComparisonModel):
    """원문·Prompt·Evidence 본문을 포함하지 않는 Runtime 측정치."""

    runtime_name: str
    latency_ms: float = Field(ge=0)
    status: str
    failure_stage: str | None
    retry_count: int = Field(ge=0, le=1)
    risk_level: str
    guidance_status: str
    evidence_count: int = Field(ge=0)
    followup_question_count: int = Field(ge=0)
    tokens_used: int | None = Field(default=None, ge=0)
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PipelineComparisonReport(_ComparisonModel):
    """동일 입력의 두 Runtime 비교 결과."""

    single_rag: PipelineRuntimeMeasurement
    multi_agent: PipelineRuntimeMeasurement
    public_contract_equal: bool
    safety_result_equal: bool
    evidence_identity_equal: bool
    followup_question_count_equal: bool
    latency_delta_ms: float
    token_delta: int | None


class PipelineComparisonRunner:
    """실제 Provider 호출 여부를 숨기지 않고 두 Runtime을 각각 한 번 실행한다."""

    def compare(
        self,
        *,
        single_router,
        multi_agent_router,
        request_kwargs: dict[str, Any],
    ) -> PipelineComparisonReport:
        single_result, single_public, single_measurement = self._measure(
            single_router,
            "single_rag",
            request_kwargs,
        )
        multi_result, multi_public, multi_measurement = self._measure(
            multi_agent_router,
            "multi_agent",
            request_kwargs,
        )

        single_tokens = single_result.context.model_metadata.tokens_used
        multi_tokens = multi_result.context.model_metadata.tokens_used
        token_delta = (
            multi_tokens - single_tokens
            if single_tokens is not None and multi_tokens is not None
            else None
        )
        return PipelineComparisonReport(
            single_rag=single_measurement,
            multi_agent=multi_measurement,
            public_contract_equal=single_public == multi_public,
            safety_result_equal=(
                single_public["safety_assessment"]
                == multi_public["safety_assessment"]
            ),
            evidence_identity_equal=(
                single_measurement.evidence_identity_sha256
                == multi_measurement.evidence_identity_sha256
            ),
            followup_question_count_equal=(
                single_measurement.followup_question_count
                == multi_measurement.followup_question_count
            ),
            latency_delta_ms=round(
                multi_measurement.latency_ms - single_measurement.latency_ms,
                3,
            ),
            token_delta=token_delta,
        )

    @staticmethod
    def _measure(router, runtime_name: str, request_kwargs: dict[str, Any]):
        started_at = time.perf_counter()
        result = router.run_pipeline(
            **request_kwargs,
            runtime_name=runtime_name,
        )
        latency_ms = round((time.perf_counter() - started_at) * 1000.0, 3)
        public_result = result.to_analysis_result()
        public_payload = public_result.model_dump(mode="json")
        evidence_ids = sorted(
            reference.chunk_id for reference in public_result.evidence_references
        )
        output_bytes = json.dumps(
            public_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        evidence_bytes = json.dumps(
            evidence_ids,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        measurement = PipelineRuntimeMeasurement(
            runtime_name=runtime_name,
            latency_ms=latency_ms,
            status=public_result.status.value,
            failure_stage=(
                public_result.failure_stage.value
                if public_result.failure_stage is not None
                else None
            ),
            retry_count=public_result.retry_count,
            risk_level=public_result.safety_assessment.risk_level.value,
            guidance_status=public_result.usage_guidance.guidance_status.value,
            evidence_count=len(public_result.evidence_references),
            followup_question_count=len(public_result.followup_questions),
            tokens_used=result.context.model_metadata.tokens_used,
            output_sha256=hashlib.sha256(output_bytes).hexdigest(),
            evidence_identity_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
        )
        return result, public_payload, measurement
