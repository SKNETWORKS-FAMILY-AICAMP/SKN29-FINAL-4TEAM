# Contracts Changelog

<<<<<<< HEAD
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
=======
## 0.1.0

- `contracts/` 초기 골격 생성
- REST API, AI JSON Schema, State Machine, 공통 코드, 오류 코드 영역 분리
>>>>>>> 2998a75c72ef8d47f3be00e9e845ed8940ce2ed1
