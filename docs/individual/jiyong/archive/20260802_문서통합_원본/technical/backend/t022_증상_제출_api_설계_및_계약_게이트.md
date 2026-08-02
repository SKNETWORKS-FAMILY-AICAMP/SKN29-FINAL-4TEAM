# T-022 증상 제출 API 설계 및 계약 게이트

> 기준일: 2026-08-02
> 작성·설계 책임: 최지용(Backend·Database)
> 협업·검토: 윤승혁(PM·State 계약), 김은진(Data·QA), 이동윤(AI·RAG)
> 상태: `SUBMIT_SYMPTOM_DB_TRANSITION_READY`
> 구현 여부: **Slice A 작성자 로컬 구현·검증 완료. Slice B AI 효과와 T-022 전체는 미완료.**
> 실행 원칙: `계약 확인 → 한 작업 구현 → 집중 검증 → 다음 작업`
> 데이터 원칙: WaterBridge Active 13 범위를 유지하고 Target-only 19를
> 임의 활성화하지 않는다.

## 1. 결론

`SUBMIT_SYMPTOM`의 첫 수직 Slice는 계약과 Django Runtime까지 구현됐다.
[PM State Machine 계약](../../../../../contracts/state-machine/transition-rules.yaml)은
`DRAFT → QUESTIONNAIRE_IN_PROGRESS`, 고객 본인, `state_version`,
`Idempotency-Key`, 입력 유효성, 이력 저장을 모두 정의하고 있으며
현재 Backend는 문의 행 잠금, 멱등성 저장·Replay, 409 응답, 상태 이력을
한 트랜잭션에서 처리한다.

2026-08-01 사용자 전달 기준으로 오늘 우선순위와 Slice A 착수가
검토·승인되었다. 이에 따라 다음 계약·물리 경계를 구현에 반영했다.

1. [OpenAPI](../../../../../contracts/api/openapi.yaml)에
   `POST /inquiries/{id}/submit`, `operationId=submitSymptom`, 요청·응답
   Schema와 성공·Replay 예시를 확정했다.
2. `MARK_QUESTIONNAIRE_SUBMITTED`는 ADHOC 문의의 상태와 이력으로
   파생한다. Target-only `QuestionnaireSession`을 생성하지 않는다.
3. 최초 `Inquiry.raw_text`를 불변 입력으로 사용하며 제출 요청은
   `{ "state_version": 1 }`만 허용한다.
4. PM State Guard를 변경하지 않고, 제출 시점의 활성 구독과 제품 모델
   연결은 최지용 관할 OpenAPI의 `x-runtime-preconditions`에 명시한다.

다만 `REQUEST_AI_STRUCTURING` 효과를 실행할
   [Backend AI Service](../../../../../backend/apps/inquiries/services/inquiry_ai_service.py)와
   [AI Adapter](../../../../../backend/integrations/ai/client.py)는 아직
설명 문자열만 있다. DB 트랜잭션 안에서 AI HTTP 호출을 임의로 추가하면
중복 호출과 부분 커밋 위험이 생기므로 Slice B는 구현하지 않았다.

따라서 첫 수직 Slice는 아래 두 단계로 분리한다.

| 단계 | 범위 | 착수 조건 | 완료 주장 |
| --- | --- | --- | --- |
| Slice A | 고객 본인 DRAFT 문의 제출, 상태·버전·이력·멱등 결과를 원자적으로 저장 | OpenAPI의 `submitSymptom` 동작 계약과 ADHOC 제출 Projection 확정 | `SUBMIT_SYMPTOM_DB_TRANSITION_READY` |
| Slice B | 커밋 이후 AI 구조화 요청, stale 결과 차단, 재처리·실패 추적 | 이동윤 AI Runtime, Backend Adapter, durable dispatch 저장 경계 확정 | `SUBMIT_SYMPTOM_AI_EFFECT_READY` |

Slice A만 끝낸 상태를 T-022 전체 완료나 AI 연동 완료로 표시하지 않는다.

## 2. 기준 원본과 우선순위

문서와 코드가 다를 때 다음 순서를 적용한다.

