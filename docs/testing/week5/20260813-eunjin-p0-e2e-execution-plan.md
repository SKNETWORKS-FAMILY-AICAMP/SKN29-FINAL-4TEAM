# 2026-08-13 김은진 P0 E2E 당일 실행 계획서

> 담당: 김은진 — 데이터·QA·DevOps / 통합 검증 환경과 E2E Gate
> 실행 기준 Commit: `1289d4b3673d9b061833fa94d45096bde1541a02`
> 실행 ID: `W5-P0-CONSULTATION-20260813-001`
> 문서 상태: `IN_PROGRESS`
> 비밀정보 정책: Token, Password, DSN 원문, 실제 개인정보와 고객 원문 전체를 기록하지 않는다.

## 1. 오늘의 목표와 판정 범위

오늘 목표는 새로운 기능을 늘리는 것이 아니라 현재 Baseline을 사용해 다음 무방문 P0 흐름을 같은 Commit·Backend·AI·PostgreSQL에서 최대한 닫는 것이다.

```text
고객 Mobile
→ 문의 생성·증상 제출
→ Backend 저장
→ 실제 AI local Baseline·pgvector 검색
→ AI 결과와 근거 저장
→ 고객 안내 확인
→ 상담 요청
→ 상담사 Web에서 같은 문의 확인·처리
→ 고객이 최신 상태 확인
```

이번 P0에서는 방문기사 흐름을 제외한다. 기존 `SYN-JAC104-002` 대표 Fixture는 방문·기사·고객 해결 피드백·최종 완료까지 포함하므로 오늘 실행 ID로 사용하지 않는다. 제품 `WPUJAC104DWH`, 출수량 저하 증상과 승인된 공식 근거만 입력 기준으로 재사용한다.

상담사가 상담을 완료한 직후의 현재 계약상 종점은 `COMPLETION_PENDING`이다. 고객 해결 피드백과 마지막 담당자의 `FINALIZE_INQUIRY` Runtime이 없는 상태에서 `RESOLVED` 또는 전체 E2E `PASS`로 표현하지 않는다.

## 2. 오늘 이미 수행한 준비와 결과

| 항목 | 실행 결과 | 판정 |
|---|---|---|
| Git 기준 고정 | `eunjin@1289d4b3673d9b061833fa94d45096bde1541a02`, 시작 작업 트리 Clean | `PASS` |
| Backend 환경 Gate | Python `3.13.13`, pip `26.0.1`, 고정 패키지 32개, fingerprint 일치, `pip check`, Django system check | `PASS` |
| AI 환경 | Python `3.13.13`, `pip check` 이상 없음 | `PASS` |
| 독립 PostgreSQL | Container `watercare-e2e-1289d4b6`, DB `watercare_test_e2e_1289d4b6`, `127.0.0.1:55432`, PostgreSQL `16.14`, UTC, 전용 Volume | `PASS` |
| Django Migration | 전체 Plan 검토 후 전용 QA DB에 적용, `migrate --check`, Migration drift 없음 | `PASS` |
| pgvector Schema | Disposable Guard를 사용해 전용 QA DB에 `ai_rag_chunks` 초기화 | `PASS` |
| 실제 Baseline Index | 고정 bge-m3 Revision `5617a9f61b028005a4858fdac845db406aefb181`, 1024차원, 승인 청크 7개 적재 | `PASS` |
| 청크 결정성 | `chunk_set_sha256=175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958` | `PASS` |
| Backend→AI local 실제 HTTP | 아직 실행 증거 없음 | `NOT_RUN` |
| Web Lint | `npm run lint`, ESLint 오류 없음 | `PASS` |
| Web Test 1차 | 기본 병렬 실행에서 18 files·48 assertions 통과 후 Vitest fork worker 응답 시간초과 15건, 명령 종료 코드 1 | `HARNESS_ENVIRONMENT_FAILED` |
| Web Test 재실행 | `npm run test -- --maxWorkers=1 --no-file-parallelism`, 33 files·144 tests·오류 0 | `PASS` |
| Web Build | `npm run build`, TypeScript·Vite production build, 142 modules 변환 | `PASS` |
| Mobile Build·실기기 | Android SDK·ADB·`local.properties` 없음 | `ENVIRONMENT_BLOCKED` |

위 PASS는 해당 행의 좁은 범위만 의미한다. PostgreSQL과 pgvector 준비가 끝났다는 사실을 고객→AI→상담사 E2E PASS로 확대하지 않는다.

