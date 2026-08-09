# Django REST API 문의·증상 제출 구현·검증·인계서

> 기준일: 2026-08-02 KST
> 구현·검증 책임: Backend·Database 담당
> 협업·검토 역할: State 계약 담당(PM), Data·QA 담당, AI·RAG 담당
> 구현 상태: Slice A 작성자 로컬 검증 완료 (`SUBMIT_SYMPTOM_DB_TRANSITION_READY`, `LOCAL_VERIFIED`)
> PostgreSQL 검증 환경: `waterbridge.public`, PostgreSQL 16.14
> 범위 판정: **Slice A 작성자 로컬 구현·검증 완료. Slice B AI 효과와 T-022 전체는 미완료.**

이 문서는 문의·증상 제출 업무(T-022)의 계약, Slice A 구현·검증 증거,
Slice B 중단 조건과 인계 기준을 한곳에서 제공한다. 2026-08-01에 확정된
Slice A 착수 범위에 대해, 이 문서에 기록한 검증 결과는 2026-08-02 로컬
실행 결과다.

## 1. 계약

### 1.1 기준 원본과 적용 순서

문서와 코드가 다를 때 다음 순서를 적용한다.

1. [State Machine 기계 계약](../../../../contracts/state-machine/)
2. [OpenAPI 기계 계약](../../../../contracts/api/openapi.yaml)
3. [오류 코드 Registry](../../../../contracts/error-codes/error-codes.yaml)
4. [AI 요청·응답 Schema](../../../../contracts/ai/)
5. 실제 [Django Runtime](../../../../backend/)
6. 사람용 [API 명세](../../../api/waterbridge_api_specification.md)와
   [화면설계서](../../../planning/md/화면설계서.md)

[공통 개발 규칙](<../../../planning/md/공통 개발 규칙.md>)에 따라
클라이언트는 다음 상태를 직접 지정하지 않고 행동 API를 호출한다. Backend가
역할·소유권·현재 상태·`state_version`·멱등성을 다시 검사한다.

데이터 범위는 WaterBridge Active 13을 유지한다. Target-only 19를 임의로
활성화하지 않으며, 제품 차단 조건에서는 AI·RAG를 호출하지 않는다.

### 1.2 `SUBMIT_SYMPTOM` State 계약

| 항목 | 확정 값 | 근거 |
| --- | --- | --- |
| 이벤트 | `SUBMIT_SYMPTOM` | [이벤트 계약](../../../../contracts/state-machine/inquiry-events.yaml) |
| 작업 ID | `submitSymptom` | 이벤트 계약·[Allowed Action](../../../../contracts/state-machine/allowed-actions.yaml) |
| 허용 역할 | `CUSTOMER` | [역할 계약](../../../../contracts/state-machine/role-permissions.yaml) |
| 시작 상태 | `DRAFT` | [TR-INQ-002](../../../../contracts/state-machine/transition-rules.yaml) |
| 성공 상태 | `QUESTIONNAIRE_IN_PROGRESS` | `TR-INQ-002` |
| 방문 상태 | 없어야 함(`REQUIRE_ABSENT`) | `TR-INQ-002` |
| 필수 Guard | 고객 역할, 문의 본인, 버전, 멱등 키, 증상 Payload | [Guard 계약](../../../../contracts/state-machine/transition-guards.yaml) |
| 상태 이력 | Inquiry 상태 이력과 업무 이벤트 기록 | `TR-INQ-002` |
| 상태 버전 | 성공 시 1 증가 | [동시성 정책](../../../../contracts/state-machine/concurrency-policy.yaml) |
| 효과 | 고객 입력 저장, 문진 제출 표시, AI 구조화 요청 | `TR-INQ-002` |
| 성공 후 고객 행동 | `SUBMIT_ANSWERS`, `CANCEL_INQUIRY` | Allowed Action 계약 |

`G-SYMPTOM-PAYLOAD-VALID`는 고객 원문 2~2000자, 문의 제품 연결,
첨부 개수·형식 검증을 요구한다. 문의 생성 OpenAPI는 `raw_text` 최대
5000자를 허용하므로 2001~5000자의 DRAFT가 제출 시 422가 되는 경계를
유지한다. 두 제한을 몰래 같게 바꾸지 않는다.

### 1.3 외부 API와 최소 요청

```text
POST /api/v1/inquiries/{id}/submit
operationId: submitSymptom
Authorization: Bearer <access-token>
Idempotency-Key: <1..128자 승인 토큰>
```

신규 generic `/events` Endpoint를 만들지 않는다. 첫 Slice는 DRAFT에 이미
저장된 원문·대표 증상을 제출 확정하는 행동별 Endpoint이며, 요청은 아래
필드만 허용한다.

```json
{
  "state_version": 1
}
```

- 최초 원문은 `START_INQUIRY`가 저장한 `Inquiry.raw_text`를 사용한다.
- 대표 증상은 기존 `SymptomEntry`가 있으면 사용한다.
- 제출 요청에서 새 원문·답변·첨부를 받거나 기존 입력을 덮어쓰지 않는다.
- `request.customer_message` Guard 입력은 저장된 `Inquiry.raw_text`로 매핑한다.
- 추가 원문·문진 응답은 OpenAPI-only
  `PATCH /inquiries/{id}/questionnaire`의 별도 Runtime Slice에서 누적한다.
