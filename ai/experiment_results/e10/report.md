# E10 — OpenTelemetry Trace Observability

- Git SHA: `55bbc96057e46ebbf11d165da25c63fd6cde61a0`
- Result: **4/4 PASS**
- OTLP requests captured: `3`
- Decoded spans: `9`
- Sensitive payload leak count: `0`

## 실험 질문

> AI Runtime의 Reliability 흐름이 실제 OTLP Trace로 Export되고, 장애와 HITL 결정을 Payload 노출 없이 추적할 수 있는가?

## 결과 요약

| Case | Scenario | Result |
|---|---|---:|
| E10-01 | REAL_OTLP_EXPORT | PASS |
| E10-02 | FAILURE_TRACE_TOPOLOGY | PASS |
| E10-03 | HITL_TRACE | PASS |
| E10-04 | METADATA_ONLY | PASS |

## Key Span Coverage

| Span / Condition | Present |
|---|---:|
| `waterbridge.e10.export_probe` | PASS |
| `waterbridge.harness.runtime/ESCALATE` | PASS |
| `waterbridge.harness.verify/TIMEOUT` | PASS |
| `waterbridge.handoff.create` | PASS |
| `waterbridge.harness.runtime/HUMAN_REVIEW` | PASS |
| `waterbridge.hitl.start` | PASS |
| `waterbridge.harness.resume_review` | PASS |
| `waterbridge.hitl.resume` | PASS |

## 핵심 해석

WaterBridge AI Runtime에서 실제 OTLP/HTTP trace export를 확인했고, Harness Timeout→ESCALATE→Handoff 및 HITL 상태/결정을 Span metadata로 추적할 수 있었다. 주입한 Evidence 본문, Human reviewer note, 전화번호, 이메일, 수정 Guidance 본문은 exported OTLP payload에서 검출되지 않았다.

### Failure Trace

```text
waterbridge.harness.runtime
├─ waterbridge.harness.verify
│    ├─ decision = ESCALATE
│    └─ error_code = AI_PROCESSING_TIMEOUT
└─ waterbridge.handoff.create
     └─ redaction.enabled = true
```

### HITL Trace

```text
Original runtime trace
waterbridge.harness.runtime
└─ waterbridge.hitl.start
     └─ status = WAITING_FOR_REVIEW

Later resume call
waterbridge.harness.resume_review
└─ waterbridge.hitl.resume
     ├─ decision = modify
     ├─ reviewer_note.present = true
     ├─ modified_guidance.present = true
     └─ status = COMPLETED
```

HITL Resume는 별도 요청 시점의 로컬 Root Span으로 관측된다. 본 실험에서는 start/resume 사이의 cross-request traceparent propagation을 주장하지 않는다.

## Metadata-only 검증

실험은 Evidence 본문, Human Reviewer Note, 전화번호, 이메일, 수정 Guidance 본문에 식별 가능한 marker를 주입한 뒤 실제 OTLP protobuf body와 decode 결과를 모두 검사했다.

- Sensitive Payload Leak Count: **0**
- Reviewer Note 내용 대신 `reviewer_note.present`만 기록
- Handoff 본문 대신 `redaction.enabled` 등 운영 metadata 기록
- 오류 원문 대신 `AI_PROCESSING_TIMEOUT` 같은 표준 error code 기록

## 주장 범위

본 실험은 AI Runtime 내부 OpenTelemetry trace와 OTLP export만 검증한다. Web→Backend→AI traceparent propagation 또는 전체 Distributed Tracing, OpenTelemetry GenAI Semantic Conventions 적용을 증명하지 않는다.

따라서 발표에서는 **'Web부터 AI까지 전체 Distributed Tracing을 완성했다'**가 아니라 **'AI Runtime 내부 주요 Reliability 흐름의 OTel Trace 생성과 실제 OTLP Export를 검증했다'**고 표현한다.

## E10-01 — REAL_OTLP_EXPORT

