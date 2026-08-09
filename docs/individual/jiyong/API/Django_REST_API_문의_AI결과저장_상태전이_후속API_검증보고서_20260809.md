# Django REST API 문의 AI 결과 저장·상태 전이·후속 API 검증 보고서

> 검증일: 2026-08-09 KST
> 범위: T-022·T-023·Backend–AI 내부 처리 Slice
> 기준선: 2026-08-08 22:00 KST 기준 `origin/main`(data-ci.yml 충돌 처리 반영) 기반 별도 안전 Worktree
> 판정: `LOCAL_AUTHOR_VERIFIED / PUBLIC_DISPATCH_NOT_CONNECTED`
> 게시 범위: `origin/jiyong` 검토 후보

## 1. 결론

기존 T-022·T-023 문서는 최초 증상 제출과 기본 상태 Engine을 설명하지만,
최근 추가된 AI 결과의 내부 저장·전이 처리를 반영하지 못한다. 이 문서는 해당
증분만 현재화한다.

| 구분 | 현재 상태 |
| --- | --- |
| AI Client·요청/응답 Mapper·Schema 검증 | 내부 구현·단위 검증 |
| AI 실행·결과 저장 Service | 내부 구현·Transaction 검증 |
| AIRun·Assessment·Guidance·Follow-up 저장 | 내부 구현·Replay/Conflict 검증 |
| AI 결과 기반 상태 전이·이력 | 제한 구현·Guard 검증 |
| 공개 View·Job·Queue Dispatch | 미연결 |
| 실제 FastAPI·PostgreSQL 공동 E2E | 미실행 |

따라서 내부 Backend 후보는 검증했지만 T-022·T-023 또는 Backend–AI 연동을
공식 완료로 판정할 수 없다.

## 2. 구현 구조

| 계층 | 책임 | 주요 파일 |
| --- | --- | --- |
| AI Adapter | HTTP 호출, Timeout·Retry, 응답 수신 | `backend/integrations/ai/client.py`, `retry_policy.py` |
| Mapper | 문의 Domain ↔ AI Schema 변환 | `request_mapper.py`, `response_mapper.py` |
| Validator | 요청·응답 JSON Schema 검증 | `schema_validator.py` |
| 실행 원장 | 요청 상태·Hash·응답·오류 추적 | `backend/apps/audit/models/ai_run.py` |
| 적용 Service | 실행, 잠금, 저장, 상태 전이 | `backend/apps/inquiries/services/inquiry_ai_service.py` |
| 결과 Model | Assessment·Guidance·QA 저장 | `backend/apps/inquiries/models/` |
| Workflow | Transition History 기록 | `backend/apps/workflow/services/transition_history_service.py` |

AI 호출 실패는 Domain 원문을 덮어쓰지 않으며 내부 예외와 Prompt·원문을 API
응답이나 일반 로그에 노출하지 않는다.

## 3. Transaction·동시성 경계

외부 HTTP 호출은 DB Transaction 밖에서 수행한다. 네트워크 대기 중 Row Lock을
유지하지 않기 위한 경계다. 응답을 Domain에 반영할 때만 단일 Atomic 구간을
열고 문의를 `select_for_update`로 다시 잠근다.

| 상황 | 처리 |
| --- | --- |
| 같은 요청 ID·같은 Payload | 저장된 결과 Replay, 중복 Domain 적용 금지 |
| 같은 요청 ID·다른 Payload | Conflict 처리 |
| 호출 중 문의 Version 변경 | stale 판정, Domain 결과 적용 0 |
| 저장 중 예외 | Assessment·Guidance·QA·상태·이력 전체 Rollback |
| 적용 성공 | AI 결과와 Workflow History를 같은 Transaction에 기록 |

`state_version`은 호출 전 값과 적용 시점 값을 비교한다. stale 결과는 AIRun
추적 정보만 남기고 고객 안내나 문의 상태를 갱신하지 않는다.

## 4. AI 결과별 적용 규칙

| 결과 | 저장·전이 | 안전 경계 |
| --- | --- | --- |
| `SAFE_GUIDANCE_READY` | 검증 Evidence가 있을 때 Guidance 저장 후 `AI_GUIDANCE` | 공식 근거 없으면 적용 금지 |
| `NO_EVIDENCE` | 근거 없음 기록 후 `CONSULTATION_REQUIRED` | 임의 자가조치 생성 금지 |
| `DANGER_DETECTED` | 위험 결과 보존, 상담 전이 후보 | 매칭된 Safety Rule ID 전에는 자동 적용 보류 |
| Follow-up 질문 | Inquiry QA로 저장 | 상태 자동 진전 없음 |

