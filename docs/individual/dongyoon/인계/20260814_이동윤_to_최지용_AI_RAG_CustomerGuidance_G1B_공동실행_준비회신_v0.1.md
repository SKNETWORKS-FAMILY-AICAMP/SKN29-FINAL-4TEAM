# 이동윤 → 최지용: AI RAG Customer Guidance G1-B 공동실행 준비 회신 v0.1

> 작성일: 2026-08-14
>
> 전달 대상: 최지용 Backend·DB, 김은진 Data·QA·DevOps
>
> 범위: 김은진 QA 통합환경의 실제 AI Runtime 기동과 Backend G1-B 공동검증 지원
>
> 제외: 추가 AI 구현, 이동윤 Host DB Migration, Secret·DSN·Raw 원문·Vector·Prompt 본문 전달

## 1. 회신 결론

추가 AI 구현이나 이동윤 Host DB Migration은 진행하지 않는다. 김은진 QA 통합환경을
합의된 최종 main 40자리 SHA로 재기동한 뒤, 현재 준비된 AI Runtime을 사용한 Backend
G1-B 공동검증을 지원한다.

```ini
reviewer=이동윤
ai_runtime_ready=YES
additional_ai_implementation=NOT_REQUIRED
dongyoon_host_migration=NOT_RUN_AS_REQUESTED
qa_runtime_command=PROVIDED
joint_happy_path=WAITING_QA_RUNTIME_START
no_evidence=DEFERRED_AFTER_HAPPY_PATH
danger_total_stop=DEFERRED_AFTER_HAPPY_PATH
availability=김은진_ENVIRONMENT_READY와_공동실행시간_ACK_수신_즉시
```

## 2. 김은진 QA Host AI Runtime 기동

저장소 Root에서 보호 Loader와 Uvicorn을 반드시 같은 PowerShell Process로 실행한다.

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

Backend와 AI가 김은진 Host에서 함께 실행되는 현재 단일 Host 통합구성에서는 Backend
Process에 다음 변수 이름과 값을 사용한다.

```ini
AI_SERVICE_BASE_URL=http://127.0.0.1:8001
AI_SERVICE_MODE=local
```

다른 Host에서 AI에 접근하도록 `0.0.0.0` 바인딩하거나 Windows 방화벽을 변경하지
않는다. 단일 Host 구성이 바뀌면 주소·접근통제·방화벽 범위를 먼저 별도로 합의한다.

## 3. AI Process 필수 환경변수 이름

```text
OPENAI_API_KEY
AI_VECTOR_DSN
AI_VECTOR_TABLE_NAME
AI_EMBEDDING_REVISION
AI_LLM_MODEL
```

보호 Loader가 위 값을 현재 AI Process에만 주입해야 한다. 기존 Runtime 보호파일을
다른 Host로 복사하거나 실제 값을 채팅·문서·Git·구조화 로그에 기록하지 않는다.

## 4. 기동 확인

AI 기동 Terminal은 종료하지 않고 유지한다. 별도 Terminal에서 다음을 확인한다.

```powershell
Invoke-WebRequest -UseBasicParsing `
  -Uri http://127.0.0.1:8001/health `
  -TimeoutSec 5
```

```ini
expected_http_status=200
expected_service=ai-service
health_scope=LIVENESS_AND_CONFIG_LOADED
pgvector_query_proven_by_health=NO
openai_call_proven_by_health=NO
```

Health 200만으로 실제 pgvector Query나 OpenAI 호출을 PASS 처리하지 않는다. 실제
Provider와 검색은 새 Inquiry Happy Path에서 확인한다.

## 5. 공동검증 순서

1. Backend·AI·QA가 동일한 최종 main 40자리 SHA인지 확인한다.
2. AI `/health` HTTP 200을 확인한다.
3. 기존 실패 Inquiry·Submit Key를 재사용하지 않고 새 합성 Inquiry, 새 Idempotency
   Key와 새 Correlation ID를 생성한다.
4. 정상 Guidance Happy Path로 실제 Backend → AI 요청을 실행한다.
5. 실제 OpenAI·Readonly pgvector 응답과 AI 로그를 확인한다.
6. AIRun·Assessment·Guidance·Evidence 저장 여부를 확인한다.
7. 동일 요청 Replay에서 AI 추가 호출 0회와 중복 저장 0건을 확인한다.
8. Backend 요청·응답, AI 로그와 DB의 Correlation ID가 모두 일치하는지 확인한다.
9. 고객 Guidance GET 결과와 내부 Chunk·Score·Prompt·Trace 비노출을 확인한다.
10. Happy Path 결과를 확인한 뒤 NO_EVIDENCE·DANGER 추가 실행 여부를 결정한다.

## 6. AI 로그 지원 범위

AI 로그에서는 동일 Correlation의 다음 이벤트 순서를 확인한다.

```text
analysis_started
llm_guidance_completed
analysis_completed
```

공동 증거에는 Event 이름, Correlation 일치 여부, 실행 상태, 모델 식별자, Prompt
Version과 Token 사용 여부만 남긴다. Raw Prompt·고객 입력·Evidence 원문·Vector·Secret
값은 남기지 않는다.

## 7. 이번 단계에서 실행하지 않는 항목

```ini
additional_ai_code_change=NO
dongyoon_host_pending_migrations=NOT_APPLIED_AS_REQUESTED
injected_http_504=NOT_RERUN_PHASE_B_ACCEPTED
no_evidence=WAIT_HAPPY_PATH_RESULT
danger_total_stop=WAIT_HAPPY_PATH_RESULT
official_source_public_redistribution=HOLD
```

## 8. 공동 실행 ACK 요청

김은진 작업자가 다음 Secret 제거 상태를 회신하면 해당 시간에 Runtime과 Correlation
로그 확인을 지원한다.

```ini
qa_main_sha=<agreed_final_main_40sha>
ai_health=PASS
backend_health=PASS
ai_service_base_url=CONFIGURED_SAME_HOST
environment_ready=YES
joint_execution_time=<KST>
secret_values_printed=NO
```

위 ACK 수신 후 Happy Path를 먼저 실행한다. NO_EVIDENCE와 DANGER는 정상 저장·Replay·
Correlation 결과를 확인한 뒤 별도 실행 여부를 결정한다.
