# E02 Chunking Strategy Ablation

- Git SHA: `8a25bb8825a1b5c76e316883af2036e8044485c3`
- Result Label: `DRAFT_DIAGNOSTIC`
- Embedding: `BAAI/bge-m3` / `5617a9f61b028005a4858fdac845db406aefb181`
- Top-K: `5`
- Score Threshold: `0.4`
- Product Filter: `exact_sales_code` pre-filter
- Query Expansion: runtime policy applied
- Answerability Gate: three_model_integration policy applied
- Ranking postprocess: `NONE` (모든 청킹 Variant에 동일 적용)

## Results

| Variant | Chunks | Avg Tok | Max Tok | H@1 | H@3 | H@5 | MRR@5 | nDCG@5 | No-Evidence | Mean Groups/Hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current | 53 | 107.736 | 234 | 0.6744 | 0.9070 | 0.9070 | 0.7752 | 0.8090 | 0.7143 | 1.000 |
| fixed512 | 28 | 311.857 | 512 | 0.6047 | 0.9302 | 1.0000 | 0.7500 | 0.8127 | 0.7143 | 2.307 |
| section | 6 | 1316.667 | 2240 | 0.6977 | 1.0000 | 1.0000 | 0.8488 | 0.8884 | 0.7143 | 8.644 |
| parent_child | 43 | 204.558 | 256 | 0.5349 | 0.9070 | 0.9070 | 0.6977 | 0.7514 | 0.7143 | 1.324 |

## Interpretation Guardrails

- 이 실험의 latency는 로컬 NumPy Exact ranking 시간이며 E01 pgvector Runtime latency와 직접 비교하지 않는다.
- Query embedding은 모든 Variant가 공유하는 동일 BGE-M3 입력이므로 한 번 계산하고 재사용했다.
- Section처럼 하나의 Chunk가 여러 Evidence Group을 포함하는 전략은 Hit@K가 높더라도 Chunk 크기와 `Mean Groups/Hit`를 함께 해석한다.
- Fixed512/Parent-Child의 Gold span은 window 경계 절단을 허용하되 동일 Parent 내 최대 문자 겹침 단 하나의 Chunk에만 매핑했다.
- E02는 청킹 전략 선택용 Ablation이며 E01의 공식 Runtime Baseline 수치를 대체하지 않는다.