1. [State Machine 기계 계약](../../../../../contracts/state-machine/)
2. [OpenAPI 기계 계약](../../../../../contracts/api/openapi.yaml)
3. [오류 코드 Registry](../../../../../contracts/error-codes/error-codes.yaml)
4. [AI 요청·응답 Schema](../../../../../contracts/ai/)
5. 실제 [Django Runtime](../../../../../backend/)
6. 사람용 [API 명세](../../../../api/watercare_api_specification.md)와
   [화면설계서](../../../../planning/md/화면설계서.md)

[공통 개발 규칙](../../../../planning/md/공통%20개발%20규칙.md)에 따라
클라이언트는 다음 상태를 직접 지정하지 않고 행동 API를 호출한다. Backend가
역할·소유권·현재 상태·`state_version`·멱등성을 다시 검사한다.

### 2.1 기존 T-022 준비도에서 승계한 유효 기준

2026-07-27 착수 전 준비도 문서의 Model·Migration·Route `0개` 판정은
현재 사실이 아니므로 폐기한다. 다음 계약·구현 원칙만 이 설계서에
승계한다.

| 범위 | 현재 경계 | 이 설계에서 유지할 기준 |
| --- | --- | --- |
| `POST /api/v1/inquiries` | Runtime 구현 | 자연어 원문과 선택 입력 `representative_symptom_code`를 저장하고 공개 UUID를 반환 |
| `PATCH /api/v1/inquiries/{id}/questionnaire` | OpenAPI-only | 동일 `inquiry_id`에 문진을 누적하고 고객 본인 범위·Transaction을 적용 |
| `POST /api/v1/inquiries/{id}/action-results` | OpenAPI-only | 동일 `inquiry_id`에 자가조치 결과를 누적하고 실패 시 반쪽 데이터를 남기지 않음 |
| `submitSymptom` | OpenAPI·Runtime 구현, 작성자 로컬 검증 완료 | Slice A 증거 리뷰·PM 병합 뒤 소비하고 AI 효과는 Slice B에서 별도 구현 |

대표 증상은 선택 단수 필드 `representative_symptom_code`가 기준이다.
과거 후보였던 복수 `symptom_codes`를 별도 표준처럼 추가하지 않는다.
세 문의 API와 `submitSymptom`은 모두 다음 공통 경계를 지킨다.

- 다른 고객의 문의는 존재 여부를 숨기는 404로 처리한다.
- 문진·자가조치·상태 이력은 같은 문의 Public UUID 아래 누적한다.
- 저장 실패 시 Transaction 전체를 Rollback하고 기존 고객 입력을
  보존한다.
- API 완료는 Model·번호 Migration·Service·Route뿐 아니라 실제
  PostgreSQL 수직 Smoke까지 통과해야 한다.
- 제품 차단 조건에서는 AI·RAG 호출을 실행하지 않는다.

## 3. 검증된 사실

### 3.1 State Machine 계약

| 항목 | 확정 값 | 근거 |
| --- | --- | --- |
| 이벤트 | `SUBMIT_SYMPTOM` | [이벤트 계약](../../../../../contracts/state-machine/inquiry-events.yaml) |
| 작업 ID | `submitSymptom` | 이벤트 계약·[Allowed Action](../../../../../contracts/state-machine/allowed-actions.yaml) |
| 허용 역할 | `CUSTOMER` | [역할 계약](../../../../../contracts/state-machine/role-permissions.yaml) |
| 시작 상태 | `DRAFT` | [TR-INQ-002](../../../../../contracts/state-machine/transition-rules.yaml) |
| 성공 상태 | `QUESTIONNAIRE_IN_PROGRESS` | `TR-INQ-002` |
| 방문 상태 | 없어야 함(`REQUIRE_ABSENT`) | `TR-INQ-002` |
| 필수 Guard | 고객 역할, 문의 본인, 버전, 멱등 키, 증상 Payload | [Guard 계약](../../../../../contracts/state-machine/transition-guards.yaml) |
| 상태 이력 | Inquiry 상태 이력과 업무 이벤트 기록 | `TR-INQ-002` |
| 상태 버전 | 성공 시 1 증가 | [동시성 정책](../../../../../contracts/state-machine/concurrency-policy.yaml) |
| 효과 | 고객 입력 저장, 문진 제출 표시, AI 구조화 요청 | `TR-INQ-002` |
| 성공 후 고객 행동 | `SUBMIT_ANSWERS`, `CANCEL_INQUIRY` | Allowed Action 계약 |

