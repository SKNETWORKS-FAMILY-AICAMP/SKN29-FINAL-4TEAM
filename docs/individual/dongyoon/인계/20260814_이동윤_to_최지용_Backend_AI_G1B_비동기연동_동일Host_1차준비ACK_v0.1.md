# 이동윤 → 최지용: Backend↔AI G1-B 비동기 연동 동일 Host 1차 준비 ACK v0.1

> 작성일: 2026-08-14
>
> 요청서: `20260814_최지용_to_이동윤_Backend_AI_G1B_비동기연동_최우선_실행회신요청_v0.2.md`
>
> 연결 방식: `SAME_HOST`
>
> 기준 main: `720573906c5cba166a7f8fb35c9ff17f359350ab`
>
> AI 실행 Commit: `237a9b525f64670e1afef4fbc9fa1db2545a3aa5`
>
> 제외: Public/LAN 공개, 방화벽 변경, 추가 AI 구현, NO_EVIDENCE·DANGER·HTTP 504 선실행

## 1. 이동윤 1차 준비 ACK

```ini
reviewer=이동윤
main_commit=720573906c5cba166a7f8fb35c9ff17f359350ab
ai_execution_commit=237a9b525f64670e1afef4fbc9fa1db2545a3aa5
vector_fix_in_ai_commit=YES
ai_runtime_ready=YES
ai_health=HTTP_200
ai_base_url=http://127.0.0.1:8001
network_scope=SAME_HOST
runtime_provider=openai
runtime_model=gpt-4.1-mini
prompt_version=customer_guidance/v2
runtime_mode=local
retrieval_source=backend_ai_rag_chunks_v1
correlation_log_events_ready=YES
blocker=NONE
```

현재 AI Runtime은 `127.0.0.1:8001`에서 Listen 중이며 `/health` HTTP 200과
`config_loaded=true`를 확인했다. 이 Base URL은 같은 Host의 Backend Process에서만
사용한다.

## 2. 실행 Commit·보호 입력 확인

```ini
current_branch=dongyoon
origin_main_in_ai_commit=PASS
vector_fix_commit=11d771ab71aa8adc01a72af45dfe9eff280c219e
vector_fix_in_ai_commit=PASS
ai_contract_canonical_diff_count=0
```

기준 main과 현재 AI Commit 사이 다음 보호 범위 차이는 0건이다.

- `ai/**`
- `contracts/ai/**`
- `data/processed/structured/rag/**`
- `data/config/evidence/**`

기존에 수용된 실제 OpenAI·Readonly pgvector·Schema·`GUIDANCE_ONLY` 검증은 입력이
변경되지 않았으므로 반복하지 않았다.

## 3. 동일 Host Backend 설정

최지용은 AI와 같은 Host에서 Backend Process를 기동하고 다음 설정을 사용한다.

```ini
AI_SERVICE_BASE_URL=http://127.0.0.1:8001
AI_SERVICE_MODE=local
AI_MODEL_PROVIDER=openai
AI_MODEL_NAME=gpt-4.1-mini
AI_PROMPT_VERSION=customer_guidance/v2
```

다른 PC에서 위 `127.0.0.1`로 접속하지 않는다. AI를 `0.0.0.0`으로 바인딩하거나
Windows 방화벽을 변경하지 않으며, Private LAN·Public Endpoint를 만들지 않는다.

Backend 기동 후 같은 Host에서 다음 Health를 먼저 확인한다.

```powershell
Invoke-WebRequest -UseBasicParsing `
  -Uri http://127.0.0.1:8001/health `
  -TimeoutSec 5
```

Health 200은 Liveness와 설정 적재 증거다. 실제 pgvector Query·OpenAI 호출·Backend
저장은 새 Inquiry Submit에서 확인한다.

## 4. AI Runtime 재기동 명령

AI Runtime이 중지된 경우 저장소 Root에서 보호 Loader와 Uvicorn을 같은 PowerShell
Process로 실행한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '& {
  . .\scripts\deployment\import_team_integration_env.ps1 `
    -Role AI -RequireOpenAIKey | Out-Null

  & .\ai\.venv\Scripts\python.exe -B -m uvicorn `
    ai.app.main:app `
    --host 127.0.0.1 `
    --port 8001
}'
```

AI Process에 필요한 환경변수 이름은 다음과 같다. 실제 값은 보호 Loader가 Process에만
주입한다.

```text
OPENAI_API_KEY
AI_LLM_MODEL
AI_VECTOR_DSN
AI_EMBEDDING_REVISION
AI_VECTOR_TABLE_NAME
```

## 5. Correlation 로그 준비

최지용이 전달하는 Correlation ID로 다음 이벤트를 대조할 준비가 됐다.

```text
analysis_started
llm_guidance_completed
analysis_completed
```

실행 후 확인 항목:

```ini
correlation_id_match=PENDING_BACKEND_SUBMIT
actual_provider=PENDING_BACKEND_SUBMIT
actual_model=PENDING_BACKEND_SUBMIT
actual_pgvector_query=PENDING_BACKEND_SUBMIT
verified_evidence_count=PENDING_BACKEND_SUBMIT
expected_evidence_hit=PENDING_BACKEND_SUBMIT
schema_validation=PENDING_BACKEND_SUBMIT
guidance_only=PENDING_BACKEND_SUBMIT
token_usage_present=PENDING_BACKEND_SUBMIT
```

Raw Prompt·고객 입력·Evidence 원문·Vector·Secret은 로그 대조 회신에 포함하지 않는다.

## 6. 최지용 실행 후 전달 요청

Backend Submit이 완료되면 다음 Secret 제거 정보만 전달한다.

```ini
backend_commit=<40SHA>
backend_environment=SAME_HOST
inquiry_id=<공개 UUID>
correlation_id=<검증용 UUID>
submitted_at=<KST>
backend_http_status=<상태>
backend_result_status=<상태>
```

Idempotency Key, 인증 Token, 고객 원문과 DSN은 전달하지 않는다. 위 정보를 수신하면 AI
로그를 비동기로 대조하고 요청서의 2차 실제 AI 실행 증거 형식으로 회신한다.

## 7. 현재 판정

```ini
ai_first_ack=READY
backend_same_host_health_check=NEXT_OWNER_최지용
backend_submit=WAITING
ai_second_evidence=WAITING_BACKEND_INQUIRY_AND_CORRELATION
author_g1b_decision=NOT_RUN
qa_handoff_ready=NO_WAIT_AUTHOR_G1B_PASS
```
