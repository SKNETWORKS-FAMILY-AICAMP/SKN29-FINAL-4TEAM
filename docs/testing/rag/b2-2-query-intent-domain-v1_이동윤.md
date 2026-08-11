# B2-2 Query Intent·Domain Policy 비교 실험 v1

> 실행일: 2026-08-11 KST  
> 상태: `DRAFT_QUERY_INTENT_DOMAIN_EXPERIMENT_COMPLETE`  
> 공식 성능 사용: 불가 — 표현 변형·Gold 2인 검수 및 PM Gate 대기

## 결론

B2-1에 남아 있던 계약·부품 구매·상품 옵션 3종의 무근거 Query는 Dense
Threshold를 더 높이지 않고 명시적인 Query Intent 정책으로 중단할 수 있었다.
기존 Gold DEV 35건에서 무근거 중단 정확도는 `0.625`에서 `1.0`으로 개선됐고,
양성 27건의 오차단은 `0`건이었다. Hit@1 `0.703704`, Hit@5 `0.888889`, MRR
`0.790123`은 정책 전후 동일했다.

그러나 이 결과로 운영 정책을 확정하지 않는다. 표현 변형 18건은 정책 설계와
함께 만든 미검수 Draft이므로 독립 Holdout 일반화 증거가 아니다. 정책은
Experiment Lab에만 있으며 운영 `scope_filter.py`, FastAPI Pipeline, Backend
계약은 변경하지 않았다.

## 실험 구성

- Python `3.13.13`, Windows 11, CPU
- Embedding `BAAI/bge-m3`
- Revision `5617a9f61b028005a4858fdac845db406aefb181`
- Dimension `1024`, L2 Normalize
- Dense Cosine Exact, Top-K `5`, Exact Product Filter
- 임시 고정 조합 `parent_child_v1 + Threshold 0.5`
- Scope `MODEL_CAPABILITY_SCOPE_V1`
- Intent Policy 적용/미적용
- Gold DEV 35건 + 표현 변형 DEV 18건
- Intent Policy 2종, 총 Case Result `106`
- Source HEAD `df96616d7010a2f61bddc91f8974235ba5ec92d3`, Dirty

## 표현 변형 Dataset

운영 Gold 60건과 분리된 실험 전용 Dataset을 만들었다.

| 구분 | 수 | 목적 |
|---|---:|---|
| 차단 표현 | 9 | 계약·결제 3, 부품 가격·구매 3, 판매 색상·옵션 3 |
| 허용 Hard Negative | 9 | 렌탈 제품 고장, 필터 교체, 외관·조작부 지원 문의 |

모든 Case는 `UNREVIEWED_DRAFT`이며 승인자 0명이다. 예를 들어 `렌탈` 한 단어를
차단하지 않고 `렌탈료`, `제휴카드`, `할인 금액`처럼 상업 계약 의도가 분명한
표현만 차단한다. 필터 규칙도 부품어와 가격·구매어가 함께 있어야 발동하며
`필터 가격이 아니라 교체 주기`와 `얼마마다 교체`는 허용한다.

## 결과

| Dataset | Intent Policy | 판정 정확도 | 차단 Recall | 허용 정확도 | 무근거 중단 | 양성 Hit@5 | 양성 오차단 |
|---|---|---:|---:|---:|---:|---:|---:|
| 표현 변형 18 | 없음 | 0.500 | 0.000 | 1.000 | 0.333333 | 1.000000 | 0 |
| 표현 변형 18 | 적용 | 1.000 | 1.000 | 1.000 | 1.000000 | 1.000000 | 0 |
| Gold DEV 35 | 없음 | 해당 없음 | 해당 없음 | 해당 없음 | 0.625000 | 0.888889 | 0 |
| Gold DEV 35 | 적용 | 해당 없음 | 해당 없음 | 해당 없음 | 1.000000 | 0.888889 | 0 |

Gold DEV에서 새 정책이 차단한 3건은 다음 Rule로 각각 분리된다.

- `EXP-INTENT-COMMERCIAL-001`: 월 렌탈료·제휴카드 할인
- `EXP-INTENT-PART-PURCHASE-001`: 교체용 필터 현재 판매 가격
- `EXP-INTENT-PRODUCT-OPTION-001`: 제품 외관 판매 색상

Scope Policy의 기존 4건과 Intent Policy의 3건은 중복되지 않았다. 나머지
무근거 1건은 Threshold `0.5`에서 검색 결과가 없어 중단됐다.

## 남은 실패와 다음 실험 입력

의도 정책 적용 후에도 Gold 양성 검색 품질은 개선되지 않았다.

- Top-5 검색 누락 3건: `RAGV2-GOLD-0004`, `0025`, `0027`
- 정답이 1위가 아닌 순위 오류 5건: `RAGV2-GOLD-0007`, `0012`, `0013`,
  `0014`, `0021`

따라서 다음 B2-3은 Keyword/BM25와 Dense의 Case별 차이를 먼저 비교한다. BM25가
누락 3건을 후보에 포함하는지 확인한 뒤에만 Hybrid를 구성하고, 후보에 이미
정답이 있으나 순위가 틀린 5건은 그 다음 Reranker 입력으로 넘긴다. Reranker를
먼저 붙여도 Top-K에 없는 3건은 복구할 수 없다.

## 판정

- Query Intent 정책 Draft 비교: `COMPLETE`
- 운영 Intent Policy 적용: `BLOCKED`
- 독립 Holdout 일반화: `NOT_EVALUATED`
- 차단 사유: 표현 변형·Gold 2인 검수, IAC425 양성 문항, PM Gate 미완료
- 다음 작업: `B2-3 Keyword/BM25 vs Dense 비교`

## 재현 명령

```powershell
.\ai\.venv\Scripts\python.exe -m ai.scripts.build_query_intent_domain_dataset_v1
.\ai\.venv\Scripts\python.exe -B -m ai.scripts.run_query_intent_domain_experiment_v1 --allow-draft-gold
```

검증 결과는 AI Unit `153 passed, 3 warnings`, `pip check=PASS`, Backend Integration
Fixture `12 passed, 1 warning`, `git diff --check=PASS`다.

## 산출물

- `ai/configs/experiments/query_intent_domain_profiles.yaml`
- `ai/evaluation/schemas/query_intent_domain_case_v1.schema.json`
- `ai/evaluation/datasets/experiments/query_intent_domain_v1.jsonl`
- `ai/evaluation/datasets/experiments/query_intent_domain_v1_manifest.json`
- `ai/evaluation/query_intent_domain_policy.py`
- `ai/scripts/build_query_intent_domain_dataset_v1.py`
- `ai/scripts/run_query_intent_domain_experiment_v1.py`
- `ai/evaluation/reports/experiments/query_intent_domain_v1/`
- `ai/tests/unit/test_query_intent_domain_experiment_v1.py`
