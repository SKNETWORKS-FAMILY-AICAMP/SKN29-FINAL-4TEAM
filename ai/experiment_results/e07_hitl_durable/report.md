# E07 — HITL + LangGraph Checkpointed Resume

- Git SHA: `5611f31337a76a089d43959c57994dc01de77a48`
- Checkpointer: `InMemorySaver`
- 결과: **4/4 PASS**

## 목적

사람 검토가 필요한 요청을 LangGraph interrupt에서 중단하고, 동일 Checkpoint/Thread의 Context를 보존한 채 APPROVE/MODIFY/REJECT로 Resume할 수 있는지 검증한다.

## 핵심 결과

| Case | 기대 결과 | PASS |
|---|---|---|
| APPROVE | 기존 Guidance 보존 | True |
| MODIFY | 사람 수정 Guidance 반영 | True |
| REJECT | 자동 Release 차단 + Handoff | True |
| STALE_STATE_VERSION | 불일치 버전 Fail-closed 차단 | True |

## 해석 범위

- 현재 `InMemorySaver`이면 같은 AI 프로세스 안의 interrupt/resume만 주장한다.
- 프로세스 재시작 후 Persistent Durability는 본 실험 범위가 아니다.
- 현재 HITL 계약의 `state_version`은 증가시키는 값이 아니라 checkpoint 요청과 동일해야 하는 consistency key다.
- Resume 시 Harness verification 재호출 여부는 동적 call counter로 확인한다.
- Retrieval/Generation 전체 E2E 재실행 여부는 E07의 독립 측정 대상이 아니다.

## 발표용 문장

> 사람 판단이 필요한 요청은 LangGraph Checkpoint에서 중단하고, 검토 후 동일 Thread와 Context를 유지한 채 Resume했습니다. 승인·수정·거절을 각각 다른 후속 처리로 연결하고, 불일치 State Version의 검토 응답은 Fail-closed로 차단했습니다.

## APPROVE

- PASS: `True`

### BEFORE
```json
{
  "customer_request": "얼음 기능도 사용할 수 있는지 확인해 주세요.",
  "product_model": "WPUJAC104DWH",
  "supported_functions": [
    "cold_water",
    "hot_water"
  ],
  "requested_function": "ice",
  "harness_decision": "HUMAN_REVIEW",
  "harness_issues": [
    "UNSUPPORTED_FUNCTION"
  ],
  "hitl_status": "WAITING_FOR_REVIEW",
  "thread_id": "hitl-320e7abb4c034be60e8d8126120ef154",
  "state_version": 7,
  "evidence_chunk_ids": [
    "E07-JAC104-EVIDENCE-001"
  ],
  "harness_run_calls": 1
}
```
### AFTER
```json
{
  "status": "COMPLETED",
  "final_guidance": {
    "guidance_status": "NORMAL",
    "message": "요청하신 기능은 현재 자동 안내 범위를 벗어나므로 제품 사양을 추가 확인해 주세요.",
    "restricted_functions": [],
    "next_actions": [
      "제품 사양 확인"
    ]
  },
  "handoff_present": false,
  "harness_run_calls": 1
}
```
### CHECKS
```json
{
  "completed": true,
  "approved": true,
  "same_thread_id": true,
  "original_guidance_preserved": true,
  "no_harness_reverification_on_resume": true,
  "interrupt_inquiry_preserved": true,
  "checkpoint_inquiry_preserved": true,
  "ai_request_id_preserved": true,
  "model_code_preserved": true,
  "state_version_preserved": true,
  "evidence_ids_preserved": true
}
```

## MODIFY

- PASS: `True`