`G-SYMPTOM-PAYLOAD-VALID`는 고객 원문 2~2000자, 문의 제품 연결,
첨부 개수·형식 검증을 요구한다. 현재 문의 생성 OpenAPI는 `raw_text`
최대 5000자를 허용하므로, 2001~5000자의 DRAFT가 제출 시 422가 되는
경계도 테스트해야 한다. 두 제한을 몰래 같게 바꾸지 않는다.

### 3.2 현재 구현된 Backend 기반

| 기반 | 현재 사실 | 재사용 방향 |
| --- | --- | --- |
| 문의 생성 | [InquiryService](../../../../../backend/apps/inquiries/services/inquiry_service.py)의 `create()`가 `START_INQUIRY`를 구현 | DRAFT와 초기 `state_version=1`을 입력 기준선으로 사용 |
| 문의 취소 | 같은 Service의 `cancel()`이 행 잠금, 소유권, 버전, 멱등성, 409, 이력을 구현 | 동시 요청 처리 순서의 검증된 기준으로 재사용 |
| 소유권 잠금 | [InquiryRepository](../../../../../backend/apps/inquiries/repositories/inquiry_repository.py)의 `lock_owned_inquiry()` | 타 고객에게 존재 여부를 숨기는 404 경계 유지 |
| 상태 계산 | [StateMachine](../../../../../backend/apps/workflow/engine/state_machine.py)이 `TR-INQ-002`를 읽어 결정적 전이를 계산 | 상태 문자열을 Service에 중복 하드코딩하지 않음 |
| Guard | [GuardEvaluator](../../../../../backend/apps/workflow/engine/guard_evaluator.py)가 역할·버전·멱등·도메인 결과를 fail-closed로 평가 | 소유권·증상 Payload 결과를 명시적으로 주입 |
| 멱등성 | [IdempotencyService](../../../../../backend/apps/workflow/services/idempotency_service.py)와 `workflow_idempotency_record` | actor + `submitSymptom` + key 범위 사용 |
| 상태 이력 | [TransitionHistoryService](../../../../../backend/apps/workflow/services/transition_history_service.py)와 `support_inquiry_status_history` | `SUBMIT_SYMPTOM`, DRAFT, QUESTIONNAIRE_IN_PROGRESS, 새 버전 기록 |
| 고객 입력 | [Inquiry](../../../../../backend/apps/inquiries/models/inquiry.py)의 `raw_text`, [SymptomEntry](../../../../../backend/apps/inquiries/models/symptom_entry.py) | 최초 입력을 덮어쓰지 않는 정책 유지 |
| 공통 응답 | 취소 Runtime의 정상·409·Replay 응답 | 새 응답도 공통 Wrapper와 공개 UUID만 사용 |

### 3.3 현재 Slice A Runtime

- [문의 URL](../../../../../backend/apps/inquiries/api/urls.py)에
  `POST /api/v1/inquiries/{inquiry_id}/submit`이 연결돼 있다.
- [문의 View](../../../../../backend/apps/inquiries/api/views.py)의
  `SubmitSymptomView`가 인증·CUSTOMER 권한, 멱등 Header, 요청·응답
  Serializer를 적용한다.
- [증상 제출 Serializer](../../../../../backend/apps/inquiries/api/serializers/symptom_submission.py)는
  양의 `state_version`만 받고 저장된 원문을 덮어쓸 추가 필드를 거부한다.
- [문의 전이 Service](../../../../../backend/apps/inquiries/services/inquiry_transition_service.py)는
  State Machine·Guard·행 잠금·멱등성·이력·응답 Snapshot을 원자적으로
  처리한다. AI Service는 호출하지 않는다.
- [OpenAPI Runtime 매핑 테스트](../../../../../backend/tests/api/test_openapi_runtime_coverage.py)는
  10개 Operation 중 Runtime 8개, OpenAPI-only 2개를 고정한다.
- [사람용 API 명세](../../../../api/watercare_api_specification.md)보다
  현행 OpenAPI와 Runtime이 우선한다.

## 4. 계약 Gap과 도미노 위험

