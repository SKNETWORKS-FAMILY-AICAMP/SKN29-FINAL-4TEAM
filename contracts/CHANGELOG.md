# Contracts Changelog

## 2026-08-11 — Backend Runtime 12 후속 계약 결정 적용

### Changed

- `submitSymptom` 저장 Transaction은 AI 결과를 포함하지 않으며 성공
  Commit 이후 `transaction.on_commit` Callback으로 분석을 후속 실행하는
  경계와 Commit 시점 응답 Snapshot을 OpenAPI에 명시했다.
- `updateVisitSchedule`에 `TR-INQ-028`, `REVISIT_REQUIRED`,
  `FOLLOW_UP_REQUIRED`를 포함하고 담당 상담사 Guard를 정합화했다.
- 고객 본인 Inquiry Snapshot에 Backend 동적 Resolver가 계산한
  `allowed_actions`를 추가했다. 질문 생성 전·후·답변 후마다 최신 Guard
  결과를 반환하며 클라이언트 자체 계산은 허용하지 않는다.
- `CANCEL_INQUIRY`의 `reason_code`와 선택 `reason_detail` 분리 저장은
  유지하고, 상태 변경 이력의 `change_reason`에는 `CODE | DETAIL` 또는
  상세가 없을 때 `CODE`를 저장한다.

### Boundary

- 공개 API 경로와 취소 요청·응답 Shape는 변경하지 않는다.
- 신규 DB Migration과 기존 NULL 취소 이력 Backfill은 수행하지 않는다.
- 작성자 검증은 독립 PostgreSQL QA와 PM Backend ACK를 대신하지 않는다.

## 2026-08-11 — Backend Runtime 12 소비 정합 수정

### Changed

- `CANCEL_INQUIRY` Runtime을 고객 본인·담당 상담사·명시 권한 운영자와
  `DRAFT`·`QUESTIONNAIRE_IN_PROGRESS`의 `TR-INQ-004/005`로 확장했다.
- 취소 성공 응답에 동적 `allowed_actions`를 포함하고 실제 직전 상태와
  증가된 `state_version`을 전이 이력에 기록한다.
- `allowed_actions`는 State·Role 후보에서 Crosswalk
  `RUNTIME_IMPLEMENTED`, Transition Rule, 저장된 Domain Guard를 통과한
  Action만 반환하며 성공과 stale 409가 같은 Resolver를 사용한다.

### Validation

- State Machine, Crosswalk, OpenAPI, Example, Code Registry Validator PASS
- Backend 표적 `128 passed / 5 skipped`, 전체 `993 passed / 19 skipped`
- 격리 PostgreSQL 16.14 Row Lock 5건과 취소 Runtime·계약 25건 PASS
- Data CI Unit 76건·결정적 Rebuild·Source Hash·생성물 Drift Gate PASS

### Boundary

- `UPDATE_VISIT_SCHEDULE`의 `TR-INQ-028`은 후속 계약 Owner 결정에서
  동일 Operation 전이로 승인됐으며 위 절에서 적용 범위를 기록한다.
- 코드 커밋 `e290fe3d43ae5adf2a6ab758cbf2e19922046cd1`은 작성자 검증
  후보이며 독립 QA와 PM 소비 ACK를 대신하지 않는다.
- Inquiry Model Source Hash와 파생 Manifest는
  `5b60fd18ba72ff7272be8621e72710b8cbdaa391`에서 정합화했다.

## 2026-08-11 — Backend 소비 의미 불일치 확인

### Audit

- `CANCEL_INQUIRY` Runtime이 승인된 고객·상담사·운영자와 DRAFT·QUESTIONNAIRE_IN_PROGRESS 범위보다 좁은 것을 확인했다.
- Backend `allowed_actions`가 State·Role 후보만 반환하고 Visit·Transition·Domain Guard와 Runtime availability를 평가하지 않는 것을 확인했다.
- Validator·Crosswalk `12/7/0/4`·Contract Test PASS는 정적 증거이며 Runtime 의미 승인과 분리한다.

### Decision boundary

- 승인된 취소 역할·상태 계약은 유지하고 Backend Runtime을 계약에 맞춘다.
- `allowed_actions`는 동적 Guard와 Runtime availability를 모두 통과한 행동만 반환한다.
- 수정·표적 회귀·PostgreSQL 독립 QA 전까지 `TEAM_BASELINE` 전환과 Backend 소비 ACK를 보류한다.

## 2026-08-11 — Contract CI 현행 감사

### Audit

- 로컬 State·Mermaid·Code·OpenAPI·Example·Crosswalk·Root Contract Test 7개 Gate는 현재 기준선에서 모두 통과한다.
- 현행 Data CI는 State Machine Validator와 Mermaid Drift만 자동 실행한다.
- `contracts/api/**`, `contracts/codes/**`, `contracts/examples/**`, `contracts/error-codes/**`, `tests/contract/**` 변경은 현행 Data CI Trigger에서 누락돼 있다.

