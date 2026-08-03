# Django State Machine API 구현·검증·인계서

> 기준일: 2026-08-02 KST
> 구현·검증 책임: Backend·Database 담당
> 계약 책임: State Machine 계약 담당(PM)
> 협업·검토 역할: Data·QA·DevOps, AI·RAG, Web, Mobile 담당
> 현재 판정: 공통 기반과 세 개의 Action Slice 로컬 검증 완료, 전체 Action Runtime 미완료 (`T023_CORE_PARTIAL_LOCAL_VERIFIED`)
> 범위 판정: **State 계약·Engine·Guard·정적 Allowed Action 기반과 START·SUBMIT·DRAFT 고객 CANCEL 수직 흐름은 존재한다. 전체 T-023 Action Runtime은 미완료다.**

이 문서는 T-023의 현재 구현, 검증 증거, 실제 결손과 후속 인계 경계를
한곳에서 확인하는 주요 작업 문서다. [2026-07-31 작업 진행도](../최지용_작업_진행도_07311640.md)는
당시 62% 스냅샷이므로 수정하지 않는다. 그 문서 이후 로컬에 추가된
`SUBMIT_SYMPTOM` Runtime과 최신 회귀는 이 문서에서 별도로 반영한다.

문서 작성은 WBS 상태를 자동으로 바꾸지 않는다. 2026-08-02 구현은 작성자
로컬 검증 범위이며, 비작성자 재현·계약 검토·팀 기준선 반영 없이
`T-023 완료`로 표시하지 않는다.

## 1. 최종 판정

T-023은 `미구현`도 아니고 `완료`도 아니다. 정확한 판정은 **공통
State Machine 기반과 세 개의 최소 Action Slice가 구현됐지만, 상담·방문·AI
내부 이벤트·완료 정책까지 연결하는 범용 전이 Runtime은 아직 없는 상태**다.

| 범위 | 현재 상태 | 근거 | 완료를 막는 항목 |
| --- | --- | --- | --- |
| PM State 계약 v1.0.0 | 팀 승인 완료 (`TEAM_APPROVED`) | [State 계약 README](../../../../contracts/state-machine/README.md)와 6개 기계 계약 | 계약 변경 시 공동 변경 절차 필요 |
| Loader·Validator·Engine·Guard | 구현·집중 검증 | [Workflow Engine](../../../../backend/apps/workflow/engine/)과 계약 회귀 | 실제 모든 Action을 호출하는 공통 Orchestrator 없음 |
| `allowed_actions` | 정적 State·Role 조회 구현 | [AllowedActionResolver](../../../../backend/apps/workflow/engine/allowed_action_resolver.py) | Visit 조건·동적 Guard·담당자 조건을 아직 평가하지 않음 |
| `START_INQUIRY` | Runtime 구현 | Inquiry 생성, DRAFT v1, 이력, 멱등성 | 공통 StateMachine·Guard 경로를 사용하지 않음 |
| `SUBMIT_SYMPTOM` | Slice A 로컬 구현·검증 | DRAFT → QUESTIONNAIRE_IN_PROGRESS, Engine·Guard·409·Replay·PG 동시성 | AI 구조화 효과와 제품 실패 내부 전이 미구현 |
| `CANCEL_INQUIRY` | DRAFT 고객 Slice 구현·검증 | 사유 저장, v2, 409, Replay, Rollback, 이력 | QIP 취소·상담사·운영자 취소 미구현, 공통 Engine 미사용 |
| SYSTEM 이벤트 | 계약만 존재 | `SAFE_GUIDANCE_READY`, `DANGER_DETECTED`, `NO_EVIDENCE` | 내부 인증·AI 결과 검증·효과 저장·SYSTEM 이력 미구현 |
| 상담 요청 | State 계약만 존재 | `REQUEST_CONSULTATION`과 전이 규칙 | OpenAPI·Route·Serializer·UPSERT Service 없음 |
| 상담·방문·완료 Action | Model·Migration 기반만 존재 | Consultation·Visit Model | URL·View·Service·Repository가 설명 문자열뿐이고 `/api/v1` 미등록 |
| 공식 완료 | 미충족 | [WBS T-023](../../../planning/md/WBS.md) | 전체 Action, 담당자 권한, 완료·재개, 독립 검토·통합 증거 부족 |

