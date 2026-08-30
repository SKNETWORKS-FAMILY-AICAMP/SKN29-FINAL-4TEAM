# E11 — Playwright Browser User E2E

- Git SHA: `f0a72d9862667f6f0cf323909cb40e7c6c853f44`
- Result: **4/4 PASS**
- Browser: `Chromium`
- Mock API: `false`
- Mock Auth: `false`
- Backend: real local Backend
- Database: local PostgreSQL only
- Playwright exit code: `0`
- Playwright test result: `2 passed / 0 failed / 0 skipped`

## 실험 질문

> 상담사가 실제 브라우저 UI에서 문의 확인부터 상담 완료, 동시성 충돌 처리, 접근 경계, 방문기사 선택까지 주요 업무를 실제 Backend와 연결해 수행할 수 있는가?

## 결과 요약

| Case | Scenario | Source | Result |
|---|---|---|---:|
| E11-01 | CONSULTATION_HAPPY_PATH | `e2e/specs/consultation-workflow.spec.ts` | PASS |
| E11-02 | STALE_STATE_CONFLICT | `e2e/specs/consultation-workflow.spec.ts` | PASS |
| E11-03 | ACCESS_BOUNDARY | `e2e/specs/consultation-workflow.spec.ts` | PASS |
| E11-04 | VISIT_TECHNICIAN_WORKFLOW | `e2e/specs/technician-selection.spec.ts` | PASS |

## Consultant Login Preflight

Demo Seed는 합성 상담사 계정을 unusable password 상태로 생성한다. E11 Runner는 Browser 실행 전에 저장소 공식 `set_synthetic_consultant_password` 명령으로 Runtime 전용 비밀번호를 적용하고, 실제 `/api/v1/auth/login` HTTP 200과 `role_code=CONSULTANT`를 확인한다. Token/비밀번호는 Artifact에 기록하지 않는다.

- Credential command: `APPLIED`
- Password source: `EPHEMERAL_RUNTIME`
- Real login HTTP: `200`
- Login role: `CONSULTANT`
- Secret exposed: `False`

## Native Fixture Contract

Repository의 `web/e2e/support/backendFixture.ts`가 공식 Workflow Action Registry에서 유효 Action을 검증하고, `START_CONSULTATION` 포함을 강제하며, Backend가 반환한 유효 배열을 보존하는지 실행 전에 확인한다. Runner는 Source를 수정하지 않는다.

- Runtime parser patch: `False`
- Product code modified: `False`
- Native contract checks: `{'official_action_registry': True, 'start_action_required': True, 'valid_actions_preserved': True, 'legacy_exact_length_absent': True}`

## Browser Workflow

```text
Chromium
  ↓
WaterBridge Web (Vite)
  ↓
Real Local Backend
  ↓
Local PostgreSQL
```

Playwright 설정의 Mock API/Auth는 비활성 상태이며, Backend Fixture는 로컬 DB에만 생성된다.

## E11-01 — Consultation Happy Path

```text
Login
  ↓
Inquiry Detail
  ↓
Start Consultation
  ↓
Save Consultation
  ↓
Confirm Summary
  ↓
Complete Consultation
  ↓
COMPLETION_PENDING
  ↓
Browser Reload
  ↓
Persisted Data Re-loaded
```

## E11-02 — Stale State Conflict

```text
Browser state_version = N
          ↓
Concurrent request saves first
          ↓
Server state_version = N+1
          ↓
Browser submits stale state
          ↓
409 STATE-CONFLICT-01
          ↓
Latest server state refresh
          ↓
Counselor draft fields preserved
```

## E11-03 — Access Boundary

Runner가 Backend 공식 `create_web_concealed_e2e_fixture` 명령으로 다른 상담사에게 배정된 합성 문의를 생성한 뒤, 실제 로그인 Browser Session에서 목록 미노출과 직접 Detail/Start 접근의 `404 RESOURCE_NOT_FOUND`를 검증한다.

## E11-04 — Visit Technician Workflow

```text
Consultation
  ↓
Visit Required
  ↓
Visit Review
  ↓
Visit Create
  ↓
Technician Select
  ↓
Preferred Date Save
  ↓
Detail Re-open
  ↓
Technician / Schedule persisted
```

## Artifact Privacy

Screenshot·Video·Trace의 Privacy 처리는 기존 `web/e2e/support/privacy.ts`와 Playwright 설정에 맡긴다. E11 Runner는 해당 원본 Artifact를 별도로 복제하지 않으며 실행 결과와 비민감 요약만 AI 실험 결과 폴더에 저장한다.

- Browser runtime artifact root: `web/.runtime/playwright`
- Recent artifact files: `10`

## 핵심 해석

Playwright Chromium에서 Mock API/Auth를 사용하지 않고 실제 로컬 Web·Backend·PostgreSQL을 연결하여 상담사 핵심 업무를 검증했다. 상담 처리와 새로고침 후 영속성, stale state_version의 409 fail-closed, 비배정 문의의 404 concealment, 방문 생성 후 기사 선택·일정 저장을 실제 Browser Workflow에서 확인했다.

## 주장 범위

본 E11은 Consultant Web <-> Backend의 Browser E2E다. Mobile -> AI -> Backend -> Web 전체 서비스 E2E나 실제 고객/RDS 환경 실행을 증명하지 않는다.

따라서 발표에서는 **'실제 Chromium Browser에서 상담사 Web과 Backend 업무 Workflow를 E2E로 검증했다'**고 표현하고, **'고객 입력부터 AI 추론까지 전체 서비스 E2E'**라고 확대하지 않는다.

## 재현 Artifact

```text
ai/scripts/experiments/e11_playwright_user_e2e.py

ai/experiment_results/e11/
├─ summary.json
├─ report.md
├─ playwright.log
└─ backend_server.log  # Runner가 Backend를 시작한 경우
```
