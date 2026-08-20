"""Run a deterministic FastAPI AI server for live Backend handoff E2E.

This is a test-only process entrypoint. It exercises the real FastAPI route,
real Harness ReliabilityRuntime, real ConsultationHandoffResult creation, and
real BackgroundTask delivery while keeping RAG/LLM/provider availability out
of the service-bridge gate.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from ai.app.common.timeout import CancellationToken  # noqa: E402
from ai.app.interfaces.http.routes import analysis_routes  # noqa: E402
from ai.app.orchestration.harness.product_match import (  # noqa: E402
    ProductContext,
    ProductFamily,
)
from ai.app.orchestration.harness.runtime import ReliabilityRuntime  # noqa: E402
from ai.app.orchestration.pipeline_context import PipelineContext  # noqa: E402
from ai.app.orchestration.pipeline_result import PipelineResult  # noqa: E402
from ai.app.retrieval import RetrievalOutcome  # noqa: E402
from ai.app.schemas import (  # noqa: E402
    RiskLevel,
    SafetyAssessment,
    SafetyPriority,
    StructuredSymptom,
    TraceContext,
    UsageGuidance,
    UsageGuidanceStatus,
)


TARGET_MODEL = "WPUJAC104DWH"


class DeterministicNoEvidenceRouter:
    """Return a real Harness NO_EVIDENCE handoff without external providers."""

    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs
        self.reliability_runtime = ReliabilityRuntime()

    def run_pipeline(
        self,
        inquiry_id,
        correlation_id,
        ai_request_id,
        state_version,
        raw_symptom,
        model_code=TARGET_MODEL,
        selected_symptoms=None,
        previous_answers=None,
        cancellation_token=None,
        runtime_name=None,
    ) -> PipelineResult:
        del selected_symptoms, runtime_name

        if model_code != TARGET_MODEL:
            raise RuntimeError("live handoff E2E supports WPUJAC104DWH only")

        ctx = PipelineContext(
            trace_context=TraceContext(
                inquiry_id=inquiry_id,
                correlation_id=correlation_id,
                ai_request_id=ai_request_id,
                state_version=state_version,
            ),
            raw_symptom=raw_symptom,
            model_code=model_code,
            previous_answers=previous_answers or [],
            structured_symptom=StructuredSymptom(
                symptom_type="출수량 저하",
                occurrence_time="오늘",
                target_water_type="정수",
                occurrence_condition="출수 시 유량 감소",
                accompanying_symptoms=[],
                actions_taken=[],
            ),
            safety_assessment=SafetyAssessment(
                risk_level=RiskLevel.CAUTION,
                priority=SafetyPriority.CONSULTATION_RECOMMENDED,
                requires_consultation=True,
                matched_safety_rule_ids=[],
                detected_risks=[],
                safety_reason="공식 근거가 없어 상담 확인이 필요합니다.",
            ),
            evidence_references=[],
            retrieval_outcome=RetrievalOutcome.NO_MATCH,
            usage_guidance=UsageGuidance(
                guidance_status=UsageGuidanceStatus.PENDING_CONSULTATION,
                message=(
                    "확인 가능한 공식 근거가 부족하여 "
                    "상담 연결이 필요합니다."
                ),
                restricted_functions=[],
                next_actions=["상담 연결을 요청해 주세요."],
            ),
            awaiting_customer_input=False,
        )

        product = ProductContext(
            model_code=TARGET_MODEL,
            product_family=ProductFamily.DIRECT_WATER_PURIFIER,
            runtime_approved=True,
            supported_functions={"cold_water", "hot_water", "purified_water"},
        )
        reliability = self.reliability_runtime.run(
            ctx=ctx,
            product=product,
            evidence_capture=None,
            search_service=None,
            llm_client=None,
            cancellation_token=cancellation_token or CancellationToken(),
        )

        handoff = reliability.harness_runtime.handoff
        if handoff is None:
            raise RuntimeError(
                "deterministic E2E router did not produce a handoff"
            )

        return PipelineResult(
            success=False,
            context=ctx,
            runtime_name="single_rag",
            reliability_runtime=reliability,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    # This script owns only the test subprocess behavior.
    os.environ.pop("AI_VECTOR_DSN", None)
    os.environ["AI_OTEL_ENABLED"] = "false"
    os.environ["AI_PIPELINE_RUNTIME"] = "single_rag"

    analysis_routes.PipelineRouter = DeterministicNoEvidenceRouter

    from ai.app.bootstrap import create_app

    uvicorn.run(
        create_app(),
        host=args.host,
        port=args.port,
        log_level="warning",
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
