# E04-v2 — Generation Model Matrix

- Git SHA: `68666b88fcf33273906710f23a8d17f7f1faa07f`
- Prompt: `customer_guidance/v3`
- Result: `DRAFT_DIAGNOSTIC`
- Retrieval fixed: `E03 GTE Top-5 / Parent-Child-256`
- Answerable cases: `39`

## 전체 10모델

| Model | Family | Size | Relevant Acc. | Guard Accept | p50 ms | p95 ms | Cost USD |
|---|---|---|---:|---:|---:|---:|---:|
| gpt-4o-mini-2024-07-18 | 4o | mini | 0.5897 | 0.9231 | 3956.196 | 5486.193 | 0.044876 |
| gpt-4.1-nano-2025-04-14 | 4.1 | nano | 0.6154 | 0.9487 | 3255.982 | 7513.484 | 0.029831 |
| gpt-4.1-mini-2025-04-14 | 4.1 | mini | 0.7436 | 0.9744 | 4816.265 | 6818.401 | 0.120303 |
| gpt-4.1-2025-04-14 | 4.1 | full | 0.8462 | 0.9744 | 2776.972 | 4158.168 | 0.584370 |
| gpt-5-nano-2025-08-07 | 5 | nano | 0.5385 | 0.9487 | 3379.537 | 5204.6 | 0.017246 |
| gpt-5-mini-2025-08-07 | 5 | mini | 0.6923 | 0.8974 | 4783.926 | 6344.634 | 0.085079 |
| gpt-5-2025-08-07 | 5 | full | 0.8718 | 0.9744 | 3641.924 | 10176.372 | 0.427422 |
| gpt-5.4-nano-2026-03-17 | 5.4 | nano | 0.5385 | 0.9487 | 2637.065 | 3605.626 | 0.064656 |
| gpt-5.4-mini-2026-03-17 | 5.4 | mini | 0.7436 | 0.9744 | 2298.141 | 7095.35 | 0.240034 |
| gpt-5.4-2026-03-05 | 5.4 | full | 1.0000 | 0.9744 | 2575.266 | 3575.201 | 0.780690 |

## Mini 세대 비교

| Model | Relevant Acc. | p50 ms | Cost USD |
|---|---:|---:|---:|
| gpt-4o-mini-2024-07-18 | 0.5897 | 3956.196 | 0.044876 |
| gpt-4.1-mini-2025-04-14 | 0.7436 | 4816.265 | 0.120303 |
| gpt-5-mini-2025-08-07 | 0.6923 | 4783.926 | 0.085079 |
| gpt-5.4-mini-2026-03-17 | 0.7436 | 2298.141 | 0.240034 |

## 4.1 세대 크기 비교

| Size | Model | Relevant Acc. | p50 ms | Cost USD |
|---|---|---:|---:|---:|
| nano | gpt-4.1-nano-2025-04-14 | 0.6154 | 3255.982 | 0.029831 |
| mini | gpt-4.1-mini-2025-04-14 | 0.7436 | 4816.265 | 0.120303 |
| full | gpt-4.1-2025-04-14 | 0.8462 | 2776.972 | 0.584370 |

## 5 세대 크기 비교

| Size | Model | Relevant Acc. | p50 ms | Cost USD |
|---|---|---:|---:|---:|
| nano | gpt-5-nano-2025-08-07 | 0.5385 | 3379.537 | 0.017246 |
| mini | gpt-5-mini-2025-08-07 | 0.6923 | 4783.926 | 0.085079 |
| full | gpt-5-2025-08-07 | 0.8718 | 3641.924 | 0.427422 |

## 5.4 세대 크기 비교

| Size | Model | Relevant Acc. | p50 ms | Cost USD |
|---|---|---:|---:|---:|
| nano | gpt-5.4-nano-2026-03-17 | 0.5385 | 2637.065 | 0.064656 |
| mini | gpt-5.4-mini-2026-03-17 | 0.7436 | 2298.141 | 0.240034 |
| full | gpt-5.4-2026-03-05 | 1.0000 | 2575.266 | 0.780690 |

## 해석 가드레일

- GPT-4o/4.1은 temperature=0을 사용한다.
- 구형 GPT-5 계열은 temperature 파라미터를 지원하지 않아 reasoning=minimal을 사용한다.
- GPT-5.4는 reasoning=none일 때 temperature를 지원하므로 reasoning=none + temperature=0을 사용한다.
- 따라서 세 세대의 decoding knob가 완전히 동일하지는 않으며, 각 API 세대에서 가능한 최소 reasoning/최저 randomness 프로필을 사용한 비교다.
- strict enum string literal 호환성을 위해 E04 입력 evidence의 CR/LF/TAB 및 연속 공백은 단일 ASCII 공백으로 정규화한다.
- 정규화는 모든 모델/모든 case에 동일하게 적용하며 원본 chunk text SHA-256을 dataset에 남긴다.
- E03 GTE Top-5에 Gold Evidence가 없는 4건은 E04 primary에서 제외한다.
- 본 평가는 LLM-as-a-Judge가 아니라 Gold Evidence Group과 선택된 normalized exact evidence 문장의 객관적 일치로 계산한다.
- 본 결과는 DRAFT_DIAGNOSTIC이며 FINAL_TEST가 아니다.