- 대표 증상은 선택 단수 `representative_symptom_code`가 기준이다. 복수
  `symptom_codes`를 별도 표준처럼 추가하지 않는다.

### 1.4 성공·Replay 응답

정상과 Replay는 동일한 `SubmitSymptomResult` Schema를 사용한다.

```json
{
  "success": true,
  "data": {
    "inquiry_id": "018f2f9b-7c30-7981-b541-1a987c88b201",
    "state": "QUESTIONNAIRE_IN_PROGRESS",
    "state_version": 2,
    "idempotent_replay": false,
    "allowed_actions": [
      {
        "code": "SUBMIT_ANSWERS",
        "label": "추가 답변 제출",
        "operation_id": "submitFollowUpAnswers",
        "style": "PRIMARY",
        "requires_confirmation": false,
        "confirmation_message": null
      },
      {
        "code": "CANCEL_INQUIRY",
        "label": "문의 취소",
        "operation_id": "cancelInquiry",
        "style": "DESTRUCTIVE",
        "requires_confirmation": true,
        "confirmation_message": "문의를 취소하시겠습니까?"
      }
    ]
  },
  "error": null,
  "metadata": {
    "correlation_id": "4e437c06-5023-4b40-a0d1-ef8fef76d010"
  }
}
```

동일 Key·동일 요청 Replay는 저장된 성공 응답을 반환하되
`idempotent_replay=true`만 바꾼다. Inquiry, 상태 이력, AI dispatch를 다시
만들지 않는다.

### 1.5 ADHOC 문진 제출 Projection과 계약 Gap

현재 Active 13에서는 `support_questionnaire_session`에 새 행을 만들지
않는다. ADHOC 제출 여부는
`Inquiry.status_code=QUESTIONNAIRE_IN_PROGRESS`와 상태 이력에서 파생한다.
화면의 `questionnaire_status=SUBMITTED` Projection일 뿐,
`CARE_PRECHECK`용 `QuestionnaireSession`을 재정의하지 않는다. 별도 물리
저장이 필요하면 Active 13 범위와 ERD를 먼저 갱신한 뒤 별도 구현한다.

| 계약 Gap | 도미노 위험 | 적용한 안전 경계 |
| --- | --- | --- |
| Web·Mobile의 submit Path·Body 차이 | 서로 다른 계약 소비 | OpenAPI Method·Path·`operationId`·Schema·예시 확정 |
| 제출 요청에 원문·첨부 포함 | 고객 입력 덮어쓰기 | `state_version`만 허용, 추가 필드 422 |
| `customer_message`와 `raw_text` 명칭 차이 | Guard와 API 값 불일치 | 저장된 `Inquiry.raw_text`로 단일 매핑 |
| 정상·Replay 응답 차이 | 버전·Allowed Action 불일치 | 동일 결과 Schema·저장 Snapshot 사용 |
| ADHOC 제출 Projection | Target-only 테이블 오활성화 | Inquiry 상태·이력에서 파생, 신규 Session 0 |
| AI Adapter·Outbox 부재 | Rollback 뒤 AI만 실행되거나 DB 트랜잭션 확정 뒤 호출 유실 | 트랜잭션 안 HTTP 금지, Slice B Gate |
| stale AI 결과 | 최신 문의 덮어쓰기 | 호출 시작 버전과 현재 버전 재비교 필요 |
| 추가 입력 저장소 미확정 | 원문 덮어쓰기·유실 | 최초 원문 불변, 승인 저장소 전 추가 입력 미수신 |

## 2. 구현 범위

### 2.1 Slice 구분과 현재 판정

| 단계 | 범위 | 착수 조건 | 현재 판정 |
| --- | --- | --- | --- |
| Slice A | 고객 본인 DRAFT 문의 제출, 상태·버전·이력·멱등 결과 원자 저장 | `submitSymptom` 계약과 ADHOC Projection 확정 | 작성자 로컬 검증 완료 (`SUBMIT_SYMPTOM_DB_TRANSITION_READY`) |
| Slice B | DB 트랜잭션 확정 이후 AI 구조화 요청, stale 결과 차단, 재처리·실패 추적 | AI Runtime·Backend Adapter·durable dispatch 저장 경계 확정 | 미착수 |

Slice A만 끝낸 상태를 T-022 전체 완료나 AI 연동 완료로 표시하지 않는다.

### 2.2 기존 Backend 기반과 현재 Runtime

| 기반 | 현재 사실 | 적용 방향 |
| --- | --- | --- |
| 문의 생성 | `InquiryService.create()`가 `START_INQUIRY` 구현 | DRAFT·초기 `state_version=1` 사용 |
| 문의 취소 | 행 잠금·소유권·버전·멱등성·409·이력 구현 | 동시 요청 기준 재사용 |
| 소유권 잠금 | `InquiryRepository.lock_owned_inquiry()` | 타 고객 404 유지 |
| 상태 계산 | `StateMachine`이 `TR-INQ-002` 해석 | 상태 하드코딩 금지 |
| Guard | `GuardEvaluator`가 역할·버전·멱등·도메인 결과 fail-closed 평가 | 소유권·Payload 결과 주입 |
| 멱등성 | `IdempotencyService`와 `workflow_idempotency_record` | actor + operation + key 범위 |
| 상태 이력 | `TransitionHistoryService`와 `support_inquiry_status_history` | 이전·다음 상태·새 버전 기록 |
| 고객 입력 | `Inquiry.raw_text`, `SymptomEntry` | 최초 입력 불변 |
| 공통 응답 | 취소 Runtime의 정상·409·Replay | Wrapper·공개 UUID만 노출 |

