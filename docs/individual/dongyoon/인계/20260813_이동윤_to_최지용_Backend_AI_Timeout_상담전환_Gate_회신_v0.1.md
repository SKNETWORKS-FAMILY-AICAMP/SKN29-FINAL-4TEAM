# Backend AI Timeout 상담 전환 Gate 회신

> 작성일: 2026-08-13  
> 발신: 이동윤(AI·RAG)  
> Backend 담당: 최지용  
> 중요도: **P1 — 통합 완료 전 필수 Gate**  
> 검토 기준 HEAD: `1289d4b3673d9b061833fa94d45096bde1541a02`

## 1. 바로 보낼 회신문

아래 블록을 그대로 복사해 회신할 수 있다.

```text
[최지용 담당 Backend AI Timeout Gate 추가 요청]

중요도는 P1로 판단합니다. 현재 Backend의 AI Timeout 처리는 AIRun 실패
감사 저장까지만 구현되어 있고, 자동 상담 전환은 수행하지 않습니다.
따라서 Timeout 발생 문의가 QUESTIONNAIRE_IN_PROGRESS에 잔류할 수 있습니다.

현재 확인된 동작은 다음과 같습니다.
- Backend AI Client가 HTTP Timeout을 AI-TIMEOUT-01 / 504로 매핑
- AIRun에 TIMED_OUT, AI-TIMEOUT-01, retry_count, latency_ms, completed_at 저장
- Timeout 결과는 event_candidate=None, event_applied=None으로 반환
- StateMachine, GuardEvaluator, CONSULTATION_REQUIRED 전이와 SYSTEM History는 미적용

timeout_backend_owner=최지용
timeout_backend_event_contract=AI-TIMEOUT-01을 CONSULTATION_REQUIRED로 연결할 SYSTEM Event 및 Guard 매핑 승인
timeout_backend_completion=AI Timeout(504 매핑) AIRun 저장 + CONSULTATION_REQUIRED 상담 전환 1회만 적용 + state_version/Guard 검증 + SYSTEM TransitionHistory 원자 저장

완료 시 아래 증거가 필요합니다.
1. Timeout AIRun 정확히 1건: status=TIMED_OUT, error_code=AI-TIMEOUT-01,
   retry_count=0, latency/completed_at 저장
2. 최신 state_version에서만 QUESTIONNAIRE_IN_PROGRESS →
   CONSULTATION_REQUIRED 전환 및 state_version 1회 증가
3. 동일 ai_request_id 또는 동일 멱등 요청 Replay 시 AI 호출·상태 전이·
   Version 증가·History 추가가 모두 0회
4. stale state_version이면 Timeout 감사 정보만 저장하고 상담 전이는 미적용
5. Guard 실패 시 Inquiry/History 부분 적용 없음
6. 결정적 Timeout 단위 테스트와 실제 Backend→AI Timeout HTTP 주입 E2E를
   각각 제시하며, 실제 주입 미실행 시 NOT_RUN 표기

주의: 현재 State Machine에는 Timeout 전용 SYSTEM Event가 없습니다.
NO_EVIDENCE는 정상 검색 완료 후 공식 근거 0건을 뜻하므로 504 Timeout을
NO_EVIDENCE로 임의 치환하지 말고 Event/Guard 매핑을 먼저 승인받아야 합니다.
```

## 2. 결론과 현재 Gap

현재 Backend는 AI 호출 Timeout을 `504` 성격의 통합 예외로 변환하고
`AIRun.status_code=TIMED_OUT`, `error_code=AI-TIMEOUT-01`로 저장한다. 다만
`504` 숫자 자체를 별도 DB 컬럼에 저장하는 구현은 아니다. “AI 504 저장”은 아래
감사 필드 저장을 의미하도록 해석해야 한다.

- `status_code=TIMED_OUT`
- `error_code=AI-TIMEOUT-01`
- `error_message`
- `retry_count`
- `latency_ms`
- `completed_at`

Timeout 예외 분기는 위 저장 후 `event_candidate=None`, `event_applied=None`으로
반환한다. 검증된 성공·Fallback 결과가 사용하는 `StateMachine.resolve()`,
`GuardEvaluator.evaluate()`, `InquiryRepository.apply_state_transition()`과
`TransitionHistoryService.record_ai_result()`에는 진입하지 않는다. 그러므로 현재
코드만으로는 `CONSULTATION_REQUIRED` 전환, `state_version` 증가 및 SYSTEM 상태
이력이 발생하지 않는다.

## 3. 근거 빠른 확인 순서

검토자는 아래 순서로 열면 현재 동작과 미구현 경계를 빠르게 확인할 수 있다.

