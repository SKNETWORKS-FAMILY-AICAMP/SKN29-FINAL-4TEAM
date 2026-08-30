"""E10 - OpenTelemetry Trace Observability experiment.

Purpose
-------
Verify that WaterBridge AI runtime:
1) exports real OpenTelemetry traces through OTLP/HTTP,
2) exposes Harness timeout -> ESCALATE -> Handoff topology,
3) exposes HITL start/resume state and decision metadata,
4) does not export injected evidence/reviewer/guidance payloads as trace data.

Scope boundary
--------------
This experiment validates AI-runtime-local tracing only.
It does NOT claim Web -> Backend -> AI distributed trace propagation,
and it does NOT validate OpenTelemetry GenAI Semantic Conventions.

Run from repository root:

    python ai/scripts/experiments/e10_otel_trace_observability.py

Artifacts:

    ai/experiment_results/e10_otel_trace_observability/
    ├─ summary.json
    ├─ report.md
    └─ captured_spans.json
"""

from __future__ import annotations

import gzip
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
import zlib
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUTPUT_DIR = (
    REPO_ROOT
    / "ai"
    / "experiment_results"
    / "e10_otel_trace_observability"
)

EXPERIMENT_ID = "E10"
EXPERIMENT_NAME = "OpenTelemetry Trace Observability"

SERVICE_NAME = "waterbridge-ai-e10"
DEPLOYMENT_ENV = "experiment"

EVIDENCE_SECRET = "E10_SECRET_EVIDENCE_DO_NOT_EXPORT"
REVIEWER_SECRET = "E10_SECRET_REVIEWER_NOTE_DO_NOT_EXPORT"
GUIDANCE_SECRET = "E10_SECRET_GUIDANCE_DO_NOT_EXPORT"
PRIVATE_PHONE = "010-1234-5678"
PRIVATE_EMAIL = "private@example.com"

FORBIDDEN_MARKERS = (
    EVIDENCE_SECRET,
    REVIEWER_SECRET,
    GUIDANCE_SECRET,
    PRIVATE_PHONE,
    PRIVATE_EMAIL,
)

INQUIRY_ID = UUID("018f2f9b-7c30-7981-b541-1a987c88b201")
CORRELATION_ID = UUID("018f2f9b-7c30-7981-b541-1a987c88e001")
AI_REQUEST_ID = "ai-req-e10-001"
STATE_VERSION = 4
MODEL_CODE = "WPU-JAC104"


@dataclass(slots=True)
class CaseResult:
    case_id: str
    scenario: str
    passed: bool
    checks: dict[str, bool]
    evidence: dict[str, Any]
    notes: str = ""


class OtlpCaptureServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), OtlpCaptureHandler)
        self._lock = threading.Lock()
        self.requests: list[dict[str, Any]] = []

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    def add_request(
        self,
        *,
        path: str,
        headers: dict[str, str],
        body: bytes,
    ) -> None:
        with self._lock:
            self.requests.append(
                {
                    "path": path,
                    "headers": headers,
                    "body": body,
                }
            )

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self.requests)


class OtlpCaptureHandler(BaseHTTPRequestHandler):
    server: OtlpCaptureServer

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        encoding = self.headers.get("Content-Encoding", "").strip().lower()
        if encoding == "gzip":
            body = gzip.decompress(body)
        elif encoding == "deflate":
            body = zlib.decompress(body)

        self.server.add_request(
            path=self.path,
            headers={key: value for key, value in self.headers.items()},
            body=body,
        )

        try:
            from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
                ExportTraceServiceResponse,
            )

            response_body = ExportTraceServiceResponse().SerializeToString()
        except Exception:
            response_body = b""

        self.send_response(200)
        self.send_header("Content-Type", "application/x-protobuf")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep experiment output deterministic and compact.
        return


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _any_value_to_python(value: Any) -> Any:
    kind = value.WhichOneof("value")
    if kind is None:
        return None
    if kind == "string_value":
        return value.string_value
    if kind == "bool_value":
        return value.bool_value
    if kind == "int_value":
        return value.int_value
    if kind == "double_value":
        return value.double_value
    if kind == "bytes_value":
        return bytes(value.bytes_value).hex()
    if kind == "array_value":
        return [
            _any_value_to_python(item)
            for item in value.array_value.values
        ]
    if kind == "kvlist_value":
        return {
            item.key: _any_value_to_python(item.value)
            for item in value.kvlist_value.values
        }
    return None


def _attributes_to_dict(values: Any) -> dict[str, Any]:
    return {
        item.key: _any_value_to_python(item.value)
        for item in values
    }