## 3. 오늘 시간표와 Cut-off

기준 시각은 2026-08-13 11:35 KST다. 한 구간이 막혀도 다른 준비를 병렬로 진행하되, 아래 Cut-off 뒤에는 기다리는 대신 증거와 담당자를 고정한다.

| 목표 시각 | 작업 | 종료 조건 | 지연 시 조치 |
|---|---|---|---|
| 12:30 | Phase A 실제 AI local·pgvector Smoke | Local Analyze 200과 공식 Evidence 확인 | AI Blocker 발행, Backend Mock 결과로 대체 금지 |
| 14:00 | Phase B Backend→AI local→PostgreSQL | 실제 Route·저장·Correlation·Replay 증거 | 첫 실패 경계로 Backend/AI 인계 |
| 14:30 | P0 Blocker 담당자 전달 | 재현법·기대·실제·해제 조건 전달 완료 | PM에게 범위 결정 요청 |
| 17:00 | 담당자 수정 수신·표적 재검증 | Blocker 001·002 해제 여부 판정 | 미해제 항목은 당일 `PARTIAL` 후보로 고정 |
| 19:00 | Web Remote·Mobile 가능한 구간 연결 | 같은 Inquiry를 양쪽 소비자가 확인 | Mobile 환경 미확보 시 팀 실기기 증거 요청 |
| 20:00 | Happy Path 재시도 | `COMPLETION_PENDING`까지 실제 흐름 | 실패 경계 이후 비정상·전화 Smoke 보류 |
| 21:00 | 최소 비정상·전화 문의 Smoke | 멱등·409·AI 실패·전화 문의 결과 | Happy Path 미완료 시 핵심 원인만 재검증 |
| 22:00 | 종료 감사·PM 보고 | 종료 SHA, 작업 트리, 산출물, Container 정리 | 미실행을 PASS로 올리지 않고 다음 날 첫 순서 지정 |

오늘 안에 완료하기 위한 의사결정 원칙은 다음과 같다.

1. 14:30까지 실제 재현 없이 정적 추정만 전달하지 않는다. 실행이 환경상 불가능하면 `ENVIRONMENT_BLOCKED` 증거를 전달한다.
2. 17:00 이후 새 기능을 추가하지 않는다. 받은 수정의 실패 구간만 재검증한다.
3. 20:00까지 Happy Path가 닫히지 않으면 예외 Case 수를 늘리지 않는다.
4. `PARTIAL`은 실패가 아니라 당일 실제 도달 범위를 정확히 고정한 결과다. Mock·Fixture로 빈 구간을 메우지 않는다.
5. PM이 `RESOLVED`까지를 오늘 P0로 요구하면 Blocker 004가 별도 구현 Task가 되며, 기존 일정과 동시에 달성 가능하다고 가정하지 않는다.

## 4. 오늘의 실행 순서

### Phase A — 실제 AI local 수직 Gate

목표는 Mock이 아니라 현재 Baseline인 규칙·템플릿 생성과 실제 bge-m3·pgvector 검색을 검증하는 것이다.

1. AI Process에 다음 값만 안전하게 주입한다.
   - `AI_VECTOR_DSN`: 전용 QA DB DSN, 출력·문서화 금지
   - `AI_EMBEDDING_REVISION=5617a9f61b028005a4858fdac845db406aefb181`
2. AI를 `127.0.0.1:8001`에서 실행한다.
3. Health는 Liveness로만 기록한다.
4. `mode=local` 분석 요청으로 실제 검색을 실행한다.
5. 응답 Header와 Body의 `correlation_id`, `ai_request_id`, `state_version`을 확인한다.
6. 제품·세대 Filter, 공식 검증 근거 Hit, 검색 점수와 허용 범위를 확인한다.

```powershell
# 첫 터미널 — 비밀 DSN은 승인된 Process 환경으로만 주입
$env:AI_VECTOR_DSN = '<redacted-disposable-dsn>'
$env:AI_EMBEDDING_REVISION = '5617a9f61b028005a4858fdac845db406aefb181'
.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app `
  --host 127.0.0.1 --port 8001

# 둘째 터미널 — 실제 pgvector 행·차원·제품 Filter·공식 근거 검색
.\ai\.venv\Scripts\python.exe -m pytest `
  ai\tests\integration\test_pgvector_runtime.py `
  -q -p no:cacheprovider

