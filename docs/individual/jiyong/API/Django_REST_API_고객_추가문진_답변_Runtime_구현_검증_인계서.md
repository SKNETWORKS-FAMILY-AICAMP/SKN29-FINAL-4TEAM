# Django REST API 고객 추가문진 답변 계약 적용·Runtime 보류 인계서

- 작성일: 2026-08-10 KST
- 담당: 최지용 — Backend·DB
- 관련 업무: T-022, `SUBMIT_ANSWERS`
- 현재 판정: `OPENAPI_CONFIRMED / RUNTIME_NOT_IMPLEMENTED / POSTGRESQL_BLOCKED / QA_PENDING`
- 계약 버전: OpenAPI `0.8.0`

## 1. 결론

PM이 승인한 고객 추가답변 HTTP 경계를 지금 기계 계약에 적용했다.

```http
POST /api/v1/inquiries/{inquiry_uuid}/answers
Authorization: Bearer <customer_access_token>
Idempotency-Key: <unique-key>
X-Correlation-ID: <uuid>
```

- `operationId`: `submitFollowUpAnswers`
- Event: `SUBMIT_ANSWERS`
- Transition: `TR-INQ-003`
- Actor: 본인 문의를 소유한 `CUSTOMER`
- 현재 Runtime 상태: `NOT_IMPLEMENTED`

이 문서는 과거 로컬 `PATCH /questionnaire` 후보를 완료 Runtime으로 승인하지
않는다. 최신 main의 기존 `PATCH /questionnaire` 계약은 원래
`accumulateInquiryQuestionnaire` 의미로 유지하고, 새 답변 Runtime URL은
등록하지 않았다.

## 2. 왜 Runtime을 보류했는가

단순히 PATCH를 POST로 바꾸면 저장 의미가 깨질 수 있다.

| 확인된 충돌 | 현재 안전 판정 |
| --- | --- |
| PM 입력은 `answer_text` 또는 `answer_payload`, 로컬 후보는 `response_kind` 필수 | PM 계약을 우선하고 Runtime 보류 |
| `InquiryQA.answer_payload`가 AI 질문 옵션·Target Field 저장에도 사용됨 | 질문 Metadata와 고객 답변 Payload 분리 설계 필요 |
| 일반 구조화 Payload가 AI `previous_answers`로 전달되지 않음 | Mapper 계약 확정 전 Dispatch 금지 |
| 거절·모름의 공개 JSON 형태가 PM 계약에 없음 | 임의 필드 승격 금지 |
| 고객 최신 질문 Snapshot 전용 GET이 없음 | PATCH 응답을 독립 조회 완료로 확대 금지 |
| PostgreSQL 연결 Timeout | Row lock·실동시성 PASS 금지 |

PM 적용 요청서의 원칙에 따라 Model·Payload 충돌을 임의 매핑하지 않고
`OPENAPI_CONFIRMED / NOT_IMPLEMENTED`로 남겼다.

## 3. 적용한 요청 계약

```json
{
  "state_version": 2,
  "answers": [
    {
      "question_id": "31b58743-d099-4e9b-99d8-73017c7fb129",
      "answer_text": "필터 교체 직후부터입니다."
    },
    {
      "question_id": "b4f2bc98-a238-4f15-95e4-9512661830b5",
      "answer_payload": {
        "selected_option": "FILTER_REPLACED"
      }
    }
  ]
}
```

계약 규칙:

- `state_version`은 1 이상의 정수다.
- `answers`는 1~50개다.
- `question_id`는 UUID이며 배열 안에서 중복할 수 없다.
- 각 답변은 `answer_text`와 `answer_payload` 중 정확히 하나만 사용한다.
- Runtime이 열리면 `Idempotency-Key`, `X-Correlation-ID`, 객체 소유권,
  State Version, 409 복구를 함께 구현해야 한다.
- 거절·모름, 선택형 Payload의 세부 Shape는 후속 계약 결정 전 임의로 만들지 않는다.

기계 계약 정본:

- [OpenAPI](../../../../contracts/api/openapi.yaml)
- [Workflow Path](../../../../contracts/api/paths/workflow.yaml)
- [요청 Schema](../../../../contracts/api/components/schemas/questionnaire/SubmitFollowUpAnswersRequest.yaml)
- [답변 항목 Schema](../../../../contracts/api/components/schemas/questionnaire/FollowUpAnswerRequest.yaml)
- [Action Crosswalk](../../../../contracts/api/action-operation-crosswalk.yaml)
- [State Transition](../../../../contracts/state-machine/transition-rules.yaml)

예시:

- [요청](../../../../contracts/api/examples/workflow/submit-followup-answers-request.json)
- [성공 응답](../../../../contracts/api/examples/workflow/submit-followup-answers-success-response.json)

## 4. 함께 적용한 PM 승인 8 Action