```json
{
  "passed": true,
  "checks": {
    "force_flush_success": true,
    "otlp_http_request_received": true,
    "otlp_trace_path_used": true,
    "protobuf_decode_success": true,
    "service_name_preserved": true,
    "service_version_present": true,
    "deployment_environment_preserved": true
  },
  "evidence": {
    "otlp_request_count_after_flush": 1,
    "probe_trace_id": "463e690489668119dd2eb6ee2321eb5e",
    "probe_span_id": "d01dcb5bcd3872b1",
    "resource_attributes": {
      "telemetry.sdk.language": "python",
      "telemetry.sdk.name": "opentelemetry",
      "telemetry.sdk.version": "1.44.0",
      "service.instance.id": "ff0929a2-1837-490a-bc4b-ad295ec6a02a",
      "service.name": "waterbridge-ai-e10",
      "service.version": "1.0.0",
      "deployment.environment.name": "experiment"
    }
  },
  "notes": "Real OTLP/HTTP protobuf export to an out-of-process HTTP receiver running on loopback."
}
```

## E10-02 — FAILURE_TRACE_TOPOLOGY

```json
{
  "passed": true,
  "checks": {
    "runtime_result_escalate": true,
    "runtime_handoff_created": true,
    "force_flush_success": true,
    "runtime_span_present": true,
    "verify_span_present": true,
    "handoff_span_present": true,
    "same_trace_id": true,
    "verify_parent_is_runtime": true,
    "handoff_parent_is_runtime": true,
    "timeout_error_code_observable": true,
    "handoff_observable": true,
    "handoff_redaction_metadata_present": true
  },
  "evidence": {
    "runtime_trace_id": "c23853ee4b4d06f3b02bfc8fd9bfbdc0",
    "runtime_span_id": "8e89a0cbb6bb3156",
    "verify_parent_span_id": "8e89a0cbb6bb3156",
    "handoff_parent_span_id": "8e89a0cbb6bb3156",
    "decision": "ESCALATE",
    "error_code": "AI_PROCESSING_TIMEOUT"
  },
  "notes": "Actual Harness timeout path. No external LLM is invoked for supplementary context synthesis."
}
```

## E10-03 — HITL_TRACE

```json
{
  "passed": true,
  "checks": {
    "runtime_entered_human_review": true,
    "runtime_waiting_for_review": true,
    "resume_completed": true,
    "modified_guidance_released": true,
    "force_flush_success": true,
    "hitl_start_span_present": true,
    "hitl_resume_span_present": true,
    "harness_resume_span_present": true,
    "hitl_start_child_of_runtime": true,
    "hitl_resume_child_of_harness_resume": true,
    "waiting_status_observable": true,
    "modify_decision_observable": true,
    "modified_guidance_presence_observable": true,
    "reviewer_note_presence_observable": true,
    "completed_status_observable": true,
    "approved_observable": true
  },
  "evidence": {
    "hitl_start_trace_id": "d3e871fbecb868b85954581bdf733428",
    "hitl_resume_trace_id": "8be6a51041f10ee68c9e581240ab9af2",
    "checkpoint_thread_id": "hitl-3d5e571f64dba959548746d0ca266b71",
    "start_status": "WAITING_FOR_REVIEW",
    "resume_decision": "modify",
    "resume_status": "COMPLETED",
    "note_content_recorded_in_evidence": false
  },
  "notes": "HITL start belongs to the original Harness runtime trace. The later resume call creates a new local root (waterbridge.harness.resume_review), with hitl.resume as its child. This experiment does not claim cross-request traceparent propagation."
}
```

## E10-04 — METADATA_ONLY

```json
{
  "passed": true,
  "checks": {
    "sensitive_payload_leak_count_zero": true,
    "reviewer_note_content_not_exported": true,
    "evidence_content_not_exported": true,
    "modified_guidance_content_not_exported": true,
    "phone_not_exported": true,
    "email_not_exported": true,
    "reviewer_note_presence_metadata_kept": true,
    "handoff_redaction_metadata_kept": true,
    "failure_code_metadata_kept": true
  },
  "evidence": {
    "otlp_request_count": 3,
    "decoded_span_count": 9,
    "sensitive_payload_leak_count": 0,
    "forbidden_marker_count_checked": 5,
    "metadata_examples": {
      "reviewer_note_present": true,
      "handoff_redaction_enabled": true,
      "harness_error_code": "AI_PROCESSING_TIMEOUT"
    }
  },
  "notes": "Leak detection scans both decoded span data and the raw OTLP protobuf bodies. Artifact files never persist the injected sensitive marker values."
}
```
