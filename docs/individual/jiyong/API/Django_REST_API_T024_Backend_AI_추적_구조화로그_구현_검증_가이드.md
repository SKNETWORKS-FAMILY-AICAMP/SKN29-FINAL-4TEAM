# Django REST API T-024 Backend AI 추적·구조화 로그 구현·검증 가이드

> 작성자: 최지용 — Backend·DB
> 작성일: 2026-08-11 KST
> 대상: `T-024` 중 Backend→AI 최소 추적 Slice
> 판정: **작성자 검증 PASS / T-024 전체는 진행 중 / 독립 QA 대기**

## 1. 결론

이번 Slice는 `SUBMIT_SYMPTOM`의 업무 Commit 이후 AI Callback부터 AI 분석
종료까지 안전한 구조화 로그로 연결한다.

```text
backend_ai_trace_slice=AUTHOR_PASS
live_mock_http_trace=PASS
t024_overall=PARTIAL
independent_qa=NOT_RUN
migration_change=NONE
contract_change=NONE
remote_push=NOT_PERFORMED
```

T-024 전체 완료로 올리지 않는다. RAG 검색 근거 Lineage, 모델·생성 정보 전체,
상담·방문을 포함한 주요 사용자 행위 추적은 T-023과 AI·RAG 후속 Runtime이
완료된 뒤 별도 검증해야 한다.

## 2. 해결한 공백

| 공백 | 반영 내용 |
| --- | --- |
| Callback 시작·종료를 재현하기 어려움 | `CALLBACK_STARTED`, `CALLBACK_COMPLETED` 구조화 로그 추가 |
| 예상 밖 Callback 오류가 Django 기본 로그로 재노출될 위험 | 원문·Traceback을 재발생시키지 않고 안전한 오류 코드만 기록 후 종료 |
| AI 실행 결과의 stale·보류 이유 확인 어려움 | 상태·후보 Event·적용 여부·보류 사유를 Allowlist 필드로 기록 |
| 임의 Correlation 문자열 로그 주입 가능성 | UUID 정규화에 성공한 명시값만 보존하고 나머지는 요청 Context로 대체 |
| 로그 식별자와 DB 원장의 연결 근거 부족 | 실제 Mock HTTP Test에서 History·Idempotency·AIRun 연결을 검증 |

## 3. Runtime 흐름

```text
고객 SUBMIT_SYMPTOM
→ Inquiry·TransitionHistory·IdempotencyRecord Commit
→ ai_callback_started
→ AI 요청 계약 검증
→ ai_analysis_started
→ 실제 HTTP /analyze?mode=mock
→ AIRun·Assessment·Guidance 저장
→ ai_analysis_terminal
→ ai_callback_completed
```

같은 요청의 Replay는 기존 업무 응답만 재사용하고 AI Callback과 AIRun을
추가 생성하지 않는다.

## 4. 구조화 로그 허용 필드

다음 Metadata만 JSON 로그에 허용한다.

- `correlation_id`
- `trace_stage`
- `inquiry_id`
- `ai_request_id`
- `ai_run_id`
- `ai_status`
- `event_candidate`, `event_applied`
- `pending_reason`
- `idempotent_replay`, `stale`
- `failure_code`, `latency_ms`

다음 값은 기록하지 않는다.

- 고객 자연어 증상과 추가 답변
- AI 요청·응답 Payload 전체
- Prompt·검색 문서 원문·Evidence 본문
- Token·Secret·DSN·Password
- 예외 메시지·Stack Trace에 포함될 수 있는 원문

## 5. 오류 경계

### 5.1 예상된 AI 오류

Timeout·계약 오류는 고객 입력과 업무 Commit을 되돌리지 않는다. AIRun 상태와
안전한 `failure_code`만 Warning 로그에 남긴다.

### 5.2 예상 밖 Callback 오류

Callback은 이미 업무 Transaction이 Commit된 뒤 실행된다. 따라서 오류를 다시
던져 고객 저장 결과를 변경하지 않고 다음 안전 로그만 남긴다.

```text
message=ai_callback_failed_unexpected
trace_stage=CALLBACK_FAILED_UNEXPECTED
failure_code=UNEXPECTED_CALLBACK_ERROR
```