현재 Slice A Runtime은 다음과 같다.

- [URL](../../../../backend/apps/inquiries/api/urls.py)에
  `POST /api/v1/inquiries/{inquiry_id}/submit`이 연결돼 있다.
- [View](../../../../backend/apps/inquiries/api/views.py)의
  `SubmitSymptomView`가 인증·CUSTOMER 권한, 멱등 Header와 Serializer를
  적용한다.
- [Serializer](../../../../backend/apps/inquiries/api/serializers/symptom_submission.py)는
  양의 `state_version`만 받고 원문을 덮어쓸 추가 필드를 거부한다.
- [전이 Service](../../../../backend/apps/inquiries/services/inquiry_transition_service.py)는
  State Machine·Guard·행 잠금·멱등성·이력·응답 Snapshot을 원자 처리하며
  AI Service는 호출하지 않는다.
- OpenAPI Runtime 매핑은 Operation 10개 중 Runtime 8개,
  OpenAPI-only 2개를 고정한다.

관련 문의 API 경계는 다음과 같다. 2026-07-27 착수 전 준비도 문서의
Model·Migration·Route `0개` 판정은 현재 사실이 아니므로 승계하지 않는다.

| 범위 | 현재 경계 | 유지 기준 |
| --- | --- | --- |
| `POST /api/v1/inquiries` | Runtime 구현 | 자연어 원문과 선택 `representative_symptom_code` 저장·공개 UUID 반환 |
| `PATCH /api/v1/inquiries/{id}/questionnaire` | OpenAPI-only | 같은 문의에 누적·본인 범위·Transaction 적용 |
| `POST /api/v1/inquiries/{id}/action-results` | OpenAPI-only | 같은 문의에 자가조치 결과 누적·실패 시 반쪽 데이터 금지 |
| `submitSymptom` | OpenAPI·Runtime 구현 | Slice A 외부 리뷰·PM 병합 뒤 소비, AI는 Slice B |

### 2.3 Slice A 완료 증거와 남은 Runtime

완료 증거:

- OpenAPI에 Method·Path·Schema·응답·예시 존재
- 정상·권한·404·409·422·Replay 계약 테스트 통과
- 상태·버전·이력·멱등 결과 각 1회 저장
- 실패·Replay 시 고객 입력·DB 수량 불변
- PostgreSQL 동시 요청 결과 결정적
- 내부 정수 PK·원문·Token 비노출

Slice A 이후에도 남는 범위:

- 실제 AI HTTP 호출과 실행·검색·근거 저장
- `SUBMIT_ANSWERS` Runtime
- OpenAPI-only 문진 누적·자가조치 결과 Runtime
- AI 자동 이벤트와 최종 안내 화면 E2E

## 3. Transaction

한 DB 트랜잭션에서 아래 순서를 지킨다.

1. Header와 Body를 Serializer에서 형식 검증한다.
2. `actor + submitSymptom + Idempotency-Key`의 기존 기록을 잠가 같은
   Hash이면 Replay, 다른 Hash이면 409로 끝낸다.
3. 공개 UUID와 고객 본인 조건으로 Inquiry를 `select_for_update()`한다.
4. 행 잠금 대기 중 완료된 동일 Key가 있을 수 있으므로 멱등 기록을 다시
   확인한다.
5. 현재 상태 `DRAFT`와 요청 `state_version` 일치를 확인한다.
6. `StateMachine.resolve(SUBMIT_SYMPTOM)`로 `TR-INQ-002`를 구한다.
7. 인증·역할·소유권·제품 연결·원문 길이·첨부 검증 결과를 Guard에 넣고
   fail-closed 평가한다.
8. 새 멱등 기록을 만든다. Unique 충돌 시 기존 기록을 다시 읽어 Replay
   또는 409로 끝낸다.
9. 상태를 `QUESTIONNAIRE_IN_PROGRESS`로 바꾸고 버전을 1 증가시킨다.
10. `SUBMIT_SYMPTOM` 상태 이력을 한 건 저장한다.
11. 새 상태의 고객 `allowed_actions`와 응답 Snapshot을 멱등 기록에 저장한다.
12. DB 트랜잭션을 확정한다.

Guard·이력·멱등 결과·응답 직렬화 중 하나라도 실패하면 8~11의 쓰기를
전부 Rollback한다. `Inquiry.raw_text`를 빈 문자열로 만들거나 제출 요청으로
덮어쓰지 않으며, 409·422·AI 실패 시 기존 원문과 대표 증상을 보존한다.
요청 Hash와 로그에는 고객 원문을 출력하지 않는다.

## 4. 권한

