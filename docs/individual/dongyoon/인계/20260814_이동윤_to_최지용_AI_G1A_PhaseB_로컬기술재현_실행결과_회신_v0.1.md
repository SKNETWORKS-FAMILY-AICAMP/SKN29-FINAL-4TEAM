# 이동윤 → 최지용: AI G1-A Phase B 이동윤 Host 기술재현 실행결과 회신 v0.1

> 작성일: 2026-08-14
>
> 요청 기준 main: `ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7`
>
> 실행 기준: `dongyoon@d6ab1e480e090369a03360aa385c74eff64720a6`
>
> 실행 환경: `이동윤_HOST_LOCAL_TECHNICAL_REPRODUCTION`, Python `3.13.13`, PostgreSQL `16.15`, pgvector `0.8.6`
>
> 제외: Secret·DSN·Password·Fixture Vector·고객 입력·공식 원문 본문

## 1. 결론

AI G1-A Phase B의 실제 OpenAI 호출, Readonly pgvector 검색, 계약 3.0.0 Strict HTTP
Smoke와 HTTP 504 노출을 이동윤 Host의 로컬 기술재현환경에서 통과했다. 요청 기준 main은 실행
HEAD의 조상이며, 두 Commit 사이 AI·계약·Canonical 입력에는 차이가 없다.

다만 이 결과를 김은진 Host의 공식 공동 실행이나 Backend 저장·상태 전환 E2E로
확대하지 않는다. Timeout은 실제 HTTP 504 응답을 확인했지만, 실제 OpenAI Provider
네트워크 장애가 아니라 기존 테스트 계약과 동일한 Pipeline Stage Timeout 주입이다.

```ini
reviewer=이동윤
fixed_main_commit=ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7
execution_branch=dongyoon
execution_commit=d6ab1e480e090369a03360aa385c74eff64720a6
fixed_main_is_execution_ancestor=PASS
g1a_relevant_inputs_diff=NONE
execution_scope=이동윤_HOST_LOCAL_TECHNICAL_REPRODUCTION

phase_a_decision=PASS
ai_exporter_commit=626a7a4584d381085615d80b2269b8155322176d
ai_exporter_paths=ai/scripts/export_canonical_embedding_fixture.py,ai/tests/unit/test_canonical_embedding_fixture_exporter.py
exporter_tests=10_passed_0_failed
fixture_schema_version=1.0.0
fixture_status=GENERATED_FROM_APPROVED_BASELINE_PENDING_DB_IMPORT
fixture_model_revision=5617a9f61b028005a4858fdac845db406aefb181
fixture_embedding_dtype=FLOAT32
fixture_rows_dimension=7x1024
fixture_row_order=chunk_id_ASC
fixture_nfc=7/7
fixture_sha256=759379308abdafbe66ef205e13cd829d8ad49714d0b824032eb0fbc58546d019
artifact_delivery=DELIVERED_TO_QA_HOST_BY_PRIOR_QA_ACK
artifact_repo_commit=NO

qa_environment_ready=YES_BY_QA_ACK
phase_b_g1a=PASS_이동윤_HOST_TECHNICAL_REPRODUCTION
actual_openai=PASS
actual_model=gpt-4.1-mini-2025-04-14
actual_token_usage=VERIFIED_GT_0,total_1180
actual_pgvector=PASS
retrieval_object=backend_ai_rag_chunks_v1
expected_evidence_hit=PASS,RAG-WPUJAC104DWH-LOW-FLOW-001
strict_http_smoke=PASS
schema_3_0_0=PASS
guidance_only_boundary=PASS
correlation_actual=PASS
timeout_actual_http_504=PASS_INJECTED_PIPELINE_STAGE_TIMEOUT
actual_provider_network_timeout=NOT_RUN
backend_submit_persistence_e2e=NOT_RUN
official_qa_host_joint_rerun=NOT_PROVEN_BY_THIS_EXECUTION

source_policy_review=PENDING
openai_evidence_summary_transmission=APPROVED_FOR_LOCAL_G1A_ONLY_BY_REQUESTER
official_source_public_redistribution=HOLD
secret_values_printed=NO
fixture_vector_printed=NO
```

## 2. 선행 DB·계약 Gate

| 검증 | 결과 | 범위 |
| --- | --- | --- |
| Canonical Import 최초 적용 | Chunk 7, Embedding 7 | 이동윤 Host 로컬 DB |
| 동일 Fixture Replay | created 0, updated 0 | 멱등 PASS |
| Crosswalk·Page Link | 7/7, Link 8 | PASS |
| Readiness Audit | `READY`, blocker 0 | PASS |
| AI Readonly View | 8열, 7행, 고유 Chunk 7 | PASS |
| AI Role 정책 | View SELECT 허용, Base Table·DML·CREATE 거부 | PASS |
| AI pgvector Integration | `1 passed in 9.97s` | 실제 DB Query |
| Backend 표적 회귀 | `81 passed in 11.88s` | Unit·계약, 실제 Backend E2E 아님 |
| PostgreSQL Role Matrix | `1 passed` | 실제 Role 권한 |

Fixture SHA, Canonical Source SHA, Crosswalk와 View 결과는 서로 일치했다. Fixture와
Vector 본문은 출력하거나 Git에 추가하지 않았다.

## 3. 실제 OpenAI Runtime 검증

보호 Loader로 현재 Process에만 환경을 주입하고 다음을 실행했다.

```powershell
. .\scripts\deployment\import_team_integration_env.ps1 -Role AI -RequireOpenAIKey
.\ai\.venv\Scripts\python.exe -B -m ai.scripts.verify_local_runtime
```