오류 메시지를 Django 기본 Logger로 다시 넘기지 않아 고객 입력·Upstream
Payload가 일반 로그로 새어 나가는 경로를 닫는다.

## 6. DB 추적 연결

실제 Mock HTTP Test는 같은 제출 1건에서 다음을 검증한다.

- `TransitionHistory.inquiry_id == AIRun.inquiry_id`
- `TransitionHistory.correlation_id == AIRun.correlation_id`
- `AIRun.idempotency_key == str(IdempotencyRecord.public_id)`
- AI 요청·응답 Echo의 `correlation_id`가 동일함
- Replay 이후 AIRun·Assessment·Guidance 수량이 증가하지 않음

이 연결은 Commit 문자열이 아니라 업무 UUID와 DB 원장으로 재현한다.

## 7. 변경 파일

| 구분 | 파일 |
| --- | --- |
| AI Callback 추적 | `backend/apps/inquiries/services/inquiry_transition_service.py` |
| AI 분석 Lifecycle 추적 | `backend/apps/inquiries/services/inquiry_ai_service.py` |
| 로그 Correlation 검증 | `backend/common/logging/filters.py` |
| 안전 필드 Allowlist | `backend/common/logging/formatter.py` |
| API Callback 회귀 | `backend/tests/api/test_t022_submit_symptom.py` |
| AI 결과·로그 회귀 | `backend/tests/unit/ai_integration/test_inquiry_ai_service.py` |
| 공통 로그 보안 회귀 | `backend/tests/unit/common/test_logging.py` |
| 실제 HTTP·DB 원장 연결 | `backend/tests/integration/test_backend_ai_submit_symptom_live_http.py` |

AI 담당자의 Runtime·계약 파일과 DB Migration은 변경하지 않았다.

## 8. 작성자 검증

### 8.1 표적 회귀

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  tests/unit/common/test_logging.py `
  tests/api/test_t022_submit_symptom.py `
  tests/unit/ai_integration/test_inquiry_ai_service.py
```

결과: `42 passed, 2 skipped`, Exit Code `0`. Skip 2건은 기존 PostgreSQL
Row Lock 전용 Case다.

### 8.2 실제 Uvicorn Mock HTTP

AI Mock 서버를 `127.0.0.1:8001`에 실행한 뒤 opt-in Test를 수행했다.

```powershell
$env:BACKEND_AI_LIVE_HTTP_TEST = "1"
$env:BACKEND_AI_TEST_BASE_URL = "http://127.0.0.1:8001"
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  tests/integration/test_backend_ai_submit_symptom_live_http.py
```

결과: `1 passed`, Exit Code `0`.

### 8.3 Backend 전체 통합 회귀

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

결과: `966 passed, 17 skipped`, Exit Code `0`. Skip은 PostgreSQL 전용
구조·Row Lock·팀 통합 Role Case와 opt-in 실제 HTTP Case다. 실제 HTTP Case는
8.2에서 별도로 실행해 PASS했다.

## 9. 독립 QA 요청 범위

김은진 QA는 현재 후보를 동일 환경에서 다음 순서로 독립 재현한다.

1. 표적 로그·T-022·AI Integration Test
2. 실제 Uvicorn `mode=mock` HTTP Test
3. 동일 Correlation로 History·Idempotency·AIRun 연결 확인
4. Replay 시 AI 추가 호출·추가 저장 0건 확인
5. Timeout·오류에서 고객 입력과 업무 Commit 보존 확인
6. JSON 로그에 원문·Payload·Secret·예외 메시지 비노출 확인
7. Backend 전체 회귀와 PostgreSQL 대상 회귀

## 10. 남은 작업과 완료 금지선

| 잔여 범위 | 현재 판정 |
| --- | --- |
| RAG RetrievalRun·Hit·Evidence Lineage Runtime 추적 | 미구현 |
| 모델·생성 Metadata 전체 추적 | AI Runtime 후속 필요 |
| 상담·방문·완료 주요 행위 공통 추적 | T-023 후속 필요 |
| PostgreSQL·독립 QA | 대기 |
| T-024 전체 완료 | 금지 |

최종 판정은 **Backend AI 최소 Slice 작성자 PASS**다. 독립 QA와 잔여
Runtime이 완료되기 전에는 `T-024=완료` 또는 소비자 연결 완료로 표시하지 않는다.
