# 5주차 Backend↔AI Integration Gate

> 감사일: 2026-08-11 14:33 KST
> 기준 Commit: `main@92b0674cd1a3376a2c058715cd5ef32222125755`
> 판정: **HOLD**
> 범위: 코드 존재, 실제 실행 증거, Mock·환경 차단을 분리해 판정

## 1. 한 줄 결론

Django→FastAPI 호출, AI Run·분석·안내 저장, Backend State Event 적용 코드는 존재한다. 그러나 현재 실제 소켓 통합 테스트는 FastAPI `mock` 모드이며, 실제 Multi-Agent·LLM·팀 pgvector·공식 Evidence 검증 연결이 완료되지 않아 3.5를 PASS로 닫을 수 없다.

## 2. 현재 구현·증거 판정

| 검토 항목 | 확인된 내용 | 현재 판정 |
|---|---|---|
| Backend→AI HTTP Client | `backend/integrations/ai/client.py`가 `httpx`로 FastAPI를 1회 호출 | CODE_PRESENT |
| Commit 이후 AI 호출 | 증상 제출·추가답변이 `transaction.on_commit`에서 `InquiryAIService` 호출 | CODE_PRESENT |
| 실제 소켓 통합 Test | Django LiveServer→AI Uvicorn 소켓 Test가 존재하지만 AI 모드를 `mock`으로 강제 | MOCK_HTTP_ONLY |
| Schema·Trace | 요청·응답 검증과 `correlation_id` 전달·AIRun·TransitionHistory 연결 코드 존재 | CODE_PRESENT |
| Backend 저장 | AIRun·SymptomAssessment·Guidance·GuidanceItem·InquiryQA 저장 코드 존재 | CODE_PRESENT |
| State 전이 권위 | AI는 Event 후보만 반환하고 Backend Guard·State Machine이 적용 | PASS_BY_CODE_REVIEW |
| AI Runtime | `PipelineRouter`가 `SingleRAGPipeline` 하나를 실행 | SINGLE_RAG_ONLY |
| Multi-Agent | 역할별 Agent·Supervisor·Handoff Runtime이 확인되지 않음 | NOT_IMPLEMENTED |
| 실제 LLM | `llm_client.py`, `model_router.py`가 설명 문자열 수준이며 생성은 규칙·Template 사용 | NOT_IMPLEMENTED |
| 팀 pgvector | Adapter와 opt-in 통합 Test는 있으나 현재 DSN·Embedding Revision·실행 결과 없음 | ENVIRONMENT_BLOCKED |
| Evidence 검증 | `InquiryAIService`는 Verifier 주입을 지원하지만 실제 Runtime 호출점에서 주입하지 않음 | NOT_WIRED |
| 정상·위험·근거 없음·Timeout | 단위·Mock 후보는 있으나 실제 LLM·팀 DB·Backend 같은 Commit 실행 없음 | NOT_RUN |

## 3. 주요 근거

### 확인된 연결 기반

- `backend/apps/inquiries/services/inquiry_transition_service.py`: 증상 저장 Commit 이후 AI 호출
- `backend/apps/inquiries/services/followup_answer_service.py`: 추가답변 Commit 이후 AI 재평가 호출
- `backend/apps/inquiries/services/inquiry_ai_service.py`: 결과 검증·저장·Backend Event 적용
- `backend/tests/integration/test_backend_ai_submit_symptom_live_http.py`: 실제 소켓과 DB 저장·Trace·Replay 검증 골격
- `ai/app/interfaces/http/routes/analysis_routes.py`: Mock·Local 모드 분리와 Timeout·검색 오류 응답
- `ai/app/integrations/vector_store/vector_store.py`: PostgreSQL/pgvector Exact Search Adapter
- `ai/tests/integration/test_pgvector_runtime.py`: 팀 pgvector 환경 제공 시 실행되는 opt-in Test

### PASS로 사용할 수 없는 경계

1. 소켓 Test가 `settings.AI_SERVICE_MODE = "mock"`을 사용하므로 실제 Pipeline·LLM·pgvector를 실행하지 않는다.
2. `PipelineRouter`는 `SingleRAGPipeline`을 직접 생성하며 실제 역할 기반 Multi-Agent Runtime이 아니다.
3. 생성 Stage는 `UsageGuidanceClassifier`의 결정론적 규칙을 사용하고 실제 LLM Provider를 호출하지 않는다.
4. 현재 환경에는 Backend·AI 가상환경, AI Service URL, 팀 pgvector DSN, Embedding Revision, LLM Key가 없다.
5. 실제 Runtime 호출은 `evidence_verifier`를 전달하지 않아 공식 근거가 있어도 검증된 Evidence ID로 승격되지 않는다.
6. `docs/testing/ai/week5-ai-entry-gate.md`의 “실제 LLM·Multi-Agent는 P1” 설명은 최신 이동윤 5주차 지침서의 필수 업무와 일치하지 않는다. 3.5 판정에는 최신 지침서의 실제 Multi-Agent·LLM 요구를 적용한다.

## 4. Blocker

| ID | 차단 내용 | 담당 | 해제 조건 |
|---|---|---|---|
| `W5-INT-001` | 실제 Multi-Agent Runtime 없음 | 이동윤 | 역할별 Agent·Router·Handoff·Fallback Source와 Test PASS |
| `W5-INT-002` | 실제 LLM Provider Client·Routing·Structured Output 없음 | 이동윤 | 제한된 실제 Provider 호출과 Integration Test PASS |
| `W5-INT-003` | 팀 pgvector 실행 환경·현재 Commit 결과 없음 | 이동윤·김은진·최지용 | 팀 DSN Secret 주입 후 제품·세대 Filter 검색 PASS |
| `W5-INT-004` | 공식 Evidence Verifier가 Backend Runtime에 미주입 | 최지용·이동윤 | `chunk_id`→공식 Evidence 검증·저장과 `SAFE_GUIDANCE_READY` 적용 Test PASS |
| `W5-INT-005` | 실제 Local 모드 Django→FastAPI 통합 Test 없음 | 최지용·이동윤 | Mock이 아닌 Local 모드 소켓 Test와 DB·Trace 증거 PASS |
| `W5-INT-006` | 세 담당자의 같은 Commit 실행 증거 없음 | 김은진·최지용·이동윤 | 같은 SHA의 정상·위험·근거 없음·Timeout 결과 취합 |

## 5. 현재 환경 확인

```text
backend_venv=false
ai_venv=false
ai_service_base_url=false
ai_vector_dsn=false
ai_embedding_revision=false
external_llm_key_hint=false
current_head_runtime_test=NOT_RUN
```

Secret·DSN·Token 값은 확인하거나 기록하지 않았다.

## 6. PM Gate 판정

```text
reviewer=윤승혁
baseline_commit=92b0674cd1a3376a2c058715cd5ef32222125755
backend_http_code=CODE_PRESENT
actual_django_fastapi_http=MOCK_HTTP_ONLY
multi_agent_runtime=NOT_IMPLEMENTED
actual_llm=NOT_IMPLEMENTED
team_pgvector=ENVIRONMENT_BLOCKED
backend_persistence=CODE_PRESENT_NOT_LIVE_VERIFIED
backend_state_authority=PASS_BY_CODE_REVIEW
normal_scenario=NOT_RUN
danger_scenario=NOT_RUN
no_evidence_scenario=NOT_RUN
timeout_scenario=NOT_RUN
same_commit_evidence=0/3
overall_decision=HOLD
```

최지용·이동윤·김은진의 실행 결과를 같은 Commit으로 받은 뒤 `PASS / CONDITIONAL_PASS / HOLD`를 다시 판정한다.
