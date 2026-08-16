# 방문 일정·기사 배정 API 구현 가이드

> 관련 업무: 방문 검토·요청·일정·확정·재방문

## 1. 기능 흐름

```text
방문 필요 검토
→ 방문 요청 생성 또는 불필요 처리
→ 기사 배정 후 일정 조율
→ 방문일 확정
→ 결과 제출·재방문 처리
```

방문 날짜는 P0에서 Date-only를 사용한다. `ASSIGNING`은 기사 미배정,
`SCHEDULING`은 기사 배정 후 일정 조율, `CONFIRMED`는 방문일 확정이다.

## 2. 주요 경로

- `backend/apps/visits/**`
- `contracts/api/paths/visits.yaml`
- `contracts/state-machine/**`
- `backend/tests/api/test_consultation_visit_runtime.py`
- `backend/tests/unit/visits/**`

## 3. 권한·잠금

- 방문 검토·일정 저장·확정은 담당 상담사만 수행한다.
- 기사 결과는 현재 배정과 합성 기사 여부를 확인한다.
- Inquiry와 Visit의 잠금 순서를 고정한다.
- Nullable Technician을 포함한 Outer Join 전체에 `FOR UPDATE`를 적용하지 않고
  필요한 Visit 행만 잠근다.

## 4. 재방문과 결과 이력

기사를 교체해도 과거 `VisitResult.submitted_by`는 역사적 제출자로 보존한다.
신규 결과 생성 시에는 현재 배정 기사를 검증하고, 저장된 결과의 제출자·Visit
연결은 변경하지 않는다. PostgreSQL Trigger·제약과 Model `clean()`의 의미를
일치시킨다.

## 5. 쓰기 공통 규칙

- `state_version`과 `Idempotency-Key` 검증
- 409 최신 Snapshot
- Visit·Handoff·History·Idempotency 단일 Transaction
- Replay 추가 저장 0
- 실패 주입 시 부분 저장 0

## 6. PostgreSQL 검증

| Case | 기대 결과 |
| --- | --- |
| Nullable 기사 방문 잠금 | 오류 없이 대상 Visit만 잠금 |
| 결과 INSERT 중 기사 교체 | Lock 대기 후 안전하게 처리 |
| 기사 교체 후 옛 기사 결과 | FK·Guard로 거부 |
| 재방문 일정 | 과거 결과 보존, 새 일정 반영 |
| Rollback | Visit·Handoff·History·Key 증가 0 |

## 7. 판정

상태·권한·Date-only·멱등·Rollback과 PostgreSQL 동시성 Case가 통과하면
Backend 방문 Runtime 구현 완료다. Web·Mobile 화면 연결은 별도다.