| Gap | 그대로 구현할 때 생기는 문제 | 안전 조치 |
| --- | --- | --- |
| submit 동작 계약 | Web·Mobile이 서로 다른 Path·Body를 소비할 위험 | OpenAPI Method·Path·`operationId`·Schema·예시 확정 완료 |
| 제출 요청 경계 | 원문·첨부 덮어쓰기 위험 | `state_version`만 허용하고 추가 필드는 422로 거부 |
| `customer_message`와 `raw_text` 명칭 차이 | Guard와 API가 서로 다른 값을 검증할 위험 | Slice A는 저장된 `Inquiry.raw_text`를 Guard 입력으로 사용 |
| 제출 응답·Replay | 새 버전과 `allowed_actions` 불일치 위험 | 정상·Replay가 동일 `SubmitSymptomResult` Schema 사용 |
| ADHOC 제출 Projection | Target-only 테이블을 뜻하지 않게 활성화할 위험 | Inquiry 상태·이력에서 파생하고 `QuestionnaireSession` 신규 0 유지 |
| AI Adapter·Outbox 없음 | DB Rollback 뒤 AI만 실행되거나, DB Commit 뒤 호출 유실 | 트랜잭션 안 HTTP 금지; durable dispatch 또는 승인된 후속 Worker Gate |
| AI 결과 stale 처리 미연결 | 뒤늦은 결과가 최신 문의를 덮어씀 | 호출 시작 버전과 현재 버전을 Backend가 재비교 |
| 제출 입력 저장 정책 불명확 | 기존 고객 원문 덮어쓰기·유실 | 최초 `Inquiry.raw_text` 불변, 추가 입력은 별도 승인 저장소 없이는 받지 않음 |

## 5. 확정된 Slice A 계약

이 절은 2026-08-01 구현에 반영된 OpenAPI·Runtime 계약이다. PM 병합
전에는 팀 공용 `main` 기준선으로 인용하지 않는다.

### 5.1 외부 API

사람용 명세의 기존 후보를 유지한다.

```text
POST /api/v1/inquiries/{id}/submit
operationId: submitSymptom
Authorization: Bearer <access-token>
Idempotency-Key: <1..128자 승인 토큰>
```

신규 generic `/events` Endpoint를 동시에 만들지 않는다. 현재 공통 규칙과
취소 Runtime이 행동별 Endpoint를 사용하므로, 첫 Slice도 행동별 경계를
유지한다.

### 5.2 최소 요청

첫 Slice는 DRAFT에 이미 저장된 원문·대표 증상을 **제출 확정**하는
동작으로 제한한다.

```json
{
  "state_version": 1
}
```

제출 요청에서 새 원문·답변·첨부를 함께 받지 않는다.

- 최초 원문은 `START_INQUIRY`가 저장한 `Inquiry.raw_text`를 사용한다.
- 대표 증상은 기존 `SymptomEntry`가 있으면 사용한다.
- 추가 원문·문진 응답은 OpenAPI-only
  `PATCH /inquiries/{id}/questionnaire`의 별도 Runtime Slice에서
  누적한다.
- 이 분리는 한 요청이 입력 누적·상태 전이·AI 호출을 한꺼번에 수행하다
  부분 실패하는 것을 막는다.

`G-SYMPTOM-PAYLOAD-VALID`의 `request.customer_message`는 Slice A에서
`Inquiry.raw_text`로 해석한다. 이 매핑은 OpenAPI의 `x-state-machine`
주석과 Runtime Guard 입력에 동일하게 반영했다.

### 5.3 성공·Replay 응답 계약

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

동일 키·동일 요청 Replay는 저장된 성공 응답을 반환하되
`idempotent_replay=true`만 바꾼다. Inquiry, 상태 이력, AI dispatch를
다시 만들지 않는다.

### 5.4 ADHOC 문진 제출 Projection

현재 Active 13 정책에서는 `support_questionnaire_session`에 새 행을
만들지 않는다. Slice A에서는 ADHOC 문의의 제출 여부를
`Inquiry.status_code=QUESTIONNAIRE_IN_PROGRESS`와 해당 상태 이력에서
파생한다.

이 Projection은 화면의 `questionnaire_status=SUBMITTED` 표시를 위한
Projection일 뿐, `CARE_PRECHECK`용 `QuestionnaireSession`을 재정의하지
않는다. 후속 단계에서 별도 물리 저장이 필요하다고 결정하면 현재 Slice A를
소급 변경하지 않고 Active 13 범위와 ERD를 먼저 갱신한 뒤 별도 구현한다.

## 6. 원자적 처리 순서

