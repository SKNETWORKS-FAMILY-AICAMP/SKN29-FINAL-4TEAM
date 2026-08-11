# Backend Contract Runtime 12 후속 수정·검증 가이드

> 작성일: 2026-08-11 KST
>
> 기준선: `origin/main@4dbf7c0e225757f193b8f326bd97b73edaed959e`
>
> 상태: `AUTHOR_VERIFIED / POSTGRESQL_AUTHOR_PASS / INDEPENDENT_QA_PENDING`

## 1. 결론

PM이 확정한 Runtime12 후속 4건을 계약·Runtime·Test에 함께 반영했다.

1. `CANCEL_INQUIRY` 이력에 취소 사유를 `reason_code | reason_detail`로 저장한다.
2. `submitSymptom`의 AI 실행 경계를 성공 Commit 이후 `transaction.on_commit`으로 명시한다.
3. `updateVisitSchedule`에 `TR-INQ-028` 재방문 일정을 포함한다.
4. 고객 Inquiry Snapshot에 서버가 계산한 동적 `allowed_actions`를 포함한다.

작성자 표적·전체 회귀, 계약 Validator, 격리 PostgreSQL Row Lock은 모두 통과했다.
팀 승인과 최종 기준선 반영은 김은진 독립 QA 후 판단한다.

## 2. 구현 결과

| 항목 | 적용 내용 | 판정 |
|---|---|---|
| Cancel 사유 이력 | Inquiry 본체의 code/detail 분리 저장은 유지하고 History에는 `CODE | DETAIL`, 상세가 없으면 `CODE` 저장 | PASS |
| Submit AI 경계 | 저장 Transaction 성공 Commit 뒤 `on_commit`으로 1회 실행, Replay는 추가 실행 없음 | PASS |
| 재방문 일정 | `REVISIT_REQUIRED + FOLLOW_UP_REQUIRED`에서 `TR-INQ-028`로 일정 갱신 | PASS |
| 고객 Snapshot | 최신 공개 질문·State·Role·Runtime Guard로 계산한 `allowed_actions` 반환 | PASS |

## 3. 주요 변경 파일

### 3.1 Cancel 사유

- [InquiryService](../../../../backend/apps/inquiries/services/inquiry_service.py): code/detail을 History 계층으로 전달한다.
- [TransitionHistoryService](../../../../backend/apps/workflow/services/transition_history_service.py): PM 형식으로 `change_reason`을 만든다.
- [WorkflowRepository](../../../../backend/apps/workflow/repositories/workflow_repository.py): 기존 `change_reason` 컬럼에 값을 저장한다.
- [Cancel API Test](../../../../backend/tests/api/test_t023_cancel_inquiry.py): 상세 있음·없음·공백·Replay·중복 Payload·메타데이터를 검증한다.

### 3.2 Submit AI 경계

- [Inquiry OpenAPI](../../../../contracts/api/paths/inquiries.yaml): Commit-time Snapshot과 post-commit AI 실행을 명시한다.
- [InquiryTransitionService](../../../../backend/apps/inquiries/services/inquiry_transition_service.py): 기존 `transaction.on_commit(..., robust=True)` 구현을 유지한다.
- [OpenAPI Inquiry Test](../../../../backend/tests/api/test_openapi_inquiry_contract.py): 구조화된 `x-ai-dispatch` 경계를 검증한다.

`on_commit`은 별도 Queue나 비동기 Worker를 뜻하지 않는다. AI 결과는 저장 응답 Snapshot에 포함되거나 완료가 보장되지 않는다.

### 3.3 TR-INQ-028

- [Visit OpenAPI](../../../../contracts/api/paths/visits.yaml), [G2 Crosswalk](../../../../contracts/api/g2-operation-crosswalk.yaml): `TR-INQ-028`과 재방문 상태를 추가한다.
- [Transition Rules](../../../../contracts/state-machine/transition-rules.yaml): 담당 상담사 Guard를 추가한다.
- [VisitRepository](../../../../backend/apps/visits/repositories/visit_repository.py): 완료 결과는 보존하고 재일정에 맞춰 mutable lifecycle 필드를 초기화한다.
- [Consultation·Visit Test](../../../../backend/tests/api/test_consultation_visit_runtime.py): 성공·Replay·stale 409·History·Version을 검증한다.
- [G2 Contract Test](../../../../backend/tests/api/test_g2_machine_contract.py), [Resolver Test](../../../../backend/tests/unit/workflow/test_allowed_action_resolver.py): 계약과 노출 조건을 검증한다.

이번 Slice는 재방문 일정 재조율까지 검증한다. 동일 Visit의 2차 완료 결과 저장 모델은 후속 방문 완료 Runtime 범위다.

### 3.4 Customer Snapshot