| Event | Method·Path | 현재 상태 |
| --- | --- | --- |
| `SUBMIT_ANSWERS` | `POST /inquiries/{id}/answers` | OpenAPI 확인, Runtime 미구현 |
| `REQUEST_CONSULTATION` | `POST /inquiries/{id}/request-consultation` | OpenAPI 확인, Runtime 미구현 |
| `START_VISIT` | `POST /visits/{visit_id}/start` | OpenAPI 확인, Runtime 미구현 |
| `VISIT_COMPLETED` | `POST /visits/{visit_id}/complete` | OpenAPI 확인, Runtime 미구현 |
| `SUBMIT_RESOLUTION_FEEDBACK` | `POST /inquiries/{id}/resolution-feedback` | OpenAPI 확인, Runtime 미구현 |
| `FINALIZE_INQUIRY` | `POST /inquiries/{id}/finalize` | OpenAPI 확인, Runtime 미구현 |
| `CUSTOMER_REPORTED_UNRESOLVED` | `POST /inquiries/{id}/report-unresolved` | OpenAPI 확인, Runtime 미구현 |
| `RESUME_CONSULTATION` | `POST /inquiries/{id}/resume-consultation` | OpenAPI 확인, Runtime 미구현 |

현재 게시 후보 기준 전체 Crosswalk는
`RUNTIME_IMPLEMENTED 11 / OPENAPI_CONFIRMED 8 / CONTRACT_ONLY 0 / DEFERRED 4`다.
이번 계약 변경은 앞서 게시된 상담·방문 Runtime 증거를 보존하고, PM이 승인한
8개 신규 경계만 `OPENAPI_CONFIRMED`로 추가한다.

## 5. Runtime 재착수 전 필수 설계

1. `InquiryQA`의 AI 질문 Metadata와 고객 답변 Payload를 물리적으로 분리한다.
2. 기존 Row를 보존하는 새 Forward Migration과 데이터 감사 절차를 작성한다.
3. `answer_payload`의 허용 JSON 형태·크기·깊이를 계약한다.
4. 거절·모름 Wire 표현을 PM·Mobile·AI와 확정한다.
5. 질문 Metadata 비노출과 Payload Round-trip을 Contract Test로 고정한다.
6. 고객 최신 Snapshot 조회 또는 409 복구 계약을 별도 결정한다.
7. 답변 Commit 이후에만 AI 재평가를 Dispatch한다.
8. 격리 PostgreSQL에서 멱등·Version 경쟁을 재현한다.

적용된 Migration을 직접 수정하지 않는다. 변경이 필요하면 새 번호의 Forward
Migration으로만 진행한다.

## 6. 검증 결과

```text
OpenAPI Validator: PASS — 30 paths, 31 operations
Action Crosswalk Validator: PASS — 11/8/0/4, confirmed 19
Example Validator: PASS — API 50/50
State Machine Validator: PASS — 1.0.0, 30 events, 34 transitions
Root Contract Test: 12 passed
Backend 표적 Contract Test: 39 passed
T-022 Readiness Test: 35 passed
Backend 전체: 901 passed, 14 skipped, 0 failed
Django system check: PASS
makemigrations --check --dry-run: No changes detected
Git whitespace check: PASS
PostgreSQL Runtime Test: NOT_RUN — 계약-only 후보
```

Skip 14건은 PostgreSQL 전용 구조·행 잠금 또는 명시적 opt-in Test다.
Skip을 Runtime PASS로 계산하지 않는다.

## 7. QA 인계 기준

현재 QA가 검증할 수 있는 범위는 계약 후보다.

1. 8개 Method·Path·operationId·Event·Transition 정합
2. `state_version`, 두 Header, 409 오류 계약
3. 추가답변 `answer_text`·`answer_payload` XOR
4. 방문 Version·결과 코드·완료 시각 계약
5. 16개 요청·성공 Example
6. OpenAPI·Example·Crosswalk·State Machine Validator

Runtime·PostgreSQL QA는 Model/Payload 분리와 POST 구현 후보가 나온 뒤 별도
요청한다. 공식·공유 DB에는 승인 없이 Migration·Rollback·Seed를 실행하지 않는다.

## 8. 완료 주장 경계

현재 가능한 주장:

- `PM_8_ACTION_OPENAPI_APPLIED`
- `SUBMIT_ANSWERS_CONTRACT_CONFIRMED`
- `SUBMIT_ANSWERS_RUNTIME_ROUTE_NOT_ADDED`
- `AUTHOR_NON_POSTGRES_REGRESSION_PASS`

현재 금지하는 주장:

- `SUBMIT_ANSWERS_RUNTIME_IMPLEMENTED`
- T-022 전체 완료
- PostgreSQL 동시성 PASS
- AI 재평가·실 Backend↔AI E2E 완료
- 고객 최신 Snapshot GET 완료
- 독립 QA·PM 완료 판정

다음 실행 순서는 **Payload 저장 구조 결정 → Forward Migration → POST Runtime →
Contract/API Test → 격리 PostgreSQL → 독립 QA → PM WBS 반영**이다.
