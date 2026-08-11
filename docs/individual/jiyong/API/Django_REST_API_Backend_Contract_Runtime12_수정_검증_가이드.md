# Backend Contract Runtime 12 수정·검증 가이드

> 작성일: 2026-08-11 KST
>
> 코드 커밋: [`e290fe3d43ae5adf2a6ab758cbf2e19922046cd1`](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN29-FINAL-4TEAM/commit/e290fe3d43ae5adf2a6ab758cbf2e19922046cd1)
>
> Data 정합 커밋: [`5b60fd18ba72ff7272be8621e72710b8cbdaa391`](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN29-FINAL-4TEAM/commit/5b60fd18ba72ff7272be8621e72710b8cbdaa391)
>
> 기준 `jiyong`: `5669960200207f134af8ac2e2a6b1c4e267e478e`
> 상태: `AUTHOR_VERIFIED / INDEPENDENT_QA_PENDING / PM_ACK_PENDING`

## 1. 목적과 판정

PM이 발견한 Backend 소비 불일치 두 건을 승인 계약에 맞췄다.

1. `CANCEL_INQUIRY`를 고객 본인·담당 상담사·명시 권한 운영자가
   `DRAFT`와 `QUESTIONNAIRE_IN_PROGRESS`에서 실행한다.
2. `allowed_actions`는 State·Role 정적 목록이 아니라 State Machine,
   저장된 Domain Guard, Crosswalk Runtime 가용성을 평가한다.
3. 성공 응답과 stale 409는 같은 Snapshot Builder와 Resolver를 사용한다.

작성자 검증은 PASS다. 독립 PostgreSQL QA와 PM 소비 ACK 전에는
`TEAM_BASELINE` 또는 전체 완료로 확대하지 않는다.

## 2. 핵심 구현

- [Cancel 권한](../../../../backend/apps/inquiries/permissions.py):
  CUSTOMER·CONSULTANT·OPERATOR 진입과 운영자
  `inquiries.cancel_inquiry` 명시 권한을 분리했다.
- [Inquiry Model](../../../../backend/apps/inquiries/models/inquiry.py),
  [0012 Migration](../../../../backend/apps/inquiries/migrations/0012_alter_inquiry_options.py):
  운영자 취소 Permission을 생성한다.
- [Inquiry Repository](../../../../backend/apps/inquiries/repositories/inquiry_repository.py):
  현재 owner·assignment·operator scope를 확인한 뒤 Inquiry 본행만 잠근다.
- [Inquiry Service](../../../../backend/apps/inquiries/services/inquiry_service.py):
  TR-INQ-004/005, Guard, Version, 멱등성, 실제 이전 상태 이력,
  활성 AIRun 논리 취소를 하나의 Transaction으로 처리한다.
- [History](../../../../backend/apps/workflow/services/transition_history_service.py):
  DRAFT 하드코딩을 제거하고 실제 전이 전·후 상태와 Version을 기록한다.
- [AllowedActionResolver](../../../../backend/apps/workflow/engine/allowed_action_resolver.py):
  State·Role → Runtime Crosswalk → Transition → 저장 Guard 순으로 평가한다.
- [Assigned Action Service](../../../../backend/apps/workflow/services/assigned_consultant_action_service.py):
  현재 배정 Scope 확인 후 Replay하고 성공·409 Snapshot을 통일한다.
- [AI Service](../../../../backend/apps/inquiries/services/inquiry_ai_service.py):
  취소 전·HTTP 중 취소·늦은 응답이 고객 상태와 Projection을 덮지 않는다.
- [Crosswalk](../../../../contracts/api/action-operation-crosswalk.yaml),
  [Cancel OpenAPI](../../../../contracts/api/paths/workflow.yaml),
  [Cancel Result](../../../../contracts/api/components/schemas/workflow/CancelInquiryResult.yaml):
  Runtime Source·Test와 성공 응답을 현행화했다.

## 3. Runtime 12 증거 Matrix

