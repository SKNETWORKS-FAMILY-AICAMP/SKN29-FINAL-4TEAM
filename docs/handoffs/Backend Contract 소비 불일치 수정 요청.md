# 최지용 — Backend Contract 소비 불일치 수정 요청

> 기준 Commit: `92b0674cd1a3376a2c058715cd5ef32222125755`
> PM 결정: `docs/decisions/Backend Contract 소비 불일치 PM 결정.md`
> 상태: **CHANGE_REQUEST**

## 요청 작업

1. `CANCEL_INQUIRY`를 고객 본인·담당 상담사·명시 권한 운영자에게 구현해 주세요.
2. `DRAFT`와 `QUESTIONNAIRE_IN_PROGRESS`에서 계약 Guard로 전이해 주세요.
3. 취소 이력의 이전 상태를 실제 값으로 기록해 주세요.
4. `allowed_actions`는 State·Role 후보에 Visit·Transition·Domain Guard를 적용해 주세요.
5. Guard 통과 후 실제 Runtime 제공 Action만 반환해 주세요.
6. 성공 응답과 409 최신 Snapshot에서 같은 Resolver를 사용해 주세요.
7. 실패 Test→최소 수정→표적 회귀→PostgreSQL QA 순서를 지켜 주세요.

Web·Mobile에서 Action 가능 여부를 다시 계산하게 하거나 계약을 고객 DRAFT로 축소하지 않습니다.

## 회신 형식

```text
reviewer=최지용
fixed_commit=<전체 SHA>
decision=FIXED | CHANGE_REQUEST | HOLD
cancel_roles_states=<Test 결과>
cancel_history=<Test 결과>
dynamic_guard_resolver=<Test 결과>
runtime_filter=<Test 결과>
success_409_parity=<Test 결과>
targeted_tests=<passed/skipped/failed>
postgresql_result=PASS | FAIL | NOT_RUN
crosswalk_result=<분류 수치와 의미 판정>
remaining_blocker=<없으면 NONE>
```
