# 고객·AI·상담 통합 시나리오 검증 가이드

> 관련 업무: Web G4 반복 검증과 Backend·AI·Mobile·Web 수직 E2E
> 핵심 원칙: 완료된 Fixture를 Reset하지 않고 실행마다 새 합성 Inquiry를 사용한다.

## 1. 검증 Lane 분리

| Lane | 시작점 | 판정 |
| --- | --- | --- |
| Web G4 | `CONSULTATION_REQUIRED` 신규 Fixture | `fixture_readiness=READY` |
| 전체 수직 E2E | Mobile 신규 문의·실제 AI·상담 요청 | `g3_audit_result=READY` |

Web G4 Fixture는 실제 AI·Evidence를 생성하지 않으므로
`g3_audit_result=NOT_APPLICABLE`이다. 이를 전체 수직 E2E PASS로 승격하지 않는다.

## 2. 전체 수직 E2E 목표 시나리오

```text
고객 Login
→ 구독 조회
→ 새 Inquiry 생성
→ 최초 증상 제출
→ 실제 AI 분석·RAG·Guidance 저장
→ 고객 Guidance 조회
→ 고객 상담 요청
→ 상담사 목록·상세
→ 상담 시작·기록·확정·완료
→ 같은 Inquiry 최종 재조회
```

## 3. 새 Inquiry가 필요한 이유

- 기존 Inquiry는 과거 Mock·상태·Idempotency 기록이 섞일 수 있다.
- 신규 제출 AI 호출 1회와 Replay 0회를 정확히 측정할 수 있다.
- 하나의 Correlation과 Aggregate 이력을 처음부터 추적할 수 있다.
- Seed 완료와 실제 Runtime 저장을 구분할 수 있다.

## 4. 시작 전 Gate

| 구간 | 준비 조건 |
| --- | --- |
| Git | 팀이 사용할 최종 코드 기준 |
| Backend | Health 200, Migration pending 0 |
| PostgreSQL | `operations.0002` 적용·`visits.0005` HOLD·예상 외 Migration 0 |
| AI | Health 200, 실제 Provider·RAG Mode 준비 |
| Mobile | Backend Remote Mode·Login 가능 |
| Web | Mock Off·상담사 Remote Adapter 준비 |

환경이 다르면 실행하지 않고 `ENVIRONMENT_BLOCKED`로 기록한다.

## 5. Web G4 실행별 신규 Fixture

Demo 계정·제품·구독 Seed 후 매 실행마다 고유한 `run_id`를 사용한다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py seed_demo_accounts
.\.venv\Scripts\python.exe manage.py seed_demo_products
.\.venv\Scripts\python.exe manage.py seed_demo_subscriptions
.\.venv\Scripts\python.exe manage.py create_web_consultation_e2e_fixture `
  --run-id "web-e2e-<build>-<attempt>" --json
```

성공 출력은 신규 `inquiry_id`, `CONSULTATION_REQUIRED`, 현재 `state_version`,
`START_CONSULTATION`, `DEMO-CONSULTANT-001`, `WAITING`을 포함한다. 소비 전 같은
`run_id`는 동일 문의를 반환하고, 소비 후에는 이력을 되돌리지 않고 새 `run_id`를
요구한다. 초기 Playwright는 `workers=1`, `retry=0`으로 실행한다.

Web Runtime은 다음 흐름을 실제 API로 검증한다.

```text
상담 시작 → 내용 저장 → 요약 확정 → 상담 완료
→ COMPLETION_PENDING → 새로고침 후 기록 유지
```

필수 오류는 미존재·비배정 404와 오래된 `state_version` 409다. Fixture 명령은
공개 API가 아니며 실제 고객·운영 DB 또는 완료 문의 Reset에 사용하지 않는다.

## 6. Backend·DB 사전검증