1. [Timeout → 504 예외 매핑](../../../../backend/integrations/ai/client.py#L78-L82)
2. [Timeout 실패 저장 후 Event 없이 반환](../../../../backend/apps/inquiries/services/inquiry_ai_service.py#L168-L189)
3. [AIRun TIMED_OUT 감사 필드 저장](../../../../backend/apps/inquiries/services/inquiry_ai_service.py#L342-L401)
4. [성공 결과에서만 state_version 비교 후 Event 적용](../../../../backend/apps/inquiries/services/inquiry_ai_service.py#L418-L466)
5. [정상 Event의 State Machine·Guard·상태·History 적용](../../../../backend/apps/inquiries/services/inquiry_ai_service.py#L614-L677)
6. [현재 Timeout 테스트 범위](../../../../backend/tests/unit/ai_integration/test_inquiry_ai_service.py#L593-L634)
7. [AI 계약의 504 Timeout과 정상 No-Evidence 구분](../../../../contracts/ai/README.md#L45-L61)
8. [State Machine에 등록된 AI 결과 Event](../../../../contracts/state-machine/inquiry-events.yaml#L456-L483)
9. [state_version Guard와 409 계약](../../../../contracts/state-machine/transition-guards.yaml#L229-L242)

## 4. 코드·계약 근거표

| 확인 항목 | 현재 증거 | 판정 |
| --- | --- | --- |
| HTTP Timeout 매핑 | [`httpx.TimeoutException`을 `AITimeoutError(http_status=504)`로 변환](../../../../backend/integrations/ai/client.py#L78-L82) | 구현 |
| Timeout 오류 코드 | [`AITimeoutError.default_code = AI-TIMEOUT-01`](../../../../backend/integrations/ai/exceptions.py#L65-L68) | 구현 |
| 실패 감사 저장 | [`TIMED_OUT`, 오류, 재시도, 지연시간, 완료시각 저장](../../../../backend/apps/inquiries/services/inquiry_ai_service.py#L342-L401) | 구현 |
| Timeout Event 후보 | [예외 결과의 `event_candidate=None`, `event_applied=None`](../../../../backend/apps/inquiries/services/inquiry_ai_service.py#L168-L189) | 미구현 |
| 최신 Version 확인 | [검증된 결과 적용 직전 `inquiry.state_version` 비교](../../../../backend/apps/inquiries/services/inquiry_ai_service.py#L425-L439) | 성공 결과에 구현, Timeout 전이에는 미적용 |
| State Machine·Guard 적용 | [SYSTEM Actor, 요청 Version과 Domain Guard 평가](../../../../backend/apps/inquiries/services/inquiry_ai_service.py#L640-L664) | 성공 결과에 구현, Timeout 전이에는 미적용 |
| 상태·History 원자 적용 | [상태 변경과 AI SYSTEM History 기록](../../../../backend/apps/inquiries/services/inquiry_ai_service.py#L666-L677) | 성공 결과에 구현, Timeout 전이에는 미적용 |
| AIRun 멱등성 | [`idempotency_key` UniqueConstraint](../../../../backend/apps/audit/models/ai_run.py#L203-L216) | 기반 존재 |
| 동일 요청 Replay | [기존 AIRun 조회 및 Replay/Conflict 처리](../../../../backend/apps/inquiries/services/inquiry_ai_service.py#L118-L150) | 기반 존재 |
| 상태 이력 중복 방지 | [`inquiry + state_version` 조건부 UniqueConstraint](../../../../backend/apps/workflow/models/transition_history.py#L113-L120) | 기반 존재 |
| State Version Guard | [`request.state_version == inquiry.state_version`, 실패 시 409](../../../../contracts/state-machine/transition-guards.yaml#L229-L242) | 계약 존재 |
| Timeout 전용 Event | [등록된 AI 결과 Event는 `DANGER_DETECTED`, `NO_EVIDENCE` 등](../../../../contracts/state-machine/inquiry-events.yaml#L456-L483) | 전용 Event 없음 |
| No-Evidence 의미 | [정상 검색 완료 후 근거 0건은 HTTP 200 Fallback](../../../../contracts/ai/README.md#L59-L61) | 504와 의미가 다름 |

## 5. Timeout에 `NO_EVIDENCE`를 바로 재사용하면 안 되는 이유

계약은 다음 두 경우를 분리한다.

| 경우 | 계약 결과 | 의미 |
| --- | --- | --- |
| AI 전체 처리 Timeout | `AI-TIMEOUT-01`, HTTP 504, `failure_stage=CANCELLED` | 처리를 완료하지 못함 |
| 정상 검색 후 근거 0건 | HTTP 200, `FALLBACK`, `failure_stage=RETRIEVING`, 빈 Evidence | 검색을 완료했으나 사용할 근거가 없음 |

근거는 [AI 오류 계약](../../../../contracts/ai/README.md#L45-L61)과
[Timeout 예제](../../../../contracts/ai/examples/fallback/timeout-error.json#L12-L25)다.
Timeout을 `NO_EVIDENCE`로 암묵 치환하면 “검색 완료”와 “처리 미완료”를 같은
업무 Event로 기록하게 된다. 상담 전환이라는 목표 상태가 같더라도 감사 사유와
재처리 정책이 다르므로, Timeout 전용 SYSTEM Event 또는 PM이 승인한 명시적
매핑이 먼저 필요하다.

## 6. 최지용 담당 Gate

```text
timeout_backend_owner=최지용
timeout_backend_priority=P1_INTEGRATION_COMPLETION_GATE
timeout_backend_event_contract=AI-TIMEOUT-01을 CONSULTATION_REQUIRED로 연결할 SYSTEM Event 및 Guard 매핑 승인
timeout_backend_completion=AI Timeout(504 매핑) AIRun 저장 + CONSULTATION_REQUIRED 상담 전환 1회만 적용 + state_version/Guard 검증 + SYSTEM TransitionHistory 원자 저장
```

Backend 담당은 구현 주관을 유지한다. Timeout Event 코드 추가나 기존 Event 매핑에
PM·State Machine 계약 승인이 필요하면 그것을 선행 입력으로 명시하되, Backend
완료 책임을 다른 담당자에게 이전한 것으로 처리하지 않는다.

## 7. 완료 판정 체크리스트

### 7.1 Timeout 감사 저장

- [ ] `AIRun` 정확히 1건
- [ ] `status_code=TIMED_OUT`
- [ ] `error_code=AI-TIMEOUT-01`
- [ ] Backend 자동 재시도 `0회`
- [ ] `retry_count=0`, `latency_ms`, `completed_at` 저장
- [ ] 고객 입력, Prompt, Stack Trace, Secret이 오류·로그에 노출되지 않음

### 7.2 상담 전환

- [ ] 적용 전 Inquiry Row Lock과 최신 `state_version` 재검증
- [ ] 승인된 Timeout SYSTEM Event와 Guard 사용
- [ ] `QUESTIONNAIRE_IN_PROGRESS → CONSULTATION_REQUIRED`
- [ ] `state_version` 정확히 `+1`
- [ ] SYSTEM `TransitionHistory` 정확히 1건
- [ ] AIRun 실패 저장은 보존하고 고객 증상 원문은 덮어쓰지 않음

### 7.3 중복·경합

- [ ] 동일 `ai_request_id` Replay의 추가 AI 호출 `0회`
- [ ] Replay의 추가 상담 전환 `0회`
- [ ] Replay의 추가 Version 증가 `0회`
- [ ] Replay의 추가 History `0건`
- [ ] 다른 Payload로 같은 Key 재사용 시 Conflict
- [ ] stale `state_version`이면 AIRun 감사 저장만 유지하고 전이 `0회`
- [ ] Guard 실패 시 Inquiry와 History 부분 적용 `0건`

### 7.4 검증 증거

- [ ] 결정적 `httpx.ReadTimeout` 단위 테스트 PASS
- [ ] 상태·Version·History·Replay·stale·Guard Assertion 포함
- [ ] 실제 Backend→AI 지연 주입 HTTP E2E PASS
- [ ] 실제 공동 HTTP Timeout을 실행하지 않았다면 `NOT_RUN` 명시
- [ ] 단위 테스트 PASS를 실제 공동 HTTP 주입 PASS로 표현하지 않음

## 8. 현재 검증 결과와 제한

Python `3.13.13`에서 다음 기존 테스트를 실행했다.

```powershell
.\backend\.venv\Scripts\python.exe -m pytest `
  backend\tests\unit\ai_integration\test_inquiry_ai_service.py::test_error_contract_and_timeout_are_audited_without_backend_retry `
  backend\tests\unit\ai_integration\test_inquiry_ai_service.py::test_no_evidence_result_routes_to_consultation_required `
  backend\tests\unit\ai_integration\test_inquiry_ai_service.py::test_stale_response_is_audited_without_overwriting_domain_results `
  -q
```

결과:

```text
3 passed in 5.95s
```

이 결과가 증명하는 범위는 Timeout 감사 저장, 기존 No-Evidence 상담 전환과 검증된
성공 결과의 stale 차단이다. 아래 항목은 아직 완료 증거가 아니다.

- Timeout 자체의 `CONSULTATION_REQUIRED` 자동 전환
- Timeout Replay의 상태 전이 중복 방지
- Timeout 전이의 stale Version·Guard 검증
- 실제 Backend→AI 공동 HTTP Timeout 주입

따라서 현재 Timeout 상담 전환 Gate 상태는 `OPEN`, 실제 공동 HTTP Timeout 상태는
`NOT_RUN`으로 기록한다.

## 9. 담당자 회신 형식

```text
timeout_backend_status=<OPEN|IN_PROGRESS|PASS|BLOCKED>
timeout_backend_owner=최지용
timeout_backend_commit=<40자리 SHA>
timeout_backend_event=<승인된 SYSTEM Event 코드>
timeout_backend_transition=<before → after>
timeout_backend_state_version=<before → after>
timeout_backend_airun=<status/error_code/retry_count>
timeout_backend_replay=<AI 추가 호출/전이/Version 증가/History 추가 건수>
timeout_backend_stale=<AIRun 저장 여부/전이 건수>
timeout_backend_guard=<검증 Guard와 결과>
timeout_backend_unit_test=<명령/Exit/PASS 수>
timeout_backend_live_http=<PASS|NOT_RUN, 명령/Exit/DB 증거>
timeout_backend_remaining=<NONE 또는 담당자·필요 입력·완료 조건>
```