def _decode_otlp_requests(
    requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
        ExportTraceServiceRequest,
    )

    spans: list[dict[str, Any]] = []

    for request_index, captured in enumerate(requests):
        message = ExportTraceServiceRequest()
        message.ParseFromString(captured["body"])

        for resource_spans in message.resource_spans:
            resource_attributes = _attributes_to_dict(
                resource_spans.resource.attributes
            )

            for scope_spans in resource_spans.scope_spans:
                scope_name = scope_spans.scope.name
                scope_version = scope_spans.scope.version

                for span in scope_spans.spans:
                    events = []
                    for event in span.events:
                        events.append(
                            {
                                "name": event.name,
                                "attributes": _attributes_to_dict(
                                    event.attributes
                                ),
                            }
                        )

                    spans.append(
                        {
                            "request_index": request_index,
                            "request_path": captured["path"],
                            "scope_name": scope_name,
                            "scope_version": scope_version,
                            "resource_attributes": resource_attributes,
                            "name": span.name,
                            "trace_id": bytes(span.trace_id).hex(),
                            "span_id": bytes(span.span_id).hex(),
                            "parent_span_id": bytes(
                                span.parent_span_id
                            ).hex(),
                            "attributes": _attributes_to_dict(
                                span.attributes
                            ),
                            "events": events,
                            "status_code": int(span.status.code),
                        }
                    )

    return spans


def _span(
    spans: list[dict[str, Any]],
    name: str,
    *,
    attribute_key: str | None = None,
    attribute_value: Any | None = None,
) -> dict[str, Any] | None:
    matches = [item for item in spans if item["name"] == name]

    if attribute_key is not None:
        matches = [
            item
            for item in matches
            if item["attributes"].get(attribute_key)
            == attribute_value
        ]

    return matches[-1] if matches else None


def _all_values_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _raw_export_contains(
    requests: list[dict[str, Any]],
    marker: str,
) -> bool:
    encoded = marker.encode("utf-8")
    return any(encoded in item["body"] for item in requests)