```powershell
.\backend\.venv\Scripts\python.exe .\backend\manage.py check
.\backend\.venv\Scripts\python.exe .\backend\manage.py showmigrations
.\backend\.venv\Scripts\python.exe -B `
  .\scripts\database\audit_backend_ai_g1b_readiness.py `
  --require-ready --require-team-database
```

## 7. 전체 수직 E2E 필수 증거

- Inquiry·Symptom·State·History·Idempotency
- AI 요청 1회와 Replay 추가 호출 0회
- AIRun·Assessment·Guidance·EvidenceLink
- Backend·AI Header·Body·DB Correlation 일치
- 고객 Guidance 공개 DTO와 내부 근거 비노출
- 상담 시작·기록·확정·완료 상태 전이
- 같은 Inquiry의 최종 Snapshot

## 8. 오류 최소 범위

Happy Path가 먼저 통과한 뒤 다음을 실행한다.

1. Replay
2. Stale `state_version` 409
3. AI 503
4. AI Timeout
5. NO_EVIDENCE
6. DANGER

오류 Case는 새 Process·별도 Fixture를 사용하고 제품 코드에 테스트용 Sleep·오류
Hook을 넣지 않는다.

## 9. 중단 조건

- Provider·DB·Role·CA 미주입
- Mock 응답만 사용
- Crosswalk·Readonly View 미검증
- 새 Inquiry가 아닌 과거 실패 Inquiry 재사용
- 다른 담당자의 공유 환경을 임의 Migration·Reset

## 10. 판정

작성자 사전검증은 E2E 준비 상태다. 같은 환경에서 정상 흐름과 필수 오류 경계를
재현하고 독립 QA가 증거를 확인한 뒤 PM이 최종 Gate를 판정한다.

## 11. 2026-08-19 작성자 검증

| 검증 | 결과 |
| --- | --- |
| Allowlist·신규 Fixture 표적 | 24 passed |
| 기존 Seed·배정·상담 관련 회귀 | 58 passed, 1 skipped |
| 로컬 PostgreSQL 신규 `run_id` | 2개 문의·WAITING 상담·요청 이력 각각 독립 생성 |
| Django Check·Compile | PASS |

전체 Backend 실행은 1,310 passed·34 skipped였고 Windows 공용 Temp ACL로 5건이
Setup Error가 됐다. 해당 파일을 권한 분리 재실행해 7건 모두 PASS했다. 별도 2건은
최신 main의 `operations.0002` 테이블이 PM/Data 물리 계약에 아직 반영되지 않은 기존
`MODEL_TABLES_OUTSIDE_CONTRACT`, `MIGRATION_TABLES_OUTSIDE_CONTRACT`다. 이 작업에서는
다른 담당자 소유 Data 계약을 변경하지 않았으며 PM 후속 정합화 전까지 전체 Audit은
`NOT_READY`다.

## 12. 2026-08-20 AI 상담 인계 저장·Web 연결

### 12.1 구현 범위

```text
AI ConsultationHandoffResult
→ Backend 내부 저장 API
→ Sanitized Handoff 원장
→ 고객 REQUEST_CONSULTATION
→ Consultation.ai_draft_summary
→ 상담사 문의 상세 Web Projection
```

- 내부 경로: `POST /api/v1/internal/ai/inquiries/{inquiry_id}/consultation-handoffs`
- 인증: 보호 환경변수 `AI_HANDOFF_INTERNAL_TOKEN`과
  `X-AI-Handoff-Token`을 상수시간 비교하며 미설정 시 Fail Closed한다.
- 동일성: Path·Payload·AIRun의 `inquiry_id`, `correlation_id`,
  `ai_request_id`가 모두 일치하고 AIRun이 종료 상태여야 한다.
- 멱등성: `Idempotency-Key=ai_request_id`; 같은 Payload Replay는 같은 원장을
  반환하고, 다른 Payload 재사용은 `DUPLICATE-EVENT-01` 409로 거절한다.
