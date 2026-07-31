# T-022 `SUBMIT_SYMPTOM` 첫 수직 Slice 안전 설계

> 기준일: 2026-07-31
> 작성·설계 책임: 최지용(Backend·Database)
> 협업·검토: 윤승혁(PM·State 계약), 김은진(Data·QA), 이동윤(AI·RAG)
> 상태: `OWNER_DESIGN_READY_CONTRACT_GATES_PENDING`
> 구현 여부: **미구현 — 이 문서는 설계와 착수 Gate만 고정한다.**
> 실행 원칙: `계약 확인 → 한 작업 구현 → 집중 검증 → 다음 작업`
> 데이터 원칙: WaterBridge Active 13 범위를 유지하고 Target-only 19를
> 임의 활성화하지 않는다.

## 1. 결론

`SUBMIT_SYMPTOM`의 상태 전이 자체는 구현 준비가 되어 있다.
[PM State Machine 계약](../../../../../contracts/state-machine/transition-rules.yaml)은
`DRAFT → QUESTIONNAIRE_IN_PROGRESS`, 고객 본인, `state_version`,
`Idempotency-Key`, 입력 유효성, 이력 저장을 모두 정의하고 있으며
현재 Backend에는 문의 행 잠금, 멱등성 저장·Replay, 409 응답, 상태 이력
기반 코드가 있다.

그러나 지금 바로 Runtime을 구현하면 안 된다. 다음 세 가지가 기계 계약
또는 물리 경계에서 아직 닫히지 않았다.

1. `operation_id=submitSymptom`은 State 계약에 있으나
   [OpenAPI](../../../../../contracts/api/openapi.yaml)에는 Method·Path·
   요청·응답 Schema가 없다.
2. `MARK_QUESTIONNAIRE_SUBMITTED`가 ADHOC 문의에서 어느 Active 13
   테이블에 저장되는지 확정되지 않았다. 현재 `QuestionnaireSession`은
   `CARE_PRECHECK` 전용이고 Target-only 범위다.
3. `REQUEST_AI_STRUCTURING` 효과를 실행할
   [Backend AI Service](../../../../../backend/apps/inquiries/services/inquiry_ai_service.py)와
   [AI Adapter](../../../../../backend/integrations/ai/client.py)는 아직
   설명 문자열만 있다. DB 트랜잭션 안에서 AI HTTP 호출을 임의로 추가하면
   중복 호출과 부분 커밋 위험이 생긴다.

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

### 3.3 현재 Runtime 미구현

- [문의 URL](../../../../../backend/apps/inquiries/api/urls.py)에는 생성과
  취소만 있다.
- [문의 View](../../../../../backend/apps/inquiries/api/views.py)에
  `SubmitSymptomView`가 없다.
- [증상 제출 Serializer](../../../../../backend/apps/inquiries/api/serializers/symptom_submission.py)는
  설명 문자열만 있다.
- [문의 전이 Service](../../../../../backend/apps/inquiries/services/inquiry_transition_service.py)와
  AI Service는 설명 문자열만 있다.
- [OpenAPI Runtime 매핑 테스트](../../../../../backend/tests/api/test_openapi_runtime_coverage.py)는
  9개 Operation 중 Runtime 7개, OpenAPI-only 2개를 고정한다.
  `submitSymptom`은 이 9개 Operation에도 포함되지 않는다.
- [사람용 API 명세](../../../../api/watercare_api_specification.md)의
  `POST /api/v1/inquiries/{id}/submit`은
  `DESIGN_BASELINE_ONLY`이며 기계 계약이 아니다.

## 4. 계약 Gap과 도미노 위험

| Gap | 그대로 구현할 때 생기는 문제 | 안전 조치 |
| --- | --- | --- |
| OpenAPI에 submit 동작 없음 | Web·Mobile이 서로 다른 Path·Body를 소비 | Method·Path·`operationId`·Schema·예시를 먼저 기계 계약으로 고정 |
| 빈 `SymptomSubmissionRequest` | `state_version`, 원문, 첨부의 필수 여부가 구현자마다 달라짐 | 실질 Schema 확정 전 Serializer·View 구현 금지 |
| `customer_message`와 `raw_text` 명칭 차이 | Guard와 API가 서로 다른 값을 검증 | 외부 필드 하나를 확정하고 Service 매핑을 명문화 |
| 제출 응답 Schema 없음 | Replay·`allowed_actions`·새 버전의 형태가 불일치 | 정상·Replay가 동일 Schema를 쓰도록 확정 |
| ADHOC `questionnaire_status` 저장 위치 없음 | Target-only `QuestionnaireSession`을 뜻하지 않게 활성화 | ADHOC Projection 파생 여부를 PM·DB OWNER가 확정 |
| AI Adapter·Outbox 없음 | DB Rollback 뒤 AI만 실행되거나, DB Commit 뒤 호출 유실 | 트랜잭션 안 HTTP 금지; durable dispatch 또는 승인된 후속 Worker Gate |
| AI 결과 stale 처리 미연결 | 뒤늦은 결과가 최신 문의를 덮어씀 | 호출 시작 버전과 현재 버전을 Backend가 재비교 |
| 제출 입력 저장 정책 불명확 | 기존 고객 원문 덮어쓰기·유실 | 최초 `Inquiry.raw_text` 불변, 추가 입력은 별도 승인 저장소 없이는 받지 않음 |

