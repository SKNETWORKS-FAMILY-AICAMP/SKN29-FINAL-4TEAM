# E07-B — Interactive Human-in-the-Loop Resume

- Git SHA: `5611f31337a76a089d43959c57994dc01de77a48`
- Result: `PASS`
- Human Input Source: `INTERACTIVE_TERMINAL_INPUT`
- Checkpointer: `InMemorySaver`
- Human Wait Time: `27.523s`

## BEFORE — AI가 사람 검토를 기다리는 상태

```json
{
  "customer_request": "얼음 기능도 사용할 수 있는지 확인해 주세요.",
  "model_code": "WPUJAC104DWH",
  "requested_function": "ice",
  "supported_functions": [
    "cold_water",
    "hot_water"
  ],
  "harness_decision": "HUMAN_REVIEW",
  "harness_issues": [
    "UNSUPPORTED_FUNCTION"
  ],
  "hitl_status": "WAITING_FOR_REVIEW",
  "thread_id": "hitl-880fa5f30fc3538dfaf7146e6f06c0fb",
  "state_version": 7,
  "evidence_chunk_ids": [
    "E07-MANUAL-JAC104-EVIDENCE-001"
  ],
  "proposed_guidance": {
    "guidance_status": "NORMAL",
    "message": "요청하신 기능은 현재 자동 안내 범위를 벗어나므로 제품 사양을 추가 확인해 주세요.",
    "restricted_functions": [],
    "next_actions": [
      "제품 사양 확인"
    ]
  },
  "harness_run_calls": 1
}
```

## 실제 사람 입력

```json
{
  "decision": "modify",
  "modified_guidance": {
    "guidance_status": "NORMAL",
    "message": "얼음 기능 지원 여부는 제품 사양 확인 후 안내해 주세요.",
    "restricted_functions": [],
    "next_actions": [
      "상담사가 제품 사양을 확인합니다."
    ]
  },
  "reviewer_note": "얼음 기능을 원하면 얼음 정수기를 사든가 에라이"
}
```

## AFTER — 동일 Checkpoint에서 Resume한 결과

```json
{
  "review_status": "COMPLETED",
  "thread_id": "hitl-880fa5f30fc3538dfaf7146e6f06c0fb",
  "approved": true,
  "final_guidance": {
    "guidance_status": "NORMAL",
    "message": "얼음 기능 지원 여부는 제품 사양 확인 후 안내해 주세요.",
    "restricted_functions": [],
    "next_actions": [
      "상담사가 제품 사양을 확인합니다."
    ]
  },
  "handoff_present": false,
  "handoff_reason": null,
  "harness_run_calls": 1
}
```

## 검증 항목

```json
{
  "same_thread_id": true,
  "inquiry_id_preserved": true,
  "ai_request_id_preserved": true,
  "model_code_preserved": true,
  "state_version_preserved": true,
  "evidence_ids_preserved": true,
  "no_harness_reverification_on_resume": true,
  "completed": true,
  "approved": true,
  "human_modified_guidance_released": true,
  "original_guidance_not_released": true,
  "handoff_absent": true
}
```

## 해석

> AI가 자동 판단 범위를 벗어난 요청에서 Human Review 상태로 중단되었고, 실제 사람이 터미널에서 결정을 입력한 뒤 동일 LangGraph Thread와 Context를 유지한 채 Resume되었다.

## 범위 제한

실제 사람이 터미널에서 Human Review 결정을 입력한 same-process HITL 실험이다. Browser UI E2E 및 process restart durability는 본 실험 범위가 아니다.
