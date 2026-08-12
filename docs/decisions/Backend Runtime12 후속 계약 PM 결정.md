# Backend Runtime12 후속 계약 PM 결정

> 결정일: 2026-08-11 KST
> 결정자: 윤승혁 — PM·계약 Owner
> 현재 기준: `main@4ac79e6227ce271252054b1e986d6ee24eefce4a`
> Runtime 수정: `e290fe3d43ae5adf2a6ab758cbf2e19922046cd1`
> 작성자 후보: `83f737326de75a6015a606c0050eaa81d1f67a4f`
> 입력: 최지용 `Backend Contract Runtime 12 수정·검증 회신 v0.4`
> 판정: **AUTHOR_FIX_ACCEPTED · CONTRACT_FOLLOWUP_AND_INDEPENDENT_QA_PENDING**

## 1. 기존 변경 요청 판정

`CANCEL_INQUIRY` 역할·상태 확대와 동적 Guard·Runtime 가용성 기반 `allowed_actions` Resolver 수정은 PM 결정 방향과 일치한다. 작성자 표적·전체·PostgreSQL·원격 CI 증거도 접수했다.

다만 작성자 검증은 독립 QA를 대신하지 않는다. 아래 후속 계약 적용과 김은진의 현재 `main` 독립 재현 전까지 `backend_ack=false`, `team_baseline_allowed=false`를 유지한다.

## 2. 계약 Owner 결정 3건

### 2.1 `submitSymptom`과 AI 실행 경계

`ON_COMMIT_ASYNC_DISCLOSURE`로 결정한다.

- `SUBMIT_SYMPTOM` 저장 Transaction은 AI 결과를 기다리거나 `QuestionnaireSession`을 생성하지 않는다.
- 성공 Commit 이후 `on_commit` Callback으로 AI 분석을 후속 실행한다.
- `submitSymptom` 응답은 상태 전환이 확정된 시점의 Snapshot이며 AI 결과·추가 질문 생성 완료를 보장하지 않는다.
- 따라서 OpenAPI의 “AI 호출을 포함하지 않는다”는 표현은 위 경계가 드러나도록 수정한다.

### 2.2 `updateVisitSchedule` 전이 범위

`INCLUDE_TR_INQ_028`로 결정한다.

같은 `UPDATE_VISIT_SCHEDULE` Event·Operation이 일반 방문 조율과 재방문 조율을 모두 수행하므로 OpenAPI와 사람이 읽는 Operation Crosswalk에 다음 전이를 함께 기록한다.

```text
TR-INQ-020
TR-INQ-021
TR-INQ-028
```

From Inquiry State는 `VISIT_SCHEDULING`, `REVISIT_REQUIRED`이고 Visit From Status는 `ASSIGNING`, `SCHEDULING`, `FOLLOW_UP_REQUIRED`다.

### 2.3 비동기 질문 생성 후 고객 Snapshot

`INCLUDE_DYNAMIC_ALLOWED_ACTIONS_IN_CUSTOMER_SNAPSHOT`으로 결정한다.

- `GET /me/inquiries/{inquiry_id}`는 최신 `allowed_actions`를 동적 Resolver로 계산해 반환한다.
- 질문 생성 전 `submitSymptom` 응답에는 그 시점에 호출 가능한 Action만 포함한다.
- 비동기 AI가 미답변 질문을 저장한 뒤 고객이 Snapshot을 다시 조회하면 Guard를 통과한 `SUBMIT_ANSWERS`를 포함한다.
- 질문이 없거나 이미 답변됐거나 Runtime Guard를 통과하지 못하면 `SUBMIT_ANSWERS`를 포함하지 않는다.
- Mobile·Web은 질문 존재만으로 Action을 자체 계산하지 않고 Snapshot을 재조회한다.

## 3. 완료 순서

1. 최지용이 `contracts/api/**`와 Backend 고객 Snapshot Runtime·Test에 위 세 결정을 적용한다.
2. Contract CI와 Backend 표적 회귀를 실행한다.
3. 김은진이 최신 `main`에서 취소·Resolver·Snapshot·PostgreSQL을 독립 재현한다.
4. 윤승혁이 Backend ACK와 최종 Contract Baseline 후보를 재판정한다.

## 4. 공식 회신

```text
reviewer=윤승혁
review_scope=BACKEND_RUNTIME12_CONTRACT_OWNER_CONFIRMATION
reviewed_main=4ac79e6227ce271252054b1e986d6ee24eefce4a
runtime_fix_commit=e290fe3d43ae5adf2a6ab758cbf2e19922046cd1

original_change_request=AUTHOR_FIX_ACCEPTED
submit_symptom_ai_boundary=ON_COMMIT_ASYNC_DISCLOSURE
update_visit_schedule_transitions=TR-INQ-020,TR-INQ-021,TR-INQ-028
customer_snapshot_allowed_actions=INCLUDE_DYNAMIC_RESOLVER_RESULT
submit_response_snapshot=COMMIT_TIME_ONLY
client_recalculation=PROHIBITED

backend_ack=false
independent_qa=REQUIRED
team_baseline_allowed=false
overall_decision=APPROVE_WITH_FOLLOWUP
```
