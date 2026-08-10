# 5주차 Multi-Agent 책임·Routing 계약 초안

> 작성일: 2026-08-10 KST  
> 상태: `TARGET_CONTRACT_NOT_RUNTIME_IMPLEMENTATION`  
> 현재 Runtime: `SingleRAGPipeline`  
> 적용 조건: 단일 Workflow 팀 DB·Backend 실제 HTTP 기준선 고정 후

## 1. 현재와 목표를 분리한다

현재는 하나의 `PipelineContext`를 LangGraph Stage가 순차 처리하는 결정론적
Workflow다. Stage 파일이 여러 개라는 이유로 Agent 또는 Multi-Agent라고 부르지
않는다. 이 문서는 전환 시 지켜야 할 책임 계약이며 구현 완료 증거가 아니다.

목표 Runtime은 Supervisor가 구조화된 State와 명시적인 Routing 조건으로 독립
Agent를 선택하고, Agent별 입력·출력·Tool·실패 경계를 검증하는 구조다.

## 2. Agent 책임 계약

| Agent | 독립 책임 | 입력 | 출력·쓰기 소유권 | 허용 Tool | 실패·Retry |
|---|---|---|---|---|---|
| Supervisor | Routing·Hop 제한·종료 판정 | Routing Signals, Trace | `next_agent`, `hop_count`, 종료 상태 | 없음 | 비즈니스 판단·재시도 금지 |
| Symptom | 증상 구조화·누락 후보 | 최소 고객 진술, 이전 답변 | `structured_symptom`, 누락 후보 | Rule Structurer, 선택적 LLM Adapter | Schema Invalid만 제한 재생성, Rule Fallback |
| Safety | 위험도·안전 규칙·사용 제한 후보 | 고객 진술, 선택 증상 | `safety_assessment` | `safety_rules.yaml`, Guard | 자동 재시도 금지, 모든 외부 판단보다 우선 |
| Retrieval | 지원 범위 검증·공식 근거 검색 | 모델 코드, 구조화 Query | `retrieval_outcome`, `evidence_references` | bge-m3, pgvector, Manifest | 일시 오류 1회, 설정·정책 오류 0회 |
| Guidance | 근거 범위 안의 안내 초안 | 안전 판정, 공식 Evidence | `usage_guidance` | Rule/Template, 선택적 LLM Adapter | 근거 없음이면 자유 생성 금지 |
| Validation | Schema·Grounding·금지 표현 최종 검사 | 모든 공개 후보 결과 | `validation_result` | Validator만 | 재시도 직접 수행 금지 |
| Consultation Summary | 상담사 검토용 요약 초안 | 고객 진술, 상담 기록, 검증된 AI 결과 | 상담 요약 계약 결과 | 결정론적 Formatter, 선택적 LLM Adapter | LLM 실패 시 결정론적 기준선 |

기사 브리핑은 상담 요약·Backend 실제 E2E 이후 Formatter/Prototype으로 다룬다.

## 3. Shared State 최소 원칙

| State 필드 | 읽기 | 쓰기 | 공개 여부 |
|---|---|---|---|
| `trace_context` | 전체 Agent | 최초 요청 Adapter만 | Backend 추적용 |
| `raw_symptom` | Symptom·Safety | 요청 Adapter만 | Agent 외부 재노출 금지 |
| `model_code` | Retrieval·Validation | 요청 Adapter만 | 공개 모델 코드만 허용 |
| `structured_symptom` | Retrieval·Guidance·Summary | Symptom만 | 계약된 필드만 |
| `safety_assessment` | Supervisor·Guidance·Validation·Summary | Safety만 | 공개 계약 대상 |
| `evidence_references` | Guidance·Validation·Summary | Retrieval만 | AI 후보이며 최종 Card 아님 |
| `usage_guidance` | Validation·Summary | Guidance만 | Backend 검토 대상 |
| `validation_result` | Supervisor | Validation만 | 내부 판정 |
| `processing_traces` | Supervisor·감사 Adapter | 각 Agent 자기 항목만 Append | 고객 공개 금지 |
| `hop_count` | Supervisor | Supervisor만 | 고객 공개 금지 |

금지 State는 Backend 내부 정수 PK, Secret, Token, DSN, 전체 고객 Profile,
불필요한 개인정보다. Agent가 Backend 업무 상태를 쓰지 않는다.

## 4. Routing 우선순위

```text
START
→ Symptom
→ Safety
→ danger이면 Guidance(Safety Template)
→ danger가 아니고 누락 질문이 필요하면 질문 결과로 종료
→ Retrieval
→ 근거 0건이면 Guidance(PENDING_CONSULTATION)
→ 근거가 있으면 Guidance(Evidence Grounded)
→ Validation
→ valid이면 END
→ invalid이면 허용된 1회 보정 또는 상담 Fallback
→ END
```

