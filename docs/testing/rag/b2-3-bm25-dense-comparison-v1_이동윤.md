# B2-3 BM25·Dense 검색 방식 비교 실험 v1

> 실행일: 2026-08-11 KST  
> 상태: `DRAFT_RETRIEVAL_METHOD_COMPARISON_COMPLETE`  
> 공식 성능 사용: 불가 — Gold 60건 2인 검수 및 PM Gate 대기

## 결론

현재 DEV에서는 BM25를 Dense와 결합할 근거가 없다. Parent/Child 기준 Dense의
Hit@5는 `0.888889`, BM25는 `0.666667`이며, BM25가 Dense의 누락 3건을 복구한
Case는 `0건`이다. 두 방식의 Top-5 후보 겹침은 `0.318311`로 낮았지만 BM25의
고유 후보가 정답 Evidence는 아니었다.

따라서 다음 단계에서 단순 Hybrid를 구현하지 않는다. 두 방식이 함께 놓친 3건은
`누수`, `출수되지 않음`과 사용자의 간접 표현이 일치하지 않는 문제에 가깝다.
먼저 검수 가능한 Alias Query Expansion 후보를 별도 실험하고, 실제 복구가 생긴
경우에만 Hybrid·Reranker로 진행한다.

이 결과는 운영 검색 변경 승인이 아니다. BM25는 Experiment Lab에만 구현했고
운영 `keyword_search.py`, `hybrid_search.py`, FastAPI Pipeline과 Backend 계약은
변경하지 않았다.

## 실험 구성

- Python `3.13.13`, Windows 11, CPU
- Gold DEV 35건: 양성 27, 무근거·제품 범위 8
- Corpus 96쪽, Exact Product Filter
- Scope `MODEL_CAPABILITY_SCOPE_V1`
- Intent `MANUAL_DOMAIN_INTENT_V1`
- Top-K `5`
- 청킹 후보 `fixed_512_v1`, `parent_child_v1`
- Dense: BGE-M3, Cosine Exact, Threshold `0.5`
- BM25: 단어 + 단어 내부 문자 bigram, `k1=1.5`, `b=0.75`, Score `>0`
- 총 Case Result `140`
- Source HEAD `f052b6eb6800fd419569fe2d1946dfae24653c17`, Dirty

BM25의 단어·문자 bigram 분석기는 외부 사전 없이 재현 가능하고 한글 조사·어미
차이를 일부 완화한다. Dense 점수와 BM25 점수는 척도가 다르므로 절대 Score를
서로 비교하지 않는다.

## 전체 결과

| 청킹 | 방식 | Hit@1 | Hit@3 | Hit@5 | MRR | nDCG@5 | 무근거 중단 |
|---|---|---:|---:|---:|---:|---:|---:|
| Fixed 512 | Dense | 0.592593 | 0.851852 | 0.851852 | 0.716049 | 0.734017 | 1.000 |
| Fixed 512 | BM25 | 0.481481 | 0.629630 | 0.666667 | 0.540123 | 0.544472 | 0.875 |
| Parent/Child | Dense | 0.703704 | 0.888889 | 0.888889 | 0.790123 | 0.798392 | 1.000 |
| Parent/Child | BM25 | 0.481481 | 0.629630 | 0.666667 | 0.540123 | 0.544472 | 0.875 |

Parent/Child에서 Dense 검색 구간 p50은 `0.0345ms`, BM25는 `0.1327ms`였다. 이
수치는 48개 JAC104 후보를 메모리에서 처리한 단일 Process 진단값이며 운영 DB
지연이나 동시성 성능으로 확대하지 않는다.

## Case별 상호 보완성

| 항목 | Fixed 512 | Parent/Child |
|---|---:|---:|
| Dense Hit@5 성공 | 23/27 | 24/27 |
| BM25 Hit@5 성공 | 18/27 | 18/27 |
| 양쪽 성공 | 18 | 18 |
| Dense만 성공 | 5 | 6 |
| BM25만 복구 | 0 | 0 |
| 양쪽 실패 | 4 | 3 |
| Oracle Union Hit@5 | 0.851852 | 0.888889 |
| Top-5 후보 Jaccard | 0.311876 | 0.318311 |

BM25가 추가한 후보는 많지만 정답 복구가 없어서 Oracle Union도 Dense 단독과
동일하다. 현재 데이터에서 Hybrid는 후보 수와 조정 Parameter만 늘리고 Hit@5
상한을 높이지 못한다.

BM25는 Dense가 맞힌 다음 Parent/Child 6건을 놓쳤다.

- `RAGV2-GOLD-0005`, `0011`, `0012`, `0021`, `0023`, `0031`

또한 기사 도착 시간 Query `RAGV2-GOLD-0053`에 매뉴얼 후보를 반환해 무근거
중단 정확도가 `0.875`로 낮아졌다. BM25용 중단 Threshold를 DEV에서 즉시 맞추면
과적합 위험이 있으므로 이번 단계에서는 조정하지 않았다.

## 양쪽이 놓친 3건

Parent/Child에서 다음 Case는 Dense와 BM25 모두 Top-5 Evidence를 찾지 못했다.

| Case | 사용자 표현 | 매뉴얼 핵심 표현 | 다음 가설 |
|---|---|---|---|
| `RAGV2-GOLD-0004` | 물이 새는 것 같음 | 제품 누수 발생 | `물이 새다 → 누수` Alias |
| `RAGV2-GOLD-0025` | 물이 한 방울도 안 나옴 | 물이 출수되지 않음 | `안 나오다 → 출수되지 않음` Alias |
| `RAGV2-GOLD-0027` | 바닥에 물이 흥건함 | 제품 누수 발생 | `바닥이 흥건하다 → 누수` Alias |

이 Alias는 아직 승인된 사전이 아니다. 원문 근거를 바꾸지 않고 Query에 공식
용어를 보조 추가하는 Draft 후보로만 설계하고, Data Owner 검수와 Hard Negative
오확장 평가를 거쳐야 한다.

## 판정과 다음 순서

- Dense 우위: `SUPPORTED_ON_DRAFT_DEV`
- BM25 단독 운영 후보: `REJECTED_ON_CURRENT_DRAFT_DEV`
- Dense+BM25 Hybrid 착수: `DEFERRED_NO_COMPLEMENTARY_RECOVERY`
- Reranker 착수: `DEFERRED` — 양쪽 누락 3건은 후보에 없어 재정렬로 복구 불가
- 다음 작업: `B2-4 Approved Alias Query Expansion Draft 비교`
- 운영 변경: `BLOCKED`

## 재현 명령

```powershell
.\ai\.venv\Scripts\python.exe -B -m ai.scripts.run_retrieval_method_comparison_v1 --allow-draft-gold
```

검증 결과는 AI Unit `156 passed, 3 warnings`, `pip check=PASS`, Backend Integration
Fixture `12 passed, 1 warning`, `git diff --check=PASS`다.

## 산출물

- `ai/configs/experiments/retrieval_method_profiles.yaml`
- `ai/evaluation/lexical_retrieval.py`
- `ai/scripts/run_retrieval_method_comparison_v1.py`
- `ai/evaluation/reports/experiments/retrieval_method_comparison_v1/`
- `ai/tests/unit/test_retrieval_method_comparison_v1.py`
