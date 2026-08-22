# AI 계약 4.0 제품 미승인 Backend Runtime 구현·검증

- 작성일: 2026-08-21 (최신 자체검증: 2026-08-22)
- 담당: 최지용(Backend·DB)
- 기준선: `origin/main=origin/jiyong=0d2869eb5b5ead3da833eb11e7c592b33030af31`
- AI 계약 후보: `origin/dongyoon=17ac06f33fcba8a7ad4598699903264cb8d7716d`
- AI 계약 구현 원본: `d11829424cc729fb9e35640df1cd69d7805530e6`
- Backend 구현 Commit: `556994affdbfbc00486cefd0b906edcd3238c19f`
- Evidence 회귀 보강 Commit: `5168436f06dce3af7f600179624eb47740c91e19`
- 최신 판정: `BACKEND_DB_5CASE_READY / ACTUAL_AI_MCP_PROVIDER_NOT_RUN`

## 1. 목적

AI 계약 4.0.0이 반환하는 `model_code`와 `fallback_reason_code`를 Backend가
기계적으로 검증하고, 공개 Runtime 미승인 제품만 기존 State Machine의
`PRODUCT_VALIDATION_FAILED` 이벤트로 전환한다.

이번 변경은 Backend Mapper·Workflow 적용·테스트만 다룬다. `ai/**`,
`contracts/**`, Migration, DB Schema, Web, Mobile은 수정하지 않았다.

## 2. 적용 조건

다음 조건이 모두 참일 때만 `PRODUCT_VALIDATION_FAILED` 후보를 만든다.

1. 응답 `status=FALLBACK`
2. 응답 `fallback_reason_code=RUNTIME_PRODUCT_NOT_APPROVED`
3. 응답 `model_code`가 요청 `model_code`와 정확히 일치
4. 요청 `model_code`는 소유권이 확인된 Subscription의 ProductModel에서 생성
5. 응답 Evidence가 비어 있음
6. `requires_consultation=true`
7. 일반·주의 응답은 `PENDING_CONSULTATION`
8. 위험 응답은 기존 안전 규칙대로 `TOTAL_STOP`

`failure_stage`는 감사 정보로만 저장하며 제품 미승인 판정에는 사용하지 않는다.

## 3. 판정표

| AI 응답 | Backend 판정 | 상태 이벤트 |
| --- | --- | --- |
| `FALLBACK/RUNTIME_PRODUCT_NOT_APPROVED` + 제품 Echo 일치 | 제품 Runtime 미승인 | `PRODUCT_VALIDATION_FAILED` |
| `FALLBACK/NO_EVIDENCE` | 공식 근거 없음 | `NO_EVIDENCE` |
| `FALLBACK/MCP_TOOL_FAILURE` 등 | 자동 상태 전이 금지, 고객 안내 비공개 | 없음 |
| 응답·요청 `model_code` 불일치 | 식별자 계약 오류 | 없음 |
| `SUCCEEDED` + 안전·Evidence 조건 충족 | 기존 안전 안내 흐름 | 기존 이벤트 유지 |

계약 3.0에는 `fallback_reason_code`가 없으므로 기존 No-Evidence 판정만 호환
유지한다. 계약 4.0이 병합된 뒤에는 사유 코드만 판정 기준으로 사용한다.

## 4. 상태·DB 처리

정상 제품 미승인 응답은 다음과 같이 처리된다.

```text
QUESTIONNAIRE_IN_PROGRESS(v2)
-- PRODUCT_VALIDATION_FAILED / SYSTEM -->
CONSULTATION_REQUIRED(v3)
```

- `AIRun`: HTTP·Schema 처리는 성공했으므로 `SUCCEEDED`로 보존
- `validated_output_payload`: `model_code`, `fallback_reason_code` 포함
- `Inquiry.requires_fallback`: `true`
- `TransitionHistory.changed_by_type_code`: `SYSTEM`
- History actor: `null`
- History Correlation·Idempotency: AI 요청 값과 동일
- 일반·주의: `caution/PENDING_CONSULTATION`
- 등록된 누수 위험: `danger/TOTAL_STOP`
- 고객 Guidance 조회: Fallback 결과이므로 기존 409 Fail-closed 유지

