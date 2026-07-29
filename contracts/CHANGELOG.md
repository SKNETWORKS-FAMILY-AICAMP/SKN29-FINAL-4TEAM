# Contracts Changelog

## 2026-07-29 — State Machine v1.0.0 채택

### Adopted

- State Machine 핵심 계약 8종과 대표 예시를 `TEAM_APPROVED`로 채택
- Inquiry 13상태와 Visit 7상태를 별도 Aggregate로 확정
- `RESOLVED`, `CANCELLED`를 변경 불가능한 Terminal 상태로 확정
- `REOPENED`를 `COMPLETION_PENDING + CUSTOMER_REPORTED_UNRESOLVED` 경로로 제한
- Backend를 상태 전이의 최종 권위로 확정하고 Web·Mobile은 `allowed_actions`만 소비
- 외부 쓰기의 `state_version`·`Idempotency-Key`·409 충돌 정책 확정

### Added

- `contracts/state-machine/data-state-crosswalk.yaml`
- `contracts/state-machine/examples/representative-e2e.yaml`
- `SYN-JAC104-002` 기준 14단계 대표 이벤트 순서와 최종 Version 14 검증

### Implementation status

- 계약 채택은 구현 완료를 의미하지 않는다.
- Backend Runtime은 START·CANCEL 대표 흐름만 부분 구현 상태이다.
- Consultation·Visit Runtime과 Web·Mobile·AI 실제 연동은 후속 이행 대상으로 유지한다.

## 2026-07-26 — State Machine v0.1.0 초안

### Added

- 문의 상태 13종과 이벤트 정의
- 상태 전이 규칙과 Guard
- 상태·역할별 `allowed_actions`
- 역할 권한, 완료 정책, 동시성 정책
- Mermaid 흐름도와 대표 정상·오류 예시
- 계약 간 참조 검증 스크립트

### Resolved

- `VISIT_REVIEW_PENDING`에서 방문이 필요하지 않은 경우 빠져나갈 수 없던 문제를 해결
- `VISIT_NOT_NEEDED` 이벤트 추가
- `VISIT_REVIEW_PENDING + VISIT_NOT_NEEDED → COMPLETION_PENDING` 전이 추가
- 상담사 화면용 `방문 불필요 확정` 행동 추가