WBS의 `미착수`는 현재 로컬 코드의 부재를 뜻하지 않는다. WBS 완료 기준이
`COMPLETION_PENDING`, `REOPENED`, `FINALIZE_INQUIRY`, 상담·방문 담당자,
고객 행동과 방문 일정 이력까지 포함하므로 현재 세 Slice만으로 상태를
`완료`로 올릴 수 없다는 뜻으로 해석해야 한다.

## 2. 프로젝트 구조와 책임 경계

```text
contracts/state-machine/
├─ inquiry-states.yaml          상태·종료 상태
├─ inquiry-events.yaml          외부 Action·SYSTEM_EVENT
├─ transition-rules.yaml        상태·이벤트·Visit·Effect
├─ transition-guards.yaml       역할·소유권·버전·안전 Guard
├─ allowed-actions.yaml         상태·역할별 행동 후보
├─ role-permissions.yaml        역할별 이벤트·리소스 범위
└─ concurrency-policy.yaml      Lock·state_version·멱등·409

backend/apps/workflow/
├─ contracts/                   YAML Loader·Validator
├─ domain/                      Snapshot·Event·Transition 값 객체
├─ engine/                      StateMachine·Guard·AllowedActionResolver
├─ models/                      TransitionHistory·IdempotencyRecord
├─ repositories/                이력·멱등성 ORM 경계
└─ services/                    Replay·이력 기록

backend/apps/inquiries/
├─ api/                         START·SUBMIT·CANCEL Route·Serializer·View
├─ repositories/                owner lock·상태 저장·Visit 상태 조회
└─ services/                    InquiryService·InquiryTransitionService

backend/apps/consultations/      Model·Migration만 존재, URL·View·Serializer·Service 미구현
backend/apps/visits/             Model·Migration만 존재, URL·View·Serializer·Service 미구현
backend/tests/                   계약·Engine·Action·이력·동시성 검증
```

외부 클라이언트가 다음 상태를 지정하지 않는다. Web·Mobile은 행동 API를
호출하고, Django Backend가 현재 상태·역할·담당자·버전·멱등성·Guard를
확인한 뒤 상태와 이력을 같은 트랜잭션에서 저장해야 한다. AI도 DB 상태를
직접 바꾸지 않고 내부 이벤트 후보와 검증 데이터를 Backend에 전달한다.

## 3. Action별 현재 구현

### 3.1 `START_INQUIRY`

```text
POST /api/v1/inquiries
event: START_INQUIRY
result: null → DRAFT, state_version=1
actor: CUSTOMER
```

[InquiryService.create](../../../../backend/apps/inquiries/services/inquiry_service.py)는
다음을 구현한다.

- 활성 상태이며 요청 고객이 소유한 구독을 Public UUID로 조회한다.
- `actor + startInquiry + Idempotency-Key` 범위의 요청 Hash를 저장한다.
- Inquiry를 `DRAFT`, `state_version=1`로 생성한다.
- 선택 대표 증상과 선택 문진 연결을 저장한다.
- `START_INQUIRY` 상태 이력과 `correlation_id`를 남긴다.
- Backend 계산 결과인 DRAFT 고객 `allowed_actions`를 반환한다.
- 동일 Key·동일 요청은 저장 응답을 Replay하고, 다른 요청은 409로 거부한다.

다만 이 흐름은 [StateMachine](../../../../backend/apps/workflow/engine/state_machine.py)과
[GuardEvaluator](../../../../backend/apps/workflow/engine/guard_evaluator.py)를
직접 호출하지 않는다. 소유 구독 조회와 생성 Service가 `TR-INQ-001`의
일부 Guard·Effect를 개별 구현한 수직 Slice다. `START_INQUIRY`가 동작한다는
사실과 모든 Action이 공통 전이 경로를 사용한다는 주장은 구분한다.

### 3.2 `SUBMIT_SYMPTOM`

