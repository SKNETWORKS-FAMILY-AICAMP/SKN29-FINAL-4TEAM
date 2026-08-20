"""Verify WaterBridge Reliability spans through the real OTel SDK.

This is a LOCAL verification command, not production telemetry bootstrap.

Run from repository root:
    python ai/scripts/verify_reliability_otel_export.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class CollectingSpanExporter(SpanExporter):
    """Collect exported ReadableSpan objects for deterministic assertions."""

    def __init__(self) -> None:
        self.spans = []

    def export(self, spans):
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        del timeout_millis
        return True


def _configure_provider() -> tuple[TracerProvider, CollectingSpanExporter]:
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "waterbridge-ai",
                "service.version": "1.0.0",
                "deployment.environment.name": "local-verification",
            }
        )
    )
    collector = CollectingSpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(collector))
    provider.add_span_processor(
        SimpleSpanProcessor(ConsoleSpanExporter(out=sys.stdout))
    )
    trace.set_tracer_provider(provider)
    return provider, collector


# Configure SDK before importing WaterBridge modules that acquire tracers.
_PROVIDER, _COLLECTOR = _configure_provider()

from ai.app.orchestration.harness import (  # noqa: E402
    HarnessDecision,
    HarnessRunner,
    ProductContext,
    ProductFamily,
)
from ai.app.orchestration.hitl import (  # noqa: E402
    HumanReviewDecision,
    HumanReviewResume,
    HumanReviewStatus,
)
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk  # noqa: E402
from ai.app.schemas import UsageGuidance, UsageGuidanceStatus  # noqa: E402


PRIVATE_REVIEW_NOTE = (
    "OTEL_PRIVATE_SENTINEL 010-1234-5678 private@example.com"
)


def _guidance() -> UsageGuidance:
    return UsageGuidance(
        guidance_status=UsageGuidanceStatus.NORMAL,
        message="로컬 OTEL 검증용 안내",
        next_actions=["상태 확인"],
    )


def _ctx():
    return SimpleNamespace(
        trace_context=SimpleNamespace(
            inquiry_id=UUID(
                "018f2f9b-7c30-7981-b541-1a987c88b201"
            ),
            correlation_id=UUID(
                "018f2f9b-7c30-7981-b541-1a987c88e001"
            ),
            ai_request_id="ai-req-otel-export-001",
            state_version=4,
        ),
        model_code="WPU-JAC104",
        structured_symptom=None,
        previous_answers=[],
        evidence_references=[],
        safety_assessment=None,
        usage_guidance=_guidance(),
        missing_fields=[],
    )


def _product() -> ProductContext:
    return ProductContext(
        model_code="WPU-JAC104",
        product_family=ProductFamily.DIRECT_WATER_PURIFIER,
        supported_functions={"cold_water", "hot_water"},
    )


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="jac104-otel-export-1",
        document_title="WPU-JAC104 공식 매뉴얼",
        manual_model="WPU-JAC104",
        model_code="WPU-JAC104",
        content="OTEL_PRIVATE_EVIDENCE_BODY",
        similarity_score=0.95,
    )


def _run_timeout_handoff(runner: HarnessRunner) -> None:
    result = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[],
        safety_assessment=None,
        guidance=None,
        timed_out=True,
    )
    assert result.harness.decision == HarnessDecision.ESCALATE
    assert result.handoff is not None


def _run_hitl(runner: HarnessRunner) -> None:
    initial = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=None,
        guidance=_guidance(),
        required_functions={"ice"},
    )
    assert initial.harness.decision == HarnessDecision.HUMAN_REVIEW
    assert initial.human_review is not None
    assert (
        initial.human_review.status
        == HumanReviewStatus.WAITING_FOR_REVIEW
    )

    resolved = runner.resume_human_review(
        ctx=_ctx(),
        product=_product(),
        interrupted=initial.human_review,
        response=HumanReviewResume(
            decision=HumanReviewDecision.APPROVE,
            state_version=4,
            reviewer_note=PRIVATE_REVIEW_NOTE,
        ),
    )
    assert resolved.guidance is not None
    assert resolved.handoff is None


def _assert_exported_spans() -> list[str]:
    _PROVIDER.force_flush()
    names = [span.name for span in _COLLECTOR.spans]
    required = {
        "waterbridge.harness.runtime",
        "waterbridge.harness.verify",
        "waterbridge.harness.resume_review",
        "waterbridge.hitl.start",
        "waterbridge.hitl.resume",
        "waterbridge.handoff.create",
    }
    missing = sorted(required.difference(names))
    if missing:
        raise AssertionError(
            f"Required exported spans missing: {missing}; got={names}"
        )

    serialized_attributes = repr(
        [dict(span.attributes or {}) for span in _COLLECTOR.spans]
    )
    for forbidden in (
        "OTEL_PRIVATE_SENTINEL",
        "010-1234-5678",
        "private@example.com",
        "OTEL_PRIVATE_EVIDENCE_BODY",
        "raw_symptom",
        "system_prompt",
    ):
        if forbidden in serialized_attributes:
            raise AssertionError(
                f"Forbidden value leaked into span attributes: {forbidden}"
            )

    resources = [
        dict(span.resource.attributes)
        for span in _COLLECTOR.spans
    ]
    if not all(
        item.get("service.name") == "waterbridge-ai"
        for item in resources
    ):
        raise AssertionError("service.name resource attribute is missing")

    return names


def main() -> int:
    runner = HarnessRunner()
    _run_timeout_handoff(runner)
    _run_hitl(runner)
    names = _assert_exported_spans()

    print(
        "OTEL_EXPORT_VERIFIED "
        f"span_count={len(names)} "
        "pii_safe=true "
        "service_name=waterbridge-ai"
    )
    print(
        "OTEL_REQUIRED_SPANS "
        + ",".join(sorted(set(names)))
    )
    _PROVIDER.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
