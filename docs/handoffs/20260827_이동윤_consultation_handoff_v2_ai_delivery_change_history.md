# Consultation Handoff 2.0 AI 전송 변경 이력

- 작업일: 2026-08-27
- 작업 Branch: `dongyoon`
- 변경 전 HEAD: `9862bac3749118f81ab2770016f61630b0f189e2`
- 승인 범위: 윤승혁 담당 Harness·Handoff·Backend Handoff Client 및 관련 테스트
- 현재 상태: `LOCAL_AI_TO_BACKEND_SOCKET_E2E_PASS / PROTECTED_HTTP_E2E_NOT_RUN`

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

## 2026-08-27 Backend 병합 후 Route Authority 정합성 보완

### 발견 및 원인

- 기준 HEAD: `68666b88fcf33273906710f23a8d17f7f1faa07f`
- Backend Handoff 2.0 구현 병합 후 Local Socket E2E를 실행했을 때 최초 결과는
  `1 failed in 34.86s`였다.
- AI의 실제 No-Evidence Handoff가 `routing_reason=HARNESS_ESCALATE`,
  `escalation_reason=HARNESS_ESCALATE:NO_EVIDENCE`로 생성됐다.
- Backend는 같은 AI Run의 확정 결과가 `fallback_reason_code=NO_EVIDENCE`이면
  `routing_reason=FAIL_CLOSED_CONSULTATION`,
  `escalation_reason=NO_EVIDENCE`만 승인하므로 요청을 HTTP 409로 거절했다.

### 보완한 동작

1. `NO_EVIDENCE`, `RUNTIME_PRODUCT_NOT_APPROVED`,
   `AI_PROCESSING_TIMEOUT`을 Backend 권위에 맞는
   `FAIL_CLOSED_CONSULTATION`으로 분류했다.
2. MCP Tool 실패, 출력 Schema 실패와 권위가 없는 기타 Harness 실패는 공개
   `failure_stage=VALIDATING`일 때만 `HARNESS_ESCALATE`로 유지했다. 같은 사유라도
   혼합 실패로 공개 Stage가 `RETRIEVING`이면 Backend 허용 조합에 맞춰
   `FAIL_CLOSED_CONSULTATION`으로 분류했다.
3. `HARNESS_ESCALATE:<세부 코드>`처럼 Backend 실행 결과와 결속할 수 없는 문자열을
   제거하고, 공개 AI Fallback 우선순위와 같은 정규 사유 코드만 전송하도록 했다.
4. 제품 미승인과 Danger가 동시에 보존되는 경우에는 Backend Event 우선순위에
   맞춰 `PRODUCT_VALIDATION_FAILED` 권위의 `FAIL_CLOSED_CONSULTATION`을 유지했다.
5. 출력 Schema 재시도 소진을 내부적으로 `NO_EVIDENCE`라고 기록하던 오류를
   `OUTPUT_SCHEMA_INVALID`로 정정했다.
6. 가이드가 없어 Human Review를 시작할 수 없는 비정상 경로도 임의 사유 문자열
   대신 확정 AI Fallback 사유로 축소하도록 했다.

### 이번 보완 변경 파일

```text
ai/app/orchestration/harness/runner.py
ai/app/orchestration/harness/runtime.py
ai/tests/unit/harness/test_runtime_routing.py
ai/tests/unit/harness/test_pipeline_runtime_integration.py
docs/handoffs/20260827_이동윤_consultation_handoff_v2_ai_delivery_change_history.md
```

### 재검증 결과

```text
핵심 Harness 표적: 33 passed in 1.60s
Handoff·Harness·Handoff v2 Contract 표적: 137 passed in 6.54s
직접 Route 진단:
  routing_reason=FAIL_CLOSED_CONSULTATION
  escalation_reason=NO_EVIDENCE
  fallback_reason_code=NO_EVIDENCE
  failure_stage=RETRIEVING
AI 전체 Unit: 690 passed, 4 warnings, 41 subtests passed in 27.97s
AI 전체 Contract: 56 passed in 0.87s
AI→Backend Local Socket E2E: 1 passed in 31.78s
```

### 수정하지 않은 범위와 남은 Gate

- `backend/**`와 `contracts/ai/handoff/**`는 수정하지 않았다.
- 운영 `AI_HANDOFF_BACKEND_ENABLED` 값은 변경하지 않았다.
- 위 E2E는 로컬의 결정론적 No-Evidence 한 건으로 AI FastAPI,
  BackgroundTask HTTP 전송, Backend 검증·저장을 연결한 결과다.
- 보호 환경의 실제 AI→Backend HTTP E2E, 운영 활성화, 상담사 화면 Projection 확인은
  아직 `NOT_RUN`이다.
