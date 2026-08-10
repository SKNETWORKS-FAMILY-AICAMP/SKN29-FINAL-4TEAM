# Django REST API 문의 AI Runtime Wiring·실제 Mock HTTP 구현·검증 가이드

> 기준일: 2026-08-10 KST
>
> 범위: `SUBMIT_SYMPTOM` 저장 완료 후 Backend→AI 분석 1회 호출
>
> 작성자 판정: `AUTHOR_ACTUAL_MOCK_HTTP_PASS`
>
> 전체 판정: `POST_COMMIT_SYNC_DISPATCH / LOCAL_RAG_PENDING / QA_PENDING / T022_PARTIAL`

## 1. 결론

고객이 `POST /api/v1/inquiries/{id}/submit`을 성공하면 DB Transaction을
먼저 확정한 뒤 `InquiryAIService.analyze_inquiry()`를 정확히 한 번 호출한다.
실제 Django 소켓→`AIClient`→실제 FastAPI Uvicorn Mock→AIRun·Assessment·
Guidance 저장까지 작성자 환경에서 통과했다.

| 항목 | 현재 판정 |
| --- | --- |
| 고객 증상 저장·상태 전이 | 구현·회귀 PASS |
| Commit 후 AI 호출 Wiring | 구현·표적 Test PASS |
| 실제 FastAPI Mock HTTP | 작성자 실제 소켓 PASS |
| 동일 Key Replay | AI 재호출·중복 저장 0 |
| AI 실패 | 고객 입력·상태·이력·멱등 결과 보존 |
| Local RAG·pgvector | 미실행 |
| 팀 DB·Chunk Crosswalk | Mock 단계 비필수, Local E2E 전 별도 Gate |
| 비작성자 독립 QA·PM 완료 | 대기 |

따라서 “Backend Runtime 호출점 없음”은 이번 후보에서 해소됐다. 다만
Mock PASS를 실제 RAG·팀 DB·T-022 전체 완료로 확대하지 않는다.

## 2. 호출 흐름

```text
CUSTOMER POST /inquiries/{id}/submit
  -> SubmitSymptomView
  -> InquiryTransitionService.submit_symptom()
  -> Inquiry·state_version·History·Idempotency 원자 저장
  -> 응답 Serializer 성공
  -> DB COMMIT
  -> transaction.on_commit(robust=True)
  -> InquiryAIService.analyze_inquiry()
  -> AIClient POST /api/v1/ai/analyze?mode=mock
  -> AI Schema·식별자 Echo 검증
  -> AIRun·SymptomAssessment·Guidance 저장
  -> Guard를 통과한 경우에만 State Event 적용
```

주요 구현:

- [증상 제출 View](../../../../backend/apps/inquiries/api/views.py)
- [증상 전이·Commit Callback](../../../../backend/apps/inquiries/services/inquiry_transition_service.py)
- [AI 실행·저장 Service](../../../../backend/apps/inquiries/services/inquiry_ai_service.py)
- [실제 HTTP Client](../../../../backend/integrations/ai/client.py)
- [TR-INQ-002](../../../../contracts/state-machine/transition-rules.yaml)
- [AI 계약 3.0.0](../../../../contracts/ai/README.md)

## 3. Transaction·멱등 경계

| 상황 | 보장 |
| --- | --- |
| 신규 성공 | 상태·버전·이력·멱등 응답을 먼저 Commit한 뒤 AI 1회 |
| 같은 Key·같은 Body Replay | 저장 응답 Replay, AI Callback 추가 등록 0 |
| 같은 Key·다른 Body | 409, AI 호출 0 |
| 상태·Guard·Serializer 실패 | 전체 Rollback, AI 호출 0 |
| AI Timeout·계약 오류 | AIRun 실패 기록, 고객 제출 성공은 유지 |
| 예상 밖 Callback 예외 | `robust=True`로 제출 Rollback 금지, 로그로 추적 |
| AI 결과 수신 중 Version 변경 | stale 판정, 최신 Domain 덮어쓰기 금지 |

AI 호출 ID는 제출 멱등 원장의 Public UUID를 사용한다. 같은 고객 요청이
Replay돼도 AI 실행 ID가 새로 만들어지지 않는다. `correlation_id`는 고객
요청 Header→History→AI Header·Body→AIRun·AI 응답에 동일하게 보존한다.

## 4. 동기 Dispatch의 한계

현재 Callback은 Commit 이후 실행되지만 같은 Django Request Process에서
동기 실행된다. DB Lock을 잡고 HTTP를 기다리지는 않지만 AI 응답 시간만큼
고객 응답 지연이 늘 수 있다.

다음은 이번 Slice의 완료 범위가 아니다.

- Process가 Commit 직후 종료돼도 재전송하는 Durable Outbox·Worker
- 예상 밖 실패의 자동 Retry·관리자 재처리 API
- 실제 `mode=local` RAG·pgvector 검색
- Canonical Chunk→Backend Evidence Crosswalk
- 팀 DB 최소 권한 Role·DSN과 원격 TLS