## 5. Slice A OWNER 제안

이 절은 **구현 중인 계약이 아니라 검토할 OWNER 제안**이다. 승인 전
OpenAPI·Runtime 사실로 인용하지 않는다.

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
`Inquiry.raw_text`로 해석한다는 계약 주석이 필요하다. 이 매핑이
승인되지 않으면 request body에 새 원문을 추가하지 말고 해당 Gate에서
멈춘다.

### 5.3 성공·Replay 응답 제안

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
파생하는 방안을 제안한다.

이 제안은 화면의 `questionnaire_status=SUBMITTED` 표시를 위한
Projection일 뿐, `CARE_PRECHECK`용 `QuestionnaireSession`을 재정의하지
않는다. PM과 김은진이 별도 물리 저장이 필요하다고 결정하면 Active 13
범위와 ERD를 먼저 갱신한 뒤 구현한다.

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

### 7.1 상태 버전 409

- 조건: 새 Key지만 요청 버전이 현재 버전과 다름
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

| 순서 | 한 번에 할 작업 | 바로 뒤 검증 | 실패 시 |
| ---: | --- | --- | --- |
| 0 | submit OpenAPI 계약과 ADHOC 제출 Projection 확정 | OpenAPI 참조·예시·Operation inventory 검사 | Runtime 착수 중단 |
| 1 | 요청·응답 Serializer만 구현 | Serializer 정상·경계·추가 필드 거부 테스트 | View 미착수 |
| 2 | Repository의 본인 문의 잠금·상태 저장 추가 | 소유권 404·row lock·Rollback 단위 테스트 | Service 미착수 |
| 3 | Service에서 StateMachine·Guard 연결 | DRAFT 정상·역할·버전·Payload Guard 테스트 | Route 미착수 |
| 4 | 멱등성·이력·응답 Snapshot 연결 | Replay·다른 Hash 409·동시 요청 테스트 | Route 미착수 |
| 5 | 행동별 View·Route 연결 | API 정상·401·403·404·409·422 | AI 연동 미착수 |
| 6 | PostgreSQL 집중 검증 | 동시 요청, 이력 Unique, 전체 Rollback | AI 연동 미착수 |
| 7 | Slice A 전체 Backend 회귀 | OpenAPI 9+변경분, SQLite·PostgreSQL 회귀 | 인계 중단 |
| 8 | AI durable dispatch 경계 구현 | Commit/Replay/Timeout/stale 테스트 | 자동 이벤트 미착수 |
| 9 | AI 결과 소비와 자동 이벤트 연결 | 정상·위험·근거 없음·오류 E2E | 완료 주장 금지 |

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

2026-07-31 실행 결과는 `40 passed`다. 이 수치는 기존 생성·취소·
State Engine 기준선이며, `SUBMIT_SYMPTOM` Runtime 통과 수치가 아니다.

구현 후에는 최소 다음을 추가한다.

```powershell
& .\backend\.venv\Scripts\python.exe -B -m pytest `
  -q -p no:cacheprovider `
  backend/tests/api/test_t022_submit_symptom.py

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

마지막 Gate는 같은 Commit의 빈 PostgreSQL Migration, Seed 2회,
PostgreSQL 전체 회귀, Web·Mobile 소비 Smoke다.

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

| 순서 | 담당 | 요청 내용 | 받으면 확인할 증거 |
| ---: | --- | --- | --- |
| 1 | 최지용 | 본 문서의 Slice A API 제안과 ADHOC Projection 제시 | 변경 전 계약 Diff |
| 2 | 윤승혁 | `submitSymptom` Path·요청·응답, `MARK_QUESTIONNAIRE_SUBMITTED` 의미 검토 | PM State 계약과 불일치 0 |
| 3 | 김은진 | Active 13 유지·입력 보존·동시 요청·QA Case 검토 | DB 수량·Rollback·Replay 기준 |
| 4 | 이동윤 | AI Endpoint·`ai_request_id`·Timeout·stale 결과 인계 | AI 계약 버전과 실행 명령 |
| 5 | 최지용 | Slice A를 작업→검증 단위로 구현 | PostgreSQL 집중·전체 회귀 |
| 6 | 이동윤·최지용 | Slice B Adapter·dispatch·결과 소비 구현 | 정상·위험·근거 없음·오류 E2E |
| 7 | 윤승혁·김은진 | 비작성자 검토와 완료 승인 | 40자리 main SHA·같은 Commit 증거 |

팀원은 이 문서를 “구현 완료 보고서”가 아니라 **착수 전 충돌 제거
설계서**로 사용한다.