# 실행 중인 AI local HTTP의 Schema·Trace Smoke
.\ai\.venv\Scripts\python.exe -m ai.scripts.smoke_test `
  --base-url http://127.0.0.1:8001 `
  --mode local `
  --expected-analysis-status 200
```

통과 증거:

- AI Health 200
- Local Analyze 200
- Mock Fallback 없음
- 공식 승인 Evidence 최소 1건
- 같은 Correlation Trace
- pgvector 검색 오류 0

### Phase B — Backend→AI local→PostgreSQL 저장 Gate

현재 저장소의 `test_backend_ai_submit_symptom_live_http.py`는 실제 Socket을 사용하지만 AI Mode를 `mock`으로 강제한다. 이 결과를 actual-local PASS로 사용하지 않는다.

1. Backend를 전용 QA PostgreSQL과 `AI_SERVICE_MODE=local`로 실행한다.
2. Demo 고객과 합성 제품·구독만 Seed한다.
3. API로 문의를 생성하고 증상을 제출한다.
4. 제출 전후 DB Count를 비교한다.
5. 같은 `correlation_id`로 Inquiry, AIRun, TransitionHistory와 구조화 로그를 연결한다.
6. 직접 DB 수정 없이 Runtime만 사용한다.

필수 DB Delta:

| 대상 | 기대 Delta |
|---|---:|
| Inquiry | `+1` |
| AIRun | `+1`, `SUCCEEDED`, Schema `PASSED` |
| SymptomAssessment | `+1` |
| Guidance | `+1` |
| Evidence Link 또는 검증 근거 | 실제 AI 응답과 일치 |
| TransitionHistory | 제출·AI Event별 기대 증가 |
| IdempotencyRecord | Operation별 `+1`, Replay 시 추가 없음 |

통과 증거:

- Backend 실제 HTTP Route 사용
- AI `mode=local`
- PostgreSQL 사용
- Header·metadata·AIRun·History의 Correlation 일치
- AI 응답 저장 완료
- Replay 시 AIRun·Assessment·Guidance 중복 0
- 실패 시 부분 기록 0

### Phase C — 현재 첫 Blocker 재현과 담당자 수정 요청

정적 검토에서 아래 E2E Blocker가 확인됐다. 실제 실행에서 동일 경계가 재현되면 즉시 담당자에게 전달한다.

#### `W5-P0-BLOCKER-001` — Backend Evidence Verifier 미주입

- 구간: 실제 AI local 결과 → Backend `SAFE_GUIDANCE_READY`
- 예상 실제 결과: 공식 Evidence가 있어도 검증된 Evidence ID가 비어 상태 전이가 보류됨
- 대상: `backend/apps/inquiries/services/inquiry_transition_service.py`, `backend/apps/inquiries/services/followup_answer_service.py`, `backend/apps/inquiries/services/inquiry_ai_service.py`
- 담당: 최지용·이동윤 협의
- 해제 조건:
  - Production 호출점에 canonical Evidence Verifier 주입
  - 공식 `chunk_id`만 검증·저장
  - 미검증 근거는 fail-closed
  - 실제 PostgreSQL+local AI 표적 Test PASS
- 김은진 조치: 코드 수정 없이 재현 명령·기대·실제·핵심 로그와 DB Delta 전달 후 수정 Commit 재검증

#### `W5-P0-BLOCKER-002` — Mobile Guidance·상담 요청 경로 미구현

- 구간: AI 결과 저장 → 고객 Guidance 확인 → `REQUEST_CONSULTATION`
- 확인된 상태:
  - Mobile Remote Repository가 Guidance를 `GUIDANCE_ROUTE_UNAVAILABLE`로 차단
  - `WaterCareApi`에 Guidance·상담 요청 공개 호출이 없음
- 담당: Backend 최지용, Mobile 양정현
- 해제 조건:
  - Backend 고객 공개 Guidance DTO·Route 확정
  - 내부 Evidence 원문·점수·경로를 노출하지 않는 응답
  - Mobile Remote Repository·API·UI 연결
  - 실제 Backend 대상 실기기 Remote Smoke
- 김은진 조치: 계약·응답·실기기 증거 검증, 제품 코드 직접 수정 금지

#### `W5-P0-BLOCKER-003` — Mobile 실행 환경 없음

- 분류: `ENVIRONMENT_BLOCKED`
- 현재 환경: Android SDK·ADB·`local.properties` 없음, Java `26.0.1`, 프로젝트 Target Java 17
- 담당: 양정현 실행 지원 또는 Android SDK가 준비된 팀 환경
- 해제 조건:
  - 검증된 JDK·Android SDK·ADB
  - 정확한 Remote Smoke 명령과 대상 기기
  - 같은 Backend 주소 사용 확인
