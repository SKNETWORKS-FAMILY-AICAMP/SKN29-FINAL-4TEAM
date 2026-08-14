# Backend-AI 실제 LLM Runtime 공동 검증 요청 회신

## 1. 회신 정보

- 발신: 이동윤 — AI·RAG
- 수신: 최지용 — Backend·Database
- 회신일: 2026-08-13 KST
- 원 요청: `20260813_최지용_to_이동윤_Backend_AI_양방향로컬환경_실제LLM_Runtime_공동작업요청_v0.1.md`
- 판정 범위: `G1-A AI Runtime` 사전 검증과 공동 Smoke 준비 상태
- 최종 판정: `BLOCKED_BY_INTEGRATION_ENV`

## 2. 결론

요청 문서의 `f1691df17dfdbc82283982379d9422d6a31e3c68` 이후 AI 안전·Privacy·
팀 DB Runtime Gate 보강이 추가됐습니다. 현재 원격 `origin/dongyoon`과 로컬
후보는 다음 SHA로 일치하며 작업 트리는 회신서 작성 전 Clean 상태였습니다.

```text
ai_candidate_commit=502570487510749e9e3cb4351610df5ca5e46f5f
tested_commit=7d07862e50a796e83701bda6ffd04dc974325b57
tested_scope_diff_after_pull=NONE(ai/**,contracts/ai/**,backend/**,contracts/state-machine/**)
ai_candidate_base_commit=df9c01ccc4f6de748dec4503bb08f53aa42efe76
backend_base_included=YES
branch=codex/dongyoon-reconcile
```

현재 후보는 코드·계약·결정적 회귀 범위에서 공동 Smoke 준비 상태입니다. 그러나
현재 PC에 `OPENAI_API_KEY`, `AI_LLM_MODEL`, `AI_VECTOR_DSN`,
`AI_EMBEDDING_REVISION`, `AI_VECTOR_TABLE_NAME`이 모두 미주입이므로 실제
OpenAI·팀 pgvector·Local HTTP·Backend DB 저장 흐름은 실행하지 못했습니다.

따라서 `G1-A AI Runtime`을 PASS로 회신하지 않습니다. 현재 판정은
`BLOCKED`이며, Secret과 팀 최소권한 DSN이 통합환경에 주입된 뒤 아래 순서대로
실행해야 합니다.

## 3. 요청 항목 대조 결과

| 요청 항목 | 확인 결과 | 판정 |
| --- | --- | --- |
| 실제 OpenAI `gpt-4.1-mini` | Runtime Identity·모델 Profile·Adapter는 고정됐으나 Secret 부재로 실제 호출 미실행 | `NOT_RUN` |
| 실제 승인 7개 pgvector Corpus | 팀 View·Manifest·7행·1024차원·검색·최소권한 검증 Test가 있으나 DSN 부재 | `NOT_RUN` |
| 조회 대상 | `AI_VECTOR_TABLE_NAME=backend_ai_rag_chunks_v1` 지원 및 팀 Gate에서 정확한 View 이름 강제 | `READY` |
| 계약 `3.0.0` | 공개 `contracts/ai/**` 변경 없이 Schema·Pydantic Parity 및 Strict Smoke 검증 | `PASS` |
| `GUIDANCE_ONLY` | LLM은 Evidence 원문 message와 Runtime Allowlist의 `next_actions`만 반환 가능 | `PASS` |
| Safety·Evidence·State 소유권 | AI가 변경하지 않고 Rule/Runtime·Backend가 소유 | `PASS` |
| Timeout | Provider 408·504와 LLM Timeout을 `AI-TIMEOUT-01`, HTTP 504로 유지 | `PASS_UNIT` |
| No-Evidence·Danger | LLM 호출 없이 기존 Fallback·Safety 경계 유지 | `PASS_UNIT` |
| Correlation | 계약·단위·Mock HTTP Echo 검증은 통과, 실제 공동 HTTP는 미실행 | `PARTIAL` |
| Backend 저장·Replay | Evidence/Danger 관련 Backend 단위 35건 통과, 실제 AIRun·EvidenceLink DB 저장 및 Replay는 미실행 | `NOT_RUN_E2E` |

OpenAI 공식 문서에서도 `gpt-4.1-mini`는 Responses API와 Structured Outputs를
지원하는 모델로 확인됩니다.