한 DB 트랜잭션에서 다음 순서를 지킨다.

1. 요청 Header와 Body를 Serializer에서 형식 검증한다.
2. `actor + submitSymptom + Idempotency-Key` 범위의 기존 기록을 잠가
   동일 Hash이면 Replay, 다른 Hash이면 409로 종료한다.
3. 공개 UUID와 고객 본인 조건으로 Inquiry를 `select_for_update()`한다.
4. 행 잠금 대기 중 완료된 동일 Key가 있을 수 있으므로 멱등 기록을 다시
   확인한다.
5. 현재 상태가 `DRAFT`이고 요청 `state_version`과 현재 버전이 같은지
   확인한다.
6. `StateMachine.resolve(SUBMIT_SYMPTOM)`로 `TR-INQ-002`를 구한다.
7. `GuardEvaluator`에 인증·고객 역할·소유권·제품 연결·원문 길이·
   첨부 검증 결과를 넣고 fail-closed로 평가한다.
8. 새 멱등 기록을 만든다. Unique 충돌 시 기존 기록을 다시 읽어
   Replay 또는 409로 종료한다.
9. Inquiry 상태를 `QUESTIONNAIRE_IN_PROGRESS`로 바꾸고 버전을 1
   증가시킨다.
10. `SUBMIT_SYMPTOM` 상태 이력을 같은 트랜잭션에 한 건 저장한다.
11. 새 상태의 고객 `allowed_actions`를 계산해 응답 Snapshot을 멱등
    기록에 저장한다.
12. Commit한다.

다음 중 하나라도 실패하면 8~11의 쓰기를 모두 Rollback한다.

- 상태·버전·소유권·입력 Guard 실패
- 이력 저장 실패
- 멱등 결과 저장 실패
- 응답 Snapshot 직렬화 실패

## 7. 409·권한·입력 보존 정책

### 7.1 상태·버전 409

- 조건: 새 Key지만 요청 버전이 현재 버전과 다르거나 현재 문의 상태에서
  `SUBMIT_SYMPTOM`이 허용되지 않음
- 공개 코드: `STATE-CONFLICT-01`
- 응답 상세: `current_status`, `current_state_version`,
  `allowed_actions`
- DB 결과: Inquiry·이력·멱등 완료 기록 변경 없음
- 클라이언트: 최신 상태를 반영하고 입력을 로컬에 보존한 뒤 사용자 확인
  후 새 Key로 재요청

### 7.2 Idempotency-Key 재사용 409

- 같은 actor·`submitSymptom`·Key·같은 Hash:
  저장 응답 Replay
- 같은 actor·`submitSymptom`·Key·다른 Hash:
  `DUPLICATE-EVENT-01`
- 처리 중인 같은 Key:
  현재 Runtime 정책대로 409
- 다른 actor 또는 다른 operation:
  별도 멱등 범위

### 7.3 권한과 존재 숨김

| 요청 | 상태 | 이유 |
| --- | ---: | --- |
| 미인증 | 401 | `AUTH_REQUIRED` |
| 인증됐지만 역할이 CUSTOMER가 아님 | 403 | `FORBIDDEN` |
| 다른 고객 문의 Public UUID | 404 | IDOR 방지를 위해 존재 숨김 |
| 존재하지 않는 문의 UUID | 404 | 같은 외부 응답 |
| 본인 문의·CUSTOMER | 다음 Guard 진행 | 역할만으로 상태 전이를 허용하지 않음 |

### 7.4 고객 입력 보존

- `Inquiry.raw_text`는 절대 빈 문자열로 바꾸거나 제출 요청 값으로
  덮어쓰지 않는다.
- 409·422·AI 실패 시 기존 원문과 대표 증상은 그대로 남는다.
- 요청 Hash와 로그에는 고객 원문을 출력하지 않는다.
- 추가 입력을 받기 전에는 누적 저장소와 조회 Projection을 먼저
  확정한다. Hash만 저장하고 “입력이 보존됐다”고 주장하지 않는다.

### 7.5 계약·데이터 무결성 오류는 500 Fail-closed

`TERMINAL_STATE`·`UNLISTED_TRANSITION`처럼 정상적인 고객 상태 충돌만
409 Snapshot으로 반환한다. `AMBIGUOUS_TRANSITION`, 잘못된 Version Action,
문의·방문 상태 모순처럼 클라이언트 재시도로 해결할 수 없는 State 계약·
데이터 무결성 이상은 `INTERNAL_ERROR` 500으로 숨기고 모든 DB 쓰기를
Rollback한다. 이 구분은 같은 409의 무한 재시도를 막는다.