| 요청 | HTTP | 외부 계약·처리 |
| --- | ---: | --- |
| 미인증 | 401 | `AUTH_REQUIRED` |
| CUSTOMER 이외 역할 | 403 | `FORBIDDEN`, 대상 변경 0 |
| 다른 고객 문의 UUID | 404 | IDOR 방지를 위해 존재 숨김 |
| 존재하지 않는 문의 UUID | 404 | 타 고객과 동일 외부 응답 |
| 본인 CUSTOMER 문의 | 다음 Guard | 역할만으로 전이 허용 안 함 |

문의·문진·자가조치·상태 이력은 동일한 공개 `inquiry_id` 아래 누적한다.
외부 응답에는 내부 정수 PK를 노출하지 않는다.

## 5. 409와 Fail-closed 오류

### 5.1 상태·버전 충돌

- 새 Key지만 요청 버전이 현재 버전과 다르거나 현재 상태에서
  `SUBMIT_SYMPTOM`이 허용되지 않으면 `STATE-CONFLICT-01` 409를 반환한다.
- 응답은 `current_status`, `current_state_version`, `allowed_actions`를
  포함한다.
- Inquiry·이력·완료 멱등 기록을 변경하지 않는다.
- 클라이언트는 최신 상태를 반영하고 입력을 로컬에 보존한 후 새 Key로
  재요청한다.

### 5.2 멱등 키 충돌

- 같은 actor·operation·Key·같은 Hash: 저장 응답 Replay
- 같은 actor·operation·Key·다른 Hash: `DUPLICATE-EVENT-01` 409
- 처리 중인 같은 Key: 현재 Runtime 정책대로 409
- 다른 actor 또는 operation: 별도 멱등 범위

### 5.3 409로 감추지 않는 내부 오류

`TERMINAL_STATE`·`UNLISTED_TRANSITION` 같은 정상 고객 상태 충돌만 409
Snapshot으로 반환한다. `AMBIGUOUS_TRANSITION`, 잘못된 Version Action,
문의·방문 상태 모순 같은 State 계약·데이터 무결성 이상은
`INTERNAL_ERROR` 500으로 숨기고 DB 쓰기를 모두 Rollback한다.

활성 구독과 제품 모델 연결은 PM State Guard에 조건을 임의 추가하지 않고
OpenAPI `x-runtime-preconditions`에 둔다. 제출 시점에 조건이 깨지면 현재
확정 범위는 `VALIDATION_ERROR` 422이며 쓰기를 하지 않는다. 단,
`ProductModel.is_supported_mvp`·`is_active` 실패의 외부 응답과
`PRODUCT_VALIDATION_FAILED` 내부 이벤트 시점은 아직 별도 계약 Gate다.

## 6. 멱등성과 동시성

- 멱등 범위는 `actor + submitSymptom + Idempotency-Key`다.
- 성공 Snapshot을 저장한 뒤 Replay는 상태·이력·dispatch를 추가하지 않는다.
- 같은 Key 동시 요청은 성공 1회와 Replay 1회, 이력 1건이어야 한다.
- 다른 Key·같은 Version 동시 요청은 성공 1회와 409 1회, 이력 1건이어야
  한다.
- PostgreSQL 행 잠금 뒤 멱등 기록을 재확인해 대기 중 완료된 요청을 놓치지
  않는다.
- 같은 `ai_request_id` 결과의 중복 적용과 stale AI 결과 차단은 Slice B에서
  구현한다.

## 7. 검증 Matrix

### 7.1 현재 자동 증거

| 경계 | 자동 증거 | 판정 |
| --- | --- | --- |
| 정상 제출 | 200, `DRAFT → QUESTIONNAIRE_IN_PROGRESS`, version 2 | PASS |
| 자연어 단독 | 대표 증상 행 없이 원문 보존·200·이력·멱등 각 1건 | PASS |
| Replay | 같은 Key·Body는 쓰기 1회·저장 응답 재사용 | PASS |
| 중복 Key 충돌 | 같은 Key·다른 Body는 409 | PASS |
| 상태 충돌 | stale Version·허용되지 않은 상태는 최신 Snapshot 409 | PASS |
| 권한 | 미인증 401·비고객 역할 403·타 고객 404 | PASS |
| 입력 검증 | Header·Body·원문 길이·ACTIVE 구독 위반 422 | PASS |
| 트랜잭션 | 늦은 실패·응답 직렬화 실패 시 전체 Rollback | PASS |
| 내부 계약 오류 | 모호한 State 계약을 409로 노출하지 않고 500 | PASS |
| PostgreSQL 동시성 | 같은 Key 1회+Replay, 다른 Key 200+409 | PASS |

### 7.2 Slice A 필수 Case와 현재 경계