- <https://developers.openai.com/api/docs/models/gpt-4.1-mini>

## 4. 반영된 공동 Smoke 보강

1. 팀 pgvector 조회 Table을 `AI_VECTOR_TABLE_NAME`으로 선택하며 기본 팀 값은
   `backend_ai_rag_chunks_v1`입니다.
2. Backend View가 소문자로 반환하는 SHA-256은 Hex 유효성을 유지한 채
   대소문자만 정규화하고, 누락·비정상 Hash는 Fail-closed 처리합니다.
3. 팀 pgvector Gate는 다음을 확인하며 환경변수 누락을 Skip하지 않고 실패시킵니다.
   - 정확한 View 이름과 PostgreSQL View 객체 여부
   - 현재 Role의 View `SELECT`만 허용
   - `default_transaction_read_only=on`
   - `public` Schema `CREATE=false`
   - 사용자·Chunk·Embedding·Crosswalk 원본 Table의 SELECT/DML 금지
   - 승인 7행, 1024차원, 실제 Exact Search와 예상 Chunk
4. `verify_local_runtime`은 실제 Pipeline 내부에서 다음을 추가 확인합니다.
   - 실제 Provider 모델이 `gpt-4.1-mini` 계열
   - Prompt `customer_guidance/v2`
   - 실제 Token 사용량 `> 0`
   - Low-flow 승인 Evidence 검색
   - LLM message가 승인 Evidence 원문과 일치
5. Strict HTTP Smoke는 HTTP 200만으로 PASS하지 않습니다.
   - 계약 `3.0.0` 전체 Schema
   - Inquiry·Correlation·AI Request·State Version Echo
   - `status=SUCCEEDED`, `failure_stage=null`
   - 공식 Evidence·페이지·HTTPS URL과 예상 Chunk
   - 승인 Evidence 원문 message
6. OpenAI 응답은 `status=completed`만 성공으로 인정하고 `store=false`를 고정합니다.
7. 고객 자유 문진 답변·발생 조건·발생 시점·기존 조치는 Provider 입력에서
   제외하고, 증상 유형·출수 종류 Allowlist와 정규화된 오류 코드만 사용합니다.
8. LLM 결과가 Safety·Grounding Gate를 통과하지 못하면 결정적 안내로 성공을
   가장하지 않고 Generation 실패로 종료합니다.

## 5. 실행 결과

### 5.1 AI 전체 단위·계약 회귀

```powershell
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
```

```text
219 passed, 5 warnings, 7 subtests passed
exit=0
```

### 5.2 AI 의존성 무결성

```powershell
.\ai\.venv\Scripts\python.exe -m pip check
```

```text
No broken requirements found.
exit=0
```

### 5.3 G1-A 표적 Gate 회귀

```powershell
.\ai\.venv\Scripts\python.exe -m pytest `
  ai\tests\unit\test_llm_guidance.py `
  ai\tests\unit\test_smoke_test.py `
  ai\tests\unit\test_verify_local_runtime.py -q
```

```text
43 passed, 3 warnings
exit=0
```

### 5.4 Backend Evidence·Danger 회귀

```powershell
.\backend\.venv\Scripts\python.exe -m pytest `
  backend\tests\unit\evidence\test_ai_chunk_crosswalk.py `
  backend\tests\unit\ai_integration\test_inquiry_ai_service.py -q
```

```text
35 passed
exit=0
```

이 결과는 Backend 단위 회귀이며 실제 HTTP·팀 DB 저장 E2E PASS가 아닙니다.

### 5.5 실제 LLM·pgvector Gate 시도

```powershell
.\ai\.venv\Scripts\python.exe -m ai.scripts.verify_local_runtime
```

```text
result=FAIL
message=필수 환경변수가 없습니다: OPENAI_API_KEY
exit=1
```

```powershell
.\ai\.venv\Scripts\python.exe -m pytest `
  ai\tests\integration\test_pgvector_runtime.py -q
```

```text
1 failed
reason=팀 pgvector Gate 필수 환경변수가 없습니다: AI_VECTOR_DSN
exit=1
```

위 두 실패는 제품 결함을 숨긴 결과가 아니라 통합환경 미주입을 Fail-closed로
드러낸 결과입니다. 실제 Provider·팀 DB 실행 증거는 아직 `NOT_RUN`입니다.

## 6. Secret 제외 실행 절차