```ini
exit_code=0
result=PASS
analysis_status=SUCCEEDED
failure_stage=null
model_name=gpt-4.1-mini-2025-04-14
prompt_version=customer_guidance/v2
tokens_used=1180
expected_evidence_id=RAG-WPUJAC104DWH-LOW-FLOW-001
```

실제 Provider 인증 사전검증도 인증된 요청의 누락 Payload 오류인 HTTP 400 JSON으로
확인했다. API Key 값과 Request 본문은 기록하지 않았다.

## 4. Local Strict HTTP Smoke

보호 환경을 주입한 Uvicorn을 `mode=local`로 기동하고 `ai/README.md`의 Strict Smoke
전체 조건을 실행했다. `--expected-guidance-message`를 생략하지 않았다.

```ini
exit_code=0
health=PASS
analysis=PASS
analysis_http_status=200
analysis_result_status=SUCCEEDED
analysis_failure_stage=null
evidence_count=5
expected_evidence_hit=PASS
verified_evidence=PASS
guidance_message_match=PASS
correlation_trace=PASS
```

동일 요청의 Header·Body·AI 구조화 로그에서 Correlation을 확인했다. 로그에는
`analysis_started` → `llm_guidance_completed` → `analysis_completed`가 같은
Correlation로 기록됐고, 모델·Prompt·Input 1052·Output 128·Total 1180 Token을
확인했다.

## 5. 계약 3.0.0·GUIDANCE_ONLY 경계

`contracts/ai/responses/SymptomAnalysisResponse.schema.json`은
`x-contract-version=3.0.0`이고 `additionalProperties=false`다. Strict Smoke는 공개
응답 전체를 이 Schema로 검증했다.

공개 응답에는 Evidence Reference와 안내 제안만 있으며 `event_candidate`,
`event_code`, `target_state`, `state_transition`, `EvidenceCardDTO` 또는
`evidence_card` 필드가 없다. 따라서 AI가 Backend 상태 적용이나 공개 Evidence 승인권을
침범하지 않는 `GUIDANCE_ONLY` 경계를 PASS로 판정했다.

## 6. HTTP 504 검증과 정확한 범위

별도 임시 Uvicorn Process에서 기존 단위 테스트와 동일하게
`PipelineStageTimeoutError("RETRIEVING")`를 주입하고 실제 HTTP 요청을 보냈다.

```ini
http_status_504=PASS
error_code_AI_TIMEOUT_01=PASS
retryable_true=PASS
failure_stage_RETRIEVING=PASS
retry_count_0=PASS
success_false=PASS
request_echo_fields=PASS
correlation_body_header_log=PASS
timeout_driver=LIVE_HTTP_INJECTED_PIPELINE_STAGE_TIMEOUT
actual_provider_network_timeout=NOT_RUN
```

초기 두 번의 임시 Harness 기동은 Module Search Path와 `python -c` 인용 문제로
실패했다. 제품 Runtime 요청 전에 발생한 Harness 기동 실패이며, 수정 후 실제 HTTP
504 검증은 세 번 재현했다. 임시 Launcher는 검증 후 삭제했고 제품 코드는 변경하지
않았다.

## 7. 남은 경계와 다음 담당자

- 이번 PASS는 `이동윤_HOST_LOCAL_TECHNICAL_REPRODUCTION` 범위의 기술재현이다. 김은진 Host 공동
  실행 결과가 필요하면 같은 고정 입력과 보호 Loader로 재실행 ACK가 필요하다.
- Backend AIRun·Assessment·Guidance 저장, Idempotency Replay와 최종 상태 전환은
  실행하지 않았다. 최지용의 G1-B Submit 범위다.
- Django `vector_dims(unknown)` 사전검증 경고는 저장 DB Constraint·Replay·검색을
  막지 않은 `P1_BACKEND_VALIDATION_WARNING_NON_BLOCKING`으로 유지한다.
- `jsonschema.RefResolver` Deprecation Warning은 이번 실행의 비차단 유지보수 항목이다.
- `source_policy_review=PENDING`이므로 로컬 G1-A 실행 승인과 공식 원문 공개·재배포
  승인을 같은 것으로 해석하지 않는다. 공개·재배포는 계속 HOLD다.

```ini
next_owner=최지용_Backend
next_action=AI 보호환경 재주입과 Service 기동 확인 후 G1-B Submit·저장·Replay 실행
g1a_service_after_test=STOPPED
postgres_container_after_test=HEALTHY_VOLUME_PRESERVED
blockers_for_local_g1a_technical_reproduction=NONE
blockers_for_official_joint_e2e=OFFICIAL_QA_HOST_SCOPE_NOT_PROVEN;BACKEND_SUBMIT_PERSISTENCE_NOT_RUN
```

## 8. Secret 없는 증거 위치

- `contracts/ai/responses/SymptomAnalysisResponse.schema.json`
- `ai/scripts/verify_local_runtime.py`
- `ai/scripts/smoke_test.py`
- `ai/tests/integration/test_pgvector_runtime.py`
- `.runtime/g1a/20260814-173551/ai.stderr.log`
- `.runtime/g1a/timeout-20260814-174023/timeout.stdout.log`
- `.runtime/g1a/timeout-20260814-174023/timeout.stderr.log`

`.runtime/**` 증거는 Git 산출물이 아닌 로컬 Runtime 증거다. 전달 시 Secret·DSN·원문
또는 Vector가 포함되지 않았는지 다시 확인하고, 공개 저장소에는 올리지 않는다.