활성 구독과 제품 모델 연결은 PM State Guard에 새 조건을 임의 추가하지
않고 OpenAPI의 `x-runtime-preconditions`에 명시한다. 위 조건이 제출
시점에 깨졌다면 `VALIDATION_ERROR` 422이며 상태·이력·멱등 기록은 변하지
않는다.

## 8. Slice B AI Effect 경계

AI Effect는 Slice A DB 트랜잭션 안에서 실행하지 않는다.

### 8.1 확정된 AI 전달 계약

[SymptomAnalysisRequest](../../../../../contracts/ai/requests/SymptomAnalysisRequest.schema.json)은
다음 값을 요구한다.

- 문의 Public UUID `inquiry_id`
- 동일 요청 추적 `correlation_id`
- Backend 발급 `ai_request_id`
- 호출 시작 시점 `state_version`
- `raw_symptom`
- 제품 `model_code`

AI는 업무 상태를 직접 바꾸지 않는다. 응답의 `state_version`은 Echo이며
Backend가 현재 버전과 다시 비교한다.

### 8.2 아직 필요한 구현 결정

| 결정 | 담당 | 완료 증거 |
| --- | --- | --- |
| AI HTTP Endpoint와 인증·Timeout | 이동윤 + 최지용 | Adapter 통합 테스트 |
| durable dispatch 저장 위치 | 최지용 + 윤승혁 | Commit 이후 유실·중복 방지 테스트 |
| `ai_request_id` 생성·멱등 범위 | 최지용 + 이동윤 | 동일 요청 Replay·다른 Payload 충돌 |
| AI 실패·Timeout 후 재처리 상태 | 윤승혁 + 이동윤 | 상태·오류 계약과 E2E |
| stale 응답 처리 | 최지용 | 요청 버전과 현재 버전 불일치 시 적용 0건 |

현재 13개 Active 테이블 정책에서 `aiops_ai_run`을 활성화하지 않기로
했다면, durable dispatch 원장을 새로 만들거나 Target-only 테이블을
사용하는 결정을 독단적으로 하지 않는다. 이 Gate가 닫히기 전 Slice A
응답에 `AI 요청 완료`를 표시하지 않는다.

### 8.3 절대 금지

- DB 트랜잭션 내부 동기 AI HTTP 호출
- Backend 자동 재시도
- 실패한 AI 호출 때문에 고객 원문·상태 이력을 삭제
- stale AI 결과로 최신 상태·안내 필드 덮어쓰기
- 같은 `ai_request_id`의 중복 결과를 두 번 적용
- AI 응답이 State Machine Guard 없이 문의 상태를 직접 변경

## 9. 테스트 설계

### 9.1 Slice A 필수 API 테스트

| 번호 | Case | 기대 결과 |
| ---: | --- | --- |
| 1 | 본인 CUSTOMER, DRAFT, version 1, 새 Key | 200, QUESTIONNAIRE_IN_PROGRESS, version 2 |
| 2 | 성공 요청 동일 Key·동일 Body 재전송 | 200 Replay, DB 쓰기 추가 0 |
| 3 | 같은 Key·다른 version 또는 Body | 409 `DUPLICATE-EVENT-01` |
| 4 | 새 Key·stale version | 409 `STATE-CONFLICT-01`과 최신 Snapshot |
| 5 | 다른 고객 문의 | 404, 대상 변경 0 |
| 6 | CONSULTANT·TECHNICIAN·OPERATOR | 403, 대상 변경 0 |
| 7 | 미인증 | 401 |
| 8 | DRAFT가 아닌 상태 | 409, 현재 Snapshot |
| 9 | 누락·빈 Idempotency-Key | 422 |
| 10 | 누락·0 이하 state_version | 422 |
| 11 | 기존 raw_text 1자 또는 2001자 이상 | 422, 원문 보존 |
| 12 | 제품 연결 없음·비활성 구독 | 422 또는 승인된 접근 오류, AI 호출 0 |
| 13 | 동시 동일 Key 2요청 | 성공 1·Replay 1, 이력 1 |
| 14 | 동시 다른 Key·같은 version | 성공 1·409 1, 이력 1 |
| 15 | 이력 저장 강제 실패 | 전체 Rollback |
| 16 | 응답에서 내부 정수 PK 비노출 | Public UUID만 노출 |

