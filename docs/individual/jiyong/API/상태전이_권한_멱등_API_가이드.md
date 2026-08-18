# 상태 전이·권한·멱등 API 구현 가이드

> 관련 업무: Workflow·State Machine·상담·방문 상태 전이

## 1. Source of Truth

- `contracts/state-machine/inquiry-states.yaml`
- `contracts/state-machine/inquiry-events.yaml`
- `contracts/state-machine/transition-rules.yaml`
- `contracts/state-machine/transition-guards.yaml`
- `contracts/state-machine/allowed-actions.yaml`
- `contracts/state-machine/role-permissions.yaml`
- `contracts/state-machine/concurrency-policy.yaml`

## 2. Runtime 구성

- State Machine: 현재 상태와 Event로 후보 전이 계산
- Guard: 역할·배정·도메인 결과·Version 검증
- Allowed Actions: 현재 Actor가 실행할 수 있는 Action 계산
- Transition Service: Aggregate Lock과 상태 변경
- History·Audit: Actor·이유·Correlation·Version 기록
- Idempotency: 최초 응답 저장과 Replay·충돌 구분

## 3. 쓰기 순서

1. Aggregate Row Lock
2. `state_version` 비교
3. Idempotency-Key와 Payload Hash 확인
4. 역할·객체·Guard 검증
5. 도메인 저장과 상태 전이
6. Transition History·Audit 저장
7. 최초 응답 저장
8. Commit

## 4. 오류 경계

| 조건 | 결과 |
| --- | --- |
| Stale Version | 409와 최신 Snapshot |
| 동일 Key·동일 Payload | 최초 응답 Replay |
| 동일 Key·다른 Payload | 멱등 충돌 409 |
| 역할·배정 불일치 | 403 또는 존재 은닉 404 |
| Guard 데이터 부족 | Fail-closed, 상태 유지 |
| 저장 실패 | 업무·상태·이력·멱등 전체 Rollback |

## 5. SYSTEM Event

SYSTEM Event도 Actor 종류·`change_reason`·Correlation을 기록한다. AI 결과가
Event 후보를 반환해도 Backend가 최신 상태·Version·Guard를 다시 확인한다.
AI가 Backend 상태를 직접 변경하지 않는다.

## 6. 계약·Runtime 정합

Action–Operation Crosswalk에서 `OPENAPI_CONFIRMED`는 구현 완료가 아니다.
Route·Service·권한·이력·PostgreSQL 동시성 Test까지 존재해야
`RUNTIME_IMPLEMENTED`로 판단한다.

## 7. 검증

```powershell
.\backend\.venv\Scripts\python.exe -B .\scripts\contracts\validate_state_machine.py
.\backend\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  .\tests\contract\test_contract_validators.py `
  .\backend\tests\unit\workflow\test_state_machine.py
```

## 8. 판정

전 상태의 Action·Guard·권한·409·Replay·History·Rollback이 계약과 일치하면
상태 전이 공통 Runtime 작성자 검증 완료다.
