# ADR 0011: T-005 요청 멱등성과 상태 이력 책임 분리

> 기계 상태: `OWNER_BASELINE_ACCEPTED`
>
> 현재 해석: `ACTIVE_IMPLEMENTED` — 공식 검토 Gate 대기
>
> 결정일: 2026-07-28
>
> 초기 결정 책임: Backend·Database 담당(T-005)
>
> 적용 범위: `T005_STATUS_HISTORY_IDEMPOTENCY_SCOPE`
>
> 선행 결정: [ADR 0010](0010-t005-three-layer-identifier-bridge.md)
>
> 결정 당시 계약:
> [Physical Contract v1.2](../database/t-005/t005_physical_contract_v1.2.json)
>
> 현재 활성 계약:
> [Physical Contract v1.3](../database/t-005/t005_physical_contract_v1.3.json)

## 1. 배경

역사 Snapshot의 `support_inquiry_status_history.idempotency_key`는
전역 `UNIQUE`로 설명돼 있었다. 그러나 하나의 HTTP 업무 요청이 문의와
방문 상태를 함께 바꾸면 같은 `Idempotency-Key`로 서로 다른
Aggregate의 이력을 각각 기록해야 한다. 전역 고유 제약은 정상적인
두 번째 이력을 거부한다.

HTTP 요청 재실행 차단과 상태 이력의 전이 중복 방지는 서로 다른
책임이므로 별도 원장과 제약으로 분리한다.

## 2. 결정

`support_inquiry_status_history.idempotency_key`에는 전역 `UNIQUE`를
적용하지 않는다.

- `QUESTIONNAIRE`, `INQUIRY`, `CONSULTATION`, `VISIT` 중 정확히
  하나의 대상 FK만 값이 있어야 한다.
- `target_type_code`는 값이 있는 대상 FK와 일치해야 한다.
- 상태 이력의 `idempotency_key`는 요청과 이력을 연결하는 추적값이며
  replay 판정 원장이 아니다.
- 대상 FK·`event_code`·`idempotency_key` 조합에는 대상 유형별
  partial non-unique Index를 둔다.
- 대상 FK와 `state_version` 조합에는 대상 유형별 partial
  `UniqueConstraint`를 둔다.
- HTTP 요청의 replay·payload hash 충돌 판단은
  `workflow_idempotency_record`의
  `(actor, operation_id, idempotency_key)` 범위가 담당한다.

이 결정은 상태 전이 규칙을 바꾸지 않는다. 이벤트·Guard·다음 상태는
`contracts/state-machine/**`의 기계 계약을 따른다.

## 3. 결과

- 하나의 요청이 여러 Aggregate의 상태 이력을 남길 수 있다.
- 같은 Client Key를 다른 actor·operation에서 독립적으로 사용할 수 있다.
- 동일 대상의 중복 상태 버전은 데이터베이스 제약으로 차단한다.
- 같은 요청의 재실행과 payload 충돌은 요청 멱등성 원장에서 판정한다.
- 상태 이력은 요청 원장과 `correlation_id`·`idempotency_key`로
  추적할 수 있다.

역사 Snapshot인 `watercare_schema_v3.json`은 수정하지 않고 활성
Physical Contract가 차이를 명시한다.

## 4. 구현 결과

| 책임 | 현재 구현 |
| --- | --- |
| 요청 멱등성 원장 | [IdempotencyRecord](../../backend/apps/workflow/models/idempotency_record.py) |
| 통합 상태 이력 | [TransitionHistory](../../backend/apps/workflow/models/transition_history.py) |
| 대상 FK 확장 | [Migration 0002](../../backend/apps/workflow/migrations/0002_expand_transition_targets.py) |
| 계약 정렬·데이터 보정 | [Migration 0004](../../backend/apps/workflow/migrations/0004_align_contract_status_history.py) |
| 제약·Index 명칭 정렬 | [Migration 0005](../../backend/apps/workflow/migrations/0005_status_history_contract_names_indexes.py) |
| 계약·Migration 회귀 | [상태 이력 테스트](../../backend/tests/unit/workflow/test_status_history_contract.py) |

현재 Model에는 네 대상별 `state_version` 고유 제약, 정확히 하나의 대상
FK만 허용하는 CheckConstraint, 대상 유형 일치 CheckConstraint와
네 대상별 멱등키 추적 Index가 반영돼 있다.

활성 계약은 기술 구현 완료·공식 검토 대기로 판정한다. 작성자 검증을
팀의 독립 재현이나 PM 완료 승인으로 확장하지 않는다.

## 5. 유지보수 조건

1. 상태 이력의 `idempotency_key`에 전역·대상별 고유 제약을 새로
   추가하지 않는다.
2. replay·payload hash 판정은 요청 멱등성 원장 한 곳에서 수행한다.
3. 상태 이력은 append-only로 운영하고 적용된 Migration을 수정하지
   않는다.
4. 대상 유형을 추가할 때 FK, `target_type_code`, CheckConstraint,
   상태 버전 제약, 추적 Index와 테스트를 함께 추가한다.
5. 상태 전이 계약 변경은 Runtime Service·이력 기록·OpenAPI·회귀
   테스트와 같은 변경 단위로 검증한다.
6. 준비되지 않은 대상 FK를 임시 문자열이나 범용 nullable ID로
   대체하지 않는다.

## 6. 검증

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\unit\workflow\test_status_history_contract.py -q -p no:cacheprovider
backend\.venv\Scripts\python.exe -m pytest backend\tests\unit\database\test_t005_schema_validator.py -q -p no:cacheprovider
```

검증은 동일 요청 replay, payload 충돌, 다중 Aggregate 이력 기록,
대상 FK 무결성, 동일 대상 상태 버전 중복 차단을 포함해야 한다.