- 주의: 승인되지 않은 SDK 자동 다운로드를 CI나 로컬에 추가하지 않는다.

#### `W5-P0-BLOCKER-004` — 최종 `RESOLVED` Runtime 없음

- 구간: `COMPLETION_PENDING` → 고객 해결 피드백 → 마지막 담당자 Finalize → `RESOLVED`
- 현재 상태: `SUBMIT_RESOLUTION_FEEDBACK`, `FINALIZE_INQUIRY`는 계약에 있으나 Runtime 없음
- 담당: 최지용·양정현, PM 범위 결정
- 해제 조건: Runtime·Migration 필요 여부·테스트·Mobile 소비와 실제 E2E 증거
- 오늘 판정: 상담 완료 후 고객 최신 상태 `COMPLETION_PENDING` 확인까지만 P0 후보로 인정

#### `W5-P1-HARNESS-001` — 기존 AI Demo Smoke의 UUID 불일치

- 대상: `scripts/demo/verify_ai_runtime.ps1`
- 확인된 결함: AI 요청 계약은 `correlation_id`를 UUID로 요구하지만 스크립트는 `demo-mock-001`, `demo-danger-001`, `demo-local-rag-001` 문자열을 전송한다.
- 영향: 현재 계약에서 요청 검증 422가 예상되므로 actual-local Gate 명령으로 사용할 수 없다.
- 임시 대체: 유효 UUID를 사용하는 `ai.scripts.smoke_test`와 `test_pgvector_runtime.py`를 조합한다.
- 담당: 이동윤 또는 해당 Demo Script 주관자
- 김은진 조치: 관할 밖 `scripts/demo/**`를 직접 수정하지 않고 재현 증거를 인계한다.

### Phase D — API/Web/Mobile 수직 연결

Blocker 수정 Commit이 올라오면 전체 테스트를 처음부터 반복하지 않고 실패한 경계부터 재검증한다.

1. Mobile 가능한 앞 구간: 로그인 → 제품 조회 → 문의 생성 → 증상·추가 답변
2. Backend·AI: actual-local 처리 → Guidance 저장 → 상담 요청 상태 전이
3. Web Remote: 같은 Inquiry 목록·상세 → 상담 시작 → 상담 내용 저장 → 요약 확정 → 상담 완료
4. Mobile: 같은 Inquiry Snapshot 재조회 → `COMPLETION_PENDING` 확인

Web은 `VITE_USE_MOCK_API=false` 또는 동등한 Remote 설정을 증거에 명시한다. Fake·Fixture 화면은 실제 E2E 화면 증거로 사용하지 않는다. 기본 병렬 Test는 Vitest Worker 시작 오류로 실패했으나 `npm run test -- --maxWorkers=1 --no-file-parallelism` 재실행에서 33 files·144 tests가 모두 통과했다. 이는 Web 코드 Gate 증거이며 실제 Remote Browser E2E를 대신하지 않는다.

### Phase E — 정상 흐름 후 최소 비정상·전화 문의 Smoke

Happy Path 후보가 먼저 닫힌 뒤 다음만 확인한다.

1. 동일 `Idempotency-Key` Replay: 중복 Inquiry·AIRun·Guidance 0
2. 오래된 `state_version`: HTTP 409, 최신 State·Version·`allowed_actions` 반환
3. AI 503: 서비스 전체 중단과 부분 저장 없음
4. 전화 문의: 상담사 고객 조회 → 전화 문의 등록 → 같은 Inquiry Workflow 진입 → DB 저장

성능·대량 안전 실험, 모델·청킹·Retriever 비교, 방문기사 E2E는 오늘 실행하지 않는다.

## 5. 역할별 당일 인계

