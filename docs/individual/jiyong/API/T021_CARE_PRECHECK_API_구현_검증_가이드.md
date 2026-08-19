# T-021 CARE_PRECHECK API 구현·검증 가이드

## 1. 문서 정보

- 담당: 최지용 — Backend·Database
- 작성일: 2026-08-19 KST
- 기준선: `origin/main@50f323581c36cde3d64c1ef8a265db16cb3cdb70`
- 상태: `AUTHOR_VERIFIED / COMMIT_NOT_CREATED / INDEPENDENT_QA_PENDING`
- 범위: 고객 사전 문진 Session 생성·복구·저장·제출과 신규 문의 1회 연결

이 문서는 T-021을 처음부터 다시 설계하기 위한 문서가 아니다. 구현된
Runtime의 사용 방법, 안전 경계, 검증 결과를 다른 작업자가 빠르게 확인할 수
있게 정리한다.

## 2. 구현 결과를 쉽게 설명하면

고객은 문의를 만들기 전에 정수기 상태를 사전 문진으로 작성할 수 있다.
문진은 문의와 독립적으로 시작되며 다음 세 상태를 가진다.

```text
UNANSWERED
  → 답변 임시 저장
IN_PROGRESS
  → 최종 제출
SUBMITTED
  → 상담이 필요할 때 신규 Inquiry에 1회 연결
```

문진 제출 자체가 문의를 자동 생성하지 않는다. 상담이 필요한 경우에만 기존
문의 생성 API에 `questionnaire_session_id`를 포함한다. Backend는 제출 완료,
고객 본인 소유, 동일 구독, 아직 미연결인 Session인지 확인하고 새 Inquiry와
같은 Transaction에서 연결한다.

## 3. API 계약

| 기능 | Method·Path | 주요 입력 | 성공 |
| --- | --- | --- | --- |
| 문진 시작 | `POST /api/v1/me/questionnaire-sessions` | `subscription_id` | `201` |
| 문진 복구 | `GET /api/v1/me/questionnaire-sessions/{session_id}` | 없음 | `200` |
| 답변 저장 | `PATCH /api/v1/me/questionnaire-sessions/{session_id}` | `state_version`, `answers` | `200` |
| 문진 제출 | `POST /api/v1/me/questionnaire-sessions/{session_id}/submit` | `state_version`, `answers` | `200` |
| 문의 연결 | `POST /api/v1/inquiries` | 기존 문의 입력 + `questionnaire_session_id` | `201` |

쓰기 API에는 `Idempotency-Key`가 필요하다. 저장과 제출은 현재
`state_version`을 함께 보내야 한다. `answers`는 질문 코드를 Key로 사용하는
전체 Snapshot이며 저장할 때 기존 답변을 교체한다.

계약 SSOT:

- `contracts/api/paths/questionnaires.yaml`
- `contracts/api/components/schemas/questionnaire/**`
- `contracts/api/examples/questionnaires/**`
- `contracts/api/openapi.yaml`

## 4. 데이터와 Transaction 경계

주요 테이블은 다음과 같다.

| 역할 | 모델·테이블 |
| --- | --- |
| 사전 문진 정본 | `QuestionnaireSession` / `support_questionnaire_session` |
| 문의 정본 | `Inquiry` / `support_inquiry` |
| 상태·행위 이력 | `TransitionHistory` / `workflow_transition_history` |
| 멱등 처리 | `IdempotencyRecord` / `workflow_idempotency_record` |

문진 시작·저장·제출과 상태 이력·멱등 레코드는 각각 하나의 Transaction으로
처리된다. 문의 연결은 Session Row Lock 이후 Inquiry 생성, Session 연결,
상태 이력을 하나의 Transaction으로 처리한다. 중간 저장이 실패하면 전체가
Rollback된다.

`START_CARE_PRECHECK`와 Inquiry 연결 시 사용하는 `START_INQUIRY`만 승인된
외부 Inquiry State Machine Event다. `SAVE_CARE_PRECHECK`와
`SUBMIT_CARE_PRECHECK`는 Inquiry 상태를 변경하지 않는 Questionnaire 내부
감사 Action Code이며, PM 소유 State Machine 계약에 새 전이를 추가하지 않는다.

새 Migration:

```text
questionnaires.0003_questionnaire_answers_allow_blank
```

신규 `UNANSWERED` Session의 빈 `{}` 답변을 Django 검증에서 허용하기 위한
필드 상태 정합화다. DB Column Type이나 공개 필드 구조를 변경하지 않는다.

## 5. 권한·오류 규칙

