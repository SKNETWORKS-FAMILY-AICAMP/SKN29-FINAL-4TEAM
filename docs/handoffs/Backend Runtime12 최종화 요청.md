# 최지용·김은진 — Backend Runtime12 최종화 요청

> 기준: `main@4ac79e6227ce271252054b1e986d6ee24eefce4a`
> PM 결정: `docs/decisions/Backend Runtime12 후속 계약 PM 결정.md`
> 상태: **CONTRACT_FOLLOWUP_THEN_INDEPENDENT_QA**

## 최지용 요청

1. `submitSymptom` OpenAPI에 저장 Commit 이후 AI 후속 실행과 응답 Snapshot 경계를 명시해 주세요.
2. `updateVisitSchedule`에 `TR-INQ-028`, `REVISIT_REQUIRED`, `FOLLOW_UP_REQUIRED`를 포함해 주세요.
3. 고객 Inquiry Snapshot Schema와 Runtime에 동적 `allowed_actions`를 추가해 주세요.
4. 미답변 질문 생성 전·후·답변 후 `SUBMIT_ANSWERS` 노출 Test를 추가해 주세요.
5. Contract CI와 Backend 표적 회귀 결과를 전체 SHA와 함께 회신해 주세요.

API 계약과 Backend는 최지용 주관 영역이므로 윤승혁은 결정만 확정하고 해당 파일을 대신 수정하지 않는다.

## 김은진 요청

최지용 후속 Commit이 `main`에 반영된 뒤 다음을 독립 재현해 주세요.

1. 세 역할·두 상태의 `CANCEL_INQUIRY`
2. 실제 이전 상태 이력·Version·멱등성·409
3. Visit·Transition·Domain Guard와 Runtime Filter 기반 Resolver
4. 성공 응답과 stale 409 Resolver 동등성
5. 고객 Snapshot의 질문 생성 전·후 동적 `allowed_actions`
6. PostgreSQL Row Lock·취소 Runtime
7. Contract CI·Data CI 대상 SHA와 전체 결과

## 최종 회신 형식

```text
reviewer=<최지용 | 김은진>
review_scope=BACKEND_RUNTIME12_FINALIZATION
baseline_commit=<전체 SHA>
decision=APPROVE | CHANGE_REQUEST | HOLD
submit_symptom_ai_boundary=<결과>
revisit_schedule_contract=<결과>
customer_snapshot_allowed_actions=<결과>
cancel_roles_states=<결과>
success_409_parity=<결과>
targeted_tests=<passed/skipped/failed>
postgresql_result=PASS | FAIL | NOT_RUN
contract_ci=<Run URL 또는 NOT_RUN>
data_ci=<Run URL 또는 NOT_RUN>
remaining_blocker=<없으면 NONE>
```
