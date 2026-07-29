# ADR 0011 — T-005 요청 멱등성과 상태 이력 추적 책임 분리

- 상태: `OWNER_BASELINE_ACCEPTED`
- 결정일: `2026-07-28`
- 결정자: 최지용
- 적용 범위: `T005_STATUS_HISTORY_IDEMPOTENCY_SCOPE`
- 선행 문서: [ADR 0010](0010-t005-three-layer-identifier-bridge.md)
- 구현 계약: [T-005 Physical Contract v1.2](../database/t-005/t005_physical_contract_v1.2.json)

## 1. 배경

역사 Snapshot의 `support_inquiry_status_history.idempotency_key`는 전역
`UNIQUE`로 설명돼 있다. 그러나 하나의 HTTP 업무 요청이 문의 상태와
방문 상태를 함께 바꾸면 동일한 `Idempotency-Key`로 서로 다른
Aggregate의 이력 두 건을 기록해야 한다. 전역 `UNIQUE`는 이 정상 흐름의
두 번째 기록을 거부한다.

현재 Backend의 요청 재실행 차단은
`workflow_idempotency_record`의 `(actor, operation_id, idempotency_key)`
조합이 담당한다. 요청 멱등성과 상태 이력 원장의 전이 중복 방지는 서로
다른 책임이다.

## 2. 결정

`support_inquiry_status_history.idempotency_key`에는 전역 `UNIQUE`를
적용하지 않는다.

- `QUESTIONNAIRE`, `INQUIRY`, `CONSULTATION`, `VISIT` 중 정확히 하나의
  대상 FK만 값이 있어야 한다.
- `target_type_code`는 값이 있는 대상 FK와 일치해야 한다.
- 상태 이력의 `idempotency_key`는 고유성 판단용이 아니라 요청과 이력을
  연결하는 추적값으로 저장한다.
- 대상 FK·`event_code`·`idempotency_key` 조합에는 조회용 PostgreSQL
  partial non-unique index를 적용한다.
- 대상 FK와 `state_version` 조합에도 대상 유형별 PostgreSQL partial
  `UNIQUE`를 적용한다.
- HTTP 요청 단위 replay·payload hash 충돌 판단은 계속
  `workflow_idempotency_record`의
  `(actor, operation_id, idempotency_key)` 범위가 단독으로 담당한다.

이 결정은 상태 전이 규칙 자체를 바꾸지 않는다. 이벤트·Guard·다음 상태는
PM State Machine 계약을 그대로 따른다.

## 3. 결과

하나의 요청이 문의와 방문 등 여러 Aggregate의 상태 이력을 남길 수 있고,
동일 키가 다른 actor·operation에서도 정상적으로 사용될 수 있다. 동일
대상의 중복 상태 버전은 데이터베이스 제약으로 차단하며, 같은 요청의
재실행·payload 충돌은 요청 원장에서 판정한다.

역사 Snapshot인 `watercare_schema_v3.json`은 변경하지 않는다. 이번
결정은 현행 Physical Contract override와 검증기에만 반영한다.

## 4. 후속 구현 순서

통합 상태 이력 Django Model·Migration은 관련 Aggregate가 모두 준비된
뒤 다음 순서로 구현한다.

1. Consultation·Handoff 모델과 FK 확정
2. Visit 모델과 FK 확정
3. Questionnaire Session 모델과 FK 확정
4. 통합 상태 이력 모델에 대상 무결성 `CheckConstraint` 적용
5. 네 대상별 멱등키 추적 partial `Index`와 상태 버전 partial
   `UniqueConstraint` 적용
6. 빈 PostgreSQL에서 Migration 후 동일 요청 replay와 다중 Aggregate
   이력 기록 검증

준비되지 않은 FK를 임시 문자열이나 nullable 범용 ID로 대체하지 않는다.
