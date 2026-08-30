# E05 — Single RAG vs Multi-Agent Orchestration Ablation

- Git SHA: `68666b88fcf33273906710f23a8d17f7f1faa07f`
- Result: `DRAFT_DIAGNOSTIC`
- Scenarios: `12`
- Repeats: `10`
- Paired Runs: `120`

## Primary Metrics

| Metric | Result |
|---|---:|
| parity_non_regression_rate | 1.0 |
| feedback_recovery_rate_single_rag | 0.0 |
| feedback_recovery_rate_multi_agent | 1.0 |
| danger_provider_avoidance_single_rag | 1.0 |
| danger_provider_avoidance_multi_agent | 1.0 |
| multi_handoff_trace_presence_rate | 1.0 |
| multi_raw_symptom_metadata_leak_rate | 0.0 |
| trace_context_preservation_single_rag | 1.0 |
| trace_context_preservation_multi_agent | 1.0 |

## Scenario-balanced Task Success

- Single RAG: `0.75`
- Multi-Agent: `1.0`

이 성공률은 실제 사용자 증상 분포를 반영한 production accuracy가 아니라, 정상/위험/문진/Evidence-gap/no-evidence 분기를 고르게 포함한 진단용 Scenario Set의 성공률이다.

## Interpretation Guardrails

- 정상 경로의 목표는 Multi-Agent가 Single RAG보다 더 다른 답을 만드는 것이 아니라 공개 계약을 보존하는 것이다.
- Multi-Agent의 구조적 우위는 검색 후 Evidence gap에서 추가 질문으로 복구하는 feedback branch와 audit handoff에 있다.
- Retrieval와 LLM은 deterministic test double로 고정하여 orchestration 변수만 비교했다.
- PipelineRouter의 Reliability Harness는 제외했다. Harness 효과는 E06에서 별도로 평가한다.
- 따라서 E05 결과는 일반 LLM 정확도나 실제 서비스 트래픽 빈도를 의미하지 않는다.