### Decision boundary

- 별도 Contract CI 분리를 PM 권고안으로 기록하고 `.github/workflows/**` 주관 담당자 적용·원격 검증을 요청한다.
- 실제 Branch 또는 PR Run이 확인되기 전에는 Contract CI 강화 완료로 판정하지 않는다.
- 과거 Changelog의 “전체 계약 Gate Data CI 연동” 설명은 목표 상태였으며, 현행 Workflow 기준으로는 부분 연동이다.

## 2026-08-10 — Mobile 고객 문의 읽기·추가답변 Runtime

### Added

- 고객 본인 문의 Snapshot `GET /me/inquiries/{inquiry_id}` Runtime
- 고객 본인 미답변 질문 `GET /me/inquiries/{inquiry_id}/questions` Runtime
- 고객 추가답변 `POST /inquiries/{id}/answers` Runtime
- 질문 메타데이터와 고객 답변 원장을 분리하는 Forward Migration

### Classification

- `SUBMIT_ANSWERS`는 `RUNTIME_IMPLEMENTED`로 승격한다.
- Action Crosswalk는 `RUNTIME_IMPLEMENTED=12`, `OPENAPI_CONFIRMED=7`, `CONTRACT_ONLY=0`, `DEFERRED=4`다.
- OpenAPI는 32개 Path·33개 Operation이며 State Machine 1.0.0은 변경하지 않는다.

### Boundary

- CUSTOMER 본인 문의만 허용하고 타 고객·미존재는 동일 404로 닫는다.
- 질문 조회는 답변값·AI 원천·내부 target field를 공개하지 않는다.
- 구조화 답변은 공개 선택지 `selected_option` 한 필드만 허용한다.
- 나머지 7개 5주차 Action은 계속 `NOT_IMPLEMENTED`다.

## 2026-08-10 — 대표 E2E Action OpenAPI 0.8.0 초기 적용 후보 (역사)

### Added

- PM이 승인한 8개 Action의 정확한 POST Method·Path·Actor·State Rule 연결
- 모든 신규 쓰기의 `state_version`, `Idempotency-Key`, `X-Correlation-ID`, 409 계약
- 방문 시작·완료의 Inquiry·Visit Version 동시 검사와 케어 결과 코드 계약
- 추가 답변의 `answer_text` 또는 `answer_payload` 배타 입력 Schema
- 해결 피드백·미해결 보고·마지막 처리 담당자 최종 완료 계약

### Classification

- 최신 main의 기존 Runtime 증거를 보존하고 8개 신규 경계는 `OPENAPI_CONFIRMED`로 분리한다.
- 집계는 `RUNTIME_IMPLEMENTED=2`, `OPENAPI_CONFIRMED=17`, `CONTRACT_ONLY=0`, `DEFERRED=4`다.
- OpenAPI는 30개 Path·31개 Operation이며 State Machine 1.0.0과 `contracts/VERSION`은 변경하지 않는다.

### Boundary

- 당시 `SUBMIT_ANSWERS`는 저장 경계 분리 전이라 `NOT_IMPLEMENTED`였으며, 위 최신 항목에서 Runtime 구현으로 대체됐다.
- 고객 해결 피드백만으로 종료하지 않으며 `FINALIZE_INQUIRY`에 최신 긍정 피드백과 마지막 처리 담당자 Guard가 필요하다.
- 본 적용 후보는 계약·예시·정적 검증 범위이며 독립 QA와 각 Runtime WBS 완료를 대신하지 않는다.

## 2026-08-10 — 대표 E2E Action PM 결정 및 State Example 연결

### Added

- 대표 정상 Example 14단계에 기존 Event Registry의 `operation_id` 연결
- 미해결→재상담 Example에 `reportUnresolved`, `resumeConsultation` 연결
- 8개 Action의 Actor·Guard·HTTP 경계를 정리한 PM 결정·담당자 인계 문서

### Boundary

- State 13개, Event 30개, Transition 34개, Guard 39개와 완료 정책의 의미는 변경하지 않는다.
- 고객 해결 피드백만으로 종료하지 않으며 마지막 처리 담당자의 `FINALIZE_INQUIRY`가 필요하다.
- 이 항목 작성 당시 각 주관 담당자 적용 대기였으며, 후속 OpenAPI `0.8.0` 적용과 Contract QA로 해당 대기는 해소됐다.
- 후속 Runtime 반영을 포함한 현행 수량은 위 최신 항목의 OpenAPI 33개 Operation과 Crosswalk `12/7/0/4`를 따른다.
- 이번 결정 자체는 소비자 승인 완료를 의미하지 않으며, 소비자 증거는 3.3 Contract Baseline Gate에서 별도로 확인한다.

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
