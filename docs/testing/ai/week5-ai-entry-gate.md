# 5주차 AI Entry Gate

> 검증일: 2026-08-10 KST  
> 담당: 이동윤 / AI·RAG  
> 기준 Branch: `dongyoon`  
> Source HEAD: `3485e0f1717f4afc6a5f76e469b4bb2d6bd0ecc1`  
> 판정: `PARTIAL_PASS_EXTERNAL_GATES_OPEN`

## 1. 현재 결론

단일 RAG의 계약·안전·단위 회귀·Mock HTTP 기준선은 실행 가능하다. 실제
Multi-Agent, 외부 LLM, 팀 DB pgvector, Django→FastAPI 실제 HTTP는 아직 완료
증거가 없다. 이 문서는 과거 개인 DB 결과나 Mock 결과를 팀 통합 완료로
대체하지 않는다.

현재 작업 트리는 이 Entry Gate와 상담 요약 결정론적 기준선을 추가하는 변경으로
Dirty 상태다. 아래 Source HEAD는 변경 전 기준 Commit이며, 최종 기준선은 변경을
Commit한 뒤 같은 검증을 재실행해야 한다.

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
| 외부 LLM Key | 미설정 | BLOCKED |

Secret과 실제 DSN 값은 기록하지 않는다.

## 3. AI 기준선 검증

| Gate | 결과 | 범위 제한 |
|---|---|---|
| AI 전체 단위 테스트 | `126 passed, 3 warnings` | 현재 Dirty 작업 트리 |
| JSON Schema·Pydantic | 전체 AI Schema `3.0.0` parity PASS | 단위 검증 |
| Safety | 위험 규칙 ID·부정문·금지 행동 PASS | 결정론적 규칙 |
| 새 안전 회귀 | `물이 새고` → `SAFETY-LEAK-001` PASS | 자연스러운 조사 표현 보강 |
| Consultation Summary | 정상·위험·부정문·길이 경계 4건 PASS | 외부 LLM 미사용 Fallback 기준선 |
| FastAPI | 실제 Uvicorn 기동 PASS | Local Process |
| Mock Analyze | HTTP 200·추적 ID PASS | 검색·LLM 미실행 |
| Local 위험 분기 | `물이 새고` → 위험·`SAFETY-LEAK-001`·`TOTAL_STOP`·근거 0건 PASS | Vector Store 미사용 실제 HTTP 안전 경로 |
| 팀 DB Local 검색 | 미실행 | `AI_VECTOR_DSN` 없음 |
| Backend 실제 HTTP | 미실행 | `backend/.venv` 없음 |

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
| W5-AI-B01 | 환경 | 팀 DB pgvector 미접속 | 김은진·최지용 | 최소 권한 DSN, Migration·Extension 상태 | 팀 DB 적재·검색·평가 재실행 PASS |
| W5-AI-B02 | 계약 | AI `chunk_id`→Backend `DocumentChunk.public_id` 미매핑 | 최지용·Database | canonical 7건 Crosswalk | Backend 공식 근거 검증·저장 PASS |
| W5-AI-B03 | 환경 | Backend 실행환경 없음 | 최지용 | Python 3.13.13 `backend/.venv` 재현 절차 | Backend 단위·실제 HTTP Test 실행 가능 |
| W5-AI-B04 | 결정 | 실제 LLM Provider·Model·Key 미확정 | PM·이동윤 | Provider, Model ID, Secret 전달 방식 | 실제 Structured Output Integration PASS |
| W5-AI-B05 | Runtime | EvidenceCard API가 준비 단계 | 최지용·한예나 | 공개 DTO·Endpoint·권한 계약 | Backend→Web 공식 근거 실제 전달 PASS |

## 6. 코드 차단과 환경 차단 구분

환경 차단은 팀 DB, Backend 가상환경, LLM Secret이다. 코드 차단은 실제
Multi-Agent Runtime·LLM Adapter·Agent Routing/Handoff·Backend 실제 HTTP Test가
아직 없다는 점이다. `selective_pipeline.py`와 LLM 통합 파일의 설명 한 줄은 구현
완료로 계산하지 않는다.

## 7. 다음 Gate

1. 외부 입력을 기다리는 동안 Agent 책임·입출력·Routing 계약을 확정한다.
2. 상담 요약은 결정론적 Fallback 기준선을 먼저 유지한다.
3. Backend Mock 실제 HTTP를 먼저 통과시킨다.
4. 팀 DB Retrieval을 동일 Commit에서 재검증한다.
5. 단일 Workflow의 팀 DB·Backend E2E 기준선을 고정한 뒤 Multi-Agent Runtime을
   활성화하고 동일 평가셋으로 비교한다.
6. 실제 Provider가 정해지기 전에는 외부 LLM 사용 완료로 표시하지 않는다.

## 8. 재현 명령

```powershell
.\ai\.venv\Scripts\python.exe --version
.\ai\.venv\Scripts\python.exe -m pip check
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
.\ai\.venv\Scripts\python.exe -m ai.scripts.smoke_test --base-url http://127.0.0.1:8001 --mode mock
```
