# Contracts Changelog

## 2026-08-07 — State Machine Action–OpenAPI–Runtime Crosswalk 기준선

### Added

- 외부 Action 23개 전체를 누락 없이 분류한 `api/action-operation-crosswalk.yaml`
- Action별 State Machine Event·Operation ID·HTTP Method·Path·Runtime 증거 연결
- `RUNTIME_IMPLEMENTED`, `OPENAPI_CONFIRMED`, `CONTRACT_ONLY`, `DEFERRED` 판정 기준과 집계
- Registry·Event·OpenAPI·Runtime 증거를 검증하는 `scripts/contracts/validate_contract_crosswalk.py`
- 정상 기준선과 HTTP Drift·Runtime 증거·집계 Drift 실패를 검증하는 Contract Test
- 공통 Code Registry와 State Machine 투영을 검증하는 `scripts/contracts/validate_codes.py`
- Local `$ref`·Operation ID·Path Parameter를 검증하는 `scripts/contracts/validate_openapi.py`
- JSON·`externalValue`·공통 응답 Wrapper를 검증하는 `scripts/contracts/validate_examples.py`
- 세 Validator의 현재 기준 수량과 참조 완전성을 고정하는 Repository Contract Test
- `contracts/**`, `scripts/contracts/**`, `tests/contract/**` 변경 시 전체 계약 Gate를 실행하는 Data CI 연동

### Classification

- Backend Runtime과 Test 증거가 있는 Action 2개를 `RUNTIME_IMPLEMENTED`로 분류
- 정확히 일치하는 OpenAPI Operation만 존재하는 Action 9개를 `OPENAPI_CONFIRMED`로 분류
- 4주차 우선 범위이나 정확한 OpenAPI Operation이 없는 Action 2개를 `CONTRACT_ONLY`로 분류
- 후속 구현 범위 Action 10개를 `DEFERRED`로 분류

### Boundary

- 유사한 범용 Operation, Web·Mobile Mock 또는 과거 실행 기록만으로 Runtime 완료를 선언하지 않는다.
- 이번 변경은 분류 기준선이며 Backend·Web·Mobile·AI 소비자 승인 완료를 의미하지 않는다.
- CI는 State Machine·Diagram·Code·OpenAPI·Example·Crosswalk·Contract Test를 순서대로 검증한다.

### Verification

```text
python scripts/contracts/validate_contract_crosswalk.py
python scripts/contracts/validate_codes.py
python scripts/contracts/validate_openapi.py
python scripts/contracts/validate_examples.py
python -m unittest discover -s tests/contract/api -p "test_*.py" -v
python -m unittest discover -s tests/contract -p "test_*.py" -v
```

## 2026-08-05 — T-018 R1 고객 본인 구독 목록·상세 계약

### Added

- 고객 본인 구독 목록 `GET /me/subscriptions`와 상세 `GET /me/subscriptions/{subscription_id}`
- `WPUJAC104DWH` 활성 제품 모델·ACTIVE 구독만 반환하는 서버 Scope
- Product·Subscription 공개 DTO, 목록·상세 Wrapper와 정상·빈 목록·검증 오류 예시
- 완료 CareRecord의 `performed_on` 우선, `completed_at`의 `Asia/Seoul` 업무일 Fallback 계약
- T-018 전용 정적 Contract Test와 OpenAPI Operation Inventory 23개 기준

### Boundary

- 문의 가능 여부는 T-022 Guard, `allowed_actions`는 T-023 State Machine으로 분리한다.
- 내부 PK·계약번호·시리얼·설치 주소·고객 개인정보·원본 제품 Features는 공개하지 않는다.
- 이번 변경은 기계 계약과 Contract Test만 포함한다. Backend Runtime·Migration·DB·Seed·Web·Mobile 구현은 시작하지 않는다.
- 두 T-018 Operation은 `x-runtime-status: NOT_IMPLEMENTED`이며 별도 PM Runtime Gate 전까지 이 상태를 유지한다.

## 2026-08-04 — G2 상담·방문 기계 계약 QA 보완

### Added

- 상담사 문의 목록·상세, 상담 4개 Action, 방문 5개 Action을 포함한 G2 신규 Operation 11개
- DEC→OpenAPI→DTO→State Rule→권한 범위를 고정한 `g2-operation-crosswalk.yaml`
- 400·401·403·404·409·422·500 의미와 객체 은닉 기준을 고정한 `g2-error-matrix.yaml`
- 합성 고객·기사 최소 Projection, date-only 방문 일정, 상담·방문 Request와 공식 JSON 예시
- 같은 탭 15분 Draft·이탈 경고와 서버 Draft·자동저장 제외 경계를 분리한 DEC-009 정책
- G2 전용 정적 Contract Test와 전달물 Manifest

### Changed

- 방문 일정·확정 Rule에 담당 상담사 Guard를 추가하고 기사 식별자를 `synthetic_technician_id`로 통일
- 비담당 상담 객체는 역할 실패 403과 구분해 404로 존재를 숨기도록 변경
- 방문 일정 Guard의 datetime 입력을 `preferred_date`·`confirmed_date` date-only 계약으로 교체
- Inquiry 상태·우선순위·Workflow Action 빈 공통 Code Registry를 승인 원천과 정렬

### Gate

- 이 변경은 G2 기계 계약과 정적 검증만 포함하며 Backend Runtime·DB Migration·Web·Mobile 구현 완료를 의미하지 않는다.
- DEC-006은 P1, DEC-008은 HOLD, DEC-009 서버 Draft·자동저장은 P1 또는 별도 DEC로 유지한다.

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
