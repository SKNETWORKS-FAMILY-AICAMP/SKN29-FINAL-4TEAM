# Customer Guidance Backend·AI 연결 E2E 준비 구현·검증 보고서

## 0. 문서 정보

| 항목 | 내용 |
| --- | --- |
| 작성일 | 2026-08-14 KST |
| 담당 | 최지용 — Backend·DB |
| 착수 기준 | `main@11d771ab71aa8adc01a72af45dfe9eff280c219e` |
| 작업 범위 | 고객 Guidance 조회 출구, G1-B READY 오판 방지, 실제 소켓 회귀 |
| 현재 판정 | `BACKEND_CODE_READY / TEAM_INTEGRATION_BLOCKED / ACTUAL_LLM_NOT_RUN` |

## 1. 결론

AI 담당자의 실제 분석 결과가 기존 `AIRun → Guidance` 저장 경로에 기록되고
Backend 안전 Event가 고객 공개 상태로 전환한 뒤, 고객 앱이 본인 문의의
Guidance를 조회할 수 있도록 마지막 공개 조회 경로를 구현했다.

이번 작업은 Web·Mobile·AI 코드를 변경하지 않았고 DB Model·Migration도
추가하지 않았다. Public Evidence는 P0 범위 밖이므로 빈 배열만 반환하며,
내부 Chunk·Score·Prompt·경로·AI Trace를 노출하지 않는다.

로컬 AI Mock 실제 소켓 검증은 통과했다. 다만 현재 최지용 PC의 DB는 팀 통합
DB가 아니고 Canonical Evidence가 없어 실제 LLM E2E를 시작할 수 없다.

## 2. 해결한 연결 공백

기존 흐름에는 다음이 이미 있었다.

```text
고객 증상 제출
→ Backend가 AI Runtime 호출
→ AIRun·SymptomAssessment·Guidance·Evidence 저장
→ 최신 Inquiry 상태·allowed_actions 저장
```

하지만 Mobile이 실제 Guidance를 읽는 고객 공개 Endpoint가 없었다. 따라서
AI가 정상 동작해도 앱은 `GUIDANCE_ROUTE_UNAVAILABLE`로 실패할 수밖에 없었다.

추가한 흐름은 다음과 같다.

```text
GET /api/v1/me/inquiries/{inquiry_id}/guidance
→ 고객 본인 소유권 확인
→ SUCCEEDED 또는 NO_EVIDENCE AIRun 확인
→ Schema PASSED 및 validated payload 확인
→ AI_GUIDANCE 이후의 고객 공개 상태인지 확인
→ 고객 공개 Projection 반환
→ 임시 Guidance·근거 검증 실패·비정상 Payload는 409로 Fail-closed
```

## 3. 공개 API 계약

### 3.1 성공

- Method·Path: `GET /api/v1/me/inquiries/{inquiry_id}/guidance`
- 권한: `CUSTOMER + OWN_INQUIRY`
- 성공: `200`
- 공개 항목:
  - Inquiry UUID·표시 코드·현재 상태·`state_version`
  - 증상 요약·위험도·사용 안내 상태와 메시지
  - 제한 기능·안전 행동·다음 행동·상담 필요 여부
  - 현재 Backend Resolver의 `allowed_actions`
  - `evidence=[]`

### 3.2 오류와 은닉

| 조건 | 결과 |
| --- | --- |
| 미인증 | `401` |
| CUSTOMER가 아닌 역할 | `403` |
| 없는 문의·타 고객 문의·잘못된 UUID | 동일 `404 RESOURCE_NOT_FOUND` |
| Guidance 미생성·AI 실패·Schema 실패·비정상 Payload | `409 AI_GUIDANCE_NOT_READY` |
| 알 수 없는 Query | `422 VALIDATION_ERROR` |

`409`의 details에는 최신 `inquiry_id`, `current_status`,
`current_state_version`,
`allowed_actions`만 제공한다. Client가 상태나 Action을 추론하지 않도록 한다.

## 4. 안전 경계

- AI Run은 `ANALYZE_SYMPTOM` 또는 `GENERATE_GUIDANCE`만 허용한다.
- AI 상태는 `SUCCEEDED` 또는 `NO_EVIDENCE`만 허용한다.
- Schema 상태는 반드시 `PASSED`여야 한다.
- `DRAFT`, `QUESTIONNAIRE_IN_PROGRESS`, `REOPENED`, `CANCELLED`의
  임시·과거 Guidance는 공개하지 않는다.
