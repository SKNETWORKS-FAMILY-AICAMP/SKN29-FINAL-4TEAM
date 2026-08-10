# 5주차 AI Entry Gate

> 검증일: 2026-08-10T20:07:04+09:00
> 담당: 이동윤 / AI·RAG  
> 기준 Branch: `dongyoon`  
> Source HEAD: `4d955116c00f715e1ba9e465104a381b858996b9`
> 판정: `PARTIAL_PASS_EXTERNAL_GATES_OPEN`

## 1. 현재 결론

단일 RAG의 계약·안전·단위 회귀·Mock HTTP 기준선은 실행 가능하다. 실제
Multi-Agent, 외부 LLM, 팀 DB pgvector, Django→FastAPI 실제 HTTP는 아직 완료
증거가 없다. 이 문서는 과거 개인 DB 결과나 Mock 결과를 팀 통합 완료로
대체하지 않는다.

AI 변경과 Backend 기준선이 병합된 Source HEAD에서 AI 단위 Test와 실제 Uvicorn
Mock HTTP Smoke를 다시 실행했다. 실행 직전 작업 트리는 Clean이었고 이후 이
증거 문서와 후보 기준선 갱신으로 Dirty 상태가 된다. Initial Symptom Wiring
후보 Commit은 아직 전달되지 않아 Backend→AI 실제 HTTP는 시작하지 않았다.

## 2. 실행 환경

| 항목 | 현재 값 | 판정 |
|---|---|---|
| OS | Windows 11 `10.0.26200` | PASS |
| Python | `3.13.13` / `ai/.venv` | PASS |
| Dependency | `ai/requirements.lock` | PASS |
| `pip check` | No broken requirements found | PASS |
| FastAPI | `0.136.3` | PASS |
| Pydantic | `2.13.4` | PASS |
| LangGraph | `1.2.2` | PASS |
| sentence-transformers | `5.5.1` | PASS |
| psycopg | `3.2.9` | PASS |
| Python `pgvector` package | 미설치 | INFO: 현재 Adapter는 psycopg SQL을 사용 |
| PostgreSQL `vector` Extension | 팀 DB 접속정보 없음 | BLOCKED |
| Backend 가상환경 | `backend/.venv` 없음 | BLOCKED |
| 외부 LLM Key | 미설정 | P1 후속·현재 P0 차단 아님 |

Secret과 실제 DSN 값은 기록하지 않는다.

## 3. AI 기준선 검증

| Gate | 결과 | 범위 제한 |
|---|---|---|
| AI 전체 단위 테스트 | `127 passed, 3 warnings` | 현재 Dirty 작업 트리 |
| JSON Schema·Pydantic | 전체 AI Schema `3.0.0` parity PASS | 단위 검증 |
| Safety | 위험 규칙 ID·부정문·금지 행동 PASS | 결정론적 규칙 |
| 새 안전 회귀 | `물이 새고` → `SAFETY-LEAK-001` PASS | 자연스러운 조사 표현 보강 |
| Consultation Summary | 정상·위험·부정문·길이 경계 4건 PASS | 외부 LLM 미사용 Fallback 기준선 |
| FastAPI | 실제 Uvicorn 기동 PASS | Local Process |
| Mock Analyze | HTTP 200·추적 ID PASS | 검색·LLM 미실행 |
| Local 일반·주의 구성 실패 | HTTP 503·추적 ID PASS | `AI_VECTOR_DSN` 미설정은 검색 0건이 아닌 비재시도 구성 실패 |
| Local 위험 분기 | 누수·전기 위험 → `SAFETY-LEAK-001`, `SAFETY-ELECTRICAL-001`·`TOTAL_STOP`·근거 0건 PASS | Vector Store 미사용 실제 HTTP 안전 경로 |
| Backend Integration Fixture | F01~F12 `12 passed, 1 warning` | F11의 stale State 적용 차단은 Backend 공동 E2E 대상 |
| 동일 통합 기준선 | `4d955116c00f715e1ba9e465104a381b858996b9` | AI 변경과 Backend `57326cf...` 기준선 Merge |
| 팀 DB Local 검색 | `1 skipped` | `AI_VECTOR_DSN`, `AI_EMBEDDING_REVISION` 없음 |
| 팀 DB DDL Preflight | PASS | 일반 적재·검색 경로는 DDL 미실행, 별도 초기화는 Disposable 이중 Guard 필수 |
| Backend 실제 HTTP | 미실행 | Initial Symptom Wiring 후보·Backend 실행환경 없음 |