- CUSTOMER만 실행할 수 있다.
- 본인의 삭제되지 않은 고객 Profile과 ACTIVE 구독만 시작할 수 있다.
- 타인 Session, 다른 구독 Session, 미존재 Session은 모두 `404`로 숨긴다.
- 역할이 CUSTOMER가 아니면 `403`, 미인증이면 `401`이다.
- 잘못된 Query·Body·질문 코드·중첩 답변은 `422`다.
- 오래된 `state_version`, 제출 후 재수정, 재연결은 `409`다.
- 같은 Idempotency-Key와 같은 요청은 원 응답을 Replay한다.
- 같은 Key를 다른 요청에 재사용하면 `DUPLICATE-EVENT-01 / 409`다.
- 내부 PK와 생성용 멱등 Hash는 응답에 노출하지 않는다.

## 6. 답변 Payload 경계

- 질문 코드: 영문 대문자로 시작하는 대문자·숫자·밑줄, 최대 40자
- 답변 개수: 1~100개
- 문자열: 최대 2,000자
- 복수 답변: 최대 50개, 중첩 List·Object 금지
- 허용 값: `null`, boolean, string, integer, finite float, 단일 List
- `NaN`, `Infinity`, 중첩 구조는 Fail-closed

실제 질문 문구와 선택지 Catalog는 Mobile 소비 단계에서 별도 확정할 수 있다.
이번 범위는 Session Runtime과 안전한 답변 저장 계약이다.

## 7. 구현 위치

- API: `backend/apps/questionnaires/api/**`
- Service: `backend/apps/questionnaires/services/questionnaire_service.py`
- 문의 연결: `backend/apps/questionnaires/services/inquiry_link_service.py`
- Repository: `backend/apps/questionnaires/repositories/questionnaire_repository.py`
- 문의 생성 연결점: `backend/apps/inquiries/services/inquiry_service.py`
- 상태 이력: `backend/apps/workflow/**`
- Migration: `backend/apps/questionnaires/migrations/0003_*.py`
- 작성자 API Test: `backend/tests/api/test_t021_care_precheck_runtime.py`
- PostgreSQL Test: `backend/tests/integration/questionnaires/test_t021_care_precheck_postgresql.py`

## 8. 작성자 검증 범위

### SQLite·계약 표적

- 세션 시작 시 Inquiry 0건
- UNANSWERED → IN_PROGRESS → SUBMITTED
- GET 복구 Snapshot
- 시작·저장·제출 Replay와 Key 재사용 충돌
- stale version과 제출 후 수정 409
- 본인 권한·타인 404·역할 403·미인증 401·입력 422
- 제출 Session의 신규 Inquiry 1회 연결
- 이력 실패 시 Session·이력·멱등 레코드 전체 Rollback
- OpenAPI Route·Example·Runtime Coverage 정합

### PostgreSQL 표적

- 같은 Session·같은 Version의 동시 저장: `200` 1건, `409` 1건
- 같은 제출 Session의 동시 Inquiry 연결: `201` 1건, `409` 1건
- 최종 Inquiry 1건, 승인된 START_INQUIRY 연결 이력 1건

검증은 팀 DB가 아닌 `pgvector/pgvector:0.8.6-pg16-bookworm` 일회용
PostgreSQL에서 수행했다. `questionnaires.0003`까지 실제 적용했으며
`visits.0005`는 적용하지 않았다.

## 9. 실행 명령

```powershell
$python = ".\backend\.venv\Scripts\python.exe"

& $python -B -m pytest -q -p no:cacheprovider `
  backend/tests/api/test_t021_care_precheck_runtime.py `
  tests/contract/test_contract_validators.py

& $python -B backend/manage.py check
& $python -B backend/manage.py makemigrations --check --dry-run
```

PostgreSQL 표적은 폐기형 DB 또는 승인된 QA DB에서 `config.settings.local`로
실행한다. DSN·Password는 문서와 로그에 기록하지 않는다.

```powershell
& $python -B -m pytest --ds=config.settings.local -q `
  -p no:cacheprovider `
  backend/tests/integration/questionnaires/test_t021_care_precheck_postgresql.py
```

## 10. 판정 경계와 다음 단계

작성자 검증 PASS는 Mobile 연동이나 WBS 완료 승인이 아니다.

다음 순서로 종료한다.

1. 후보 Commit을 main에 병합한다.
2. 김은진이 최신 main과 독립 PostgreSQL에서 권한·Replay·동시성·Rollback을 재검증한다.
3. 독립 QA 승인 후 윤승혁(PM)이 T-021 WBS 상태를 갱신한다.
4. Backend Gate가 끝난 뒤 양정현이 Mobile CARE_PRECHECK UI·질문 Catalog와 실제 Remote Smoke를 연결한다.

현재 범위 밖:

- Mobile 화면·APK 변경
- 질문 문구·선택지 정책의 신규 정의
- 문진 제출만으로 Inquiry 자동 생성
- 상담 자동 요청·상담사 자동 배정
- `visits.0005` 적용
- 기존 팀 DB Seed·운영 데이터 수정