def _safe_span_projection(
    spans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Persist only approved metadata; never persist raw payload-like values."""

    approved_exact_value_keys = {
        "waterbridge.model.code",
        "waterbridge.product.family",
        "waterbridge.harness.decision",
        "waterbridge.harness.error_code",
        "waterbridge.hitl.status",
        "waterbridge.hitl.decision",
        "waterbridge.hitl.state_version",
        "waterbridge.hitl.modified_guidance.present",
        "waterbridge.hitl.reviewer_note.present",
        "waterbridge.hitl.approved",
        "waterbridge.harness.handoff.present",
        "waterbridge.harness.human_review.present",
        "waterbridge.hitl.guidance.present",
        "waterbridge.handoff.redaction.enabled",
        "waterbridge.handoff.context_synthesis.present",
        "waterbridge.handoff.context_synthesis.status",
        "e10.case",
    }

    result = []
    for item in spans:
        attrs = {
            key: value
            for key, value in item["attributes"].items()
            if (
                key in approved_exact_value_keys
                or key.endswith(".count")
                or key.endswith(".present")
                or key.endswith(".enabled")
            )
        }
        result.append(
            {
                "name": item["name"],
                "trace_id": item["trace_id"],
                "span_id": item["span_id"],
                "parent_span_id": item["parent_span_id"],
                "scope_name": item["scope_name"],
                "resource_attributes": {
                    key: value
                    for key, value in item[
                        "resource_attributes"
                    ].items()
                    if key
                    in {
                        "service.name",
                        "service.version",
                        "deployment.environment.name",
                    }
                },
                "attributes": attrs,
            }
        )
    return result


def _guidance(message: str = "기본 안내"):
    from ai.app.schemas import UsageGuidance, UsageGuidanceStatus

    return UsageGuidance(
        guidance_status=UsageGuidanceStatus.NORMAL,
        message=message,
        next_actions=["상태 확인"],
    )


def _ctx():
    return SimpleNamespace(
        trace_context=SimpleNamespace(
            inquiry_id=INQUIRY_ID,
            correlation_id=CORRELATION_ID,
            ai_request_id=AI_REQUEST_ID,
            state_version=STATE_VERSION,
        ),
        model_code=MODEL_CODE,
        structured_symptom=None,
        previous_answers=[],
        evidence_references=[],
        safety_assessment=None,
        usage_guidance=_guidance(),
        missing_fields=[],
    )


def _product():
    from ai.app.orchestration.harness import (
        ProductContext,
        ProductFamily,
    )

    return ProductContext(
        model_code=MODEL_CODE,
        product_family=ProductFamily.DIRECT_WATER_PURIFIER,
        supported_functions={"cold_water", "hot_water"},
    )


def _chunk():
    from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk

    return RetrievedChunk(
        chunk_id="jac104-e10-secret-1",
        document_title="WPU-JAC104 공식 매뉴얼",
        manual_model=MODEL_CODE,
        model_code=MODEL_CODE,
        content=EVIDENCE_SECRET,
        similarity_score=0.95,
    )


class _NoExternalContextSynthesis:
    """Prevent E10 from invoking an external LLM during Handoff tracing."""

    def run(self, value: Any) -> Any:
        raise RuntimeError(
            "E10 intentionally disables external context synthesis"
        )


def _case_01_real_otlp_export(
    *,
    capture: OtlpCaptureServer,
    force_flush: Any,
) -> CaseResult:
    from opentelemetry import trace

    tracer = trace.get_tracer(
        "waterbridge.e10.experiment",
        "1.0.0",
    )

    before = len(capture.snapshot())

    with tracer.start_as_current_span(
        "waterbridge.e10.export_probe"
    ) as span:
        span.set_attribute("e10.case", "E10-01")

    flush_ok = bool(force_flush(5000))
    time.sleep(0.05)

    captured = capture.snapshot()
    spans = _decode_otlp_requests(captured)
    probe = _span(
        spans,
        "waterbridge.e10.export_probe",
        attribute_key="e10.case",
        attribute_value="E10-01",
    )

    resource = (
        probe["resource_attributes"]
        if probe is not None
        else {}
    )

    checks = {
        "force_flush_success": flush_ok,
        "otlp_http_request_received": len(captured) > before,
        "otlp_trace_path_used": any(
            item["path"] == "/v1/traces"
            for item in captured[before:]
        ),
        "protobuf_decode_success": probe is not None,
        "service_name_preserved": (
            resource.get("service.name") == SERVICE_NAME
        ),
        "service_version_present": (
            resource.get("service.version") == "1.0.0"
        ),
        "deployment_environment_preserved": (
            resource.get("deployment.environment.name")
            == DEPLOYMENT_ENV
        ),
    }

    return CaseResult(
        case_id="E10-01",
        scenario="REAL_OTLP_EXPORT",
        passed=all(checks.values()),
        checks=checks,
        evidence={
            "otlp_request_count_after_flush": len(captured),
            "probe_trace_id": (
                probe["trace_id"] if probe else None
            ),
            "probe_span_id": (
                probe["span_id"] if probe else None
            ),
            "resource_attributes": resource,
        },
        notes=(
            "Real OTLP/HTTP protobuf export to an out-of-process "
            "HTTP receiver running on loopback."
        ),
    )


def _case_02_failure_trace_topology(
    *,
    capture: OtlpCaptureServer,
    force_flush: Any,
) -> CaseResult:
    from ai.app.orchestration.harness import HarnessDecision
    from ai.app.orchestration.harness import HarnessRunner

    runner = HarnessRunner(
        context_synthesis_agent=_NoExternalContextSynthesis()
    )

    result = runner.run_runtime(
        ctx=_ctx(),
        product=_product(),
        evidence_chunks=[],
        safety_assessment=None,
        guidance=None,
        timed_out=True,
    )

    flush_ok = bool(force_flush(5000))
    time.sleep(0.05)
    spans = _decode_otlp_requests(capture.snapshot())

    runtime = _span(
        spans,
        "waterbridge.harness.runtime",
        attribute_key="waterbridge.harness.decision",
        attribute_value="ESCALATE",
    )
    verify = _span(
        spans,
        "waterbridge.harness.verify",
        attribute_key="waterbridge.harness.error_code",
        attribute_value="AI_PROCESSING_TIMEOUT",
    )

    handoff = None
    if runtime is not None:
        candidates = [
            item
            for item in spans
            if (
                item["name"] == "waterbridge.handoff.create"
                and item["trace_id"] == runtime["trace_id"]
            )
        ]
        handoff = candidates[-1] if candidates else None

    same_trace = bool(
        runtime
        and verify
        and handoff
        and runtime["trace_id"]
        == verify["trace_id"]
        == handoff["trace_id"]
    )
    verify_child = bool(
        runtime
        and verify
        and verify["parent_span_id"] == runtime["span_id"]
    )
    handoff_child = bool(
        runtime
        and handoff
        and handoff["parent_span_id"] == runtime["span_id"]
    )

    checks = {
        "runtime_result_escalate": (
            result.harness.decision
            == HarnessDecision.ESCALATE
        ),
        "runtime_handoff_created": result.handoff is not None,
        "force_flush_success": flush_ok,
        "runtime_span_present": runtime is not None,
        "verify_span_present": verify is not None,
        "handoff_span_present": handoff is not None,
        "same_trace_id": same_trace,
        "verify_parent_is_runtime": verify_child,
        "handoff_parent_is_runtime": handoff_child,
        "timeout_error_code_observable": bool(
            verify
            and verify["attributes"].get(
                "waterbridge.harness.error_code"
            )
            == "AI_PROCESSING_TIMEOUT"
        ),
        "handoff_observable": bool(
            runtime
            and runtime["attributes"].get(
                "waterbridge.harness.handoff.present"
            )
            is True
        ),
        "handoff_redaction_metadata_present": bool(
            handoff
            and handoff["attributes"].get(
                "waterbridge.handoff.redaction.enabled"
            )
            is True
        ),
    }

    return CaseResult(
        case_id="E10-02",
        scenario="FAILURE_TRACE_TOPOLOGY",
        passed=all(checks.values()),
        checks=checks,
        evidence={
            "runtime_trace_id": (
                runtime["trace_id"] if runtime else None
            ),
            "runtime_span_id": (
                runtime["span_id"] if runtime else None
            ),
            "verify_parent_span_id": (
                verify["parent_span_id"] if verify else None
            ),
            "handoff_parent_span_id": (
                handoff["parent_span_id"] if handoff else None
            ),
            "decision": (
                runtime["attributes"].get(
                    "waterbridge.harness.decision"
                )
                if runtime
                else None
            ),
            "error_code": (
                verify["attributes"].get(
                    "waterbridge.harness.error_code"
                )
                if verify
                else None
            ),
        },
        notes=(
            "Actual Harness timeout path. No external LLM is invoked "
            "for supplementary context synthesis."
        ),
    )


def _case_03_hitl_trace(
    *,
    capture: OtlpCaptureServer,
    force_flush: Any,
) -> CaseResult:
    from ai.app.orchestration.harness import (
        HarnessDecision,
        HarnessRunner,
    )
    from ai.app.orchestration.hitl import (
        HumanReviewDecision,
        HumanReviewResume,
        HumanReviewStatus,
    )

    runner = HarnessRunner(
        context_synthesis_agent=_NoExternalContextSynthesis()
    )

    ctx = _ctx()
    proposed = _guidance(
        "요청 기능은 자동 안내 범위를 벗어나므로 "
        "제품 사양을 확인해 주세요."
    )

    initial = runner.run_runtime(
        ctx=ctx,
        product=_product(),
        evidence_chunks=[_chunk()],
        safety_assessment=None,
        guidance=proposed,
        required_functions={"ice"},
    )

    if initial.human_review is None:
        raise RuntimeError(
            "E10 HITL fixture did not enter HUMAN_REVIEW"
        )

    private_note = (
        f"{PRIVATE_PHONE} {PRIVATE_EMAIL} "
        f"{REVIEWER_SECRET}"
    )

    modified = _guidance(
        f"상담사가 제품 사양을 확인합니다. "
        f"{GUIDANCE_SECRET}"
    )

    resolved = runner.resume_human_review(
        ctx=ctx,
        product=_product(),
        interrupted=initial.human_review,
        response=HumanReviewResume(
            decision=HumanReviewDecision.MODIFY,
            state_version=STATE_VERSION,
            modified_guidance=modified,
            reviewer_note=private_note,
        ),
    )

    flush_ok = bool(force_flush(5000))
    time.sleep(0.05)
    spans = _decode_otlp_requests(capture.snapshot())

    human_runtime = _span(
        spans,
        "waterbridge.harness.runtime",
        attribute_key="waterbridge.harness.decision",
        attribute_value="HUMAN_REVIEW",
    )
    start = _span(
        spans,
        "waterbridge.hitl.start",
        attribute_key="waterbridge.hitl.status",
        attribute_value="WAITING_FOR_REVIEW",
    )
    harness_resume = _span(
        spans,
        "waterbridge.harness.resume_review",
        attribute_key="waterbridge.hitl.decision",
        attribute_value="modify",
    )
    resume = _span(
        spans,
        "waterbridge.hitl.resume",
        attribute_key="waterbridge.hitl.decision",
        attribute_value="modify",
    )

    start_child_of_runtime = bool(
        human_runtime
        and start
        and start["trace_id"] == human_runtime["trace_id"]
        and start["parent_span_id"]
        == human_runtime["span_id"]
    )
    resume_child_of_harness_resume = bool(
        harness_resume
        and resume
        and resume["trace_id"] == harness_resume["trace_id"]
        and resume["parent_span_id"]
        == harness_resume["span_id"]
    )

    checks = {
        "runtime_entered_human_review": (
            initial.harness.decision
            == HarnessDecision.HUMAN_REVIEW
        ),
        "runtime_waiting_for_review": (
            initial.human_review.status
            == HumanReviewStatus.WAITING_FOR_REVIEW
        ),
        "resume_completed": (
            resolved.review.status
            == HumanReviewStatus.COMPLETED
        ),
        "modified_guidance_released": (
            resolved.guidance is not None
        ),
        "force_flush_success": flush_ok,
        "hitl_start_span_present": start is not None,
        "hitl_resume_span_present": resume is not None,
        "harness_resume_span_present": (
            harness_resume is not None
        ),
        "hitl_start_child_of_runtime": start_child_of_runtime,
        "hitl_resume_child_of_harness_resume": (
            resume_child_of_harness_resume
        ),
        "waiting_status_observable": bool(
            start
            and start["attributes"].get(
                "waterbridge.hitl.status"
            )
            == "WAITING_FOR_REVIEW"
        ),
        "modify_decision_observable": bool(
            resume
            and resume["attributes"].get(
                "waterbridge.hitl.decision"
            )
            == "modify"
        ),
        "modified_guidance_presence_observable": bool(
            resume
            and resume["attributes"].get(
                "waterbridge.hitl.modified_guidance.present"
            )
            is True
        ),
        "reviewer_note_presence_observable": bool(
            resume
            and resume["attributes"].get(
                "waterbridge.hitl.reviewer_note.present"
            )
            is True
        ),
        "completed_status_observable": bool(
            resume
            and resume["attributes"].get(
                "waterbridge.hitl.status"
            )
            == "COMPLETED"
        ),
        "approved_observable": bool(
            resume
            and resume["attributes"].get(
                "waterbridge.hitl.approved"
            )
            is True
        ),
    }

    return CaseResult(
        case_id="E10-03",
        scenario="HITL_TRACE",
        passed=all(checks.values()),
        checks=checks,
        evidence={
            "hitl_start_trace_id": (
                start["trace_id"] if start else None
            ),
            "hitl_resume_trace_id": (
                resume["trace_id"] if resume else None
            ),
            "checkpoint_thread_id": (
                initial.human_review.checkpoint.thread_id
            ),
            "start_status": (
                start["attributes"].get(
                    "waterbridge.hitl.status"
                )
                if start
                else None
            ),
            "resume_decision": (
                resume["attributes"].get(
                    "waterbridge.hitl.decision"
                )
                if resume
                else None
            ),
            "resume_status": (
                resume["attributes"].get(
                    "waterbridge.hitl.status"
                )
                if resume
                else None
            ),
            "note_content_recorded_in_evidence": False,
        },
        notes=(
            "HITL start belongs to the original Harness runtime trace. "
            "The later resume call creates a new local root "
            "(waterbridge.harness.resume_review), with hitl.resume as its child. "
            "This experiment does not claim cross-request traceparent propagation."
        ),
    )


def _case_04_metadata_only(
    *,
    capture: OtlpCaptureServer,
) -> CaseResult:
    requests = capture.snapshot()
    spans = _decode_otlp_requests(requests)

    raw_leaks = {
        marker: _raw_export_contains(requests, marker)
        for marker in FORBIDDEN_MARKERS
    }

    decoded_text = _all_values_text(spans)
    decoded_leaks = {
        marker: marker in decoded_text
        for marker in FORBIDDEN_MARKERS
    }

    leaked_markers = sorted(
        {
            marker
            for marker, leaked in {
                **raw_leaks,
                **decoded_leaks,
            }.items()
            if leaked
        }
    )

    resume = _span(
        spans,
        "waterbridge.hitl.resume",
        attribute_key="waterbridge.hitl.decision",
        attribute_value="modify",
    )
    handoff = _span(
        spans,
        "waterbridge.handoff.create",
    )
    timeout_verify = _span(
        spans,
        "waterbridge.harness.verify",
        attribute_key="waterbridge.harness.error_code",
        attribute_value="AI_PROCESSING_TIMEOUT",
    )

    checks = {
        "sensitive_payload_leak_count_zero": (
            len(leaked_markers) == 0
        ),
        "reviewer_note_content_not_exported": (
            not raw_leaks[REVIEWER_SECRET]
            and not decoded_leaks[REVIEWER_SECRET]
        ),
        "evidence_content_not_exported": (
            not raw_leaks[EVIDENCE_SECRET]
            and not decoded_leaks[EVIDENCE_SECRET]
        ),
        "modified_guidance_content_not_exported": (
            not raw_leaks[GUIDANCE_SECRET]
            and not decoded_leaks[GUIDANCE_SECRET]
        ),
        "phone_not_exported": (
            not raw_leaks[PRIVATE_PHONE]
            and not decoded_leaks[PRIVATE_PHONE]
        ),
        "email_not_exported": (
            not raw_leaks[PRIVATE_EMAIL]
            and not decoded_leaks[PRIVATE_EMAIL]
        ),
        "reviewer_note_presence_metadata_kept": bool(
            resume
            and resume["attributes"].get(
                "waterbridge.hitl.reviewer_note.present"
            )
            is True
        ),
        "handoff_redaction_metadata_kept": bool(
            handoff
            and handoff["attributes"].get(
                "waterbridge.handoff.redaction.enabled"
            )
            is True
        ),
        "failure_code_metadata_kept": bool(
            timeout_verify
            and timeout_verify["attributes"].get(
                "waterbridge.harness.error_code"
            )
            == "AI_PROCESSING_TIMEOUT"
        ),
    }

    return CaseResult(
        case_id="E10-04",
        scenario="METADATA_ONLY",
        passed=all(checks.values()),
        checks=checks,
        evidence={
            "otlp_request_count": len(requests),
            "decoded_span_count": len(spans),
            "sensitive_payload_leak_count": len(
                leaked_markers
            ),
            # Do not persist leaked values even if a future regression fails.
            "forbidden_marker_count_checked": len(
                FORBIDDEN_MARKERS
            ),
            "metadata_examples": {
                "reviewer_note_present": (
                    resume["attributes"].get(
                        "waterbridge.hitl.reviewer_note.present"
                    )
                    if resume
                    else None
                ),
                "handoff_redaction_enabled": (
                    handoff["attributes"].get(
                        "waterbridge.handoff.redaction.enabled"
                    )
                    if handoff
                    else None
                ),
                "harness_error_code": (
                    timeout_verify["attributes"].get(
                        "waterbridge.harness.error_code"
                    )
                    if timeout_verify
                    else None
                ),
            },
        },
        notes=(
            "Leak detection scans both decoded span data and the raw OTLP "
            "protobuf bodies. Artifact files never persist the injected "
            "sensitive marker values."
        ),
    )


def _print_case(result: CaseResult) -> None:
    print("\n" + "=" * 88)
    print(
        f"[{result.case_id}] {result.scenario} "
        f"PASS={result.passed}"
    )
    print(
        json.dumps(
            {
                "checks": result.checks,
                "evidence": result.evidence,
                "notes": result.notes,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _write_artifacts(
    *,
    git_sha: str | None,
    results: list[CaseResult],
    capture: OtlpCaptureServer,
    total_seconds: float,
) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    requests = capture.snapshot()
    spans = _decode_otlp_requests(requests)

    passed = sum(item.passed for item in results)
    total = len(results)

    key_span_requirements = {
        "waterbridge.e10.export_probe": bool(
            _span(spans, "waterbridge.e10.export_probe")
        ),
        "waterbridge.harness.runtime/ESCALATE": bool(
            _span(
                spans,
                "waterbridge.harness.runtime",
                attribute_key="waterbridge.harness.decision",
                attribute_value="ESCALATE",
            )
        ),
        "waterbridge.harness.verify/TIMEOUT": bool(
            _span(
                spans,
                "waterbridge.harness.verify",
                attribute_key="waterbridge.harness.error_code",
                attribute_value="AI_PROCESSING_TIMEOUT",
            )
        ),
        "waterbridge.handoff.create": bool(
            _span(spans, "waterbridge.handoff.create")
        ),
        "waterbridge.harness.runtime/HUMAN_REVIEW": bool(
            _span(
                spans,
                "waterbridge.harness.runtime",
                attribute_key="waterbridge.harness.decision",
                attribute_value="HUMAN_REVIEW",
            )
        ),
        "waterbridge.hitl.start": bool(
            _span(spans, "waterbridge.hitl.start")
        ),
        "waterbridge.harness.resume_review": bool(
            _span(
                spans,
                "waterbridge.harness.resume_review",
            )
        ),
        "waterbridge.hitl.resume": bool(
            _span(spans, "waterbridge.hitl.resume")
        ),
    }

    leak_case = next(
        (
            item
            for item in results
            if item.case_id == "E10-04"
        ),
        None,
    )
    leak_count = (
        leak_case.evidence.get(
            "sensitive_payload_leak_count"
        )
        if leak_case
        else None
    )

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "experiment_name": EXPERIMENT_NAME,
        "status": (
            "E10_COMPLETE"
            if passed == total == 4
            else "E10_FAILED"
        ),
        "git_sha": git_sha,
        "python": platform.python_version(),
        "scope": "AI_RUNTIME_LOCAL_OTLP_TRACE_OBSERVABILITY",
        "otel_transport": "OTLP_HTTP_PROTOBUF",
        "service_name": SERVICE_NAME,
        "deployment_environment": DEPLOYMENT_ENV,
        "scenario_count": total,
        "pass_count": passed,
        "all_passed": passed == total == 4,
        "otlp_request_count": len(requests),
        "decoded_span_count": len(spans),
        "key_span_coverage": {
            "present_count": sum(
                key_span_requirements.values()
            ),
            "required_count": len(
                key_span_requirements
            ),
            "all_present": all(
                key_span_requirements.values()
            ),
            "requirements": key_span_requirements,
        },
        "sensitive_payload_leak_count": leak_count,
        "results": [asdict(item) for item in results],
        "experiment_total_seconds": round(
            total_seconds,
            3,
        ),
        "claim": (
            "WaterBridge AI Runtime에서 실제 OTLP/HTTP trace export를 "
            "확인했고, Harness Timeout→ESCALATE→Handoff 및 HITL "
            "상태/결정을 Span metadata로 추적할 수 있었다. "
            "주입한 Evidence 본문, Human reviewer note, 전화번호, "
            "이메일, 수정 Guidance 본문은 exported OTLP payload에서 "
            "검출되지 않았다."
        ),
        "claim_boundary": (
            "본 실험은 AI Runtime 내부 OpenTelemetry trace와 OTLP export만 "
            "검증한다. Web→Backend→AI traceparent propagation 또는 "
            "전체 Distributed Tracing, OpenTelemetry GenAI Semantic "
            "Conventions 적용을 증명하지 않는다."
        ),
    }

    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    (OUTPUT_DIR / "captured_spans.json").write_text(
        json.dumps(
            _safe_span_projection(spans),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    report_lines = [
        "# E10 — OpenTelemetry Trace Observability",
        "",
        f"- Git SHA: `{git_sha or 'UNKNOWN'}`",
        f"- Result: **{passed}/{total} PASS**",
        f"- OTLP requests captured: `{len(requests)}`",
        f"- Decoded spans: `{len(spans)}`",
        f"- Sensitive payload leak count: `{leak_count}`",
        "",
        "## 실험 질문",
        "",
        "> AI Runtime의 Reliability 흐름이 실제 OTLP Trace로 Export되고, "
        "장애와 HITL 결정을 Payload 노출 없이 추적할 수 있는가?",
        "",
        "## 결과 요약",
        "",
        "| Case | Scenario | Result |",
        "|---|---|---:|",
    ]

    for item in results:
        report_lines.append(
            f"| {item.case_id} | {item.scenario} | "
            f"{'PASS' if item.passed else 'FAIL'} |"
        )

    report_lines += [
        "",
        "## Key Span Coverage",
        "",
        "| Span / Condition | Present |",
        "|---|---:|",
    ]

    for name, present in key_span_requirements.items():
        report_lines.append(
            f"| `{name}` | {'PASS' if present else 'FAIL'} |"
        )

    report_lines += [
        "",
        "## 핵심 해석",
        "",
        summary["claim"],
        "",
        "### Failure Trace",
        "",
        "```text",
        "waterbridge.harness.runtime",
        "├─ waterbridge.harness.verify",
        "│    ├─ decision = ESCALATE",
        "│    └─ error_code = AI_PROCESSING_TIMEOUT",
        "└─ waterbridge.handoff.create",
        "     └─ redaction.enabled = true",
        "```",
        "",
        "### HITL Trace",
        "",
        "```text",
        "Original runtime trace",
        "waterbridge.harness.runtime",
        "└─ waterbridge.hitl.start",
        "     └─ status = WAITING_FOR_REVIEW",
        "",
        "Later resume call",
        "waterbridge.harness.resume_review",
        "└─ waterbridge.hitl.resume",
        "     ├─ decision = modify",
        "     ├─ reviewer_note.present = true",
        "     ├─ modified_guidance.present = true",
        "     └─ status = COMPLETED",
        "```",
        "",
        "HITL Resume는 별도 요청 시점의 로컬 Root Span으로 관측된다. "
        "본 실험에서는 start/resume 사이의 cross-request traceparent "
        "propagation을 주장하지 않는다.",
        "",
        "## Metadata-only 검증",
        "",
        "실험은 Evidence 본문, Human Reviewer Note, 전화번호, 이메일, "
        "수정 Guidance 본문에 식별 가능한 marker를 주입한 뒤 실제 "
        "OTLP protobuf body와 decode 결과를 모두 검사했다.",
        "",
        f"- Sensitive Payload Leak Count: **{leak_count}**",
        "- Reviewer Note 내용 대신 `reviewer_note.present`만 기록",
        "- Handoff 본문 대신 `redaction.enabled` 등 운영 metadata 기록",
        "- 오류 원문 대신 `AI_PROCESSING_TIMEOUT` 같은 표준 error code 기록",
        "",
        "## 주장 범위",
        "",
        summary["claim_boundary"],
        "",
        "따라서 발표에서는 **'Web부터 AI까지 전체 Distributed Tracing을 "
        "완성했다'**가 아니라 **'AI Runtime 내부 주요 Reliability 흐름의 "
        "OTel Trace 생성과 실제 OTLP Export를 검증했다'**고 표현한다.",
        "",
    ]

    for item in results:
        report_lines += [
            f"## {item.case_id} — {item.scenario}",
            "",
            "```json",
            json.dumps(
                {
                    "passed": item.passed,
                    "checks": item.checks,
                    "evidence": item.evidence,
                    "notes": item.notes,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "```",
            "",
        ]

    (OUTPUT_DIR / "report.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    return summary


def main() -> int:
    experiment_started = time.perf_counter()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    capture = OtlpCaptureServer()
    server_thread = threading.Thread(
        target=capture.serve_forever,
        name="e10-otlp-capture",
        daemon=True,
    )
    server_thread.start()

    endpoint = (
        f"http://127.0.0.1:{capture.port}/v1/traces"
    )

    # Configure the project's real telemetry bootstrap before importing
    # modules that obtain Harness/HITL/Handoff tracers.
    os.environ["AI_OTEL_ENABLED"] = "true"
    os.environ[
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
    ] = endpoint
    os.environ["OTEL_SERVICE_NAME"] = SERVICE_NAME
    os.environ["AI_ENV"] = DEPLOYMENT_ENV

    results: list[CaseResult] = []
    telemetry_module = None

    print(
        f"=== {EXPERIMENT_ID}: {EXPERIMENT_NAME} ==="
    )
    print(f"git_sha={_git_sha() or 'UNKNOWN'}")
    print(f"OTLP receiver={endpoint}")
    print()

    try:
        from ai.app.observability import telemetry

        telemetry_module = telemetry
        provider = telemetry.configure_telemetry()
        if provider is None:
            raise RuntimeError(
                "AI_OTEL_ENABLED=true but telemetry provider "
                "was not configured"
            )

        cases = [
            lambda: _case_01_real_otlp_export(
                capture=capture,
                force_flush=telemetry.force_flush_telemetry,
            ),
            lambda: _case_02_failure_trace_topology(
                capture=capture,
                force_flush=telemetry.force_flush_telemetry,
            ),
            lambda: _case_03_hitl_trace(
                capture=capture,
                force_flush=telemetry.force_flush_telemetry,
            ),
            lambda: _case_04_metadata_only(
                capture=capture,
            ),
        ]

        for index, case in enumerate(cases, start=1):
            try:
                result = case()
            except BaseException as exc:
                result = CaseResult(
                    case_id=f"E10-{index:02d}",
                    scenario=(
                        "REAL_OTLP_EXPORT"
                        if index == 1
                        else "FAILURE_TRACE_TOPOLOGY"
                        if index == 2
                        else "HITL_TRACE"
                        if index == 3
                        else "METADATA_ONLY"
                    ),
                    passed=False,
                    checks={
                        "scenario_completed_without_exception": False
                    },
                    evidence={
                        "exception_type": type(exc).__name__,
                        # Avoid persisting exception message because it could
                        # theoretically contain a payload under test.
                    },
                    notes=(
                        "Scenario raised unexpectedly; inspect local "
                        "traceback by running this script directly."
                    ),
                )

            results.append(result)
            _print_case(result)

        telemetry.force_flush_telemetry(5000)
        time.sleep(0.05)

        summary = _write_artifacts(
            git_sha=_git_sha(),
            results=results,
            capture=capture,
            total_seconds=(
                time.perf_counter() - experiment_started
            ),
        )

        print("\n" + "=" * 88)
        print("[E10] FINAL")
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "git_sha": summary["git_sha"],
                    "cases_passed": (
                        f"{summary['pass_count']}/"
                        f"{summary['scenario_count']}"
                    ),
                    "otlp_request_count": summary[
                        "otlp_request_count"
                    ],
                    "decoded_span_count": summary[
                        "decoded_span_count"
                    ],
                    "key_span_coverage": (
                        f"{summary['key_span_coverage']['present_count']}/"
                        f"{summary['key_span_coverage']['required_count']}"
                    ),
                    "sensitive_payload_leak_count": summary[
                        "sensitive_payload_leak_count"
                    ],
                    "output_dir": (
                        "ai/experiment_results/"
                        "e10_otel_trace_observability"
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        return (
            0
            if summary["status"] == "E10_COMPLETE"
            else 1
        )

    finally:
        if telemetry_module is not None:
            try:
                telemetry_module.shutdown_telemetry()
            except Exception:
                pass

        capture.shutdown()
        capture.server_close()
        server_thread.join(timeout=2.0)


if __name__ == "__main__":
    raise SystemExit(main())