제품 미승인 누수는 상태 전이 사유를 `PRODUCT_VALIDATION_FAILED`로 기록하되,
안전 Projection의 `danger/TOTAL_STOP`은 낮추지 않는다.

## 5. Replay

동일 AIRun 입력의 Replay는 기존 저장 결과만 재사용한다.

- 추가 AI HTTP 호출: 0회
- AIRun 추가 생성: 0건
- SymptomAssessment 추가 생성: 0건
- Guidance 추가 생성: 0건
- TransitionHistory 추가 생성: 0건
- 이미 상태 버전이 증가한 경우: `STALE_STATE_VERSION`

## 6. 변경 파일

| 파일 | 변경 내용 |
| --- | --- |
| `backend/integrations/ai/response_mapper.py` | 계약 4.0 식별자·사유 판정과 이벤트 후보 |
| `backend/apps/inquiries/services/inquiry_ai_service.py` | Fallback Projection·제품 검증 Guard 연결 |
| `backend/tests/unit/ai_integration/test_ai_adapter.py` | 제품 Echo·사유·Stage 비판정 검증 |
| `backend/tests/unit/ai_integration/test_inquiry_ai_service.py` | 상태·DB·History·Replay·위험 보존 검증 |
| `backend/tests/unit/evidence/test_ai_chunk_crosswalk.py` | 계약 4.0 Evidence 응답 제품 Echo 정합화 |
| `backend/tests/integration/test_ai_handoff_backend_web_bridge.py` | 계약 버전별 No-Evidence 응답 정합화 |
| `backend/tests/integration/test_backend_ai_submit_symptom_live_http.py` | 고정 버전 대신 실제 계약 버전 검증 |

## 7. 검증 결과

### 기준선 계약 3.0 호환

```text
AI·Evidence 표적: 62 passed, 1 skipped
Django check: 0 issues
Migration drift: No changes detected
Contract diff check: PASS
```

Skip 1건은 별도 AI Uvicorn이 필요한 실제 소켓 테스트다.

### 현재 jiyong 전체 Backend 회귀

```text
전체 Backend: 1405 passed, 38 skipped
실패: 0
```

Skip 38건은 PostgreSQL 전용 Constraint·Row Lock 검증, 실제 AI 소켓,
TEAM_INTEGRATION Role 검증처럼 별도 실행 환경을 명시적으로 요구하는 Gate다.
이번 전체 회귀에는 실제 팀 pgvector·OpenAI 공동 Runtime이 포함되지 않는다.

### 이동윤 계약 4.0 결합 검증

임시 Detached Worktree에서 `origin/dongyoon@17ac06f3` 위에 Backend 두 Commit을
적용했다.

```text
AI·Evidence 표적: 62 passed, 1 skipped
State Machine·Code Registry·OpenAPI·Example·Crosswalk: PASS
Root Contract tests: 38 passed
```

전체 결합 회귀의 최초 실행에서 계약 4.0 Evidence Echo 누락 2건을 발견했고
`5168436f`로 보강 후 해당 범위를 재검증했다. 별도 G2 Operation 수치 1건은
이동윤 브랜치가 최신 main의 동시 작업보다 뒤에 있어 발생한 기준선 차이이며,
최신 jiyong 작업트리의 해당 표적은 `11 passed`다. 그 G2 테스트 파일은
이번 상태 전이 구현 전부터 존재한 별도 변경이므로 이번 커밋에서 제외했다.

## 8. 아직 완료로 선언하지 않는 항목

- 실제 Django → FastAPI Local HTTP
- 실제 팀 pgvector·OpenAI 호출
- 팀 PostgreSQL AIRun·Assessment·Guidance·History 저장 대조
- 실제 Correlation ID의 Backend·AI·DB 3자 일치
- 실제 요청 Replay의 Vector·Provider 추가 호출 0회 대조
- 김은진 독립 QA
- Ruff 정적 검증(`backend` 가상환경에 Ruff 미설치)

따라서 이 문서는 작성자 코드 검증 근거이며 실제 3모델 Runtime PASS가 아니다.

