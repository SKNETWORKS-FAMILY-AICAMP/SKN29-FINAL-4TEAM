# 이동윤 → 김은진·최지용: AI G1-A Phase B 기술 사전검증 착수 회신 v0.1

> 작성일: 2026-08-14  
> 고정 기준: `main@ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7`  
> 범위: Backend 계약 회귀, AI pgvector Gate 착수, Source Policy Hold 경계  
> 제외: Secret·DSN 값, Host 경로, 공식 원문·Fixture·Vector 본문, 실제 OpenAI 호출

## 1. 착수 판정

QA 회신의 `environment_ready=YES`와 `g1a_joint_execution_ready=YES`를 기술환경 준비
ACK로 수신했다. 다만 `source_policy_review=PENDING`과
`qa_decision=APPROVE_WITH_POLICY_HOLD`가 함께 있으므로 G1-A 전체를 무조건 승인으로
해석하지 않는다.

정책 Hold를 침범하지 않는 Backend 계약 회귀와 AI Readonly pgvector Gate 실행에는
착수했다. 실제 OpenAI 호출은 공식 Evidence Summary의 외부 Provider 전송을 포함하므로
Source Policy 승인 전까지 실행하지 않았다.

```ini
reviewer=이동윤
fixed_main=ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7
qa_environment_ready=YES
g1a_joint_execution_ready=YES
source_policy_review=PENDING
qa_decision=APPROVE_WITH_POLICY_HOLD

work_start_decision=PARTIAL_START
backend_contract_preflight=PASS
ai_pgvector_gate=BLOCKED_CURRENT_PROCESS_ENV
actual_openai=NOT_RUN_POLICY_HOLD
strict_http_smoke=NOT_RUN
timeout_actual_http_504=NOT_RUN
g1a_phase_b=IN_PROGRESS_BLOCKED

current_process_ai_vector_dsn=MISSING
current_process_embedding_revision=MISSING
current_process_vector_table_name=MISSING
secret_values_printed=NO
blockers=CURRENT_CODEX_PROCESS_QA_ENV_NOT_INHERITED;SOURCE_POLICY_REVIEW_PENDING
next_owner=김은진_QA_HOST_ENV_EXECUTION_OR_APPROVED_SECRET_INJECTION;QA_PM_SOURCE_POLICY_DECISION
```

## 2. 수신한 QA 상태

```ini
fixture_received=YES
fixture_generated_commit_ancestor=PASS
fixture_inputs_unchanged=PASS
fixture_sha_match=PASS
environment_ready=YES
g1a_joint_execution_ready=YES
source_policy_review=PENDING
qa_decision=APPROVE_WITH_POLICY_HOLD
```

Fixture 재생성·재전송은 수행하지 않았다. 위 ACK는 QA가 제공한 실행환경 상태이며,
현재 Codex 프로세스에 QA Host의 환경변수가 자동 전달됐다는 의미는 아니다.

## 3. 실행 결과

### 3.1 Backend 계약 회귀

```powershell
.\backend\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  backend\tests\unit\evidence\test_ai_canonical_embedding_fixture_builder.py `
  backend\tests\unit\evidence\test_ai_canonical_evidence_import.py `
  backend\tests\unit\evidence\test_ai_chunk_crosswalk.py `
  backend\tests\unit\database\test_backend_ai_g1b_readiness.py
```

```ini
result=81 passed in 12.54s
exit_code=0
scope=UNIT_AND_CONTRACT_ONLY
actual_team_database=NOT_PROVEN_BY_THIS_COMMAND
```

### 3.2 AI 실제 pgvector Gate

```powershell
.\ai\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider `
  .\ai\tests\integration\test_pgvector_runtime.py
```

```ini
result=1 failed in 0.25s
exit_code=1
failure_boundary=AI_VECTOR_DSN_MISSING
actual_pgvector=NOT_RUN
```

테스트는 환경변수 부재를 Skip하거나 검색 0건으로 숨기지 않고 즉시 fail-closed 했다.
DSN 값은 출력하지 않았다.

## 4. Source Policy Hold 근거

현재 Guidance Generator는 검색된 공식 Evidence의 Summary를 Provider 요청 모델에
포함하고, OpenAI Client는 이를 실제 Request JSON으로 직렬화한다.

- `ai/app/generation/customer_guidance/guidance_generator.py:208`
- `ai/app/integrations/llm/llm_client.py:271`

공식 Source 계약은 내부 QA·RAG 검증 범위를 기록하고 있으며, 프로젝트 진행 Gate는
OpenAI 사용 승인과 고객 입력 외부 전송 범위를 별도 확인사항으로 둔다.

- `data/config/evidence/backend_ai_canonical_import_v1.json:28`
- `docs/progress/이동윤_0813_0814_작업_진행도_08131159.md:42`

따라서 `source_policy_review=APPROVED` 또는 공식 Evidence Summary의 OpenAI API
전송을 허용한다는 명시적 결정 전에는 실제 OpenAI·Strict HTTP·Timeout 504 실행을
보류한다. Unit·Health 결과를 실제 G1-A PASS로 확대하지 않는다.

## 5. 재개 조건

다음 중 하나의 방식으로 QA Host Runtime 접근이 현재 실행 프로세스에 제공돼야 한다.

1. 김은진 Host에서 고정 main 명령을 직접 실행하고 Secret 없는 결과를 회신한다.
2. 승인된 Secret 전달 절차로 현재 실행 Process에 아래 환경변수를 주입한다.

```text
AI_VECTOR_DSN
AI_EMBEDDING_REVISION
AI_VECTOR_TABLE_NAME
```

Secret 값은 채팅·문서·로그에 기록하지 않는다. pgvector PASS 이후에도 실제 OpenAI
실행은 아래 정책 ACK를 추가로 요구한다.

```ini
source_policy_review=APPROVED
openai_evidence_summary_transmission=APPROVED
```

위 조건이 충족되면 Readonly pgvector → 실제 OpenAI Runtime → Strict HTTP 정상 →
실제 Timeout HTTP 504 순서로 재개한다.
