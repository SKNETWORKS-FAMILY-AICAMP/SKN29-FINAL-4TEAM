# Backend Contract 소비 불일치 PM 결정

> 결정자: 윤승혁 — PM
> 결정일: 2026-08-11 KST
> 기준 Commit: `main@92b0674cd1a3376a2c058715cd5ef32222125755`
> 입력: 최지용 `Backend Contract Runtime 12 소비 검토 회신 v0.1`
> 판정: **CHANGE_REQUEST**

## 1. 결정

### CANCEL_INQUIRY

`KEEP_APPROVED_CONTRACT`를 선택한다. 승인 계약을 고객 DRAFT Slice로 축소하지 않는다.

- 역할: 본인 문의 고객, 현재 문의 담당 상담사, `INQUIRY_CANCEL` 명시 권한 운영자
- 상태: `DRAFT`, `QUESTIONNAIRE_IN_PROGRESS`
- 전이: `TR-INQ-004`, `TR-INQ-005`
- Guard: `G-CANCEL-ACTOR-AUTHORIZED`, Version, 멱등성, 취소 사유
- 이력: 실제 전이 직전 상태를 기록하고 `DRAFT`로 고정하지 않는다.

현재 고객 DRAFT Slice만 존재하는 상태는 승인 Action 전체의 `RUNTIME_IMPLEMENTED` 완료로 인정하지 않는다. 수정 후보에서 전체 역할·상태·Guard Test가 통과하기 전까지 3.3 Backend ACK를 보류한다.

### allowed_actions

`DYNAMIC_GUARD_AND_RUNTIME_FILTER`를 선택한다.

Backend는 다음 순서로 계산한다.

1. 현재 Inquiry State·Actor Role의 후보 Action을 조회한다.
2. Visit 존재·상태와 연결 Transition을 선택한다.
3. 담당자·요약·방문·Version을 포함한 모든 동적 Guard를 평가한다.
4. 실제 Backend Runtime이 제공되는 Action만 남긴다.
5. 성공 응답과 409 최신 Snapshot에 같은 Resolver 결과를 사용한다.

Web·Mobile에 Guard나 Crosswalk 재계산 책임을 넘기지 않는다. 별도 Availability 필드도 이번 수정에서는 추가하지 않는다. 호출 가능한 행동만 `allowed_actions`에 포함한다.

## 2. 완료 조건

- 실패하는 계약 정합 Test를 먼저 추가한다.
- 세 역할·두 상태의 취소 정상·권한·IDOR·Version·멱등성·이력을 검증한다.
- Visit·담당자·요약·Domain Guard와 Runtime availability를 결합한 Resolver Test를 추가한다.
- 성공 응답과 409 응답의 `allowed_actions`가 같은 계산 정책을 사용한다.
- 표적 회귀와 PostgreSQL Row Lock Test를 수행한다.
- 최지용 수정 후보를 김은진이 독립 재현한다.
- Crosswalk는 의미상 전체 Runtime과 Test가 일치할 때만 `RUNTIME_IMPLEMENTED`를 유지한다.

## 3. 공식 회신

```text
reviewer=윤승혁
review_scope=BACKEND_CONTRACT_RUNTIME12_CONSUMER_ALIGNMENT
reviewed_commit=92b0674cd1a3376a2c058715cd5ef32222125755

backend_consumer_decision=CHANGE_REQUEST
cancel_contract_policy=KEEP_APPROVED_CONTRACT
cancel_roles=CUSTOMER_OWNER,ASSIGNED_CONSULTANT,OPERATOR_WITH_INQUIRY_CANCEL
cancel_states=DRAFT,QUESTIONNAIRE_IN_PROGRESS
allowed_actions_policy=DYNAMIC_GUARD_AND_RUNTIME_FILTER
availability_field=DO_NOT_ADD
client_recalculation=PROHIBITED

crosswalk_current_static_result=12/7/0/4_PASS
crosswalk_semantic_result=HOLD_CANCEL_PARTIAL_RUNTIME
backend_ack=false
team_baseline_allowed=false
implementation_order=FAILING_TEST,BACKEND_FIX,TARGETED_REGRESSION,POSTGRESQL_QA
overall_decision=CHANGE_REQUEST
```