```text
POST /api/v1/inquiries/{inquiry_id}/submit
event: SUBMIT_SYMPTOM
result: DRAFT → QUESTIONNAIRE_IN_PROGRESS, state_version 1 → 2
actor: CUSTOMER owner
```

[InquiryTransitionService.submit_symptom](../../../../backend/apps/inquiries/services/inquiry_transition_service.py)는
현재 세 흐름 중 StateMachine·Guard를 실제 Action Runtime에 연결한 대표
Slice다.

- Inquiry를 `select_for_update`로 잠그고 현재 Inquiry·Visit Snapshot을 만든다.
- `TR-INQ-002`를 Engine에서 결정적으로 선택한다.
- 고객 역할·owner·`state_version`·멱등 키·저장된 증상 Payload Guard를
  fail-closed로 검사한다.
- 저장된 자연어 원문을 덮어쓰지 않고 제출을 확정한다.
- 성공 상태·버전, 상태 이력, 멱등 응답을 한 Transaction에서 기록한다.
- 동일 Key 대기 요청은 Inquiry lock 이후 멱등 원장을 다시 확인해 중복
  상태 변경 대신 Replay를 반환한다.
- 새 Key의 stale version은 최신 상태·버전·`allowed_actions` 코드가 담긴
  409를 반환한다.
- PostgreSQL 동시 요청에서 같은 Key는 1 Write+1 Replay, 서로 다른 Key는
  버전 승자 하나만 허용한다.

이 Slice가 아직 하지 않는 일도 분명하다.

- `REQUEST_AI_STRUCTURING` Effect를 실행하지 않는다.
- `ProductModel.is_supported_mvp`를 이용한 `PRODUCT_VALIDATION_FAILED`
  전이를 수행하지 않는다.
- AI 요청 시점 버전과 결과 적용 시점 버전의 stale 검사를 수행하지 않는다.
- 추가 답변·AI 재평가·Evidence 저장을 포함하지 않는다.

세부 계약·검증은 [T-022 문의·증상 제출 구현·검증·인계서](Django_REST_API_문의_증상제출_구현_검증_인계서.md)를
단일 원본으로 사용한다.

### 3.3 `CANCEL_INQUIRY`

```text
POST /api/v1/inquiries/{inquiry_id}/cancel
event: CANCEL_INQUIRY
current Runtime: DRAFT → CANCELLED, state_version 1 → 2
current actor: CUSTOMER owner only
```

[InquiryService.cancel](../../../../backend/apps/inquiries/services/inquiry_service.py)와
[T-023 취소 API 테스트](../../../../backend/tests/api/test_t023_cancel_inquiry.py)는
다음을 검증한다.

- 고객 owner 범위와 타 고객 404, 비고객 403, 미인증 401
- 취소 사유 코드·상세 저장과 `cancelled_at`
- 성공 시 상태 버전 1 증가와 `CANCEL_INQUIRY` 이력
- 동일 Key·동일 Hash Replay와 다른 Hash 409
- 새 Key stale version과 종료 상태 재요청의 최신 Snapshot 409
- Header·Payload 실패 시 부수효과 0
- 늦은 실패 시 Inquiry·이력·멱등 원장 전체 Rollback

현재 Runtime은 승인 State 계약 전체보다 좁다.

| 계약 | 현재 Runtime |
| --- | --- |
| DRAFT와 QUESTIONNAIRE_IN_PROGRESS에서 취소 | DRAFT만 허용 |
| CUSTOMER·배정 CONSULTANT·권한 OPERATOR | `IsCustomer`가 적용된 CUSTOMER owner만 허용 |
| `G-CANCEL-ACTOR-AUTHORIZED`, `G-CANCELLATION-REASON` | Service 조건과 Serializer로 개별 처리 |
| StateMachine에서 TR-INQ-004/005 선택 | DRAFT·CANCELLED를 Service가 직접 비교 |
| 취소 사유가 감사 이력에 보존 | Inquiry에는 보존되나 `TransitionHistory.change_reason`은 비어 있음 |

따라서 `CANCEL_INQUIRY 구현됨`은 **DRAFT 고객 최소 Slice**를 뜻한다.
상담사·운영자 취소나 문진 진행 중 취소까지 구현됐다고 확대 해석하지
않는다.