- Evidence 검증 실패로 안전 Event가 적용되지 않은 Guidance는 공개하지 않는다.
- `PARTIAL_EVIDENCE` 또는 정상 AI Run에서 `requires_fallback=true`인 결과는
  공개 상태여도 `409`로 차단한다.
- `NO_EVIDENCE`는 AI Run 상태, `requires_fallback=true`, Evidence Mode,
  상담 필요, `PENDING_CONSULTATION`이 모두 일치할 때만 공개한다.
- `danger`는 `TOTAL_STOP`, 상담 필수, 활성 Canonical Safety Rule ID가 모두
  일치할 때만 공개한다.
- 문자열 배열은 타입·빈 값·최대 개수를 검증한다.
- Raw AI payload, Prompt, Model config, Correlation 내부값을 반환하지 않는다.
- Evidence Reference, Chunk ID, Similarity Score를 반환하지 않는다.
- Public Evidence UI를 이번 작업으로 완료 처리하지 않는다.
- 조회 API는 상태·버전·Guidance·AIRun을 변경하지 않는다.

## 5. G1-B READY 오판 방지

읽기 전용 감사 도구가 Evidence Migration `0009`, `0010`만 검사하던 공백을
보완해 다음 세 개가 모두 적용되어야 READY가 되도록 했다.

1. `0009_ai_chunk_crosswalk`
2. `0010_backend_ai_rag_chunks_view`
3. `0011_cast_chunk_embedding_vector_dimensions`

`0011`이 빠지면 다음 Blocker로 중단한다.

```text
MIGRATION_MISSING:0011_cast_chunk_embedding_vector_dimensions
```

## 6. 작성자 검증 결과

| 검증 | 결과 |
| --- | --- |
| Guidance·OpenAPI·오류 Registry·G1-B Audit 표적 | `76 passed, 1 skipped` |
| Backend 전체 회귀 | `1211 passed, 30 skipped` |
| 실제 AI Mock 소켓: Submit→임시 저장→Guidance 409→Replay | `1 passed` |
| Django System Check | `0 issue` |
| Model Migration drift | `No changes detected` |
| Python AST·YAML Parse | `PASS` |
| `git diff --check` | `PASS` |

30개 Skip은 PostgreSQL 전용 Assertion·Row Lock·Role 검증과 opt-in 실제
소켓 항목이다.
실제 소켓 테스트는 AI Mock을 별도로 기동해 실행했다. Canonical Evidence가
없는 Mock 결과가 임시 Guidance로 저장되더라도 고객 조회가 `409`로
Fail-closed 되는지와 Replay 중복 방지를 확인했고, 테스트 후 8001 프로세스를
종료했다. 별도 API 테스트에서는 공개 상태의 정상·NO_EVIDENCE·Danger Guidance
`200`, 내부 Evidence 비노출, `PARTIAL_EVIDENCE`·불일치 NO_EVIDENCE·유효하지
않은 Danger Rule의 `409` 차단을 확인했다.

이 결과는 배선 검증이며 실제 `gpt-4.1-mini` G1-A PASS가 아니다.

## 7. 현재 로컬 환경 판정

다음 명령을 읽기 전용으로 실행했다.

```powershell
backend\.venv\Scripts\python.exe `
  scripts\database\audit_backend_ai_g1b_readiness.py `
  --require-ready --require-team-database
```

현재 결과는 `BLOCKED`다.

| 항목 | 현재 값 |
| --- | --- |
| 연결 DB | 로컬 `waterbridge` — 팀 통합 DB 아님 |
| pgvector | `0.8.6` |
| 미적용 Evidence Migration | `0011` |
| Active Verified Crosswalk | `0/7` |
| Crosswalk Page Link | `0/8` |
| Readonly View | `0/7` |
| AI Readonly Role | View SELECT·기본 Read-only 미완료 |
| Backend 8000 / AI 8001 | 현재 미기동 |
| Galaxy Tab ADB Reverse 8000 | 준비됨 |

Backend `.env`의 값은 출력하지 않고 Key 존재 여부만 감사했다.

- 존재: `AI_SERVICE_BASE_URL`
- 명시 필요: `AI_SERVICE_MODE`, `AI_MODEL_PROVIDER`, `AI_MODEL_NAME`,
  `AI_PROMPT_VERSION`, PostgreSQL Timeout·SSL Key