- [Snapshot Schema](../../../../contracts/api/components/schemas/inquiry/CustomerInquirySnapshot.yaml): `allowed_actions`를 필수 응답 필드로 추가한다.
- [Customer Inquiry Path](../../../../contracts/api/paths/customer-inquiries.yaml): 서버 계산값 사용과 재조회 경계를 명시한다.
- [Repository](../../../../backend/apps/inquiries/repositories/customer_inquiry_repository.py): 공개 미답변 질문을 Prefetch한다.
- [Service](../../../../backend/apps/inquiries/services/customer_inquiry_service.py): 공통 Resolver로 동적 Action을 계산한다.
- [Serializer](../../../../backend/apps/inquiries/api/serializers/customer_inquiry.py): 기존 AllowedAction DTO를 재사용한다.
- [Customer Read Test](../../../../backend/tests/api/test_customer_inquiry_read_runtime.py): 질문 전·후·답변 후·미지원 질문을 검증한다.

Snapshot 조회는 공개 미답변 질문 Prefetch를 포함하며 현재 Query Budget은 2회로 고정한다.

## 4. 계약·API·DB 영향

| 구분 | 영향 |
|---|---|
| 신규 Endpoint | 없음 |
| Cancel Request/Response | 변경 없음 |
| Customer Snapshot Response | `allowed_actions` 필수 필드 추가 |
| State Machine | 기존 `TR-INQ-028`에 담당 상담사 Guard 보강 |
| DB Schema/Migration | 변경 없음, 신규 Migration 없음 |
| 기존 Cancel 컬럼 | `cancellation_reason_code`, `cancellation_reason_detail` 분리 저장 유지 |
| History | 기존 nullable `change_reason` 컬럼 사용, 과거 NULL 행 Backfill 없음 |

Cancel API Shape는 불변이지만 이후 생성되는 CANCEL History에서는 `change_reason`이 NULL이 아닌 PM 형식 문자열로 조회된다.

## 5. 작성자 검증 결과

| 검증 | 결과 |
|---|---|
| 후속 4건 표적 묶음 | `98 passed / 5 skipped / 0 failed` |
| Backend 전체 회귀 | `1004 passed / 19 skipped / 0 failed` |
| 격리 PostgreSQL Row Lock | `5 passed / 0 skipped / 0 failed` |
| Root Contract | `38 passed / 0 failed` |
| State Machine Validator | PASS: State 13, Event 30, Transition 34, Guard 39 |
| Crosswalk Validator | PASS: Runtime 12, OpenAPI 7, Contract 0, Deferred 4 |
| OpenAPI Validator | PASS: 32 Paths, 33 Operations |
| Example·Code Validator | PASS: Examples 50/50, Code 144 |
| Mermaid Drift | PASS |
| Django Check | PASS |
| Migration Drift | PASS: `No changes detected` |
| Git whitespace | PASS |

기본 전체 회귀의 19개 Skip은 PostgreSQL 구조·동시성 전용, 실제 Socket Mock opt-in, 팀 통합 Role opt-in이다.
필수 Row Lock 5건은 격리 PostgreSQL 16/pgvector 환경에서 Skip 없이 별도 통과했다.

## 6. 재현 명령

Repository Root:

```powershell
$py = '.\backend\.venv\Scripts\python.exe'
& $py -B scripts/contracts/validate_state_machine.py
& $py -B scripts/contracts/render_state_machine.py --check
& $py -B scripts/contracts/validate_contract_crosswalk.py
& $py -B scripts/contracts/validate_openapi.py
& $py -B scripts/contracts/validate_examples.py
& $py -B scripts/contracts/validate_codes.py
& $py -B -m pytest -q -p no:cacheprovider tests/contract
```

Backend Root:

```powershell
$py = '.\.venv\Scripts\python.exe'
& $py -B -m pytest -q -p no:cacheprovider `
  tests/api/test_t023_cancel_inquiry.py `
  tests/api/test_t022_submit_symptom.py `
  tests/api/test_consultation_visit_runtime.py `
  tests/api/test_customer_inquiry_read_runtime.py `
  tests/api/test_g2_machine_contract.py `
  tests/api/test_openapi_inquiry_contract.py `
  tests/unit/workflow/test_allowed_action_resolver.py
& $py -B manage.py check --settings=config.settings.test
& $py -B manage.py makemigrations --check --dry-run --settings=config.settings.test
& $py -B -m pytest -q -p no:cacheprovider
```

PostgreSQL은 폐기 가능한 별도 QA DB에서 `--ds=config.settings.local`로 5개 `postgresql` 표적을 실행한다.
공유·운영 DB, 실제 비밀번호, DSN은 문서와 로그에 기록하지 않는다.

## 7. 독립 QA Gate

김은진 QA는 동일 후보 Commit에서 다음을 재현한다.

- Cancel History의 actor·correlation·idempotency·정확한 `change_reason`.
- 상세가 없을 때 code-only, Replay 때 추가 History 0건, Inquiry 분리 컬럼 유지.
- Submit Callback이 Commit 전 0회/후 1회이며 Replay 추가 AI 호출 0회.
- `TR-INQ-028` 성공·Replay·stale 409·Version·Inquiry/Visit History.
- Customer Snapshot의 동적 `allowed_actions`와 미지원 질문 Fail-closed.
- 전체 회귀, Migration Drift, PostgreSQL Row Lock 5건 Skip 0.

최종 상태: `AUTHOR_PASS / POSTGRESQL_AUTHOR_PASS / INDEPENDENT_QA_PENDING / TEAM_BASELINE_HOLD`.
