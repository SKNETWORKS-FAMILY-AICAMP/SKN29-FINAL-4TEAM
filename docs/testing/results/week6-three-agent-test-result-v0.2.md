# 6주차 3-Agent 후보 Runtime 최종 main 실연결 테스트 결과 v0.2

> 검증일: 2026-08-18 KST  
> 실연결 기준 main Commit: `63103efe3248cf49579bb3c1fd163a19de37c6e8`  
> 후속 DB 비노출 보강 검증 HEAD: `31f73405568637ae545d7f38d635f7a920ec9510`  
> 후속 물맛 문진 Gate E2E 후보 HEAD: `d62a1fefe9a9d2bc570d1c81ae010120c645ad8f` (`UNCOMMITTED_WORKTREE`)
> Branch: `dongyoon`  
> 종합 판정: `ACTUAL_PROVIDER_AND_BACKEND_E2E_PASS / DEFAULT_SWITCH_NOT_APPROVED`

## 1. 판정 범위

- 기본 Runtime은 계속 `single_rag`다. 이번 PASS는 명시적으로 선택한 후보
  `multi_agent`의 실연결 검증이며 운영 기본값 전환 승인이 아니다.
- 보호 AI Role과 Runtime Role은 각 Process에만 주입했다. Secret, DSN, Password,
  승인 합성 입력, Prompt, Evidence 본문과 Vector는 결과·로그·Git에 기록하지 않았다.
- 사용자가 승인한 비개인 합성 입력으로 실제 OpenAI 호출을 수행했다. 이 승인은 해당
  검증 실행에 한정되며 공식 원문의 공개·재배포 승인을 의미하지 않는다.

## 2. 최종 main 사전 Gate

| 범위 | 결과 | 판정 |
|---|---:|---|
| AI Unit 전체 | `242 passed, 5 warnings, 7 subtests passed` | `PASS` |
| Root AI Contract·Safety | `27 passed` | `PASS` |
| Backend AI Adapter·State Event | `10 passed` | `PASS` |
| AI·Backend 의존성 | `pip check` 오류 없음 | `PASS` |
| Migration Plan | 적용 예정 작업 0건 | `PASS` |
| Django Check·Migration Drift | 0 issues·변경 없음 | `PASS` |
| Crosswalk·Readonly View | `7/7`, View 7행·고유 ID 7개 | `PASS` |
| 실제 Readonly pgvector | 권한·`7×1024` Shape·검색 | `PASS` |

Python은 `3.13.13`, PostgreSQL은 `16.15`, pgvector는 `0.8.6`에서 확인했다.

## 3. 실제 OpenAI Single RAG·Multi-Agent 비교

두 Runtime에 동일한 승인 합성 입력과 동일 Trace Identity를 사용했다. 각 Runtime은
실제 Readonly pgvector 검색과 OpenAI Provider 호출을 1회 수행했다.

| 지표 | Single RAG | Multi-Agent |
|---|---:|---:|
| 상태 | `SUCCEEDED` | `SUCCEEDED` |
| 실제 모델 | `gpt-4.1-mini-2025-04-14` | `gpt-4.1-mini-2025-04-14` |
| Prompt Version | `customer_guidance/v2` | `customer_guidance/v2` |
| Latency | `4090.477 ms` | `2066.466 ms` |
| Token | `1150` | `1150` |
| Risk / Guidance | `caution / PARTIAL_STOP` | `caution / PARTIAL_STOP` |
| Evidence 건수 | `5` | `5` |
| Follow-up 질문 | `0` | `0` |

- 공개 결과 SHA는 양쪽 모두
  `f7b20400ae8d99bd46528464ad75a20fda51f273fbb363bc29fcb91a4ac7ceef`다.
- Evidence Identity SHA는 양쪽 모두
  `943640d23348054525eec099eae81366ce1997ba0faacda595db9da1923075da`다.
- 공개 계약, 안전 결과, Evidence Identity와 Follow-up 건수 Parity는 모두 PASS다.
- Latency 차이는 `-2024.011 ms`, Token 차이는 `0`이지만 단일 입력 1회 비교이므로
  성능 우위나 비용 일반화 근거로 사용하지 않는다.
- 최초 검증 Wrapper 실행은 저장소 Python 모듈 경로가 없어 외부 호출 전에 중단됐다.
  `PYTHONPATH`를 Process 범위로 고정한 뒤 재실행했으며 제품 Runtime 실패는 아니다.

## 4. Backend→Multi-Agent→OpenAI Happy Path·Replay

AI Runtime은 `127.0.0.1:8001`, Backend는 `127.0.0.1:8000` Loopback에서 기동했다.
Backend의 AIRun Identity는 `openai / gpt-4.1-mini / customer_guidance/v2`로 고정했다.