## 4. Engine·Guard·Allowed Action의 실제 수준

### 4.1 StateMachine

[StateMachine.resolve](../../../../backend/apps/workflow/engine/state_machine.py)는
검증된 YAML 계약에서 한 개의 전이만 선택한다.

- 등록되지 않은 이벤트와 목록에 없는 전이를 거부한다.
- `RESOLVED`, `CANCELLED` 종료 상태의 후속 전이를 거부한다.
- Inquiry·Visit 상태 조합과 Visit mode를 검사한다.
- 동일 입력에 둘 이상의 규칙이 맞으면 서버 계약 오류로 거부한다.
- `INITIALIZE_1`, `INCREMENT`에 따라 다음 버전을 계산한다.

Engine은 전이 **계획**을 반환한다. DB 잠금, Effect 저장, 이력, 외부 호출을
자동 실행하지 않는다. 이 책임을 연결하는 범용 Action Orchestrator가 아직
없다.

### 4.2 GuardEvaluator

[GuardEvaluator](../../../../backend/apps/workflow/engine/guard_evaluator.py)는
인증·역할·리소스·동시성·멱등성·Payload·업무·안전 Guard를 계약 순서로
평가한다.

- 사용자 역할과 신뢰된 내부 SYSTEM actor를 구분한다.
- `correlation_id`, `Idempotency-Key`, `state_version` 필수 조건을 검사한다.
- 계약에 필수 Guard 참조가 빠지면 500 성격의 구성 오류로 fail-closed한다.
- owner·담당자·제품·안전·완료 같은 도메인 판정은 호출 Service가
  `domain_results`로 제공해야 한다.

따라서 Guard 클래스가 존재하는 것만으로 상담사 배정이나 AI 안전 검증이
동작하지 않는다. 각 Action Service가 신뢰할 수 있는 Repository 결과를
주입해야 실제 보호가 된다.

### 4.3 AllowedActionResolver

현재 Resolver는 `state_code + role_code`로 `allowed-actions.yaml`의 후보를
조회하고 아래 여섯 필드를 반환한다.

```text
code, label, operation_id, style,
requires_confirmation, confirmation_message
```

그러나 승인 계약의 전체 계산 정책과 비교하면 다음이 빠져 있다.

- 현재 Visit 존재 여부·상태와 `visit_conditions` 비교
- 연결된 `transition_rule_ids` 중 실제 적용 규칙 선택
- owner·assignee·권한·완료 조건 같은 동적 Guard 평가
- 실패 Guard가 있는 Action을 결과에서 제거하는 처리

현재 DRAFT·QUESTIONNAIRE_IN_PROGRESS 고객 흐름의 정적 후보 반환에는
사용할 수 있다. 상담·방문·완료 화면에서 Resolver 결과를 그대로 권한
판정으로 사용하면 허용되지 않은 버튼이 노출될 수 있으므로 아직 전체
권위 구현으로 보지 않는다.

## 5. 동시성·409·Replay·멱등성

[동시성 정책](../../../../contracts/state-machine/concurrency-policy.yaml)의
핵심과 현재 구현 대응은 다음과 같다.

| 항목 | 현재 구현 | 판정 |
| --- | --- | --- |
| 생성 초기 버전 1 | START에서 저장 | 구현 |
| 성공 쓰기마다 버전 증가 | SUBMIT·CANCEL에서 1 증가 | 현재 Slice 구현 |
| `select_for_update` | SUBMIT·CANCEL owner Inquiry 잠금 | 구현 |
| stale version 409 | 최신 상태·버전·허용 Action 코드 반환 | 구현 |
| 멱등 범위 | actor·operation_id·key Unique | 구현 |
| 같은 Key·같은 Hash | 저장된 성공 응답 Replay | 구현 |
| 같은 Key·다른 Hash | 공개 중복 이벤트 오류 409 | 구현 |
| 늦은 실패 Rollback | SUBMIT·CANCEL 회귀 | 구현 |
| PostgreSQL 동시 요청 | SUBMIT의 동일 Key·새 Key 경쟁 | 구현·검증 |
| CANCEL PostgreSQL Thread 경쟁 | 전용 동시성 사례 없음 | 미검증 |
| Inquiry+Visit 잠금 순서 | Visit Action Runtime 없음 | 미구현 |
| AI stale result·중복 result | AI Action Runtime 없음 | 미구현 |

