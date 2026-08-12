# 5주차 Multi-Agent QA 계획

> 담당: 김은진 — 데이터·QA·DevOps
> 작성일: 2026-08-11 KST
> 현재 Runtime: `SingleRAGPipeline`
> 목표 Runtime: 역할별 Agent·Supervisor·Handoff가 있는 Multi-Agent
> 현재 판정 원칙: **현재 단일 Workflow 기준선과 목표 Multi-Agent 완료를 분리한다.**

## 1. 목적과 완료 경계

이 계획은 구조화·안전·검색·안내·검증 단계의 현재 재현 범위와 향후
Multi-Agent Runtime의 필수 Gate를 하나의 Test ID 체계로 관리한다. Stage 파일이
여러 개이거나 문서에 Agent 역할이 정의됐다는 이유로 Multi-Agent 구현 완료로
판정하지 않는다.

`MULTI_AGENT_PASS`는 다음 조건을 모두 만족한 동일 Commit에서만 사용할 수 있다.

1. 역할별 Agent 입력·출력과 단독 Unit Test가 존재한다.
2. Supervisor가 명시적인 Routing·Handoff·Hop 제한을 적용한다.
3. 위험·누락 정보·근거 있음·근거 없음·장애가 승인된 종료 상태로 수렴한다.
4. 실제 팀 pgvector와 제한된 실제 LLM Provider 결과가 Mock과 구분된다.
5. Django→FastAPI→Django DB·State·Trace가 실제 HTTP에서 재현된다.

## 2. 실행 Mode와 상태

| 값 | 의미 |
|---|---|
| `CURRENT_UNIT` | 현재 `SingleRAGPipeline` 또는 단계 단위의 결정적 Test |
| `ROOT_CONTRACT` | Root `tests/**`에서 Data·계약·서비스 경계를 검증하는 Test |
| `LIVE_INTEGRATION` | 실제 PostgreSQL·pgvector·LLM·HTTP가 필요한 Test |
| `PASS` | 현재 Commit에서 명령과 Exit Code 0이 확인됨 |
| `FAIL` | Assertion 또는 Runtime 오류로 실패함 |
| `INTEGRATION_BLOCKED` | 필요한 Runtime·환경·담당자 수정이 없어 실행할 수 없음 |
| `NOT_RUN` | 아직 실행하지 않았거나 선행 Gate가 닫히지 않음 |

Mock·Fixture Test는 현재 회귀 증거로 사용할 수 있지만 `LIVE_INTEGRATION` PASS로
승격하지 않는다. 외부 환경이 없어서 실행되지 않은 Test도 PASS 수에 포함하지
않는다.

## 3. Test Matrix