### BEFORE
```json
{
  "customer_request": "얼음 기능도 사용할 수 있는지 확인해 주세요.",
  "product_model": "WPUJAC104DWH",
  "supported_functions": [
    "cold_water",
    "hot_water"
  ],
  "requested_function": "ice",
  "harness_decision": "HUMAN_REVIEW",
  "harness_issues": [
    "UNSUPPORTED_FUNCTION"
  ],
  "hitl_status": "WAITING_FOR_REVIEW",
  "thread_id": "hitl-013d69d88e7c4569c924f40327f74634",
  "state_version": 7,
  "evidence_chunk_ids": [
    "E07-JAC104-EVIDENCE-001"
  ],
  "harness_run_calls": 1
}
```
### AFTER
```json
{
  "status": "COMPLETED",
  "final_guidance": {
    "guidance_status": "NORMAL",
    "message": "상담사가 제품 사양을 확인한 뒤 얼음 기능 지원 여부를 안내합니다.",
    "restricted_functions": [],
    "next_actions": [
      "상담사 사양 확인"
    ]
  },
  "reviewer_note": "제품 사양 확인 표현으로 수정",
  "handoff_present": false,
  "harness_run_calls": 1
}
```
### CHECKS
```json
{
  "completed": true,
  "approved": true,
  "same_thread_id": true,
  "human_modified_guidance_applied": true,
  "original_guidance_not_released": true,
  "no_harness_reverification_on_resume": true,
  "interrupt_inquiry_preserved": true,
  "checkpoint_inquiry_preserved": true,
  "ai_request_id_preserved": true,
  "model_code_preserved": true,
  "state_version_preserved": true,
  "evidence_ids_preserved": true
}
```

## REJECT

- PASS: `True`

### BEFORE
```json
{
  "customer_request": "얼음 기능도 사용할 수 있는지 확인해 주세요.",
  "product_model": "WPUJAC104DWH",
  "supported_functions": [
    "cold_water",
    "hot_water"
  ],
  "requested_function": "ice",
  "harness_decision": "HUMAN_REVIEW",
  "harness_issues": [
    "UNSUPPORTED_FUNCTION"
  ],
  "hitl_status": "WAITING_FOR_REVIEW",
  "thread_id": "hitl-360c483a4bb9f191652255e54854f416",
  "state_version": 7,
  "evidence_chunk_ids": [
    "E07-JAC104-EVIDENCE-001"
  ],
  "harness_run_calls": 1
}
```
### AFTER
```json
{
  "status": "COMPLETED",
  "final_guidance": null,
  "handoff_present": true,
  "handoff_reason": "HUMAN_REVIEW_REJECTED",
  "harness_run_calls": 1
}
```
### CHECKS
```json
{
  "completed": true,
  "rejected": true,
  "same_thread_id": true,
  "guidance_release_blocked": true,
  "handoff_created": true,
  "handoff_reason_is_human_review_rejected": true,
  "no_harness_reverification_on_resume": true,
  "interrupt_inquiry_preserved": true,
  "checkpoint_inquiry_preserved": true,
  "ai_request_id_preserved": true,
  "model_code_preserved": true,
  "state_version_preserved": true,
  "evidence_ids_preserved": true
}
```

## STALE_STATE_VERSION

- PASS: `True`

### BEFORE
```json
{
  "customer_request": "얼음 기능도 사용할 수 있는지 확인해 주세요.",
  "product_model": "WPUJAC104DWH",
  "supported_functions": [
    "cold_water",
    "hot_water"
  ],
  "requested_function": "ice",
  "harness_decision": "HUMAN_REVIEW",
  "harness_issues": [
    "UNSUPPORTED_FUNCTION"
  ],
  "hitl_status": "WAITING_FOR_REVIEW",
  "thread_id": "hitl-f041a880e157de531ac53a5b77ee7cf6",
  "state_version": 7,
  "evidence_chunk_ids": [
    "E07-JAC104-EVIDENCE-001"
  ],
  "harness_run_calls": 1
}
```
### STALE ATTEMPT
```json
{
  "checkpoint_state_version": 7,
  "submitted_state_version": 8,
  "blocked": true,
  "error_type": "ValueError",
  "error_message": "human review state_version does not match the checkpointed request"
}
```
### AFTER
```json
{
  "automatic_guidance_released": false,
  "resume_result": "BLOCKED_FAIL_CLOSED",
  "same_checkpoint_retry_claimed": false,
  "normal_resume_is_verified_by": "APPROVE case",
  "harness_run_calls": 1
}
```
### CHECKS
```json
{
  "stale_version_blocked": true,
  "state_version_error_reported": true,
  "no_harness_reverification_on_failed_resume": true,
  "interrupt_inquiry_preserved": true,
  "checkpoint_inquiry_preserved": true,
  "ai_request_id_preserved": true,
  "model_code_preserved": true,
  "state_version_preserved": true,
  "evidence_ids_preserved": true
}
```