전체 PostgreSQL 791 PASS는 현재 코드의 통합 회귀 증거다. 이것을 모든
Action의 동시성 시나리오가 구현됐다는 증거로 사용하지 않는다. 실제 Thread
경쟁을 직접 검증한 것은 현재 `SUBMIT_SYMPTOM` 두 사례다.

## 6. 이력·SYSTEM actor·`change_reason` 결손

[TransitionHistory Model](../../../../backend/apps/workflow/models/transition_history.py)은
다음을 저장할 물리 필드를 이미 갖는다.

- 대상 유형과 정확히 하나의 대상 FK
- 사용자 actor 또는 SYSTEM actor 구분
- 이벤트·이전 상태·다음 상태·새 버전
- `correlation_id`, `idempotency_key`, `change_reason`, UTC 시각
- 대상별 `state_version` Unique와 actor 유형 Check Constraint

하지만 [WorkflowRepository.create_transition_history](../../../../backend/apps/workflow/repositories/workflow_repository.py)는
`changed_by_type_code`와 `change_reason`을 받지 않는다. Model 기본값이
`USER`이므로 `actor=None`인 SYSTEM 이력을 현재 경로로 저장하면
`ck_status_history_changed_by` 제약과 충돌한다.

또한 START·SUBMIT·CANCEL 이력 Service는 모두 사용자 actor만 전달하고
취소 사유를 `change_reason`으로 넘기지 않는다. 현재 취소 사유는
`Inquiry.cancellation_reason_code/detail`에만 저장된다. 이 때문에 다음을
아직 보장하지 못한다.

1. `SAFE_GUIDANCE_READY`, `DANGER_DETECTED`, `NO_EVIDENCE`를
   `changed_by_type_code=SYSTEM`, `actor=NULL`로 기록
2. 취소·위험·근거 없음의 업무 사유를 상태 이력 단독 조회로 재현
3. 외부 멱등 키가 없는 SYSTEM_EVENT의 이력 식별·중복 방지 규칙

이 결손은 상담·방문 Endpoint와 무관하게 Backend 담당자가 독립적으로
먼저 보강할 수 있는 State Machine API 작업(T-023)이다. 다만 SYSTEM_EVENT의
`idempotency_key` 대체값과
`ai_request_id` 중복 정책은 AI 계약과 함께 확정해야 한다.

## 7. 미구현 SYSTEM 이벤트

`SAFE_GUIDANCE_READY`, `DANGER_DETECTED`, `NO_EVIDENCE`는 Public API가
아니다. [이벤트 계약](../../../../contracts/state-machine/inquiry-events.yaml)은
세 이벤트를 `SYSTEM_EVENT`, `external_action.exposed=false`,
`operation_id=null`로 정의한다. generic Public `/events` Endpoint로 노출하면
계약 위반이다.

| 이벤트 | 전이 | 필요한 Guard | 필요한 Effect | 현재 차단점 |
| --- | --- | --- | --- | --- |
| `SAFE_GUIDANCE_READY` | QIP → AI_GUIDANCE | 안전 안내 유효·공식 근거 존재·위험 충돌 없음 | 검증 안내·Evidence 참조 저장 | AI 결과 Adapter·Evidence 저장 연결 없음 |
| `DANGER_DETECTED` | QIP → CONSULTATION_REQUIRED | 위험 판정 유효 | 일반 자가안내 차단·상담 필요·사용 제한 저장 | 안전 결과 Schema·사용 제한 저장 Service 없음 |
| `NO_EVIDENCE` | QIP → CONSULTATION_REQUIRED | 사용 가능한 근거 없음 | 근거 없는 안내 차단·상담 필요·판단 보류 | Retrieval 결과 연결·SYSTEM 이력 없음 |