| 확인 항목 | 결과 |
|---|---|
| Backend·AI Health | `PASS / PASS` |
| 신규 Submit | HTTP 200, AI Analyze 1회 |
| AIRun | `SUCCEEDED`, Schema `PASSED`, Retry 0 |
| Inquiry | `AI_GUIDANCE@v3` |
| State Event | `SAFE_GUIDANCE_READY` 정확히 1회 |
| Correlation | Backend Submit·AIRun·State Event 일치 |
| Assessment·Guidance | 각 1건 |
| 내부 EvidenceLink | 5건 |
| Retrieval Lineage | Run 1건·Hit 5건 |
| Consultation | 0건 |
| 고객 Guidance API | HTTP 200 |
| 고객 공개 Evidence | 0건, 현재 확정 공개 계약 경계 |
| 동일 Submit Replay | 최초 응답 유지, 추가 AI 호출·저장 0 |

AI Access Log의 Analyze 호출은 1회이고 Backend Submit은 최초·Replay 2회다. 따라서
Replay에서 AI Provider를 추가 호출하지 않은 실제 소켓 증거와 DB 멱등 증거가
일치한다.

## 5. 실제 Backend 장애 시나리오

외부 전송이 없는 Loopback 장애 주입 서버로 같은 최종 main의 실패 경계를 확인했다.

| 시나리오 | 결과 | 상태·부작용 |
|---|---|---|
| AI HTTP 503 | `PASS` | AIRun `FAILED / AI-FAILED-01`, Inquiry v2 유지 |
| AI 30초 Timeout | `PASS` | AIRun `TIMED_OUT / AI-TIMEOUT-01`, `CONSULTATION_REQUIRED@v3` |

- 두 시나리오 모두 Backend 자동 재시도 0, AI 요청 1회, Replay 추가 AI 호출 0이다.
- 503은 Assessment·Guidance·Evidence·Consultation을 만들지 않았다.
- Timeout은 `AI_PROCESSING_TIMEOUT` SYSTEM Event를 정확히 1회 적용했고 고객
  `system_notice`를 반환했다.
- Timeout도 Assessment·Guidance·Evidence·Consultation을 자동 생성하지 않았다.

## 6. 보안·정리 결과

- 실제 Happy Path 로그 4개와 장애 시나리오 로그 6개에서 Secret·DSN 환경변수 패턴
  검출은 0건이다.
- Happy Path 로그에는 승인 합성 입력과 Evidence 식별자 패턴도 남지 않았다.
- `.runtime/scenario-validation/**` 검증 Harness와 로그는 Git ignore 상태다.
- 검증 후 `8000`, `8001`, `8002`, `8003` Listener는 모두 종료했다.

## 7. 남은 Gate

| 범위 | 상태 | 완료 조건 |
|---|---|---|
| 후보 Runtime 기본값 전환 | `HOLD` | PM 승인과 확대 평가셋 비교 |
| 질문→고객 답변→재검색 | `PASS_CANDIDATE_HEAD` | 최종 main 병합 SHA 재실행 필요 |
| 최종 main 물맛 문진 Gate 재검증 | `HOLD` | 병합 후 동일 HTTP·DB 시나리오 PASS |
| Mobile·Web 전체 사용자 흐름 | `NOT_RUN` | 공동 실행과 동일 Inquiry 추적 |
| 상담 인계 Runtime | `CONTRACT_DECISION_REQUIRED` | 공개 계약·Backend 조합 책임 확정 |
| 독립 QA 재현 | `NOT_RUN` | 별도 작업자·Host에서 동일 Gate 실행 |
| 공식 원문 공개·재배포 | `HOLD` | 별도 Source Policy 승인 |

따라서 최종 main에서 후보 Multi-Agent의 실제 Provider·Readonly pgvector·Backend
Happy/Replay·503·Timeout 경계는 검증됐다. 다만 단일 합성 정상 입력의 PASS를 전체
제품 품질, 운영 전환 또는 Mobile·Web Feature Complete로 확대하지 않는다.

## 8. 2026-08-18 로컬·배포 pgvector 오류 비노출 보강

- 실연결 검증 뒤 `origin/main`이 Mobile·API Contract 변경으로 전진했다. AI 수정
  파일과 중첩이 없음을 확인하고 `dongyoon`을
  `31f73405568637ae545d7f38d635f7a920ec9510`으로 fast-forward한 뒤 회귀를 반복했다.
- `PgVectorStore.search`, `count`, `upsert`, `initialize_schema`의 실제 Driver 호출을
  보호 DB 경계로 통일했다. DSN은 공개 속성이 아닌 내부 `_dsn`으로 보관한다.
