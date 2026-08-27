# Consultation Handoff 2.0 AI 전송 변경 이력

- 작업일: 2026-08-27
- 작업 Branch: `dongyoon`
- 변경 전 HEAD: `9862bac3749118f81ab2770016f61630b0f189e2`
- 승인 범위: 윤승혁 담당 Harness·Handoff·Backend Handoff Client 및 관련 테스트
- 현재 상태: `READY_FOR_BACKEND_V2_E2E`

## 변경한 동작

1. Handoff 입력·결과에 원래 AI 분석 요청의 `state_version`과 실제 상담 이관
   `routing_reason`을 별도로 보존했다.
2. 맥락 합성에 실패해 `context_synthesis=null`이 되어도 기존 상담 Handoff와
   최상위 `routing_reason`이 유지되도록 했다.
3. Handoff Envelope `2.0.0` 전용 외부 DTO·Mapper를 추가했다.
4. 외부 전송 전에 v2 필수 필드, 목록 제한, Safety Enum, Evidence 순서·부분집합,
   Danger Fallback 조합을 검증하도록 했다.
5. 내부 `source_ids`, Provider 호출 여부·모델·Prompt 버전·Token·Latency와
   결정론적 처리 메타데이터를 외부 payload에서 제거했다.
6. 예상하지 못한 맥락 변환 실패만 `context_synthesis=null`로 축소하고, 기본
   Envelope 오류는 HTTP 호출 전 `PAYLOAD_INVALID`로 종료하도록 했다.
7. Backend 응답 409를 모두 재시도하던 동작을 제거했다.
8. `AI_HANDOFF_NOT_READY`, HTTP `429/500/502/503/504`, Network, Timeout만 최대
   한 번 재시도하고 그 외 409·4xx는 재시도하지 않도록 했다.
9. 재시도할 때 첫 번째 시도와 같은 JSON payload를 그대로 사용하도록 검증했다.
10. AI Handoff Local Socket 테스트를 v2 Envelope와 Backend `error.code` 응답에
    맞게 갱신했다.

## 변경 파일

```text
ai/app/orchestration/handoff/backend_handoff_v2.py
ai/app/orchestration/handoff/handoff_input.py
ai/app/orchestration/handoff/handoff_result.py
ai/app/orchestration/handoff/consultation_handoff_agent.py
ai/app/orchestration/handoff/__init__.py
ai/app/orchestration/harness/runner.py
ai/app/integrations/backend/handoff_client.py
ai/tests/unit/handoff/test_backend_handoff_v2.py
ai/tests/unit/handoff/test_backend_handoff_client.py
ai/tests/unit/harness/test_runtime_routing.py
ai/tests/integration/test_handoff_backend_http_delivery.py
```

## 수정하지 않은 범위

```text
backend/**
contracts/ai/handoff/**
ai/app/orchestration/pipeline_router.py
ai/app/orchestration/pipeline_context.py
ai/app/orchestration/pipeline_result.py
ai/app/interfaces/http/routes/analysis_routes.py
ai/app/orchestration/hitl/**
운영 AI_HANDOFF_BACKEND_ENABLED 값
```

## 검증 결과

```text
Handoff·Harness Unit: 94 passed in 4.80s
Handoff v2 Contract: 40 passed in 0.52s
AI Handoff Local Socket: 1 passed in 1.10s
AI 전체 Unit: 687 passed, 4 warnings, 41 subtests passed in 24.76s
Contract Example Validator: API JSON 73/73, Integration 5, Wrapped Response 53
git diff --check: PASS
```

Backend v2 Serializer·원장 저장·Projection과 동일 Inquiry AI→Backend E2E는
최지용 구현 후 별도로 검증한다. 그 전까지
`AI_HANDOFF_BACKEND_ENABLED=false`를 유지한다.