| Event / operationId | Method·Path | Runtime Source | 실행 Test | 판정 |
|---|---|---|---|---|
| `SUBMIT_SYMPTOM` / `submitSymptom` | POST `/inquiries/{id}/submit` | [View](../../../../backend/apps/inquiries/api/views.py), [Service](../../../../backend/apps/inquiries/services/inquiry_transition_service.py) | [T-022 Submit](../../../../backend/tests/api/test_t022_submit_symptom.py) | PASS |
| `CANCEL_INQUIRY` / `cancelInquiry` | POST `/inquiries/{id}/cancel` | [View](../../../../backend/apps/inquiries/api/views.py), [Service](../../../../backend/apps/inquiries/services/inquiry_service.py) | [T-023 Cancel](../../../../backend/tests/api/test_t023_cancel_inquiry.py), [Contract](../../../../backend/tests/api/test_cancel_inquiry_contract.py) | PASS |
| `SUBMIT_ANSWERS` / `submitFollowUpAnswers` | POST `/inquiries/{id}/answers` | [View](../../../../backend/apps/inquiries/api/views.py), [Service](../../../../backend/apps/inquiries/services/followup_answer_service.py) | [T-022 Answers](../../../../backend/tests/api/test_t022_submit_followup_answers.py) | PASS |
| `START_CONSULTATION` / `startConsultation` | POST `/inquiries/{id}/start-consultation` | [Consultation Service](../../../../backend/apps/consultations/services/consultation_service.py) | [Consultation·Visit](../../../../backend/tests/api/test_consultation_visit_runtime.py) | PASS |
| `UPDATE_CONSULTATION_SUMMARY` / `updateConsultationSummary` | PATCH `/inquiries/{id}/consultation-summary` | Consultation Service | Consultation·Visit | PASS |
| `CONFIRM_CONSULTATION_SUMMARY` / `confirmConsultationSummary` | POST `/inquiries/{id}/consultation-summary/confirm` | Consultation Service | Consultation·Visit | PASS |
| `CONSULTATION_COMPLETED` / `completeConsultation` | POST `/inquiries/{id}/complete-consultation` | Consultation Service | Consultation·Visit | PASS |
| `VISIT_REVIEW_REQUIRED` / `requestVisitReview` | POST `/inquiries/{id}/visit-review` | [Visit Service](../../../../backend/apps/visits/services/visit_service.py) | Consultation·Visit | PASS |
| `VISIT_NEEDED` / `createVisitRequest` | POST `/inquiries/{id}/visits` | Visit Service | Consultation·Visit | PASS |
| `UPDATE_VISIT_SCHEDULE` / `updateVisitSchedule` | PATCH `/visits/{id}/schedule` | Visit Service | Consultation·Visit | `PASS_WITH_CONTRACT_OWNER_CONFIRMATION` |
| `CONFIRM_VISIT` / `confirmVisit` | POST `/visits/{id}/confirm` | Visit Service | Consultation·Visit | PASS |
| `VISIT_NOT_NEEDED` / `markVisitNotNeeded` | POST `/inquiries/{id}/visit-not-needed` | Visit Service | Consultation·Visit | PASS |

상담 4개와 방문 5개는 [공통 Action Service](../../../../backend/apps/workflow/services/assigned_consultant_action_service.py)에서 담당자 Scope, `state_version`, Idempotency-Key, Replay와 409를 공통 처리한다.

## 4. 작성자 검증 결과

| 검증 | 결과 |
|---|---|
| Runtime12 핵심 표적 | `100 passed / 5 skipped / 0 failed`; Skip은 PostgreSQL 전용 |
| 소비·Example 보강 | `28 passed / 0 failed` |
| 표적 합계 | `128 passed / 5 skipped / 0 failed` |
| State Machine | PASS: State 13, Event 30, Transition 34, Guard 39, Action 23 |
| Crosswalk | PASS: Runtime 12, OpenAPI 7, Contract 0, Deferred 4 |
| OpenAPI·Example·Code | PASS: Operation 33, API Example 50, Code 144 |
| 최신 Root Contract·Safety | `42 passed / 0 failed` |
| Django Check·Migration Drift | PASS / `No changes detected` |
| Migration 왕복 | 전체 적용 → 0011 역방향 → 0012 재적용 → 미적용 0 |
| Backend 전체 | `993 passed / 19 skipped / 0 failed` |
| 격리 PostgreSQL 16.14 | Row Lock `5 passed`; Cancel Runtime·Contract `25 passed`; mandatory skip 0 |
| Data CI 동등 Gate | Unit `76 passed`; deterministic rebuild PASS; Data Drift 0 |
| Git whitespace | `git diff --check` PASS |