Secret 값은 문서·Git·명령 결과에 남기지 않습니다. 김은진이 통합환경 변수로
주입한 뒤 아래 명령을 사용합니다.

```powershell
# 필수 환경변수 이름
# OPENAI_API_KEY
# AI_LLM_MODEL=gpt-4.1-mini
# AI_VECTOR_DSN
# AI_EMBEDDING_REVISION
# AI_VECTOR_TABLE_NAME=backend_ai_rag_chunks_v1

.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app `
  --host 127.0.0.1 --port 8001

.\ai\.venv\Scripts\python.exe -m pytest `
  ai\tests\integration\test_pgvector_runtime.py -v

.\ai\.venv\Scripts\python.exe -m ai.scripts.verify_local_runtime

.\ai\.venv\Scripts\python.exe -m ai.scripts.smoke_test `
  --base-url http://127.0.0.1:8001 `
  --mode local `
  --expected-result-status SUCCEEDED `
  --expected-failure-stage NONE `
  --expected-evidence-id RAG-WPUJAC104DWH-LOW-FLOW-001 `
  --minimum-evidence-count 1 `
  --require-verified-evidence
```

실제 통합에서는 위 AI Gate 뒤 Backend 제출 흐름을 실행하고 같은
`correlation_id`에서 다음을 대조해야 합니다.

- AIRun: `model_provider=openai`
- AIRun: `model_name=gpt-4.1-mini` 또는 승인 Snapshot
- AIRun: `prompt_version=customer_guidance/v2`
- Assessment·Guidance·EvidenceLink 저장
- Guidance Snapshot 조회
- Replay의 추가 AI·LLM·업무 레코드 0건

## 7. 요청 형식 회신

```ini
ai_candidate_commit=502570487510749e9e3cb4351610df5ca5e46f5f
tested_commit=7d07862e50a796e83701bda6ffd04dc974325b57
tested_scope_diff_after_pull=NONE(ai/**,contracts/ai/**,backend/**,contracts/state-machine/**)
ai_candidate_base_commit=df9c01ccc4f6de748dec4503bb08f53aa42efe76
start_command=.\ai\.venv\Scripts\python.exe -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
g1a_ai_runtime=BLOCKED
actual_llm=NOT_RUN
configured_llm=gpt-4.1-mini
retrieval_source=backend_ai_rag_chunks_v1
actual_pgvector_retrieval=NOT_RUN
response_schema=PASS
guidance_only=PASS
correlation_verified=NO
correlation_unit_mock=PASS
timeout_http_504=PASS
timeout_actual_provider_http=NOT_RUN
no_evidence_danger_fallback=PASS
tests=AI_UNIT_219_PASS;AI_PIP_CHECK_PASS;G1A_TARGET_43_PASS;BACKEND_EVIDENCE_DANGER_35_PASS;LOCAL_RUNTIME_ENV_BLOCK_EXIT_1;PGVECTOR_ENV_BLOCK_1_FAILED_EXIT_1
blockers=OPENAI_API_KEY,AI_LLM_MODEL,AI_VECTOR_DSN,AI_EMBEDDING_REVISION,AI_VECTOR_TABLE_NAME 미주입;팀 View 승인 7행 및 최소권한 Role 실제 접속 필요;Backend AIRun/EvidenceLink/Replay 공동 E2E 필요
joint_smoke_available_time=2026-08-13 KST 통합환경 변수 주입 확인 후 즉시 협의 가능
```

## 8. 공동 판정 제안

- 현재: `G1-A=BLOCKED`, `G1-B=NOT_RUN`, 전체 Backend E2E=`HOLD`
- Secret·팀 DSN 주입 후: 팀 pgvector 최소권한 Gate → AI 내부 Runtime Gate →
  Local HTTP Strict Smoke → Backend 수직 저장·Replay 순서로 실행
- 수정이 없다면 후보 SHA는
  `502570487510749e9e3cb4351610df5ca5e46f5f`을 사용. 테스트는 조상 커밋
  `7d07862e50a796e83701bda6ffd04dc974325b57`에서 실행했으며, pull 후 AI·계약·Backend·상태 머신 범위의 파일 차이는 없음
- 추가 수정이 발생하면 새 40자리 SHA를 다시 회신하고 공동 검증 SHA를 재고정
- 실제 G1-A와 G1-B가 모두 PASS하기 전까지 전체 Backend E2E 완료로 확대하지 않음