[AIRun Model](../../../../backend/apps/audit/models/ai_run.py) 같은 실행 원장은
존재하지만 [Inquiry AI Service](../../../../backend/apps/inquiries/services/inquiry_ai_service.py)는
설명 문자열뿐이다. 따라서 AI 결과 수신, Schema 검증, 내부 actor 신뢰,
stale version 차단, Effect 저장과 상태 전이를 하나로 묶는 Runtime이 없다.

## 8. `REQUEST_CONSULTATION`과 상담·방문 Gate

`REQUEST_CONSULTATION`은 SYSTEM 이벤트와 달리 고객에게 노출되는
`USER_COMMAND`다. 승인 State 계약에는 다음 세 전이가 있다.

- `AI_GUIDANCE → CONSULTATION_REQUIRED`
- `CONSULTATION_REQUIRED → CONSULTATION_REQUIRED` 고객 확인 기록
- `COMPLETION_PENDING → CONSULTATION_REQUIRED` 재요청

그러나 현재 OpenAPI와 Django Runtime에는 `requestConsultation` Path,
요청·응답 DTO, Serializer, View, Service가 없다. 전이 Effect인
`UPSERT_CONSULTATION_REQUEST`의 중복·재요청·담당자 초기값 규칙도 Runtime으로
구현되지 않았다.

Consultation·Visit의 Model과 Migration은 존재하지만 아래 파일들은 현재
설명 문자열뿐이다.

- `backend/apps/consultations/api/{urls,views,serializers}.py`
- `backend/apps/consultations/{repositories,services}/**`
- `backend/apps/visits/api/{urls,views,serializers}.py`
- `backend/apps/visits/{repositories,services}/**`

[API 통합 URL](../../../../backend/config/api_urls.py)은 Accounts와
Inquiries만 등록한다. 따라서 상담사 배정, 기사 미배정, 방문 상태,
`COMPLETION_PENDING`, `REOPENED`, `FINALIZE_INQUIRY`의 실제 HTTP E2E는 현재
실행 대상이 없다.

## 9. 테스트 증거와 해석 범위

| 검증 | 결과 | 해석 |
| --- | --- | --- |
| 2026-08-02 T-023 집중 재실행 | `88 passed in 24.14s` | Cancel·계약·409·Engine·Guard·이력·Readiness 8개 파일, SQLite |
| 자연어 Submit 집중 | SQLite `30 passed, 2 skipped`; PostgreSQL `22 passed` | SUBMIT Slice A와 실제 PostgreSQL 경쟁 검증 |
| 계약·Runtime·예시·권한 집중 | `72 passed, 2 skipped` | T-017·T-022를 포함한 2026-08-02 교차 계약 검증 기록 |
| Backend 전체 SQLite | `778 passed, 13 skipped` | 2026-08-02 로컬 검증 대상 전체 회귀 기록 |
| Backend 전체 PostgreSQL 격리 재실행 | `791 passed` | 테스트용 환경값을 Process 범위로 격리한 전체 회귀 |

T-023 집중 재실행 명령은 다음과 같다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe -m pytest -q `
  tests\api\test_t023_cancel_inquiry.py `
  tests\api\test_cancel_inquiry_contract.py `
  tests\api\test_workflow_conflict_contract.py `
  tests\unit\workflow\test_state_machine.py `
  tests\unit\workflow\test_guard_evaluator.py `
  tests\unit\workflow\test_state_machine_contracts.py `
  tests\unit\workflow\test_status_history_contract.py `
  tests\unit\workflow\test_t023_readiness.py