이 표는 내부 적용 규칙이다. 공개 Dispatch가 연결되지 않았으므로 실제 사용자
요청 흐름에서 자동 실행된다는 뜻이 아니다.

## 5. T-022 공개 Runtime 경계

현재 공개 Runtime에서 검증된 기본 흐름은 다음과 같다.

- 문의 생성
- 증상 제출
- 문의 취소
- 역할·소유권·상태·Version·멱등·오류 응답

다음 두 Operation은 OpenAPI-only이며 Runtime 착수를 차단한다.

- `PATCH /inquiries/{id}/questionnaire`
- `POST /inquiries/{id}/action-results`

Readiness가 탐지하는 계약 공백은 다섯 개다.

1. Questionnaire Path ID의 UUID 확정
2. Questionnaire `Idempotency-Key` 선언
3. `answers`의 저장 가능한 Typed Schema 확정
4. Action Result Path ID의 UUID 확정
5. Action Result `Idempotency-Key` 선언

`--require-deferred-runtime-contracts`는 현재 의도한 종료코드 `3`을 반환한다.
이는 기존 문의 Runtime 장애가 아니라 후속 쓰기 Endpoint의 Fail-closed Gate다.

## 6. T-023 상태 전이 경계

기존 START·SUBMIT·CANCEL과 Engine의 Role·State·Payload Guard, Replay, 409 최신값,
이력은 회귀 검증 대상이다. 이번 증분에서는 AI 결과 적용을 위해 SYSTEM 수행자와
전이 이력 저장을 내부 Service에서 연결했다.

다음 항목은 여전히 별도 계약·Runtime이 필요하다.

- 상담 요청·상담 시작·임시 저장·완료
- 방문 전환·일정 저장·확정
- 실제 상담사·기사 배정 Guard
- 신규 Event별 `allowed_actions`
- 수행자·사유·`correlation_id`를 포함한 공개 E2E

## 7. 검증 증거

| 검증 | 결과 |
| --- | --- |
| AI Adapter·Schema·Mapper 단위 Test | PASS |
| InquiryAIService Replay·Conflict·stale·Rollback Test | PASS |
| AI Mapper ↔ 승인 State Event 정합 | `3 passed` |
| T-022 Readiness 단위 Test | `35 passed` |
| AI·State Machine·Evidence 관련 회귀 | `240 passed, 8 skipped` |
| 최종 Backend 전체 회귀 | `850 passed, 13 skipped` |

최종 전체 수치는 이 문서만의 Test 수가 아니라 2026-08-09 안전 Worktree에
누적된 작성자 회귀 결과다. 신규 AI·Evidence Slice의 PostgreSQL 검증은 Docker
미실행으로 `NOT_RUN`이며 과거 PASS를 신규 PASS로 확대하지 않는다.

## 8. 재현 명령

후보 파일을 포함한 동일 checkout의 저장소 루트에서 실행한다.

```powershell
$python = ".\backend\.venv\Scripts\python.exe"

& $python -m pytest -q -p no:cacheprovider `
  backend/tests/unit/ai_integration/test_ai_adapter.py `
  backend/tests/unit/ai_integration/test_inquiry_ai_service.py `
  backend/tests/unit/ai_integration/test_ai_state_event_contract_conformance.py

& $python backend/apps/inquiries/readiness.py `
  --require-deferred-runtime-contracts
```

마지막 명령은 계약 공백이 남아 있는 동안 의도적으로 Exit 3을 반환한다.

## 9. 착수 금지·후속 조건

| 범위 | 현재 판정 | 해제 조건 |
| --- | --- | --- |
| 공개 AI View·Job·Queue | `NOT_CONNECTED` | AI 담당자 Mapping 공동 확인·Dispatch 계약 |
| 실제 FastAPI E2E | `NOT_RUN` | 실행 환경·Schema·Timeout·Retry 합의 |
| T-022 후속 쓰기 | `BLOCKED` | 5개 계약 공백 해소 |
| T-023 신규 Event | `BLOCKED` | Event·Role·Guard·Effect 확정 |
| T-019 Runtime | `BLOCKED` | T-018 전체 범위 완료·Care 계약 확정 |

## 10. 관련 문서

- [문의·증상제출 구현·검증·인계서](Django_REST_API_문의_증상제출_구현_검증_인계서.md)
- [State Machine API 구현·검증·인계서](Django_State_Machine_API_구현_검증_인계서.md)
- [Backend·AI API 계약·구현 미해결 사항](../연동_인계/Backend_AI_API_계약_구현_미해결_사항.md)
- [AI 상태 이벤트·EvidenceCard 계약 준비 검증 보고서](Django_REST_API_AI_상태이벤트_EvidenceCard_계약준비_검증보고서_20260809.md)