## 9. 병합·후속 실행 순서

1. Backend 두 Commit을 먼저 main에 병합하거나 AI 계약과 같은 병합 묶음으로 처리
2. AI 계약 4.0만 단독으로 먼저 배포하지 않음
3. 최종 main SHA에서 신규 IAC425·IAC606 합성 Inquiry 생성
4. Django → FastAPI → PostgreSQL 실제 실행
5. `PRODUCT_VALIDATION_FAILED`, from/to/version/SYSTEM actor 확인
6. 일반·누수 Case의 Guidance 상태와 Fallback 비공개 확인
7. 같은 요청 Replay와 Correlation 대조
8. 김은진 독립 QA 후 Runtime 판정

이번 변경에는 `danger + PARTIAL_STOP` 정책 확대가 포함되지 않는다. 온수 전용
Safety Rule과 저장 정책은 별도 승인·구현 Gate로 유지한다.

## 10. 2026-08-22 격리 5 Case 준비·자체검증

- 기준 main: `762c77b7ffdd336a835d891bc71292edb0e8eff2`
- 추가 구현: `create_product_expansion_e2e_fixture --scenario-id`
- 허용 Scenario: `SYN-IAC425-101`, `SYN-IAC425-108`,
  `SYN-IAC606-101`, `SYN-IAC606-107`
- `data/**`는 읽기만 했으며 AI·계약·Migration·Schema는 변경하지 않았다.

| Case | inquiry_id | correlation_id |
| --- | --- | --- |
| JAC104 정상 | `bd867f55-77eb-4021-8142-7c320a61600c` | `c5697304-45fc-5827-9b15-892fb81833f0` |
| IAC425 일반 | `6379e955-1ecc-4c11-b477-df0853b068d3` | `627c0782-3f69-5585-913e-ac826add4830` |
| IAC425 누수 | `bf4d2e3d-fbcc-47b0-b4c9-935170a820c3` | `090631a0-ce36-53f6-bcbe-225757516155` |
| IAC606 일반 | `98a02472-a9ae-4de3-868c-93c1ab308946` | `f2d2b039-f5c8-5d22-9d28-f78ca3ff23b5` |
| IAC606 누수 | `03b58849-3af9-4ebd-8d94-2bc5f718d216` | `bc281130-4238-5604-97de-10644e90a54d` |

모든 Case는 `DRAFT/state_version=1`이며 최초 생성 `created=true`, 동일 실행
Replay `created=false`로 중복 Inquiry가 생기지 않았다. 일반은
`caution/PENDING_CONSULTATION`, 누수는 `danger/TOTAL_STOP`, 미승인 제품 기대값은
`RUNTIME_PRODUCT_NOT_APPROVED`와 Vector·Provider 호출 0회로 고정했다.

격리 PostgreSQL은 `16.14`, pgvector는 `0.8.6`, DB는
`waterbridge_team_integration`이다. 승인 Migration `90/90`을 적용했고
`visits.0005=NOT_APPLIED_P1_HOLD`, 예상 밖 Migration 0건을 확인했다.

Context 실제 HTTP 결과는 5건 모두 `200`이며 모델·증상·Correlation이 일치했다.
실패 경계는 Token 누락·오류 `403`, 없는 Inquiry `404`, 잘못된 Query·Correlation
누락 `422`였다. 조회 전후 `Inquiry=11`, `TransitionHistory=5`,
`IdempotencyRecord=5`, `AIRun=0`으로 DB 변경은 0건이고 PII Key도 노출되지 않았다.

표적 `22 passed`, 관련 회귀 `72 passed`, Django check 0건, Migration drift 없음,
`git diff --check` PASS다. three-model Readiness는 Crosswalk·View 데이터 0/53이므로
의도대로 `BLOCKED`다. Evidence Import와 실제 MCP·pgvector 검색·Provider 호출은
실행하지 않았으며 해당 구간을 PASS로 확대하지 않는다. 임시 Backend는 종료했고
보호 Token은 폐기했으며, 격리 PostgreSQL만 후속 공동 실행을 위해 유지한다.