### 9.2 Slice B 필수 통합 테스트

- DB Commit 전 AI 호출 0
- Commit 후 dispatch 1건
- Replay 시 dispatch 추가 0
- Timeout 시 고객 입력·상태·이력 유지
- 같은 `ai_request_id` 결과 2회 적용 시 최초 1회만 인정
- 호출 버전과 현재 문의 버전이 다르면 업무 결과 적용 0
- 정상·위험·근거 없음·Schema 오류 결과가 Backend 자동 이벤트 Guard를
  각각 통과하거나 안전하게 차단
- Header·응답·Backend·AI 로그의 `correlation_id` 일치
- 고객 원문·Authorization·Cookie·비밀키 로그 비노출

## 10. 작업 → 검증 실행 순서

| 순서 | 한 번에 한 작업 | 바로 뒤 검증 | 2026-08-01 결과 |
| ---: | --- | --- | --- |
| 0 | submit OpenAPI 계약과 ADHOC 제출 Projection 확정 | OpenAPI 참조·예시·Operation inventory 검사 | 완료 — OpenAPI 10·Runtime 8·OpenAPI-only 2 |
| 1 | 요청·응답 Serializer 구현 | Serializer 정상·경계·추가 필드 거부 테스트 | 완료 |
| 2 | Repository의 본인 문의 잠금·상태 저장 추가 | 소유권 404·row lock·Rollback 단위 테스트 | 완료 |
| 3 | Service에서 StateMachine·Guard 연결 | DRAFT 정상·역할·버전·Payload Guard 테스트 | 완료 |
| 4 | 멱등성·이력·응답 Snapshot 연결 | Replay·다른 Hash 409·동시 요청 테스트 | 완료 |
| 5 | 행동별 View·Route 연결 | API 정상·401·403·404·409·422 | 완료 |
| 6 | PostgreSQL 집중 검증 | 동시 요청, 이력 Unique, 전체 Rollback | 완료 — 작성자 환경 |
| 7 | Slice A 전체 Backend 회귀 | OpenAPI·SQLite·PostgreSQL 회귀 | 완료 — 작성자 환경, 비작성자 리뷰 대기 |
| 8 | AI durable dispatch 경계 구현 | Commit/Replay/Timeout/stale 테스트 | 미착수 — Slice B로 분리 |
| 9 | AI 결과 소비와 자동 이벤트 연결 | 정상·위험·근거 없음·오류 E2E | 미착수 — T-022 전체 완료 주장 금지 |

## 11. 검증 명령

현재 계약·Runtime 기준선은 저장소 루트에서 다음 명령으로 검사한다.

```powershell
& .\backend\.venv\Scripts\python.exe -B -m pytest `
  -q -p no:cacheprovider `
  backend/tests/api/test_openapi_runtime_coverage.py `
  backend/tests/api/test_t022_create_inquiry.py `
  backend/tests/api/test_t023_cancel_inquiry.py `
  backend/tests/unit/workflow/test_state_machine.py `
  backend/tests/unit/workflow/test_guard_evaluator.py
```

변경 전 기준선은 `40 passed`였다. 구현 후에는 다음 집중 검증을 추가했다.

```powershell
& .\backend\.venv\Scripts\python.exe -B -m pytest `
  -q -p no:cacheprovider `
  backend/tests/api/test_t022_submit_symptom.py `
  backend/tests/unit/inquiries/test_t022_submit_symptom_serializer.py

& .\backend\.venv\Scripts\python.exe -B -m pytest `
  -q -p no:cacheprovider `
  backend/tests/api `
  backend/tests/unit/inquiries `
  backend/tests/unit/workflow

& .\backend\.venv\Scripts\python.exe .\backend\manage.py `
  makemigrations --check --dry-run `
  --settings=config.settings.local

& .\backend\.venv\Scripts\python.exe .\backend\manage.py `
  migrate --check --noinput `
  --settings=config.settings.local
