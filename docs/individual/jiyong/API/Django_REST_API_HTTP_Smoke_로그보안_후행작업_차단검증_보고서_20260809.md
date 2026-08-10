# Django REST API HTTP Smoke·로그 보안·후행 작업 차단 검증 보고서

> 검증일: 2026-08-09 KST
> 기준선: 2026-08-08 22:00 KST 기준 `origin/main`(data-ci.yml 충돌 처리 반영) 기반 별도 안전 Worktree
> 판정: `LOCAL_AUTHOR_VERIFIED`
> 게시 범위: `origin/jiyong` 검토 후보

## 1. 결론

외부 회신 없이 검증할 수 있는 범위를 기존 공개 계약 안으로 제한했다.

- T-016은 실제 Socket HTTP Smoke로 기존 Endpoint와 공통 오류 Matrix를 확인했다.
- API 오류 응답은 기존 JSON 예시의 Code·Message 및 공통 Wrapper와 일치한다.
- T-024는 요청·예외 로그의 동일 `correlation_id`와 민감정보 비노출을 확인했다.
- T-019·T-020·T-021은 선행조건이 열릴 때까지 자동으로 차단되는 읽기 전용
  Preflight를 추가했다.
- 운영 Route, 공개 OpenAPI, Model, Migration 및 기존 개발 DB는 변경하지 않았다.

이 결과는 작성자 검증이며 WBS 공식 완료나 독립 QA 승인을 대신하지 않는다.

## 2. 작업 범위

| 구분 | 반영 내용 | 계약·데이터 영향 |
| --- | --- | --- |
| 실제 HTTP Smoke | `/health`, Login, `/me`, 구독 목록·상세, 문의 생성·제출·취소 | 기존 Route만 사용 |
| 오류 Matrix | 400·401·403·404·409·422·500과 공통 Wrapper·예시 정합 | 공개 응답 변경 없음 |
| 로그 보안 | Route Template, 상태, 지연, `correlation_id` 추적 | 로그 Runtime 변경 없음 |
| 후행 Gate | T-019·T-020·T-021 계약·Stub·선행조건 Readiness | 읽기 전용 검사 |

## 3. 실제 HTTP Smoke

테스트는 Django Live Server의 실제 TCP Socket으로 요청한다. 500 검증용 Route는
테스트 모듈의 임시 URLConf에만 존재하며 운영 URL에는 추가하지 않았다.

| 흐름 | 기대 결과 |
| --- | --- |
| `GET /health` | 200, 빈 본문, 요청 UUID Header Echo |
| Demo Login → `GET /api/v1/me` | 200, CUSTOMER Claim·사용자 정보 확인 |
| 구독 목록·상세 | 200, 본인 ACTIVE·지원 제품만 노출 |
| 문의 생성 → 증상 제출 | 201 → 200, 상태 Version 증가 |
| 별도 문의 생성 → 취소 | 201 → 200, `CANCELLED` 전환 |
| 인증 없음·역할 위반·미존재·입력 오류 | 401·403·404·422 |
| 동일 멱등키·다른 Payload | 409 |
| 잘못된 JSON·내부 예외 | 400·500, 내부값 비노출 |

SQLite와 격리 PostgreSQL에서 같은 Smoke를 실행했다. 임시 DB는 검증 직후
삭제했으며 기존 `waterbridge` 개발 DB에는 Migration·Seed·업무 데이터 변경을
적용하지 않았다.

## 4. API 오류 예시 정합

각 실제 오류 응답에 대해 다음을 확인했다.

1. 최상위 Key가 `success`, `data`, `error`, `metadata`로 고정된다.
2. 오류 Key가 `code`, `message`, `details`로 고정된다.
3. `metadata.correlation_id`와 `X-Correlation-ID`가 같다.
4. 기존 `contracts/api/examples/**`의 Code·Message와 같다.
5. 내부 Exception, DB 정보 및 인증정보가 응답에 포함되지 않는다.

## 5. T-024 로그 보안·추적성

404와 500 요청에서 실제 Middleware·Exception Handler·JSON Formatter를 함께
실행했다.

| 검증 항목 | 결과 |
| --- | --- |
| Header·응답 Metadata·요청 로그 `correlation_id` | 동일 UUID |
| 404 로그 Route | 실제 값이 아닌 `/api/v1/<path:unmatched_path>` |
| 500 로그 | 오류 유형만 기록, Exception Message 미기록 |
| Authorization·Cookie | 비노출 |
| Query Secret | 비노출 |
| 고객 `raw_text`·AI `prompt` | 비노출 |