- 제품: 고객 소유 구독의 `ProductModel.model_code`를 SSOT로 사용한다.
- Evidence: 활성·검증 Crosswalk와 제품·문서 제목·Page가 일치할 때만 저장한다.
- 순서 독립성: AI Handoff가 Consultation보다 먼저 도착해도 별도 원장에 보존하고,
  고객 상담 요청으로 Consultation이 생기면 같은 Transaction에서 최신 Handoff를 연결한다.
- Web 공개: 구조화 Payload 전체가 아니라 허용된 `ai_draft_summary`만 기존 상담사
  상세 Projection으로 제공한다.

### 12.2 저장·보안 경계

- 신규 Migration: `consultations.0003_consultationhandoff`
- 신규 지원 테이블: `support_consultation_handoff`
- Prompt, 임의 확장 필드, 전화번호·이메일 원문은 Serializer에서 거절한다.
- 실제 Token·Password·DSN은 코드, `.env.example`, 문서, 로그에 기록하지 않는다.
- 내부 Endpoint는 공개 OpenAPI에서 제외했다.
- Handoff 저장 자체는 Inquiry State를 변경하거나 Consultation을 자동 생성하지 않는다.

### 12.3 작성자 검증

| 검증 | 결과 |
| --- | --- |
| Handoff API·Backend/Web Bridge·환경·Readiness 표적 | 16 passed, PostgreSQL 전용 1 skipped |
| 실제 PostgreSQL 16/pgvector Migration·Runtime·동시 Replay | 6 passed, 0 skipped |
| Root Contract | 38 passed |
| Backend 전체 회귀 | 1,370 passed, 37 별도 환경 Gate skipped, 0 failed |
| Django Check | PASS |
| Migration Drift | NONE |
| `git diff --check` | PASS |

PostgreSQL 검증은 합성 전용 계정과 볼륨 없는 일회성 컨테이너에서 수행했으며 종료 후
컨테이너와 Test DB를 제거했다. Backend 저장 후보는 준비됐지만 AI Runtime이 이 내부
Endpoint를 실제 호출하는 코드는 AI 담당 범위이므로 실제 FastAPI→Django Socket
공동 E2E는 아직 `HOLD`다.

## 13. 2026-08-27 Handoff 2.0 Backend 수신·검증

### 13.1 판단과 적용 범위

- 구현 시점의 `origin/main`과 `origin/jiyong`은 모두 `8a25bb8825a1b5c76e316883af2036e8044485c3`였다.
- 요청서 기준 Commit 이후 Main 변경분은 배포 관련으로, Handoff 구현과 충돌하지 않음을 확인했다.
- 기존 Handoff 원장과 상담 요약 칸을 그대로 사용했으며 신규 테이블·Column·Migration은 만들지 않았다.
- AI 계약 파일과 `ai/**`는 수정하지 않고 Backend 수신·검증·오류 계약·테스트만 변경했다.
- 운영 활성화 값은 `false`로 유지한다. 이 단계는 연결 준비이지 운영 활성화가 아니다.

### 13.2 적용한 처리 흐름

```text
AI Handoff 수신
→ 버전별 계약 검증
→ 원래 문의·AI 실행·상태 버전 대조
→ 분기 권위와 공식 근거 대조
→ 변경 불가능한 Handoff 원장 저장
→ 연결 가능한 경우에만 상담사 요약 반영
```

| 분기 | Backend 승인 근거 | 저장·공개 결과 |
| --- | --- | --- |
| 위험 인계 | 같은 AI 실행의 위험 판정과 Backend 위험 이력 | 원장 저장, 기존 상담이 있으면 요약 연결 |
| 안전 종료 상담 | 근거 없음·제품 미승인·시간 초과 이력 또는 검토 거절 기록 | 원장 저장, 연결 가능한 기존 상담에만 요약 연결 |
| 검증 도구 에스컬레이션 | 승인된 실패 사유와 검증 단계의 정확한 조합 | 원장만 저장, 상담 요약에는 연결하지 않음 |