| Test ID | 경계 | 기대 결과 | Mode | 현재 실행 자산 |
|---|---|---|---|---|
| `W5-MA-STR-001` | 증상 구조화·누락 정보 | 확인되지 않은 값만 누락 처리하고 질문 후보 생성 | `CURRENT_UNIT` | `ai/tests/unit/test_structuring.py::test_information_poor_input_generates_deterministic_questions` |
| `W5-MA-ROU-001` | 추가 질문 Routing | 정보 부족 시 근거 없는 안내 대신 질문 결과로 종료 | `CURRENT_UNIT` | `ai/tests/unit/test_structuring.py::test_previous_answer_populates_field_and_blocks_duplicate_question` |
| `W5-MA-SAF-001` | 위험 우선 Routing | `danger`는 Vector 상태와 무관하게 사용 제한·상담 경로 | `CURRENT_UNIT`·`ROOT_CONTRACT` | `ai/tests/unit/test_pipeline.py::test_danger_path_does_not_require_vector_store`, `tests/safety/test_week5_ai_safety_crosswalk.py` |
| `W5-MA-RET-001` | 공식 근거 검색 | 승인 모델·세대·문서 Filter와 검증 근거만 반환 | `CURRENT_UNIT` | `ai/tests/unit/test_retrieval.py::test_store_results_are_revalidated_after_search` |
| `W5-MA-RET-002` | 근거 없음 | `FALLBACK`·`PENDING_CONSULTATION`·빈 Evidence로 종료 | `CURRENT_UNIT`·`ROOT_CONTRACT` | `ai/tests/unit/test_pipeline.py::test_no_evidence_uses_pending_consultation_branch`, Root Safety Test |
| `W5-MA-RET-003` | 일시 검색 장애 | 최대 1회 Retry 뒤 성공 또는 명시적 실패 | `CURRENT_UNIT` | `ai/tests/unit/test_pipeline.py::test_transient_search_failure_retries_once_then_succeeds` |
| `W5-MA-FAL-001` | 설정 오류와 0건 분리 | Vector 미설정은 근거 없음으로 위장하지 않고 503 | `CURRENT_UNIT` | `ai/tests/unit/test_api_routes.py::test_local_mode_missing_vector_config_is_non_retryable_503` |
| `W5-MA-TIM-001` | 전체·단계 Timeout | 504, 실패 단계·Retry 수·추적 ID를 보존 | `CURRENT_UNIT`·`ROOT_CONTRACT` | `ai/tests/unit/test_api_routes.py::test_stage_timeout_returns_stage_specific_504`, Root AI Contract Test |
| `W5-MA-VAL-001` | Schema·금지 표현 검증 | 잘못된 요청·응답과 금지 표현을 공개 결과로 승격하지 않음 | `CURRENT_UNIT`·`ROOT_CONTRACT` | `ai/tests/unit/test_schemas_and_configs.py`, `tests/contract/ai/test_ai_contract_examples.py` |
| `W5-MA-TRC-001` | Trace·비노출 | Correlation을 보존하고 원문·Prompt·Secret을 로그·오류에서 제외 | `CURRENT_UNIT`·`ROOT_CONTRACT` | `ai/tests/unit/test_api_routes.py::test_structured_log_excludes_customer_text`, Root AI Contract Test |
| `W5-MA-HOP-001` | Supervisor Handoff·Loop | 허용 Handoff만 수행하고 최대 Hop 초과 시 상담 Fallback | `LIVE_INTEGRATION` | 실제 Supervisor Runtime 필요 |
| `W5-MA-LLM-001` | 실제 LLM | Structured Output·Timeout·1회 Retry·Rule Fallback 구분 | `LIVE_INTEGRATION` | Provider Client·Key·실행 Mode 필요 |
| `W5-MA-PGV-001` | 팀 pgvector | 1024차원·Revision·Index·제품/세대 Filter 실제 Query | `LIVE_INTEGRATION` | 승인 DSN·Embedding Revision 필요 |
| `W5-MA-HTTP-001` | Backend↔AI 최소 수직 연결 | 실제 HTTP→Schema→Event→DB→Correlation Trace | `LIVE_INTEGRATION` | 독립 PostgreSQL·Backend·AI Local Mode 필요 |
| `W5-MA-E2E-001` | 대표 사용자 흐름 | 고객→AI→상담/방문이 같은 Inquiry·State로 종료 | `LIVE_INTEGRATION` | 모든 5주차 필수 Gate PASS 후 조건부 실행 |

## 4. 실행 순서와 증거

1. Root Contract·Safety Test를 먼저 실행해 계약·Data 경계를 고정한다.
2. AI Unit 전체를 실행해 `CURRENT_UNIT` Test ID의 결과를 취합한다.
3. pgvector 환경이 명시된 경우에만 `W5-MA-PGV-001`을 실행한다.
4. 실제 Provider Mode가 명시된 경우 최소 정상·Schema 오류·Timeout을 실행한다.
5. 독립 PostgreSQL과 두 서비스가 준비된 경우에만 `W5-MA-HTTP-001`을 실행한다.
6. 실행 결과마다 Commit SHA, 명령, PASS·FAIL·SKIP, Exit Code와 환경 구분을 기록한다.

실패 증거에는 고객 원문, DSN, Token, Prompt, Vector 원문을 저장하지 않는다.
Live Test의 수정 대상은 요청·응답·DB·State 증거로 좁힌 뒤 담당 영역에 인계한다.

## 5. 현재 예상 판정

- 현재 단일 Workflow의 계약·안전·Fallback 기준선: 실행 후 `PASS/FAIL` 판정
- 목표 Multi-Agent Runtime: `TARGET_RUNTIME_NOT_IMPLEMENTED`
- 실제 LLM·팀 pgvector·Backend HTTP: 환경 제공 전 `INTEGRATION_BLOCKED`
- 대표 E2E: 5주차 필수 Gate 전 `NOT_RUN`

따라서 현재 Unit과 Root Test가 모두 통과해도 전체 결과는
`CURRENT_BASELINE_PASS / TARGET_RUNTIME_NOT_IMPLEMENTED`를 유지한다.