| 우선순위 | 담당 | 오늘 필요한 작업 | 김은진 재검증 |
|---|---|---|---|
| P0 | 최지용 | Evidence Verifier Production 연결, 고객 Guidance Route·DTO 확인 | actual-local→DB→State 전이 |
| P0 | 이동윤 | `ai_rag_chunks` 사용 정책 확인, local 검색 응답·공식 Evidence 정합성 확인 | pgvector·Schema·Trace |
| P0 | 양정현 | Guidance·상담 요청 Mobile Remote 소비, SDK 환경에서 실기기 Smoke | 같은 Backend·Inquiry 증거 |
| P0 | 한예나 | Web Remote 모드에서 같은 Inquiry 상담 처리 | Browser/API/DB 상태 연결 |
| P0 | 윤승혁 | 오늘 P0 종점을 `COMPLETION_PENDING`으로 둘지, Finalize Runtime을 추가할지 결정 | 판정 범위 고정 |
| P1 | 최지용·한예나 | 전화 문의 최소 Smoke 지원 | 기존 Inquiry Workflow 진입 확인 |

## 6. 실행 기록 형식

```text
run_id=W5-P0-CONSULTATION-20260813-001
baseline_commit=<40자리 SHA>
started_at=<KST>
finished_at=<KST>
tree_clean_start=true|false
tree_clean_end=true|false

environment:
  backend=<address, local>
  ai=<address, local|mock>
  database=<DB name, PostgreSQL version, pgvector version; secret 제외>
  web=REMOTE|MOCK
  mobile=REMOTE|FAKE|ENVIRONMENT_BLOCKED
  llm=NOT_IMPLEMENTED|<provider/model>
  embedding_revision=<revision>

scenario:
  product=WPUJAC104DWH
  symptom=출수량 저하
  inquiry_id=<public UUID>
  mock_fallback=NONE
  direct_db_mutation=NONE

steps:
  <Actor / Operation / HTTP / 이전·이후 State·Version /
   allowed_actions / correlation_id / DB Delta / 화면 증거 / 결과>

result=PASS | PARTIAL | FAIL | ENVIRONMENT_BLOCKED | INTEGRATION_BLOCKED
first_failed_boundary=<NONE 또는 구간>
blocker=<NONE 또는 ID>
owner=<담당자>
```

## 7. 종료 판정

### `PASS`

- 같은 Commit·Backend·AI local·PostgreSQL을 사용한다.
- Mobile 실제 Remote에서 문의가 생성된다.
- 실제 pgvector 근거를 사용한 AI 결과가 저장된다.
- 고객 Guidance와 상담 요청이 실제 Mobile에 연결된다.
- 상담사 Web 실제 Remote에서 같은 Inquiry를 처리한다.
- 고객이 최신 `COMPLETION_PENDING` 상태를 확인한다.
- Mock Fallback과 직접 DB 수정이 없다.
- Correlation·DB Delta·화면 증거가 모두 연결된다.

### `PARTIAL`

- 일부 실제 Runtime 구간은 통과했지만 전체 고객→AI→상담사 흐름이 이어지지 않는다.
- 최초 실패 경계, 담당자, 수정 Commit과 재검증 상태를 반드시 기록한다.

### `ENVIRONMENT_BLOCKED`

- 코드 실행 전에 SDK·DB·Secret·접속 환경이 없어 실행하지 못했다.
- 단위·Mock PASS로 대체하지 않는다.

### `INTEGRATION_BLOCKED`

- 각 서비스는 실행되지만 Route·DTO·State·Evidence 검증 또는 소비자 연결이 없어 다음 구간으로 진행하지 못했다.

## 8. 오늘 종료 전 정리

- 시작·종료 전체 SHA가 같은지 확인한다.
- 작업 트리와 관련 Diff를 확인한다.
- 임시 QA 모듈을 만들었다면 제거한다.
- 자동 생성 Test DB가 제거됐는지 확인한다.
- 직접 시작한 PostgreSQL Container는 중지하고 전용 Volume은 보존한다.
- 실패 시 DB와 로그를 임의 복원·삭제하지 않는다.
- PM에게 다음 다섯 항목만 보고한다.
  1. E2E `PASS / PARTIAL / FAIL`
  2. 실제로 성공한 시작·종료 구간
  3. 기준 Commit SHA
  4. 남은 Blocker와 담당자
  5. E2E 뒤 Backlog

## 9. E2E 이후 Backlog

- 고객 해결 피드백·`FINALIZE_INQUIRY` Runtime
- 실제 LLM Provider가 필요할 경우 Client·Routing·Structured Output 구현
- `knowledge_*` Django Schema와 AI `ai_rag_chunks`의 장기 Adapter·운영 정책
- 공용 AWS 테스트 주소와 팀 공용 Secret 전달 방식
- Backend·AI·Web을 포함한 통합 Compose 또는 배포 자동화
- 모델·임베딩·청킹·Retriever 비교 실험
- 방문기사와 Supervisor 흐름