Safety는 누락 필드·Retrieval·LLM보다 우선한다. 위험 입력에서는 Vector Store가
없어도 안전 안내를 반환할 수 있어야 한다.

## 5. Routing Matrix

| 현재 결과 | 다음 Agent·종료 | 이유 |
|---|---|---|
| 구조화 전 | Symptom | 공개 Schema 입력 생성 |
| 구조화 완료 | Safety | 위험 우선 |
| `risk_level=danger` | Guidance Safety Template | Retrieval 의존 없이 사용 제한 |
| 비위험·답변 가능한 누락 필드 | 질문 결과 종료 | 근거 없는 안내보다 질문 우선 |
| 비위험·검색 필요 | Retrieval | 공식 근거 확보 |
| `retrieval_outcome=FOUND` | Guidance | 근거 범위 생성 |
| `retrieval_outcome=EMPTY` | Guidance Fallback | 상담 전환, 자유 생성 금지 |
| Retrieval 설정 오류 | 오류 종료 | 503, 비재시도 |
| Retrieval 일시 오류 | Retrieval 최대 1회 | 계약된 유일 Retry |
| Guidance 완료 | Validation | 최종 안전·근거 검사 |
| Validation PASS | 종료 | Backend 후보 결과 반환 |
| Validation FAIL·보정 미사용 | Guidance 1회 또는 Fallback | 무한 재생성 차단 |
| Validation FAIL·보정 사용함 | 상담 Fallback 종료 | 최대 횟수 소진 |

## 6. Handoff 계약

각 Handoff에는 다음만 기록한다.

```text
correlation_id
ai_request_id
state_version
from_agent
to_agent
reason_code
started_at
latency_ms
status
retry_count
```

고객 원문, Prompt, Evidence 원문, Secret은 Handoff Log에 기록하지 않는다.
초기 최대 Hop은 Analyze Workflow `8`로 제한한다. 같은 Agent의 연속 재호출은
Retry 또는 Validation 보정처럼 Matrix에 정의된 경우만 허용한다.

## 7. Timeout·Retry

전체 HTTP 제한은 30초다. 현재 Stage 하위 제한은 Structuring 5초, Safety 3초,
Retrieval 5초, Generation 15초, Validation 3초다. 하위 제한의 합을 전체 예산으로
오해하지 않으며, 전체 Deadline이 항상 우선한다. Agent 전환 시 남은 예산을
확인하고 새 작업이 예산을 넘으면 시작하지 않는다.

Retry는 Retrieval·향후 LLM Provider의 일시적 연결·Timeout·Rate Limit에만
최대 1회다. Schema·설정·입력·지원 범위·Safety 오류는 재시도하지 않는다.

## 8. Fallback Matrix

| 실패 | Fallback | 공개 결과 |
|---|---|---|
| LLM 미설정·장애 | Rule/Template | 가능한 계약 결과 또는 상담 전환 |
| Vector 설정 누락 | 없음 | HTTP 503 구성 실패 |
| 정상 검색 0건 | No Evidence Policy | HTTP 200 `FALLBACK`, `PENDING_CONSULTATION` |
| 위험+Vector 장애 | Safety Template | 위험 사용 제한, 근거 빈 배열 |
| Validation 실패 | 1회 보정 후 상담 Fallback | 검증 실패 결과를 정상 저장 금지 |
| 전체 Timeout | 취소 신호 | HTTP 504, 실제 실패 단계·Retry 수 |
| Supervisor Hop 초과 | 상담 Fallback | 내부 Loop를 숨기지 않고 실패 기록 |

## 9. 활성화 Gate

다음 조건 전에는 `multi_agent`를 기본 Runtime으로 전환하지 않는다.

1. 단일 Workflow 팀 DB Retrieval 재검증 PASS
2. Backend→FastAPI 실제 HTTP·저장 E2E PASS
3. Agent별 Pydantic 입력·출력과 Unit Test PASS
4. Supervisor Routing·Handoff·Hop 제한 Test PASS
5. 동일 평가셋에서 Single Workflow 대비 안전·품질·지연·실패율 비교
6. 실제 LLM Provider가 없으면 `external_llm_used=false`를 유지

## 10. 현재 구현된 선행 기준선

- Safety·Retrieval·Guidance·Validation 결정론적 Stage
- 공식 근거 검증과 근거 없음 Fallback
- 전체 30초·Retrieval 내부 최대 1회 Retry
- 계약 3.0.0과 추적 ID
- 상담 요약 결정론적 Generator·Formatter Fallback

이 목록은 Agent Runtime 구현 완료 목록이 아니다.

