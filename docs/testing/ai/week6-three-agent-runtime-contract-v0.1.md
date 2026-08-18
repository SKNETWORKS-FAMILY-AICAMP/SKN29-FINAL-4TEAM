# 6주차 3-Agent Runtime 책임·Routing 계약 v0.1

> 작성일: 2026-08-18 KST  
> 기준 Commit: `d00fca53fa024dd50624a42adb1e78c9582fd0eb`  
> 상태: `TARGET_CONTRACT / CANDIDATE_RUNTIME_DEFAULT_OFF`  
> 기존 기준선: `SingleRAGPipeline` 유지

## 1. 목적과 완료 경계

6주차 업무 지침의 세 역할을 실제 입력·출력·허용 Tool·Handoff가 분리된
Runtime으로 구현한다. 기존 Stage 파일의 이름만 Agent로 바꾸지 않으며, 기본
`local` 실행 경로는 비교와 복귀를 위해 `SingleRAGPipeline`으로 유지한다.

후보 Runtime은 `AI_PIPELINE_RUNTIME=multi_agent`가 현재 Process에 명시된 경우에만
선택한다. 이 문서와 후보 Runtime 존재만으로 서비스 E2E 또는 운영 전환 완료를
주장하지 않는다.

## 2. 3-Agent 책임 계약

| Agent | 독립 책임 | 입력 | 소유 출력 | 허용 Tool·Stage | 하지 않는 일 |
|---|---|---|---|---|---|
| Symptom Analysis | 고객 입력 구조화, 안전 우선 검사, 누락 정보와 중복 없는 질문 생성 | 고객 원문, 선택 증상, 이전 답변 | `structured_symptom`, `safety_assessment`, `missing_fields`, `followup_questions` | Structurer, Safety Rule, Missing Field Checker, Duplicate Question Guard | 최종 근거 확정, Backend 상태 변경 |
| Evidence Analysis | 제품·세대 정책을 적용한 공식 근거 검색과 충분성 판정 | 구조화 증상, 모델 코드, 검색 질의 | `retrieval_outcome`, `evidence_references`, `evidence_sufficient`, `request_more_information` | Embedding, pgvector, Manifest, Evidence Validator | 고객 최종 문구 생성, Safety 판정 변경 |
| Care Decision | Safety·Evidence·질문 대기를 종합한 고객 안내 후보와 최종 출력 검증 | Symptom·Evidence 출력 | `usage_guidance`, `requires_consultation`, 검증 완료 결과 | 결정론적 Safety/Fallback, 제한된 Guidance LLM, Output Validator | Backend Event 적용, 상담·방문 최종 결정 |

`Safety Rule`, Embedding, Retriever, Evidence Validator, Output Validator, Timeout,
Cancellation, Trace는 공통 Tool·Guard로 유지한다. 특히 Safety와 최종 Validation은
Agent의 자유 판단으로 우회할 수 없다.

## 3. Shared State

공유 State는 기존 `PipelineContext`의 공개 계약 후보와 아래 내부 제어 필드로
구성한다.

| 내부 필드 | 작성 주체 | 목적 |
|---|---|---|
| `current_agent` | Supervisor | 현재 실행 역할 추적 |
| `handoffs` | Supervisor append-only | 구조화된 역할 전환 감사 |
| `hop_count` | Supervisor | 무한 Loop 차단 |
| `max_hops` | Runtime 설정 | Analyze 1회당 최대 8 Hop |
| `awaiting_customer_input` | Supervisor | 정보 부족과 NO_EVIDENCE 분리 |
| `feedback_handoff_count` | Supervisor | 한 실행 안의 Evidence→Symptom 재전달 1회 제한 |

Handoff에는 추적 식별자, 역할, 사유 코드, Hop, 상태, 소요시간만 기록한다.
고객 원문, Prompt, Evidence 본문, Vector, Secret, DSN은 기록하지 않는다.

## 4. Routing과 Feedback Loop

```text
START
→ Symptom Analysis
   ├─ danger → Care Decision(Safety Rule) → END
   └─ non-danger → Evidence Analysis
        ├─ Evidence 있음 → Care Decision(Guidance) → END
        ├─ Evidence 없음 + 추가 질문 있음
        │    → Symptom Analysis feedback
        │    → 고객 답변 대기 결과 → END
        └─ Evidence 없음 + 추가 질문 없음
             → Care Decision(NO_EVIDENCE) → END
```

고객 답변은 같은 HTTP 실행 안에서 기다리지 않는다. Backend가 질문을 저장하고
고객이 답한 뒤 동일 `inquiry_id`의 새 상태 버전으로 다시 호출하면 Symptom Agent가
`previous_answers`를 반영하고 Evidence Agent가 재검색한다.

정확히 같은 질문은 `DuplicateQuestionGuard`로 다시 반환하지 않는다. 한 실행의
Evidence→Symptom Feedback은 최대 1회, 전체 Hop은 최대 8회다.

## 5. 정보 부족과 NO_EVIDENCE 분리

| 조건 | AI 결과 | Backend Event 후보 |
|---|---|---|
| 비위험·추가 질문 존재·Evidence 부족 | `SUCCEEDED`, 질문 반환, 고객 답변 대기 | 없음 |
| 비위험·추가 질문 없음·Evidence 0건 | `FALLBACK / RETRIEVING`, `PENDING_CONSULTATION` | `NO_EVIDENCE` |
| danger | 결정론적 사용 제한, LLM·Retrieval 생략 | `DANGER_DETECTED` |
| 공식 Evidence 있음·질문 없음 | 검증된 근거 범위 Guidance | `SAFE_GUIDANCE_READY` |

`NO_EVIDENCE`를 질문 Loop로 되돌리지 않는다. 고객 정보 부족과 공식 근거 부재를
같은 상태로 취급하지 않는다.

## 6. Runtime 선택과 복귀

```ini
AI_PIPELINE_RUNTIME=single_rag   # 기본값·현재 안정 기준선
AI_PIPELINE_RUNTIME=multi_agent  # 후보 Runtime 명시 실행
```

지원하지 않는 값은 묵시적으로 Single RAG로 우회하지 않고 구성 오류로 중단한다.
공개 HTTP Schema `3.0.0`은 변경하지 않으며 Agent Handoff는 내부 결과에만 남긴다.

## 7. 활성화 Gate

기본 Runtime 전환 전 다음을 모두 확인한다.

1. Agent별 입력·출력 Unit Test
2. danger, Evidence 있음, 정보 부족 Feedback, NO_EVIDENCE Routing Test
3. Hop 제한·중복 질문 방지·Timeout·Fallback Test
4. 동일 평가셋의 Single RAG 대비 안전·검색·응답·Latency·Token·비용 비교
5. 실제 팀 pgvector·OpenAI·Backend HTTP의 같은 Commit 실행
6. 새 Inquiry→질문→답변→재검색→Guidance와 Replay 검증
7. Mobile·Web 상담 인계는 담당 Runtime과 별도 공동 E2E로 판정

`consultation_handoff`는 `SymptomAnalysisResponse`에 임의 추가하지 않는다. 기존
`ConsultationSummaryResponse`를 별도 호출하거나 Backend가 검증된 결과를 조합하는
방식 중 하나를 Backend 담당자와 확정한다.
