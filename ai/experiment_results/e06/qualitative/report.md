# E06-Q v2 — Harness Before / Decision / After

- Git SHA: `ca1ec8f858590b776746d7dceeab4e90c9abbb50`
- Original E06 SHA 일치: `False`
- Variant: `V2_HARNESS_DISTINCT_DECISION_PATHS`

> E06 정량 실험을 대체하지 않는 발표용 Qualitative Evidence입니다.

## 발표용 핵심 구조

| Fault | Harness 결정 | 의미 |
|---|---|---|
| 다른 제품 Evidence | RETRY_RETRIEVAL | 검색 복구 |
| LLM 출력 계약 위반 | RETRY_GENERATION | 생성 복구 |
| MCP 복구 불가 장애 | ESCALATE | Fail-closed 상담 Handoff |
| 미지원 기능 요청 | HUMAN_REVIEW | HITL 사람 검토 |

## WRONG_MODEL_EVIDENCE

- Harness role: `RETRY_RETRIEVAL`

### BEFORE — Harness 직전

```json
{
  "customer_symptom": "냉수가 예전보다 적게 나와요.",
  "customer_model": "WPUJAC104DWH",
  "retrieved_document_model": "WPUIAC606SNW",
  "retrieved_document_title": "WPUIAC606SNW 공식 사용설명서",
  "candidate_evidence_text": "출수량이 적을 때는 급수 상태와 제품 내부 공급 상태를 확인하고, 증상이 지속되면 점검을 요청합니다.",
  "why_it_looks_plausible": "출수량 관련 내용은 유사하지만 고객 제품과 문서 모델이 다름"
}
```

### HARNESS

```json
{
  "first_decision": "RETRY_RETRIEVAL",
  "issues": [
    "WRONG_MODEL_EVIDENCE",
    "NO_EVIDENCE"
  ],
  "blocked_chunk_ids": [
    "E06Q-WRONG-001"
  ],
  "retry_count": 1,
  "final_decision": "PASS"
}
```

### AFTER — 고객-facing 결과 / 다음 상태

```json
{
  "first_attempt_forwarded_count": 0,
  "wrong_model_evidence_released": false,
  "accepted_retry_model": "WPUJAC104DWH",
  "customer_guidance": "냉수 출수량이 적을 때는 원수 공급 상태와 필터 장착 상태를 확인하고, 기본 점검 후에도 증상이 지속되면 전문 상담 및 점검을 요청합니다."
}
```

---

## OUTPUT_SCHEMA_INVALID

- Harness role: `RETRY_GENERATION`

### BEFORE — Harness 직전

```json
{
  "expected_contract_fields": [
    "guidance_status",
    "message",
    "restricted_functions",
    "next_actions"
  ],
  "llm_output_payload": {
    "message": "냉수 출수량이 적을 때는 원수 공급 상태와 필터 장착 상태를 확인합니다.",
    "recommendation": "상태 확인"
  },
  "problem": "내용은 읽을 수 있지만 Backend 공개 응답 계약 필드가 누락됨"
}
```

### HARNESS

```json
{
  "first_decision": "RETRY_GENERATION",
  "issues": [
    "OUTPUT_SCHEMA_INVALID"
  ],
  "generation_retry_count": 1,
  "final_decision": "PASS"
}
```

### AFTER — 고객-facing 결과 / 다음 상태

```json
{
  "regenerated_payload": {
    "guidance_status": "NORMAL",
    "message": "냉수 출수량이 적을 때는 원수 공급 상태와 필터 장착 상태를 확인합니다.",
    "restricted_functions": [],
    "next_actions": [
      "상태 확인"
    ]
  },
  "schema_contract_satisfied": true,
  "customer_guidance": {
    "guidance_status": "NORMAL",
    "message": "냉수 출수량이 적을 때는 원수 공급 상태와 필터 장착 상태를 확인합니다.",
    "restricted_functions": [],
    "next_actions": [
      "상태 확인"
    ]
  }
}
```

---

## MCP_NONRETRYABLE_FAILURE

- Harness role: `ESCALATE`

### BEFORE — Harness 직전

```json
{
  "customer_symptom": "냉수가 갑자기 안 나와요.",
  "required_tool": "search_official_evidence",
  "tool_failure_kind": "UNAVAILABLE",
  "retryable": false,
  "official_evidence_available_to_runtime": false,
  "raw_exception_exposed": false
}
```

### HARNESS

```json
{
  "decision": "ESCALATE",
  "issues": [
    "MCP_TOOL_FAILURE"
  ],
  "error_code": "MCP_TOOL_FAILURE",
  "should_escalate": true,
  "handoff_present": true,
  "handoff_reason": "MCP_TOOL_FAILURE"
}
```

### AFTER — 고객-facing 결과 / 다음 상태

```json
{
  "automatic_guidance_released": false,
  "hallucinated_manual_guidance_generated": false,
  "next_state": "Consultation Handoff",
  "customer_facing_policy": "공식 근거 조회 Tool을 사용할 수 없으므로 추측성 자가조치를 생성하지 않고 상담 경로로 전환"
}
```

---

## UNSUPPORTED_FUNCTION

- Harness role: `HUMAN_REVIEW`

### BEFORE — Harness 직전

```json
{
  "customer_product": "WPUJAC104DWH",
  "supported_functions": [
    "cold_water",
    "hot_water"
  ],
  "requested_function": "ice",
  "guidance_candidate": {
    "guidance_status": "NORMAL",
    "message": "냉수 상태를 확인하는 안내 후보입니다.",
    "restricted_functions": [],
    "next_actions": [
      "상태 확인"
    ]
  }
}
```

### HARNESS

```json
{
  "decision": "HUMAN_REVIEW",
  "issues": [
    "UNSUPPORTED_FUNCTION"
  ],
  "human_review_present": true,
  "human_review_status": "WAITING_FOR_REVIEW"
}
```

### AFTER — 고객-facing 결과 / 다음 상태

```json
{
  "customer_release": "자동 확정하지 않음",
  "next_state": "HITL Human Review 대기"
}
```

---

## 발표용 한 줄 설명

> Harness는 오류를 전부 같은 방식으로 막는 계층이 아니라, 복구 가능한 오류는 다시 시도하고, 복구 불가능한 오류는 상담으로 넘기며, 사람 판단이 필요한 요청은 HITL로 중단하는 Reliability Boundary입니다.

## Safety Conflict 보조 해석

> 누수/DANGER는 정상 실행에서 Rule-based Safety Guard가 우선 TOTAL_STOP으로 처리합니다. 따라서 Safety Conflict는 Harness의 주 사례가 아니라, 앞단 안전 판정과 최종 응답이 비정상적으로 모순되는 상태를 막는 Defense-in-Depth 사례로 분리합니다.
