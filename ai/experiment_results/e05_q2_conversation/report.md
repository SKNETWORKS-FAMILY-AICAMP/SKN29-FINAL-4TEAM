# E05-Q2 — 검색 실패 후 2턴 대화 복구 실험

- Git SHA: `95f90f843124373fc97c6cd9e258b1427e0cbde8`
- Model: `gpt-4.1-mini-2025-04-14`
- Scenarios: `15`
- Repeats: `3`
- Trials: `45`

## 설계

동일한 1턴 고객 문의에 대해 Single RAG와 Multi-Agent 모두 Retrieval NO MATCH를 받습니다.
그 후 Multi-Agent가 CUSTOMER_INPUT_PENDING을 만들면 고객의 2턴 답변을 넣어 재진입합니다.
Single은 FALLBACK 이후에도 **외부에서 강제로 재호출하면 답할 능력이 있는지** 별도 진단합니다.

따라서 이 실험은 Multi를 유리하게 보이도록 Single의 생성 능력을 제거하지 않습니다.

## 주요 결과

- Single Turn1 FALLBACK rate: **100.0%**
- Multi Turn1 CUSTOMER_INPUT_PENDING rate: **100.0%**
- Multi Feedback Handoff rate: **100.0%**
- Native continuation eligibility — Single: **0.0%**
- Native continuation eligibility — Multi: **100.0%**
- Multi native Turn2 success: **100.0%**
- Single forced re-entry Turn2 success: **100.0%**

## 해석

Multi-Agent의 핵심 우위는 'Single이 답을 생성할 능력이 없다'는 것이 아니라, 검색 실패 후 CUSTOMER_INPUT_PENDING과 Feedback Handoff를 Runtime 계약으로 유지해 다음 고객 턴을 자연스럽게 이어가는 데 있다. Single도 외부에서 강제 재진입시키면 근거가 주어진 2턴 답변을 생성할 수 있으므로, 발표에서는 답변 지능보다 상태 기반 실패 복구 능력을 강조해야 한다.

## Claim 제한

- Turn1/Turn2 Retrieval은 실제 Vector Search 성능 비교가 아니라 의도적으로 통제한 Fault-Isolation입니다.
- Turn2 Evidence 본문은 repo의 processed 공식 JAC104 매뉴얼에서 읽습니다.
- Single forced re-entry는 제품 Runtime의 자연스러운 continuation이 아니라 실험자가 강제로 재호출한 진단입니다.
- 이 결과로 'Multi-Agent가 일반적으로 더 정확하다'고 주장하면 안 됩니다.

상세 실제 답변은 `conversations.md`, 모든 반복 원본은 `raw.jsonl`을 확인하세요.
