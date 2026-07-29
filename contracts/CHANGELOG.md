# Contracts Changelog

## 2026-07-29 — AI 공개 응답 계약 정합화

### Changed

- `SymptomAnalysisResult` 공개 DTO의 `inquiry_id`, `correlation_id` 위치를 JSON Schema와 동일한 최상위로 통일
- 내부 전용 `model_metadata`, `processing_traces`, 중첩 `trace_context`를 공개 분석 응답에서 제외
- `inquiry_id`를 UUID로 강제하지 않고 Backend가 발급한 공개 UUID 또는 업무·시연 코드를 허용하되 내부 정수 PK는 금지
- 요청 원문 길이와 빈 문자열 검증 조건 추가

### Verification

- 정상·위험·근거 없음 예시와 Pydantic 직렬화 결과를 Draft 2020-12 Schema로 검증
- Backend 상태 변경은 AI가 수행하지 않으며, AI는 분석 결과만 반환하는 책임 경계를 유지

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