```

SQLite 778·PostgreSQL 791과 나머지 집중 수치는 2026-08-02 문서 감사에서
새로 전체 재실행한 값이 아니라 [API Runtime 구현 상태](../../../api/runtime_implementation_status.md)에
기록된 로컬 검증 결과다. 2026-08-02에 직접 재실행한 값은 T-023 집중
`88 passed`다.

`readiness.py`를 실행 Flag 없이 감사한 2026-08-02 결과는 부분 준비
(`PARTIAL`)다. State 계약 검증은 통과·팀 승인 완료(`PASS`,
`TEAM_APPROVED`)지만, OpenAPI Action 상태가 확인됨(`CONFIRMED`)이라 도구의
승인 상태 집합과 맞지 않고, 해당 실행에 Runtime
테스트·PostgreSQL 증거 Flag를 전달하지 않았으며, 작성자 외 Backend 리뷰가
없기 때문이다. 이 결과를 코드 실패로 오해하거나, 반대로 저장된 회귀
기록만으로 독립 리뷰를 통과했다고 해석하지 않는다.

## 10. Backend 담당자가 독립적으로 진행 가능한 안전 작업

아래 작업은 현재 승인 계약과 외부 API 동작을 넓히지 않고 로컬에서 작은
변경 묶음으로 수행할 수 있다.

| 우선순위 | 작업 | 안전한 완료 기준 |
| --- | --- | --- |
| P0-1 | 사용자·SYSTEM 이력을 모두 받을 수 있도록 이력 Repository·Service 경계 보강 | USER는 actor 필수, SYSTEM은 actor NULL·SYSTEM type 필수, DB 제약과 단위 테스트 PASS |
| P0-2 | 현재 CANCEL 사유를 `TransitionHistory.change_reason`에도 보존 | Inquiry 사유와 이력 사유가 같은 Transaction에서 저장되고 실패 시 함께 Rollback |
| P0-3 | DRAFT 고객 CANCEL 내부 구현을 StateMachine·GuardEvaluator 경로로 리팩터링 | Public 요청·응답·오류를 바꾸지 않고 TR-INQ-004·Guard 회귀 PASS |
| P0-4 | 현재 DRAFT·QIP 고객 범위의 Allowed Action 후보와 실제 전이 가능성 Characterization 보강 | 계약과 Runtime 차이를 테스트에서 명시하고 허용되지 않은 상태를 fail-closed |
| P0-5 | 409·Replay·Rollback 테스트의 Service 공통 불변식 정리 | Action별 중복 코드 제거 전 기존 응답과 DB 부수효과가 동일함을 검증 |

이 다섯 작업도 하나의 변경 단위로 묶지 않는다. `이력 → CANCEL 내부 정렬
→ Allowed Action` 순서로 분리하고 각 단계에서 SQLite 집중·전체,
PostgreSQL 집중·전체를 반복한다.

## 11. 협업·계약 확정 후에만 구현할 작업

| 작업 | 필요한 결정·협업 | 독단 구현 시 위험 |
| --- | --- | --- |
| QIP·상담사·운영자 CANCEL 확대 | PM·QA의 Action API 범위, 상담사 배정·운영 권한 조회 | 현재 고객 전용 OpenAPI·권한을 임의 확장 |
| `REQUEST_CONSULTATION` API | PM State, Web·Mobile DTO, Data·QA UPSERT·재요청 규칙 | 중복 상담 생성 또는 상태·상담 원장 불일치 |
| `SAFE_GUIDANCE_READY` | AI 결과 Schema, Evidence, Safety 검증 | 검증 전 안내 노출·근거 위조 위험 |
| `DANGER_DETECTED` | AI 안전 규칙, 제한 기능·사용 안내 저장 | 위험 안내와 상태가 서로 달라지는 안전 결함 |
| `NO_EVIDENCE` | Retrieval 결과 계약, 판단 보류 Projection | 근거 없음인데 자가조치가 노출되는 결함 |
| 상담·방문 Action | 담당자 배정·Self-Claim·Visit 상태와 Lock 순서 | 미배정 접근·중복 배정·문의/방문 상태 불일치 |
| 완료·재개 Action | 고객 피드백·마지막 담당자·완료 출처 정책 | 고객 피드백만으로 조기 RESOLVED 또는 잘못된 담당자 완료 |
| 팀 공용 완료 표시 | Data·QA 비작성자 독립 재현, 계약 승인 담당자의 판정, Web·Mobile·AI 소비 확인 | 작성자 로컬 검증 범위를 공식 통합 완료로 오인 |

## 12. 도미노 오류를 막는 후속 순서

1. 현재 START·SUBMIT·CANCEL과 T-023 집중 88건, 기록된 SUBMIT·전체
   회귀를 기준선으로 고정한다.
2. Model 변경 없이 SYSTEM actor·`change_reason` 이력 경계를 먼저 보강한다.
3. 외부 계약을 바꾸지 않고 DRAFT 고객 CANCEL만 Engine·Guard 경로로
   내부 정렬한다.
4. Allowed Action이 Transition·Visit·동적 Guard를 반영하는 입력 계약을
   PM·QA와 확정한다.
5. `REQUEST_CONSULTATION` OpenAPI·UPSERT 계약을 먼저 확정한 뒤 고객
   수직 Slice를 구현한다.
6. AI 내부 결과 Schema·신뢰 경계·stale version 정책이 준비된 후
   SYSTEM 이벤트를 하나씩 연결한다.
7. Consultation Action을 완료한 뒤 Visit Action을 동일 잠금 순서로
   추가한다.
8. 마지막으로 `COMPLETION_PENDING → REOPENED/RESOLVED` 완료 정책을
   연결하고 Web·Mobile·AI·PostgreSQL E2E를 수행한다.
9. 비작성자 재현과 계약 승인 기록 뒤에만 WBS 완료 상태를 갱신한다.

이 순서는 `상담·방문 Route가 없는 상태에서 완료 Action부터 만들기`,
`AI 검증 없이 SYSTEM 이벤트를 Public API로 노출하기`, `정적
allowed_actions를 권한 판정으로 사용하기`를 막는다.

## 13. T-023 완료 조건

다음 항목이 모두 충족돼야 `T-023 완료`라고 판단한다.

- [x] State 계약 Loader·Validator·Engine·Guard 기반이 있다.
- [x] 상태 이력·멱등 원장·Migration이 있다.
- [x] START·DRAFT 고객 CANCEL 최소 Action이 동작한다.
- [x] SUBMIT Slice A가 StateMachine·Guard·이력·409·Replay를 사용한다.
- [x] SUBMIT PostgreSQL 동시성에서 한 버전 승자만 허용한다.
- [ ] 모든 Action이 공통 전이·Guard·Effect 실행 경계를 사용한다.
- [ ] `allowed_actions`가 Visit·담당자·동적 Guard를 반영한다.
- [ ] SYSTEM actor와 사유가 이력에 정확히 저장된다.
- [ ] `SAFE_GUIDANCE_READY`, `DANGER_DETECTED`, `NO_EVIDENCE`가 내부
  신뢰 경계와 stale result 차단을 거쳐 동작한다.
- [ ] `REQUEST_CONSULTATION`과 상담 요청 UPSERT가 동작한다.
- [ ] 상담·방문·완료·재개 Action과 담당자 권한이 동작한다.
- [ ] Inquiry+Visit 동시 Lock, CANCEL·SYSTEM 동시성 사례가 PostgreSQL에서
  검증된다.
- [ ] OpenAPI·Runtime·오류·예시가 팀 승인 상태로 일치한다.
- [ ] Data·QA 담당 또는 다른 비작성자가 재현하고 계약 승인 담당자가 팀 기준선 반영을 결정한다.
- [ ] Web·Mobile·AI가 실제 응답과 409 복구 흐름을 소비한다.

## 14. 인계 시 반드시 전달할 판단

1. `START·SUBMIT·CANCEL 존재`와 `T-023 전체 완료`는 같은 말이 아니다.
2. 현재 `SUBMIT_SYMPTOM`만 StateMachine·Guard가 직접 연결된 대표 Action
   Slice다.
3. `allowed_actions`는 현재 정적 후보 Resolver이며 상담·방문 권한의 최종
   판정기로 사용하면 안 된다.
4. SYSTEM 이벤트는 내부 Action이다. Public `/events` API를 만들지 않는다.
5. 상담·방문 Model이 있다는 이유로 상담·방문 Runtime이 있다고 표시하지
   않는다.
6. SQLite 778·PostgreSQL 791은 전체 회귀 증거지만, 미구현 Action을
   구현된 것으로 바꾸지는 않는다.
7. 후속 담당자는 2026-08-02 검증 기준일과 적용 경로를 먼저 대조한 뒤
   작업 범위를 고정해야 한다.
