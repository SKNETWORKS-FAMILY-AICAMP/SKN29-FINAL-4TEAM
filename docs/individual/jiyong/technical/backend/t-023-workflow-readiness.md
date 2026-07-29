# T-023 Backend State Machine 구현 준비도 — 착수 전 스냅샷

> 기준일: 2026-07-27
> State Machine 업무 규칙: 윤승혁(PM)
> Backend·API 구현: 최지용
> 문서 시점 판정: 2026-07-27 당시 PM 계약 6영역 교차검증 통과, Engine·저장·API 미구현

> **현재 상태 안내:** 이 문서의 구현 수치와 `미구현` 판정은 착수 전
> 기록이므로 현행 완료 판정에 사용하지 않는다. 2026-07-29 현재
> CANCEL Runtime·Workflow 409·멱등성 대표 흐름은 구현돼 있다.
> 현재 지원 경계는
> [API Runtime 구현 상태](../../../../api/runtime_implementation_status.md),
> 실행 증거는
> [Backend API 계약 정합화 검증보고서](../../manuals/20260729_최지용_Backend_API_계약_정합화_검증보고서_v1.0.md)를
> 따른다.

## 0. 문서 책임·협업·검토

| 항목 | 내용 |
| --- | --- |
| 문서 상태 | PM 계약 6영역 교차검증 통과, Loader·Validator 구현, Engine·저장·API 미구현 |
| 관련 WBS | `T-022`, `T-023` |
| 작성·유지 책임 | 최지용 |
| 산출물/내용 의사결정자 | 윤승혁(PM): State Machine 상태·이벤트·전이·Guard·역할별 허용 행동·완료 정책. 최지용: Workflow Backend·API·Model·Migration·PostgreSQL 구현 |
| 협업 책임 | 김은진: 동시성·멱등성·Integration QA, 한예나·양정현: `allowed_actions`·`state_version`·`409` 소비, 이동윤: AI 이벤트 후보·실패 경계 |
| 검토 요청 대상 | 윤승혁(PM), 김은진, 한예나, 양정현, 이동윤 |
| 검토 상태 | 미요청 또는 증거 미확인 |
| PR 병합 담당 | 윤승혁(PM), 비작성자 1명 이상 리뷰 후 |
| 인계 대상 | 윤승혁(PM), 김은진, 한예나, 양정현, 이동윤 |

검토는 최지용의 ERD·테이블 명세·API 명세·Django·PostgreSQL
작성을 시작하기 위한 선행 승인이 아니다. 윤승혁(PM)의 State 업무 규칙을
Backend가 정확히 소비하는지, PostgreSQL 동시성·멱등성이 재현되는지,
각 Client와 AI 경계가 호환되는지를 확인하는 절차다.

## 1. 관할

윤승혁(PM)은 상태·이벤트·전이·Guard·역할별 허용 행동과 완료 정책의
업무 의미를 정의한다. 최지용은 해당 규칙을 읽어 검증하는 Loader,
Workflow Engine, Model·Migration, Service·Repository와 API를
구현한다.

API Method·Path·Payload는 최지용 확정 API 명세 영역이다. PM 입력은
현재 `draft_for_review` 상태의 State 업무 규칙이며, 최지용은 해당
계약을 Backend에서 임의 변경하지 않고 검증·소비한다.

## 2. 현재 계약 상태

| 계약 | 현재 상태 |
| --- | --- |
| [상태](../../../../../contracts/state-machine/inquiry-states.yaml) | 13개, `draft_for_review` |
| [이벤트](../../../../../contracts/state-machine/inquiry-events.yaml) | 30개, `draft_for_review` |
| [전이 규칙](../../../../../contracts/state-machine/transition-rules.yaml) | 34개, `draft_for_review` |
| [Guard](../../../../../contracts/state-machine/transition-guards.yaml) | 39개, `draft_for_review` |
| [역할 권한](../../../../../contracts/state-machine/role-permissions.yaml) | 5개 역할, `draft_for_review` |
| [허용 행동](../../../../../contracts/state-machine/allowed-actions.yaml) | 행동 카탈로그 23개와 상태별 매핑 |
| [완료 정책](../../../../../contracts/state-machine/completion-policy.yaml) | 값 존재 |
| [동시성 정책](../../../../../contracts/state-machine/concurrency-policy.yaml) | 값 존재 |

State 계약의 상태·이벤트·전이·Guard·역할 권한·허용 행동 6영역은
모두 값이 존재하고 교차 참조 검증을 통과한다. 계약 상태가
`draft_for_review`인 것과 값이 비어 있는 것은 다른 상태다. 윤승혁(PM)은
업무 의미와 변경을 관리하고, 최지용은 해당 값을 Backend에 중복
정의하지 않고 소비한다.

## 3. 현재 Backend 구현

실질 구현은 다음 두 계약 소비 파일이다.

- [State Machine Loader](../../../../../backend/apps/workflow/contracts/state_machine_loader.py)
- [계약 Validator](../../../../../backend/apps/workflow/contracts/contract_validator.py)

두 파일은 YAML 누락·빈 문서·손상·중복 키와 상태·이벤트·전이·Guard·
역할·허용 행동의 개수 및 교차 참조를 Fail-closed로 검사한다.

그 밖의 Engine, Domain 객체, Model, Repository와 Service 파일은
Placeholder다.