| # | Case | 기대 결과 | 현재 판정 |
| ---: | --- | --- | --- |
| 1 | 본인 CUSTOMER, DRAFT, version 1, 새 Key | 200·다음 상태·version 2 | PASS |
| 2 | 동일 Key·Body 재전송 | Replay·쓰기 추가 0 | PASS |
| 3 | 동일 Key·다른 Body/version | 409 `DUPLICATE-EVENT-01` | PASS |
| 4 | 새 Key·stale version | 409·최신 Snapshot | PASS |
| 5 | 다른 고객 문의 | 404·변경 0 | PASS |
| 6 | CONSULTANT·TECHNICIAN·OPERATOR | 403·변경 0 | PASS |
| 7 | 미인증 | 401 | PASS |
| 8 | DRAFT 이외 상태 | 409·현재 Snapshot | PASS |
| 9 | 누락·빈 Idempotency-Key | 422 | PASS |
| 10 | 누락·0 이하 state_version | 422 | PASS |
| 11 | 저장 raw_text 1자 또는 2001자 이상 | 422·원문 보존 | PASS |
| 12 | 제품 연결 없음·비활성 구독 | 422·AI 호출 0 | PASS — MVP 지원 필드 의미는 Gate |
| 13 | 동시 동일 Key 2요청 | 성공 1·Replay 1·이력 1 | PostgreSQL PASS |
| 14 | 동시 다른 Key·같은 version | 성공 1·409 1·이력 1 | PostgreSQL PASS |
| 15 | 이력·응답 저장 강제 실패 | 전체 Rollback | PASS |
| 16 | 응답 내부 PK 비노출 | 공개 UUID만 노출 | PASS |

오류 예시는 다음 공통 파일을 재사용한다.

- 400 공통 요청 오류: `contracts/api/examples/errors/invalid-request.json`
- 401: `contracts/api/examples/errors/auth-required.json`
- 403: `contracts/api/examples/errors/forbidden.json`
- 404: `contracts/api/examples/errors/resource-not-found.json`
- 409 상태 충돌: `contracts/api/examples/workflow/state-version-conflict.json`
- 409 Key 재사용: `contracts/api/examples/workflow/idempotency-key-reuse-conflict.json`
- 422 Body·Header: `body-validation-error.json`,
  `idempotency-key-validation-error.json`
- 5xx: `contracts/api/examples/errors/internal-error.json`

400은 공통 계약 예시이며 `submitSymptom` Serializer·Header 검증 Runtime은
422를 반환한다. 둘을 같은 동작으로 표시하지 않는다.

### 7.3 실행 결과

| 검증 | 결과 | 판정 |
| --- | --- | --- |
| 변경 전 기준선 | `40 passed` | 역사적 기준 |
| 자연어 단독 Submit 포함 집중 | SQLite `30 passed, 2 skipped`; PostgreSQL `22 passed` | PASS |
| 계약·Runtime·예시·권한 집중 | `72 passed, 2 skipped` | PASS |
| Django Check·Migration drift·적용 상태 | 오류 0·변경 0·미적용 0 | PASS |
| SQLite 전체 단일 실행 | `778 passed, 13 skipped` | PASS |
| PostgreSQL 전체 최초 실행 | `3 failed, 788 passed` | 로컬 Demo Login·CORS 환경 격리 누락 |
| PostgreSQL 실패 3건 재검증 | 프로세스 전용 테스트값으로 `3 passed` | PASS |
| PostgreSQL 전체 격리 재실행 | `791 passed` | PASS |

최초 PostgreSQL 3건 실패는 `.env`의 Demo Login·CORS 실행값이 테스트
기본값보다 우선해서 발생했다. 테스트 프로세스에만
`DJANGO_DEMO_LOGIN_ENABLED=false`,
`DJANGO_CORS_ALLOWED_ORIGINS=https://approved.example`를 적용해 재검증했다.
`.env`는 출력하거나 수정하지 않았다.

### 7.4 작업 → 검증 실행 순서

| 순서 | 한 번에 한 작업 | 바로 뒤 검증 | 결과 |
| ---: | --- | --- | --- |
| 0 | submit OpenAPI 계약·ADHOC Projection 확정 | 참조·예시·Operation inventory | 완료 — OpenAPI 10·Runtime 8·OpenAPI-only 2 |
| 1 | 요청·응답 Serializer | 정상·경계·추가 필드 거부 | 완료 |
| 2 | 본인 문의 잠금·상태 저장 | 404·row lock·Rollback | 완료 |
| 3 | StateMachine·Guard 연결 | DRAFT·역할·버전·Payload Guard | 완료 |
| 4 | 멱등성·이력·응답 Snapshot | Replay·다른 Hash 409·동시 요청 | 완료 |
| 5 | View·Route 연결 | 200·401·403·404·409·422 | 완료 |
| 6 | PostgreSQL 집중 검증 | 동시성·이력 Unique·Rollback | 완료 — 작성자 환경 |
| 7 | Slice A 전체 Backend 회귀 | OpenAPI·SQLite·PostgreSQL | 완료 — 비작성자 리뷰 대기 |
| 8 | AI durable dispatch | 트랜잭션 확정·Replay·Timeout·stale | 미착수 — Slice B |
| 9 | AI 결과 소비·자동 이벤트 | 정상·위험·근거 없음·오류 E2E | 미착수 — 전체 완료 주장 금지 |

## 8. 2026-08-02 기술 변경 34경로 인벤토리

아래는 2026-08-02 로컬 기술 변경을 책임 영역별로 분류한 34경로
인벤토리다. 구현 범위와 검증 대상을 설명하며 배포 단위를 의미하지 않는다.

### 8.1 계약 원본 7개