- 버전이 없거나 `1.0.0`이면 기존 허용 범위를 유지하고, `2.0.0`만 강화 계약으로 처리한다.
- 버전이 없는 요청에 새 필드가 섞여도 새 버전으로 추정하지 않고 거절한다.
- 새 버전의 상태 번호는 현재 문의 값이 아니라 원래 AI 분석 입력에 기록된 값과 대조한다.
- 근거 ID·순서·동일 실행 승인 기록·활성 검증 Crosswalk·제품·문서·페이지가 모두 맞아야 저장한다.
- 같은 요청과 같은 내용의 재전송은 기존 결과를 반환하고, 내용 또는 버전을 바꾼 재사용은 거절한다.
- 늦게 도착한 과거 결과가 더 최신 상담 요약을 덮어쓰지 못하도록 비강등 조건을 적용했다.
- 상담사 요약은 쉬운 일반 문장과 허용 정보만 사용하며 4,000자를 넘지 않는다.

### 13.3 추가한 공개 오류

| 오류 | 의미 | 재시도 기준 |
| --- | --- | --- |
| `AI_HANDOFF_NOT_READY` | 원래 AI 실행 결과가 아직 확정되지 않음 | 최대 1회 |
| `AI_HANDOFF_STALE` | 원래 실행·상태·분기 권위와 불일치 | 재시도 금지 |
| `AI_HANDOFF_EVIDENCE_REJECTED` | 공식 근거 또는 동일 실행 결속 실패 | 재시도 금지 |

### 13.4 변경 위치

- `backend/apps/consultations/api/handoff_serializers.py`: 버전 분리와 입력·개인정보 검증
- `backend/apps/consultations/services/consultation_handoff_service.py`: 실행·분기·검토·근거 권위 검증
- `backend/apps/consultations/repositories/consultation_handoff_repository.py`: 원장 연결과 요약 비강등 처리
- `backend/common/exceptions/error_codes.py`, `contracts/error-codes/**`: 공개 오류와 분류별 계약
- `backend/tests/api/test_*handoff*`, 오류·충돌 계약 테스트: 필수 성공·거절·Replay 회귀 고정

### 13.5 작성자 검증

| 검증 | 결과 |
| --- | --- |
| SQLite Handoff Runtime | 16 passed, PostgreSQL 전용 2 skipped |
| 실제 PostgreSQL 16/pgvector Handoff·동시 Replay | 18 passed, 0 failed |
| 공통 오류 Registry | 8 passed |
| 인접 상담·문의·Web Bridge·Lock 회귀 | 72 passed |
| AI Handoff 2.0 계약 | 40 passed |
| Backend 전체 회귀 | 1,630 passed, 환경별 Gate 44 skipped, 0 failed |
| Django Check·Compile·`git diff --check` | PASS |

PostgreSQL 검증은 합성 데이터와 볼륨 없는 일회성 컨테이너로 수행했고, 실행 후 컨테이너와
Test DB를 제거했다. SQLite 결과와 PostgreSQL 동시성 검증 결과를 서로 대체하지 않았다.

### 13.6 현재 상태와 다음 Gate

```text
contract_version=2.0.0
v1_regression=PASS
v2_serializer=PASS
airun_state_binding=PASS
harness_crosswalk=PASS
human_review_binding=PASS
evidence_binding=PASS
error_registry=PASS
replay_and_projection=PASS
postgresql_integration=PASS
protected_ai_backend_e2e=NOT_RUN
AI_HANDOFF_BACKEND_ENABLED=false
status=READY_FOR_AI_V2_INTEGRATION
```

남은 작업은 AI 측의 새 버전 전송 구현과 동일 문의를 사용한 보호 환경 공동 HTTP 검증이다.
두 구현이 연결되고 공동 검증 증거가 확보되기 전에는 운영 활성화와 전체 완료로 판정하지 않는다.