PostgreSQL은 `pgvector/pgvector:0.8.6-pg16-bookworm` 일회성 컨테이너와
별도 DB·Port를 사용했다. 공유 DB·영구 Volume은 사용하지 않았고 검증 후
컨테이너를 자동 삭제했다.

## 5. 정확한 재현 명령

저장소 Root에서 실행한다. `.venv`는 팀 고정 의존성을 설치한 환경이다.

```powershell
$repo = (Resolve-Path '.').Path
$py = (Resolve-Path "$repo/backend/.venv/Scripts/python.exe").Path

& $py -B scripts/contracts/validate_state_machine.py
& $py -B scripts/contracts/validate_contract_crosswalk.py
& $py -B scripts/contracts/validate_openapi.py
& $py -B scripts/contracts/validate_examples.py
& $py -B scripts/contracts/validate_codes.py
& $py -B -m pytest -q -p no:cacheprovider tests/contract tests/safety/test_week5_ai_safety_crosswalk.py
& $py -B -m unittest discover -s data/tools/tests -v
& $py -B data/tools/pipeline.py qa --verify-rebuild
& $py -B scripts/data/refresh_source_hashes.py --check
git diff --exit-code -- data

Set-Location "$repo/backend"
& $py -B -m pytest -q -rs -p no:cacheprovider tests/unit/workflow/test_allowed_action_resolver.py tests/api/test_cancel_inquiry_contract.py tests/api/test_t023_cancel_inquiry.py tests/api/test_t022_submit_symptom.py tests/api/test_t022_submit_followup_answers.py tests/api/test_consultation_visit_runtime.py tests/unit/ai_integration/test_inquiry_ai_service.py
& $py -B -m pytest -q -p no:cacheprovider tests/api/test_consultant_inquiry_runtime.py tests/api/test_customer_inquiry_read_runtime.py tests/api/test_openapi_runtime_coverage.py tests/api/test_runtime_examples_contract.py tests/api/test_workflow_conflict_contract.py
& $py -B manage.py check --settings=config.settings.test
& $py -B manage.py makemigrations --check --dry-run --settings=config.settings.test
& $py -B -m pytest -q -rs -p no:cacheprovider
```

PostgreSQL 전용 검증은 `--ds=config.settings.local`과 폐기 가능한 별도 DB를
사용한다. DSN·비밀번호는 문서나 로그에 기록하지 않는다.

## 6. 남은 승인 경계

1. 김은진이 동일 고정 SHA에서 PostgreSQL Row Lock·IDOR·Replay·409를
   독립 재현해야 한다.
2. `submitSymptom` OpenAPI의 “AI 호출 제외” 설명과 실제 on_commit
   Wiring의 문구 정합을 계약 Owner가 확인해야 한다.
3. `updateVisitSchedule` OpenAPI의 TR-INQ-020/021에 State Machine
   TR-INQ-028을 포함할지 계약 Owner가 결정해야 한다.
4. 고객 Snapshot은 최신 상태·Version을 제공하지만 비동기 질문 생성 후
   동적 `allowed_actions`까지 재조회하는 공개 응답은 소비자 계약 후속이다.

## 7. 인계 판정

`CODE_AND_AUTHOR_TESTS_PASS / JIYONG_PUSH_READY / INDEPENDENT_QA_PENDING /
BACKEND_ACK_FALSE / TEAM_BASELINE_HOLD`

민감정보·DSN·실계정·고객 원문은 코드·문서·검증 로그에 기록하지 않았다.