Backend–AI 공개 Dispatch는 구현하거나 호출하지 않았다. 따라서 이 검증은 T-024
전체 완료가 아니라 현재 Backend Route의 보안·추적성 Slice다.

## 6. T-019·T-020·T-021 차단 결과

```text
overall_status=PREPARATION_ONLY
T-019=BLOCKED
T-020=BLOCKED
T-021=BLOCKED
```

| 작업 | 자동 확인된 Blocker |
| --- | --- |
| T-019 | T-018 쓰기 범위 미계약, Care API 계약 `{}`, Care Runtime Stub |
| T-020 | T-019 미완료, NextCareSchedule 속성 공백, 일정 Service·Repository Stub |
| T-021 | T-020 미완료, Questionnaire API 계약 `{}`, Questionnaire Runtime Stub |

차단 중 허용 범위는 계약 공백 목록, Fail-closed Test, 기존 Route 회귀와 증거
문서화다. 공개 Care·Questionnaire Endpoint, 다음 케어 날짜 계산과 관련
Migration은 착수하지 않는다.

## 7. 검증 결과

| 검증 | 결과 |
| --- | --- |
| 변경 전 관련 기능 기준선 | `88 passed, 2 skipped` |
| T-016 실제 HTTP Smoke | SQLite PASS, 격리 PostgreSQL PASS |
| T-024 로그 보안·추적성 및 공통 로그 회귀 | `17 passed` |
| T-019·T-020·T-021 Preflight | `3 passed`, `PREPARATION_ONLY` |
| Django Check | PASS |
| Migration Drift | `No changes detected` |
| 격리 PostgreSQL 전체 Migration | PASS, 미적용 0 |
| 이 Slice 반영 직후 Backend 전체 회귀 | `844 passed, 13 skipped` |
| 후속 AI·Evidence Slice 포함 최종 전체 회귀 | `850 passed, 13 skipped` |

격리 PostgreSQL Base DB와 pytest Test DB는 최종 확인 후 모두 제거했다.

## 8. 작업 파일

| 파일 | 목적 |
| --- | --- |
| `backend/tests/integration/test_t016_live_http_smoke.py` | 실제 HTTP·오류 예시 Matrix |
| `backend/tests/integration/test_t024_request_trace_security.py` | 로그 추적·민감정보 비노출 |
| `scripts/contracts/audit_overdue_backend_runtime_gates.py` | 후행 Runtime 읽기 전용 Preflight |
| `backend/tests/unit/care/test_overdue_backend_runtime_gates.py` | Gate Fail-closed 회귀 |

## 9. 재현 명령

후보 파일을 포함한 동일 checkout의 저장소 루트에서 실행하며 `.env`, Token과
DSN을 출력하지 않는다.

```powershell
$python = ".\backend\.venv\Scripts\python.exe"

& $python -B -m pytest -q -p no:cacheprovider `
  backend/tests/integration/test_t016_live_http_smoke.py `
  backend/tests/integration/test_t024_request_trace_security.py `
  backend/tests/unit/care/test_overdue_backend_runtime_gates.py

& $python -B scripts/contracts/audit_overdue_backend_runtime_gates.py
```

PostgreSQL 재현은 개발 DB가 아닌 별도 임시 DB에서 수행한다.

## 10. 다음 진행 조건

1. T-018 쓰기 계약 확정 전 T-019 Runtime을 시작하지 않는다.
2. Care API와 일정 규칙 확정 후 T-019 → T-020 순서로 Gate를 갱신한다.
3. T-020 완료 뒤 Questionnaire 계약을 기준으로 T-021을 시작한다.
4. 각 Runtime 후보는 표적 → PostgreSQL → 전체 회귀 → 독립 QA 순으로 검증한다.

## 11. 관련 문서

- [Backend 작성자 회귀검증 보고서](../개발환경/Django_PostgreSQL_Backend_작성자_회귀검증_보고서_20260808.md)
- [문의 AI 결과 저장·상태 전이·후속 API 검증 보고서](Django_REST_API_문의_AI결과저장_상태전이_후속API_검증보고서_20260809.md)
- [AI 상태 이벤트·EvidenceCard 계약 준비 검증 보고서](Django_REST_API_AI_상태이벤트_EvidenceCard_계약준비_검증보고서_20260809.md)