```

2026-08-02 작성자 환경의 현재 결과는 다음과 같다.

| 검증 | 결과 | 판정 |
| --- | --- | --- |
| 자연어 단독 Submit 포함 집중 | SQLite `30 passed, 2 skipped`; PostgreSQL `22 passed` | PASS |
| 계약·Runtime·예시·권한 집중 | `72 passed, 2 skipped` | PASS |
| Django Check·Migration drift·적용 상태 | 오류 0·변경 0·미적용 0 | PASS |
| SQLite 전체 단일 실행 | `778 passed, 13 skipped` | PASS |
| PostgreSQL 전체 최초 실행 | 로컬 Demo Login·CORS 값 영향으로 `3 failed, 788 passed` | 환경 격리 누락 |
| PostgreSQL 실패 3건 재검증 | 테스트용 환경값을 프로세스에만 적용해 `3 passed` | PASS |
| PostgreSQL 전체 격리 재실행 | `791 passed` | PASS |

PostgreSQL 전체 회귀는 `--ds=config.settings.local`과 검증용 환경값을
사용하되 `.env` 값은 출력하지 않는다. 최초 전체 실행의 3건은
`DJANGO_DEMO_LOGIN_ENABLED`와 `DJANGO_CORS_ALLOWED_ORIGINS`의 로컬 실행값이
테스트 기본값보다 우선해 발생했다. 두 값을 테스트 프로세스에만
`false`와 `https://approved.example`로 적용한 재실행에서 전체 791건이
통과했다. `.env`는 수정하지 않았다.

남은 팀 Gate는 비작성자의 새 테스트 DB 독립 재현, PM 계약·병합 검토,
병합된 `main`의 Web·Mobile 소비 Smoke다. Seed·Importer는 T-005 합의
기준선이므로 T-022 Slice A가 변경하지 않는다.

## 12. 완료·중단 판정

### 12.1 Slice A 완료

- OpenAPI에 `submitSymptom` Method·Path·Schema·응답·예시가 존재
- 정상·권한·404·409·422·Replay 계약 테스트 통과
- Inquiry 상태와 버전이 한 번만 변경
- 상태 이력과 멱등 결과가 한 번만 저장
- 실패·Replay에서 고객 입력과 DB 수량 불변
- PostgreSQL 동시 요청 결과가 결정적
- 내부 PK·원문·Token 비노출

### 12.2 Slice A를 끝내도 남는 항목

- 실제 AI HTTP 호출
- AI 실행·검색·근거 저장
- `SUBMIT_ANSWERS` Runtime
- OpenAPI-only 문진 누적·자가조치 결과 Runtime
- AI 자동 이벤트와 최종 안내 화면 E2E

### 12.3 즉시 중단 조건

- OpenAPI와 PM State 계약이 서로 다른 Path·Body·상태를 요구
- Active 13을 넘어 새 물리 테이블 활성화가 필요
- 원문 보존 없이 기존 값을 덮어써야만 구현 가능
- AI 호출을 DB 트랜잭션 안에서 해야만 정상처럼 보임
- 같은 Key Replay가 상태·이력·AI 호출을 중복 생성
- 타 고객 요청이 403 또는 데이터 존재를 드러내는 응답으로 바뀜

## 13. 협업 인계

| 순서 | 담당 | 현재 요청 내용 | 완료·반환 증거 |
| ---: | --- | --- | --- |
| 1 | 최지용 | Slice A OpenAPI·Runtime을 작업→검증 단위로 구현 | 완료 — 계약·집중·PostgreSQL·전체 회귀 |
| 2 | 김은진 또는 지정 비작성자 | 새 테스트 DB에서 Active 13·원문 보존·동시 요청·Rollback·Replay 독립 검증 | 명령·환경·Exit code·불일치 목록 |
| 3 | 윤승혁 | `submitSymptom`과 PM State 계약의 불일치 0 확인 후 병합 여부 결정 | PR 리뷰·병합 또는 변경 요청 |
| 4 | 한예나·양정현 | PM 병합 뒤 실제 API의 UUID·401/403/404/409/422·Replay 소비 확인 | Web·Mobile Smoke 결과 |
| 5 | 이동윤·최지용 | Slice B AI Endpoint·`ai_request_id`·Timeout·stale·durable dispatch 계약을 별도 확정·구현 | 정상·위험·근거 없음·오류 E2E |

팀원은 이 문서를 “구현 완료 보고서”가 아니라 **착수 전 충돌 제거
설계서**로 사용한다.