- 경계 위반: Backend `.env`에 `OPENAI_API_KEY` Key가 존재한다. 실제 값은
  확인·기록하지 않았으며, Backend에서 제거하고 AI 전용 Process 환경으로만
  옮겨야 한다.

AI 작업이 다른 작업선에서 진행 중이므로 이번 작업에서 `.env`를 자동 수정하지
않았다. 실제 실행 전에 `backend/.env.example`의 공개 Key 목록을 기준으로
담당자들이 같은 실행값을 별도 보안 채널에서 맞춘다.

공식 PDF·Canonical Fixture·팀 통합 DB가 준비되지 않은 상태에서 기존 로컬
DB에 임의 Import하거나 이 결과를 G1-B PASS로 승격하면 안 된다.

## 8. AI 완료 직후 실행 순서

### 8.1 환경 Gate

1. 최종 동일 `main` 40자리 SHA를 Backend·AI·QA가 기록한다.
2. 김은진이 격리 `waterbridge_team_integration`과 실행 권한을 준비한다.
3. 공식 PDF와 AI Canonical Fixture를 안전한 Process 경로로 주입한다.
4. Import `Dry-run → Apply → Replay`를 실행한다.
5. Crosswalk `7/7`, Page Link `8/8`, View `7/7`, Role Matrix를 확인한다.
6. 위 감사 명령이 `READY` Exit `0`인지 확인한다.
7. 이동윤 AI `/health`가 `200`인지 확인한다.
8. Backend의 `AI_SERVICE_BASE_URL`이 그 Runtime을 가리키는지 확인한다.

Secret·DSN·Password·공식 PDF 실제 경로는 문서와 Git에 기록하지 않는다.

### 8.2 새 대표 Inquiry 실행

1. AI와 DB가 READY가 된 후 Mobile에서 **새 Inquiry**를 생성한다.
2. 새 Idempotency Key로 증상을 제출한다.
3. AIRun·Guidance·Evidence 저장과 동일 Correlation ID를 확인한다.
4. Snapshot이 실제 AI 결과에 따른 상태·버전을 반환하는지 확인한다.
5. 고객 Guidance GET `200`과 내부 Evidence 비노출을 확인한다.
6. 정확한 새 UUID로 합성 E2E 배정 Marker만 준비한다.

```powershell
backend\.venv\Scripts\python.exe backend\manage.py `
  prepare_synthetic_e2e_assignment `
  --inquiry-id <NEW_INQUIRY_UUID> --json
```

7. 양정현이 같은 Inquiry에서 `REQUEST_CONSULTATION`을 실행한다.
8. 같은 UUID·최신 상태·버전·Correlation을 한예나에게 인계한다.
9. 한예나가 Web에서 시작·저장·확정·완료·새로고침을 검증한다.
10. 양정현이 Mobile에서 최종 상태·버전을 재조회한다.

## 9. 반드시 새 Inquiry를 써야 하는 이유

AI가 꺼진 상태에서 증상을 제출하면 실패 AIRun이 저장될 수 있다. 같은 Submit
Idempotency Key를 재전송해도 저장된 응답만 Replay되며 AI를 다시 호출하지 않는다.

따라서 연결 완료 전 문의는 공식 E2E 증거로 재사용하지 않고, AI `/health`,
G1-B READY, Backend 설정이 모두 확인된 뒤 새 Inquiry와 새 Key로 시작한다.

## 10. 남은 담당자 입력

| 담당 | 필요한 입력 |
| --- | --- |
| 이동윤 — AI/RAG | 실제 AI Runtime, `/health 200`, Schema·pgvector·LLM 실행 증거 |
| 김은진 — Data·QA | 격리 통합 DB, 공식 원본, Import·Role·Audit `ENVIRONMENT_READY` |
| 양정현 — Mobile | Backend Route 병합 후 Guidance DTO/Remote 연결과 G2·G3 실행 |
| 한예나 — Web | 동일 main 동기화 후 같은 Inquiry의 G4 실행 |

## 11. 완료 경계

현재 완료된 것은 `BACKEND_CUSTOMER_GUIDANCE_CODE_READY`와
`MOCK_SOCKET_WIRING_PASS`다.

다음은 아직 완료가 아니다.

- 실제 LLM·팀 pgvector G1-A
- 실제 AIRun·Guidance·Evidence·Correlation G1-B
- Mobile Guidance 표시 G2
- Mobile 상담 요청 G3
- 동일 Inquiry Web 상담 G4
- Mobile 최종 재조회 G5
- 독립 QA 및 최종 E2E 판정