- 보호 예외는 Driver 메시지를 사용하지 않고 SQLSTATE로 재시도 여부만 분류한다.
  인증·권한·Schema·데이터·무결성 오류는 재시도하지 않고 연결·Statement Timeout 등
  일시 오류만 기존 계약대로 최대 1회 재시도한다.
- 새 보호 예외는 원본 Driver 예외의 `__context__`와 `__cause__`를 유지하지 않는다.
  따라서 일반 Traceback뿐 아니라 Cause Chain을 읽는 배포 관측기에도 Driver 원문을
  전달하지 않는다.
- Sentinel 표적은 `54 passed`, AI Unit 전체는
  `250 passed, 5 warnings, 7 subtests passed`, Root AI Contract·Safety는
  `27 passed`, `pip check=PASS`, 실제 Readonly pgvector 정상 검색은 `1 passed`다.
- 고정 1024차원 Vector만 사용하는 로컬 배포 Fixture로 실제 Uvicorn→FastAPI→
  Retrieval Retry→PgVectorStore Driver 실패를 실행했다. 결과는 HTTP 503,
  `retryable=true`, `retry_count=1`, `failure_stage=RETRIEVING`이다.
- 위 배포형 응답·stdout·stderr에서 Sentinel, DSN Scheme, Driver 예외 원문 패턴은
  모두 0건이었고 검증 Listener는 종료했다.
- 실제 Embedding을 사용한 최초 두 진단 요청은 DB 연결 전에 Retrieval 5초 Timeout이
  발생했으므로 DSN 방어 PASS 근거에서 제외했다. 이는 별도 첫 Encode 지연 진단이며
  이번 보안 변경에 섞어 수정하지 않았다.
- 외부 Sentry·APM이 Driver Span을 직접 수집하는 배포에서는 저장소 코드만으로 제품
  설정을 강제할 수 없다. 해당 관측 제품의 Secret Redaction 또는 `before_send` Filter는
  운영 배포 Gate로 유지한다.

현재 판정은 `LOCAL_APPLICATION_DEFENSE=PASS`,
`DEPLOYMENT_APPLICATION_BOUNDARY=PASS`,
`EXTERNAL_APM_FILTER=REQUIRED_IF_USED`다.

## 9. 2026-08-18 물맛 문진→적용성 분기 실제 HTTP·DB 후속 검증

- 이 절은 아직 병합되지 않은 `dongyoon` 후보 Worktree의 검증 결과다. 최종 main
  통합 결과로 사용하려면 병합 SHA에서 동일 시나리오를 다시 실행해야 한다.
- Backend 대표 증상 코드 `TASTE`, `ODOR`, `TASTE_ODOR`를 AI의
  `물맛/냄새 이상` 표준 증상으로 연결하고, 문진 대기 초안을 Backend DB의
  `PENDING_CONSULTATION` 안전 불변식과 맞췄다.
- 신규 합성 Inquiry의 최초 AI 호출은 Follow-up 질문 4개를 저장하고 검색·OpenAI
  생성을 실행하지 않은 채 `QUESTIONNAIRE_IN_PROGRESS@v2`를 유지했다.
- 적용 가능 고정 답변 Case는 후속 답변 뒤 실제 Readonly pgvector Run 1건·Hit 1건,
  OpenAI 완료 이벤트 1건, 내부 Evidence 1건을 확인했다.
  `SAFE_GUIDANCE_READY`를 정확히 1회 적용해 `AI_GUIDANCE@v4`로 전환했다.
- `10일 이상 부재 후`와 `해당 없음` 두 비적용 Case는 각각 AIRun
  `NO_EVIDENCE`, Schema `PASSED`, Evidence 0건, `NO_EVIDENCE` Event 1회와
  `CONSULTATION_REQUIRED@v4`를 확인했다. Consultation 행은 자동 생성하지 않았다.
- 비적용 두 Case의 AI Runtime에는 Analysis 시작·완료 Event가 각각 4건 있었고
  `llm_guidance_completed`는 0건이었다. 따라서 조건 불일치 뒤 OpenAI 생성이
  실행되지 않았음을 확인했다.
- 적용 가능·비적용 Case의 동일 답변 Replay는 모두 최초 응답을 유지했으며 추가 AI
  호출과 추가 AIRun·Assessment·Guidance·Evidence·Transition 저장은 0이었다.
- AI Unit `277 passed, 5 warnings, 7 subtests passed`, Root AI Contract·Safety
  `27 passed`, Backend AI Integration `30 passed`, `pip check=PASS`다.
  Harness는 `.runtime` Git ignore에 유지했고 8000·8001 Listener는 종료했다.
  Secret·DSN·질문·답변·Prompt·Evidence·Vector 본문은 기록하지 않았다.