경고 3건은 `jsonschema.RefResolver` 2건과 Starlette TestClient 1건의 폐기 예정
API 경고다. 실패는 아니지만 후속 의존성 정리 대상으로 유지한다.

## 4. 고정된 AI Runtime Identity

```text
contract_version=3.0.0
current_runtime=SingleRAGPipeline
external_llm_used=false
generation_method=deterministic-rules-and-templates
embedding_model=BAAI/bge-m3
embedding_revision=5617a9f61b028005a4858fdac845db406aefb181
embedding_dimension=1024
retrieval_top_k=5
score_threshold=0.4
index_version=1.0.0
chunk_count=7
chunk_set_sha256=175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958
overall_timeout_seconds=30
ai_internal_retry_max=1
backend_automatic_retry=0
```

실행값 SSOT는 `ai/configs/runtime_identity.json`, 승인 근거 Identity SSOT는
`ai/configs/canonical_evidence_identity.json`이다.

## 5. Blocker

| ID | 구분 | 차단 내용 | 담당·협업 | 필요한 입력 | 해제 조건 |
|---|---|---|---|---|---|
| W5-AI-B01 | 환경 | 팀 DB pgvector 미접속 | 제공·Migration: 최지용 / AI 실행: 이동윤 / QA 판정: 김은진 | 최소 권한 DSN Secret 전달, Migration·Extension 상태 | 팀 DB 적재·검색·평가 재실행 PASS |
| W5-AI-B02 | 계약 | AI `chunk_id`→Backend `DocumentChunk.public_id` 미매핑 | 최지용·Database | canonical 7건 Crosswalk | Backend 공식 근거 검증·저장 PASS |
| W5-AI-B03 | 환경 | Backend 실행환경 없음 | 최지용 | Python 3.13.13 `backend/.venv` 재현 절차 | Backend 단위·실제 HTTP Test 실행 가능 |
| W5-AI-B04 | Runtime | `SUBMIT_SYMPTOM` 이후 Initial AI 호출점 미구현 | 최지용 | Transaction Commit 이후 정확히 1회 호출하는 후보 Commit | 신규 요청 1회·Replay 0회·AI 실패 시 저장 보존 검증 PASS |
| W5-AI-B05 | Runtime | EvidenceCard API가 준비 단계 | 최지용·한예나 | 공개 DTO·Endpoint·권한 계약 | Backend→Web 공식 근거 실제 전달 PASS |

## 6. 코드 차단과 환경 차단 구분

P0 외부 차단은 Initial Symptom Wiring 후보, Backend 실행환경, 팀 DB, Backend
Crosswalk와 EvidenceCard Runtime이다. 현재 단일 Workflow의 AI 계약·안전·
Fixture·Mock HTTP에는 확인된 코드 차단이 없다. 실제 외부 LLM과 Multi-Agent
Runtime은 팀 DB·Backend E2E 기준선 이후 비교 평가할 P1 후속이며, 현재 완료로
계산하지 않는다.

## 7. 다음 Gate

1. 최지용이 `SUBMIT_SYMPTOM` 저장 Commit 이후 Transaction 밖에서 AI를 1회
   호출하는 후보 Commit과 Backend 재현 명령을 전달한다.
2. 후보의 신규 호출 1회, Idempotency Replay 추가 호출 0회, AI 실패 시 기존
   증상·State 저장 보존 경계를 검토한다.
3. 팀 DB와 독립적인 Backend Mock 실제 HTTP를 통과시킨다.
4. 최지용이 canonical 7건 Crosswalk, Migration과 최소 권한 DSN Secret 전달
   방식을 확정하고 팀 DB Retrieval을 같은 통합 Commit에서 재검증한다.
5. Backend 저장·State Event·EvidenceCard 전달 E2E를 검증하고 김은진이 같은
   Commit·Fixture로 재현·판정한다.
6. 단일 Workflow 기준선을 고정한 뒤 실제 LLM·Multi-Agent를 동일 평가셋으로
   비교한다. 실제 호출 경로 전에는 완료로 표시하지 않는다.

## 8. 재현 명령

```powershell
.\ai\.venv\Scripts\python.exe --version
.\ai\.venv\Scripts\python.exe -m pip check
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit\test_backend_integration_fixtures.py -q
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\integration\test_pgvector_runtime.py -q -rs
.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
.\ai\.venv\Scripts\python.exe -m ai.scripts.smoke_test --base-url http://127.0.0.1:8001 --mode mock
.\ai\.venv\Scripts\python.exe -m ai.scripts.smoke_test --base-url http://127.0.0.1:8001 --mode local --expected-analysis-status 503
```
