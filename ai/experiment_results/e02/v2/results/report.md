# E02-v2 Full-Corpus Chunking Strategy Ablation

- Run Git SHA: `35ba2ae013c6294a0c1523f838665bc44e1ca593`
- Build Git SHA: `35ba2ae013c6294a0c1523f838665bc44e1ca593`
- Result Label: `DRAFT_DIAGNOSTIC`
- Corpus: `3 official manuals / 144 processed pages`
- Embedding: `BAAI/bge-m3` / `5617a9f61b028005a4858fdac845db406aefb181`
- Top-K: `5`
- Score Threshold: `0.4`
- Product Filter: `exact_sales_code` pre-filter
- Cross-model fallback: `OFF`
- Ranking postprocess: `NONE`

## Primary — E01 50 Case

| Variant | Chunks | Candidate counts | H@1 | H@3 | H@5 | MRR@5 | nDCG@5 | No-Evidence | Mean Groups/Hit |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| fixed512 | 170 | {"WPUIAC425SNW": 62, "WPUIAC606SNW": 59, "WPUJAC104DWH": 49} | 0.1395 | 0.5814 | 0.6279 | 0.3399 | 0.4130 | 0.7143 | 0.818 |
| section_aware_512 | 134 | {"WPUIAC425SNW": 43, "WPUIAC606SNW": 42, "WPUJAC104DWH": 49} | 0.0930 | 0.5349 | 0.7209 | 0.3314 | 0.4286 | 0.7143 | 0.947 |
| parent_child_256 | 216 | {"WPUIAC425SNW": 76, "WPUIAC606SNW": 74, "WPUJAC104DWH": 66} | 0.2791 | 0.7209 | 0.7907 | 0.4919 | 0.5676 | 0.7143 | 0.649 |

## Supplemental — FAQ-origin Draft Cases

> 아래 결과는 `UNREVIEWED_DRAFT` Case이므로 공식 성능 수치에 합산하지 않는다.

| Variant | Cases | H@1 | H@3 | H@5 | MRR@5 | nDCG@5 |
|---|---:|---:|---:|---:|---:|---:|
| fixed512 | 5 | 0.2000 | 0.8000 | 1.0000 | 0.5400 | 0.6559 |
| section_aware_512 | 5 | 0.2000 | 0.8000 | 1.0000 | 0.5400 | 0.6559 |
| parent_child_256 | 5 | 0.6000 | 0.8000 | 1.0000 | 0.7400 | 0.8036 |

## Interpretation Guardrails

- E02-v1의 15-page 제한 Corpus는 `SUPERSEDED`로 취급한다.
- E02-v2는 144-page 전체 매뉴얼에서 생성된 134~216개의 자동 Chunk를 비교한다.
- 제품 선필터 후에도 모델별 후보 Chunk가 42~76개이므로 Top-5가 전체 후보를 사실상 전부 보는 구조가 아니다.
- FAQ-origin 5 Case는 사용자 표현 robustness 확인용이며 `UNREVIEWED_DRAFT`이므로 공식 TEST Metric이 아니다.
- Ranking latency는 Local NumPy Exact Cosine 시간이며 E01 pgvector Runtime latency와 직접 비교하지 않는다.
- Parent-Child는 Child text만 검색 점수에 사용하며 Parent context는 retrieval score에 영향을 주지 않는다.
- Public Runtime activation은 변경하지 않는다.