Outbox가 필요하면 동일 Callback에 숨겨 추가하지 않고 Event 계약·재처리
정책·중복 방지키를 승인한 별도 Forward Slice로 구현한다.

## 5. 구현 파일

| 파일 | 변경 의미 |
| --- | --- |
| `backend/apps/inquiries/services/inquiry_transition_service.py` | 성공 신규 Write에만 Commit Callback 등록 |
| `backend/tests/api/test_t022_submit_symptom.py` | Commit 전 미호출·1회 호출·Replay·실패보존·Rollback 검증 |
| `backend/tests/integration/test_backend_ai_submit_symptom_live_http.py` | 실제 Django·Uvicorn 소켓과 AI DB 저장 검증 |

Model·Migration·Seed·OpenAPI·AI Schema는 변경하지 않았다.

## 6. 실제 Mock HTTP 재현

저장소 루트 기준으로 AI와 Backend를 서로 다른 Terminal에서 실행한다.
실제 Secret·DSN은 명령이나 문서에 기록하지 않는다.

### 6.1 AI Terminal

```powershell
python -m venv .\ai\.venv
.\ai\.venv\Scripts\python.exe -m pip install -r .\ai\requirements.lock
.\ai\.venv\Scripts\python.exe -m pip check
.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app `
  --host 127.0.0.1 --port 8001
```

### 6.2 Backend Test Terminal

```powershell
$env:BACKEND_AI_LIVE_HTTP_TEST = "1"
$env:BACKEND_AI_TEST_BASE_URL = "http://127.0.0.1:8001"
$python = ".\backend\.venv\Scripts\python.exe"

& $python -m pytest -vv -p no:cacheprovider `
  backend/tests/integration/test_backend_ai_submit_symptom_live_http.py
```

이 Test는 다음을 한 번에 확인한다.

1. 실제 `/health` 200
2. 실제 Demo Login·문의 생성·증상 제출 HTTP
3. AI `/analyze?mode=mock` 정확히 1회 200
4. 요청·응답 Contract `3.0.0`과 UUID Echo
5. AIRun `SUCCEEDED`, Schema `PASSED`
6. Assessment·Guidance 각 1건과 문의 Projection
7. 같은 제출 Replay 뒤 모든 AI 저장 수량 불변

## 7. 2026-08-10 검증 결과

| 검증 | 결과 |
| --- | --- |
| AI `pip check` | `No broken requirements found` |
| AI 전체 Unit | `121 passed, 3 warnings` |
| 실제 Django→Uvicorn Mock HTTP | `1 passed` |
| 관련 Backend 표적 | `58 passed, 3 skipped` |
| Root 계약 Test | `12 passed` |
| OpenAPI | PASS, 108 YAML·32 Path·33 Operation |
| State Machine | PASS, 13 State·30 Event·34 Transition |
| Action Crosswalk | PASS, Runtime 12·OpenAPI 7·Deferred 4 |
| Code·Example | PASS, Code 144·Example 50/50 |
| Django Check·Migration Drift | `0 issue`, `No changes detected` |
| 빈 SQLite Migration→`migrate --check` | PASS |
| Backend 전체 | `936 passed, 16 skipped, 0 failed` |

Backend 전체의 16 Skip에는 PostgreSQL 전용 Catalog·Row Lock·Composite FK,
명시적 TEAM_INTEGRATION Role Test와 기본 비활성 실제 HTTP Test가 포함된다.
실제 HTTP Test는 별도 opt-in 실행에서 PASS했다. PostgreSQL 전용 결과는
이번 SQLite·Mock 증거로 대체하지 않는다.

## 8. 다음 작업과 인계

| 우선순위 | 작업 | 담당·조건 |
| ---: | --- | --- |
| 1 | 이동윤과 같은 명령으로 실제 Mock 공동 재현 | Backend·AI 담당 |
| 2 | 김은진 독립 Backend 회귀·Callback 경계 QA | 깨끗한 동일 후보 |
| 3 | `mode=local` RAG·격리 pgvector F01/F02 | Mock PASS 뒤 AI·QA |
| 4 | Chunk Crosswalk·Evidence 검증 | Local 검색 결과 수신 뒤 |
| 5 | Durable Outbox·재처리 필요성 결정 | PM·Backend·AI 계약 |

QA 회신에는 후보 Commit, AI·Backend Python, 실행 명령·Exit Code, HTTP
호출 수, AIRun·Assessment·Guidance의 PII 없는 건수, Test 수와 남은 Skip을
기록한다. `.env`, Token, Password, DSN, 고객 원문은 전달하지 않는다.

## 9. 관련 문서

- [문의·증상 제출 구현·검증·인계서](Django_REST_API_문의_증상제출_구현_검증_인계서.md)
- [8/9 AI 결과 저장·상태 전이 역사 보고서](Django_REST_API_문의_AI결과저장_상태전이_후속API_검증보고서_20260809.md)
- [Backend·AI 계약 미해결 사항](../연동_인계/Backend_AI_API_계약_구현_미해결_사항.md)
- [AI 실행 가이드](../../../../ai/README.md)
