# 상태 전이·권한·멱등 API 구현 가이드

> 관련 업무: T-023 Workflow·완료 피드백·최종 완료·미해결 재개
>
> 최신 반영일: 2026-08-17

## 1. Source of Truth

- `contracts/state-machine/inquiry-states.yaml`
- `contracts/state-machine/inquiry-events.yaml`
- `contracts/state-machine/transition-rules.yaml`
- `contracts/state-machine/transition-guards.yaml`
- `contracts/state-machine/allowed-actions.yaml`
- `contracts/state-machine/role-permissions.yaml`
- `contracts/state-machine/concurrency-policy.yaml`
- `contracts/state-machine/completion-policy.yaml`

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

## 7. T-023 완료·재개 Runtime

| API | Actor | 상태 변화 | 핵심 Guard |
| --- | --- | --- | --- |
| `resolution-feedback` | 본인 고객 | `COMPLETION_PENDING` 유지 | 해결됨·version·멱등 |
| `report-unresolved` | 본인 고객 | `COMPLETION_PENDING → REOPENED` | 미해결 형식·version·멱등 |
| `resume-consultation` | 담당 상담사 | `REOPENED → CONSULTATION_REQUIRED` | 담당 범위·version·멱등 |
| `finalize` | 마지막 상담사/기사 | `COMPLETION_PENDING → RESOLVED` | 최신 해결 피드백·마지막 처리자 |

### 해결 피드백

- 고객 피드백만으로 `RESOLVED`로 전환하지 않는다.
- 마지막 상담/방문 원본과 `FollowupConfirmation`을 연결한다.
- 같은 Key의 같은 요청은 최초 응답만 Replay한다.
- 상태는 유지하되 `state_version`은 증가하고 별도 상태이력은 만들지 않는다.

### 미해결·재개

- 미해결 보고는 이전 상담·방문·피드백 이력을 삭제하지 않는다.
- `reason_code` 공식 Registry는 미확정이므로 대문자 코드 형식만 검증·보존한다.
- 재개 시 완료된 상담을 수정하지 않고 새 `WAITING` 상담 Sequence를 생성한다.
- `resume-consultation`은 현재 담당 상담사 범위 밖 문의를 404로 은닉한다.

### 최종 완료

- 최신 완료 원본은 `completed_at`이 가장 늦은 상담 또는 방문으로 결정한다.
- 해당 원본 담당자와 요청 Actor가 일치해야 한다.
- 해결 피드백 `created_at`이 마지막 처리 완료시각보다 늦어야 한다.
- 성공 시 기존 `TransitionHistory`에 처리 출처·최종 메모를 `change_reason`,
  처리자를 `actor`, 처리시각을 `changed_at`으로 감사 보존한다.
- 내부 AI 필드명과 `s3://`·`gs://`·`file://` 원본 경로는 최종 메모에서 차단한다.

관련 구현:

- `backend/apps/inquiries/services/resolution_service.py`
- `backend/apps/inquiries/repositories/resolution_repository.py`
- `backend/apps/inquiries/api/serializers/resolution_feedback.py`
- `backend/tests/api/test_t023_resolution_runtime.py`

## 8. 2026-08-17 자체 검증

- T-023 신규 표적: `12 passed / 0 failed`
- 상담·방문·Workflow·Migration 확대 회귀: `137 passed / 1 skipped / 0 failed`
- Skip 1건: PostgreSQL 전용 Row-lock 검증이며 기존 조건부 Skip 유지
- Django system check: 문제 없음
- Migration drift: `No changes detected`
- Migration 경계: 신규 Migration 없음, `visits.0005` 적용 범위 변경 없음
- OpenAPI·State Machine·Action Crosswalk 검증 통과
- Crosswalk: Runtime 17, OpenAPI-only 2, Deferred 4
- 고객 `COMPLETION_PENDING` Snapshot: 2 Query 유지, 불필요한 최종 처리자 조회 없음

## 9. 검증 명령

```powershell
.\backend\.venv\Scripts\python.exe -B .\scripts\contracts\validate_state_machine.py
.\backend\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  .\tests\contract\test_contract_validators.py `
  .\backend\tests\unit\workflow\test_state_machine.py
```

## 10. 판정

전 상태의 Action·Guard·권한·409·Replay·History·Rollback이 계약과 일치하면
상태 전이 공통 Runtime 작성자 검증 완료다.

T-023 Backend Runtime은 구현·자체 검증 완료다. Web·Mobile Action 연결과
PostgreSQL 역할별 Row-lock 독립 QA는 외부 Gate이므로 이 문서만으로 전체
WBS 완료를 선언하지 않는다.