- `contracts/api/components/schemas/questionnaire/SymptomSubmissionRequest.yaml`
- `contracts/api/components/schemas/inquiry/SubmitSymptomResult.yaml`
- `contracts/api/openapi.yaml`
- `contracts/api/paths/inquiries.yaml`
- `contracts/api/examples/inquiries/submit-symptom-request.json`
- `contracts/api/examples/inquiries/submit-symptom-success-response.json`
- `contracts/api/examples/inquiries/submit-symptom-replay-response.json`

### 8.2 Runtime 원본 8개

- `backend/apps/inquiries/api/serializers/__init__.py`
- `backend/apps/inquiries/api/serializers/symptom_submission.py`
- `backend/apps/inquiries/api/urls.py`
- `backend/apps/inquiries/api/views.py`
- `backend/apps/inquiries/readiness.py`
- `backend/apps/inquiries/repositories/inquiry_repository.py`
- `backend/apps/inquiries/services/inquiry_transition_service.py`
- `backend/apps/workflow/services/transition_history_service.py`

### 8.3 자동 검증 8개

- `backend/tests/api/test_openapi_inquiry_contract.py`
- `backend/tests/api/test_openapi_runtime_coverage.py`
- `backend/tests/api/test_runtime_examples_contract.py`
- `backend/tests/api/test_t022_create_inquiry.py`
- `backend/tests/api/test_t022_submit_symptom.py`
- `backend/tests/api/test_t023_cancel_inquiry.py`
- `backend/tests/unit/inquiries/test_t022_readiness.py`
- `backend/tests/unit/inquiries/test_t022_submit_symptom_serializer.py`

### 8.4 설명·인계 문서 11개

- `backend/README.md`
- `docs/api/README.md`
- `docs/api/runtime_implementation_status.md`
- `docs/api/waterbridge_api_specification.md`
- `docs/handoffs/20260801_t017a_t022_검토_입력_패킷.md` — 역사 보존·현재 문서 안내 stub
- `docs/handoffs/README.md`
- `docs/individual/jiyong/README.md`
- `docs/individual/jiyong/연동_인계/Backend_팀_검토_인계_체크리스트.md`
- `docs/individual/jiyong/연동_인계/Backend_Mobile_API_연동_가이드.md`
- `docs/individual/jiyong/archive/20260802_문서통합_원본/technical/backend/t022_증상_제출_api_설계_및_계약_게이트.md`
- `docs/individual/jiyong/archive/20260802_문서통합_원본/technical/backend/20260802_t022_로컬_후보_분리_및_재현_패킷.md`

### 8.5 계약·Runtime 분리 검증 경계

두 교차 계층 테스트가 분리 순서에 영향을 준다.

- `test_openapi_runtime_coverage.py`: OpenAPI Operation 수와 Django
  Route·View를 함께 검증한다.
- `test_runtime_examples_contract.py`: JSON 예시와 Runtime Serializer를
  함께 검증한다.

계약과 Runtime을 분리해 검증하려면 다음 순서를 따른다.

1. OpenAPI·Schema·예시와 계약 전용 테스트로 계약 변경을 검증한다.
2. 계약 중간 상태에서는 `submitSymptom`을 `OPENAPI_ONLY`로 판정하도록
   교차 테스트를 먼저 조정한다.
3. 계약 담당자의 승인 기록 뒤 Runtime·Serializer·Repository·Service와
   Runtime 테스트를 검증한다.
4. 설명·인계 문서는 계약·Runtime의 검증일, 명령, 환경과 결과로 갱신한다.
5. 계약과 Runtime을 하나의 변경 단위로 다뤄야 한다면 교차 계층 테스트가
   중간 상태를 어떻게 판정하는지 먼저 명시한다.

## 9. 재현 명령

저장소 루트에서 실행한다. 비밀번호·Token·`.env` 값은 출력하지 않는다.

```powershell
$python = ".\backend\.venv\Scripts\python.exe"
$env:PYTHONDONTWRITEBYTECODE = "1"

& $python -B -m pytest -q -p no:cacheprovider `
  backend/tests/api/test_openapi_inquiry_contract.py `
  backend/tests/api/test_openapi_runtime_coverage.py `
  backend/tests/api/test_runtime_examples_contract.py `
  backend/tests/unit/inquiries/test_t022_submit_symptom_serializer.py

& $python -B -m pytest -q -p no:cacheprovider `
  backend/tests/api/test_t022_create_inquiry.py `
  backend/tests/api/test_t022_submit_symptom.py `
  backend/tests/api/test_t023_cancel_inquiry.py

& $python -B -m pytest --ds=config.settings.local `
  -q -p no:cacheprovider `
  backend/tests/api/test_t022_submit_symptom.py

& $python .\backend\manage.py check --settings=config.settings.local
& $python .\backend\manage.py makemigrations --check --dry-run --noinput `
  --settings=config.settings.local
& $python .\backend\manage.py migrate --check --noinput `
  --settings=config.settings.local
& $python .\scripts\database\check_postgresql_connection.py

& $python -B -m pytest backend/tests -q -p no:cacheprovider