| 항목 | 현재 값 |
| --- | --- |
| 실질 계약 소비 파일 | 2 |
| Workflow Model | 0 |
| 번호 Migration | 0 |
| Django App 등록 | 없음 |
| Workflow Route | 없음 |
| Workflow API operation | 0 |
| PM 계약 교차검증 | `PASSED`, 오류 0 |
| Workflow 집중 테스트 | 2026-07-27 현재 변경에서 `40 passed` |
| 실제 PostgreSQL 공통 환경 | 이전 스냅샷에서 검증, T-023 Runtime은 미검증 |

## 4. 현재 남은 작업

1. 순수 State Machine Engine과 Guard Evaluator
2. `allowed_actions` Resolver
3. `TransitionHistory`, `IdempotencyRecord` Model·Migration
4. Row Lock과 Transaction을 적용한 Repository·Service
5. `state_version` 충돌과 `idempotency_key` 재요청 처리
6. 확정 API 명세 기준의 Serializer·View·URL
7. 실제 PostgreSQL 동시성·Rollback·멱등성 테스트
8. PM 계약 변경 시 Loader·교차검증·Runtime 회귀 재실행

## 5. 작업·검증 순서

| 순서 | 작업 | 즉시 검증 |
| ---: | --- | --- |
| 1 | PM 계약 6영역 수신·검증 | 공식 검증기·Loader·교차 참조 검사 `PASSED` |
| 2 | Engine·Guard·허용 행동 | 정상·금지·역할별 단위 테스트 |
| 3 | Model·Migration | 제약·Migration 재현 |
| 4 | Repository·Service | 원자적 이력·stale version 409 |
| 5 | 멱등성 | 같은 Key 재요청·다른 Payload 충돌 |
| 6 | API 연결 | OpenAPI·Serializer·응답 계약 테스트 |
| 7 | PostgreSQL Smoke | 동시 요청·Rollback·중복 방지 |
| 8 | 전체 회귀 | Backend 전체 테스트 |

## 6. 금지사항

- PM 계약 값을 Backend에서 복제하거나 임의 변경하지 않는다.
- View·Serializer·Model `save()`에서 상태를 직접 변경하지 않는다.
- 상태 이력 없이 현재 상태만 갱신하지 않는다.
- stale version과 중복 Key를 정상 신규 요청으로 처리하지 않는다.
- SQLite 단위 테스트만으로 PostgreSQL 동시성 완료를 주장하지 않는다.

## 7. 검증 기준

[Workflow 계약 테스트](../../../../../backend/tests/unit/workflow/test_state_machine_contracts.py)는
Loader·Validator와 PM 계약 6영역의 개수·교차 참조·변이 차단을
검증한다. 공식 State Machine 검증도 상태 13·이벤트 30·전이 34·Guard
39·외부 행동 23으로 통과했다.

Workflow 계약·준비도 집중 테스트는 현재 변경에서 `40 passed`, Backend
전체 회귀는 `239 passed`다. Workflow Model·Migration과 API가 0개이고
Workflow Runtime의 PostgreSQL 동시성 검증을 실행하지 않았으므로 이
수치만으로 T-023 Runtime 완료를 판정하지 않는다.

## 8. 연결 문서

- [API 계약 개발·인계 가이드](api_contract_handover_guide.md)
- [DB Schema 개발·인계 가이드](database_schema_handover_guide.md)
- [T-022 문의 관리 구현 준비도](t-022-inquiry-readiness.md)
- [T-023 준비도 검사](../../../../../backend/apps/workflow/readiness.py)
- [T-023 준비도 테스트](../../../../../backend/tests/unit/workflow/test_t023_readiness.py)

## 9. 인계 사항

| 대상 | 전달 항목 | 다음 행동 | 완료 확인 | 현재 상태 |
| --- | --- | --- | --- | --- |
| 윤승혁(PM) | 현재 채워진 13개 상태·30개 이벤트·34개 전이·39개 Guard·5개 역할·23개 행동과 `draft_for_review` 상태 | 업무 의미·버전을 관리하고 변경 시 Backend 소비 결과를 내용 검토 | 공식 검증과 Loader·교차 참조 검사 통과 | 입력 존재·기계 검증 통과, 내용 검토 증거 미확인 |
| 김은진 | `state_version`, `idempotency_key`, Row Lock, 이력·Rollback 시나리오 | 실제 PostgreSQL에서 동시성·멱등성·Integration 테스트 실행 | 중복 이력 0, stale 요청 `409`, Rollback·전체 회귀 통과 | Engine·Model 미구현으로 실행 전 |
| 한예나 | Web용 `allowed_actions`, `state_version`, 행동 Endpoint와 `409` 최신 상태 응답 | Web 상태 계산을 제거하고 Backend 응답을 소비 | 허용 행동·충돌 복구 UI가 계약과 일치 | Runtime 인계 전 |
| 양정현 | Mobile용 `allowed_actions`, `state_version`, 행동 Endpoint와 중복 요청 처리 | Mobile 상태 계산을 제거하고 멱등 Key·`409` 응답을 소비 | 재전송·충돌 시 상태와 이력이 중복되지 않음 | Runtime 인계 전 |
| 이동윤 | AI 결과를 상태 직접 변경 없이 이벤트 후보로 전달하는 Schema·실패 경계 | AI 정상·위험·근거 없음·실패 결과를 이벤트 후보 계약에 정렬 | AI가 DB를 직접 변경하지 않고 후보 검증·실패 처리 통과 | 검토 미요청 또는 증거 미확인 |