$previousDemo = $env:DJANGO_DEMO_LOGIN_ENABLED
$previousCors = $env:DJANGO_CORS_ALLOWED_ORIGINS
try {
  $env:DJANGO_DEMO_LOGIN_ENABLED = "false"
  $env:DJANGO_CORS_ALLOWED_ORIGINS = "https://approved.example"
  & $python -B -m pytest backend/tests --ds=config.settings.local `
    -q -p no:cacheprovider
} finally {
  if ($null -eq $previousDemo) {
    Remove-Item Env:DJANGO_DEMO_LOGIN_ENABLED -ErrorAction SilentlyContinue
  } else {
    $env:DJANGO_DEMO_LOGIN_ENABLED = $previousDemo
  }
  if ($null -eq $previousCors) {
    Remove-Item Env:DJANGO_CORS_ALLOWED_ORIGINS -ErrorAction SilentlyContinue
  } else {
    $env:DJANGO_CORS_ALLOWED_ORIGINS = $previousCors
  }
}

git diff --check
git -c core.quotepath=false status --short
```

## 10. Slice B 중단선

### 10.1 AI 전달 계약과 미결정 항목

[SymptomAnalysisRequest](../../../../contracts/ai/requests/SymptomAnalysisRequest.schema.json)는
문의 Public UUID `inquiry_id`, `correlation_id`, Backend 발급
`ai_request_id`, 호출 시작 `state_version`, `raw_symptom`, 제품
`model_code`를 요구한다. AI는 업무 상태를 직접 바꾸지 않으며 응답의
`state_version`은 Echo다. Backend가 현재 버전과 다시 비교해야 한다.
현재 `inquiry_ai_service.py`와 `integrations/ai/client.py`는 실행 Adapter가
아닌 설명용 경계만 있으므로 DB 트랜잭션 안에 AI HTTP 호출을 추가하지
않았다.

| 결정 | 책임 역할 | 완료 증거 |
| --- | --- | --- |
| AI Endpoint·인증·Timeout | AI·RAG 담당 + Backend·API 담당 | Adapter 통합 테스트 |
| durable dispatch 저장 위치 | Backend·API 담당 + State 계약 담당(PM) | DB 트랜잭션 확정 이후 유실·중복 방지 테스트 |
| `ai_request_id` 생성·멱등 범위 | Backend·API 담당 + AI·RAG 담당 | Replay·다른 Payload 충돌 |
| AI 실패·Timeout 재처리 상태 | State 계약 담당(PM) + AI·RAG 담당 | 상태·오류 계약과 E2E |
| stale 응답 처리 | Backend·API 담당 | 요청·현재 버전 불일치 시 적용 0건 |

Active 13에서 `aiops_ai_run`을 활성화하지 않기로 했다면 durable dispatch
원장을 새로 만들거나 Target-only 테이블을 독단적으로 사용하지 않는다.
Gate가 닫히기 전 응답에 `AI 요청 완료`를 표시하지 않는다.

### 10.2 현재 계약 결정이 없어 중단한 항목

- `ProductModel.is_supported_mvp`·`is_active` 실패의 외부 HTTP 응답과
  `PRODUCT_VALIDATION_FAILED` 내부 이벤트 시점
- 복수 증상 저장: 대표 증상 계약과 `SymptomEntry`의 문의당 1행 구조 변경
- 보충 설명·문진 답변·AI 추가 질문 답변의 append/update 식별자
- AI dispatch·Timeout·재처리·stale 결과 차단
- T-023 추가 Action과 상담·방문 전이
- T-017A·T-018 Runtime

State 계약, AI·RAG, Data·QA 담당 역할의 공동 결정을 기록하기 전에 Model,
Migration, Runtime을 추측 구현하지 않는다.

### 10.3 Slice B 필수 검증

- DB 트랜잭션 확정 전 AI 호출 0, 확정 뒤 dispatch 1건
- Replay 시 dispatch 추가 0
- Timeout 시 고객 입력·상태·이력 유지
- 같은 `ai_request_id` 결과 2회 적용 시 최초 1회만 인정
- 호출 버전과 현재 버전이 다르면 업무 결과 적용 0
- 정상·위험·근거 없음·Schema 오류가 Backend 자동 이벤트 Guard를
  통과하거나 안전 차단
- Header·응답·Backend·AI 로그의 `correlation_id` 일치
- 고객 원문·Authorization·Cookie·비밀키 로그 비노출

### 10.4 절대 금지와 즉시 중단 조건

- DB 트랜잭션 내부 동기 AI HTTP 호출 또는 Backend 자동 재시도
- AI 실패 때문에 고객 원문·상태 이력 삭제
- stale AI 결과의 최신 상태·안내 덮어쓰기
- 같은 `ai_request_id` 결과 중복 적용
- AI가 State Machine Guard 없이 상태 직접 변경
- OpenAPI와 PM State 계약이 서로 다른 Path·Body·상태를 요구
- Active 13을 넘어 새 물리 테이블 활성화가 필요
- 같은 Key Replay가 상태·이력·AI 호출을 중복 생성
- 타 고객 요청이 데이터 존재를 드러내는 응답으로 변경

## 11. 외부 Gate와 인계

2026-08-02 기준 판정은 작성자 로컬 검증 완료(`LOCAL_VERIFIED`)이며 팀
공식 완료가 아니다. 다음 외부 Gate가 남아 있다.

- Data·QA 담당 또는 지정 비작성자의 새 PostgreSQL 독립 재현
- State 계약 담당(PM)의 계약 차이 0 확인과 팀 기준선 반영 결정
- 팀 기준선에서 Web·Mobile 담당의 실제 소비 검증

### 11.1 2026-08-02 작성자 전달 스냅샷과 독립 리뷰 기록

| 항목 | 전달 당시 값 |
| --- | --- |
| 비교 기준 | `origin/main` `48470ac4a8abd6b627d96ec9c886f2621b3d30ca` |
| 작성자 후보 | 로컬 `jiyong` HEAD `b3a4ff`와 미게시 Worktree |
| 게시 상태 | PR #10은 T-005 기준선 병합 완료, T-022 별도 PR은 없음 |
| DB | `waterbridge.public`, 물리 32·Active 13·Target-only 19 |
| 작성자 회귀 | SQLite `778 passed, 13 skipped`; PostgreSQL `791 passed` |

위 값은 2026-08-02 작성자 전달 시점의 스냅샷이며 최신 팀 기준선을
자동으로 뜻하지 않는다. 독립 검토자는 현재 Branch·PR·기준 SHA를 다시
기록한다.

| 검토자·역할 | 검토 범위 | 결정 | 변경 요청·계약 차이 | 결정일·근거 |
| --- | --- | --- | --- | --- |
| 윤승혁(PM·State 계약) | Path·Body·응답·전이·409·팀 기준선 반영 | `APPROVE / HOLD / CHANGE_REQUEST` |  |  |
| 김은진(Data·QA) | Active 13·원문 불변·ADHOC Projection·rollback·Replay·동시성 | `APPROVE / HOLD / CHANGE_REQUEST` |  |  |
| 이동윤(AI·RAG) | Slice B Schema·Timeout·재처리·stale·durable dispatch | `APPROVE / HOLD / CHANGE_REQUEST` |  |  |

작성자 착수 승인은 Slice A 구현 근거일 뿐 위 독립 리뷰를 대체하지 않는다.
회신은 [Backend 팀 검토 및 인계 체크리스트](../연동_인계/Backend_팀_검토_인계_체크리스트.md)의
공통 필드와 역할별 반환 형식을 사용한다.

### 11.2 외부 Gate 실행 순서

| 순서 | 책임 역할 | 요청 내용 | 완료·반환 증거 |
| ---: | --- | --- | --- |
| 1 | Backend·Database 담당 | Slice A 계약·Runtime을 작업→검증 단위로 구현 | 완료 — 계약·집중·PostgreSQL·전체 회귀 |
| 2 | Data·QA 담당 또는 비작성자 | 새 DB에서 Active 13·원문 보존·동시성·Rollback·Replay 재현 | 명령·환경·Exit code·불일치 목록 |
| 3 | State 계약 담당(PM) | `submitSymptom`과 State 계약 차이 0 검토·팀 기준선 반영 결정 | 승인·보류 또는 변경 요청 |
| 4 | Web·Mobile 담당 | 팀 기준선에서 UUID·401/403/404/409/422·Replay 소비 확인 | Web·Mobile Smoke |
| 5 | AI·RAG 담당 + Backend·API 담당 | Slice B Endpoint·`ai_request_id`·Timeout·stale·dispatch 계약 및 구현 | 정상·위험·근거 없음·오류 E2E |

Seed·Importer는 DB 스키마·Seed 기준선(T-005)이므로 문의·증상 제출
Slice A(T-022)에서 변경하지 않는다.
이 문서는 로컬 구현·검증 결과를 전달하는 기준서이며, 외부 Gate 전에는
팀 공용 기준선의 완료 근거로 인용하지 않는다.

## 12. 2026-08-08 최신 main 재검증과 추가 누적 Runtime Gate

최신 `main` clean worktree에서 기존 문의 Runtime과 PostgreSQL을 다시
검증했다. Readiness Runtime Test와 PostgreSQL 연결·Migration·Drift는
PASS했지만, `followup_answer.py`와 OpenAPI-only 두 쓰기 Operation이 남아
T-022 전체 판정은 `PARTIAL`이다.

공개 Runtime을 추측 구현하지 않도록
`backend/apps/inquiries/readiness.py`에 다음 별도 사전 Gate를 추가했다.

| Operation | 현재 계약 공백 |
| --- | --- |
| `accumulateInquiryQuestionnaire` | Path UUID, `Idempotency-Key`, typed `answers` |
| `createInquiryActionResult` | Path UUID, `Idempotency-Key` |

```powershell
$python = ".\backend\.venv\Scripts\python.exe"

& $python -m pytest `
  backend/tests/unit/inquiries/test_t022_readiness.py `
  -q -p no:cacheprovider

& $python .\backend\apps\inquiries\readiness.py `
  --require-deferred-runtime-contracts
```

단위 Test는 `35 passed`이고, 현재 사전 Gate는 계약 공백 5개를 탐지해
의도한 종료코드 `3`을 반환한다. 종료코드 3은 기존 Runtime 장애가 아니라
추가 누적 Runtime 착수 차단을 뜻한다. 계약이 해소되기 전에는 Route·View,
Model·Migration을 추가하지 않는다.

전체 실행 증거와 다른 작업의 차단 경계는
[2026-08-08 Backend 작성자 회귀검증 보고서](../개발환경/Django_PostgreSQL_Backend_작성자_회귀검증_보고서_20260808.md)를
따른다.
