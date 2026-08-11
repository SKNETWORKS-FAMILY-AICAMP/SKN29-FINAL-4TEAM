# B2-1 Threshold·Scope Policy 비교 실험 v1

> 실행일: 2026-08-11 KST  
> 상태: `DRAFT_THRESHOLD_SCOPE_EXPERIMENT_COMPLETE`  
> 공식 성능 사용: 불가 — Gold 60건 2인 검수 대기

## 결론

Threshold 상향만으로 무근거 오탐을 줄이는 방식은 현재 DEV에서 적합하지 않다.
`0.55`부터 무근거 중단은 개선되지만 정상 질의의 정답 근거도 함께 제거된다.
반면 제품·기능을 명시적으로 제한한 `MODEL_CAPABILITY_SCOPE_V1`은 Threshold
`0.4~0.5`에서 양성 검색 성능을 유지하면서 무근거 중단 정확도를 `0.25`에서
`0.625`로 높였다.

이 결과는 운영 적용 승인이 아니다. Scope Policy는 Experiment Lab에만 구현했고
운영 `ai/configs/retrieval_policy.yaml`과 Runtime 호출 경로는 변경하지 않았다.

## 실험 구성

- Python `3.13.13`, Windows 11, CPU
- Embedding `BAAI/bge-m3`
- Revision `5617a9f61b028005a4858fdac845db406aefb181`
- Dimension `1024`, L2 Normalize
- Dense Cosine Exact, Top-K `5`, Exact Product Filter
- Threshold `0.4`, `0.45`, `0.5`, `0.55`, `0.6`, `0.65`, `0.7`
- Scope Policy 적용/미적용
- 임시 청킹 후보 `fixed_512_v1`, `parent_child_v1`
- Dataset `rag_gold_v1` DEV 35건
- 총 Case Result `980`
- Source HEAD `df96616d7010a2f61bddc91f8974235ba5ec92d3`, Dirty

## Parent/Child 결과

| Scope | Threshold | Hit@1 | Hit@5 | MRR | 무근거 중단 | Scope Block | 양성 오차단 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 없음 | 0.40 | 0.703704 | 0.888889 | 0.790123 | 0.250 | 0 | 0 |
| 없음 | 0.50 | 0.703704 | 0.888889 | 0.790123 | 0.250 | 0 | 0 |
| 적용 | 0.40 | 0.703704 | 0.888889 | 0.790123 | 0.625 | 4 | 0 |
| 적용 | 0.50 | 0.703704 | 0.888889 | 0.790123 | 0.625 | 4 | 0 |
| 적용 | 0.55 | 0.629630 | 0.777778 | 0.697531 | 0.750 | 4 | 0 |
| 적용 | 0.60 | 0.444444 | 0.518519 | 0.475309 | 1.000 | 4 | 0 |

`fixed_512_v1`도 동일한 Threshold 손실 형태를 보였다. Threshold `0.5`에서
Hit@5는 `0.851852`, `0.55`에서는 `0.777778`, `0.6`에서는 `0.518519`이다.

## Scope Policy 효과

Policy는 Gold의 `query_variant_type`이나 `expected_no_evidence`를 입력으로 사용하지
않는다. 다음 명시적 입력만 사용한다.

- 요청 제품 코드
- 지원 제품 Allowlist
- 제품별 미지원 기능어

현재 차단 4건은 다음과 같다.

- `EXP-SCOPE-JAC104-ICE-001`: JAC104의 얼음·제빙 질의 3건
- `EXP-SCOPE-MODEL-001`: 지원하지 않는 WPU-IAC506 질의 1건

DEV 양성 질의 오차단은 `0`건이다. 다만 현재 35건에서의 0건은 일반화된 안전
증거가 아니므로 표현 변형과 IAC425 양성 문항을 보강한 뒤 다시 검증해야 한다.

## Threshold 상향이 부적합한 이유

Threshold `0.50→0.55`는 렌탈료 질의 1건을 추가로 중단하지만 다음 정상 질의
3건의 Top-5 정답을 함께 잃는다.

- `RAGV2-GOLD-0012`: 물맛·냄새 이상
- `RAGV2-GOLD-0023`: 출수량 감소
- `RAGV2-GOLD-0024`: 비린내 표현

Threshold `0.6`은 무근거 8건을 모두 중단하지만 양성 Hit@5가 `0.518519`로
하락한다. 따라서 무근거 정확도만 보고 Threshold를 올리면 안 된다.

## 남은 실패

Scope Policy 적용과 Threshold `0.4~0.5`에서도 다음 3건은 관련 없는 매뉴얼
근거를 반환한다.

- 월 렌탈료·제휴카드 할인
- 교체용 필터 현재 판매 가격
- 제품 외관 색상

이 3건은 청킹이나 단순 Threshold보다 Knowledge Domain·Query Intent 경계 문제에
가깝다. 가격·계약·상품 옵션을 매뉴얼 RAG 대상에서 제외하는 별도 정책은 담당자
승인과 표현 변형 Dataset을 먼저 확보한 뒤 비교한다. 현재 단어 3개를 그대로
Hard-code하여 운영 규칙으로 승격하지 않는다.

## 판정

- Draft 후속 후보: `parent_child_v1 + MODEL_CAPABILITY_SCOPE_V1`
- Threshold 후보 구간: `0.4~0.5`
- 운영 Threshold 변경: `BLOCKED`
- 운영 Scope Policy 적용: `BLOCKED`
- 차단 사유: Gold 2인 검수, 표현 변형, IAC425 양성 문항, PM Gate 미완료

## 재현 명령

```powershell
.\ai\.venv\Scripts\python.exe -B -m ai.scripts.run_retrieval_threshold_scope_experiment_v1 --allow-draft-gold
```

B1에서 만든 콘텐츠 해시 Embedding Cache를 재사용한 실행시간은 약 `1.957s`다.
Cache 적중과 원래 문서 임베딩 시간은 결과 Manifest와 구조 정보에 함께 기록된다.

## 산출물

- `ai/configs/experiments/retrieval_threshold_scope_profiles.yaml`
- `ai/evaluation/query_scope_policy.py`
- `ai/scripts/run_retrieval_threshold_scope_experiment_v1.py`
- `ai/evaluation/reports/experiments/retrieval_threshold_scope_v1/manifest.json`
- `ai/evaluation/reports/experiments/retrieval_threshold_scope_v1/case_results.jsonl`
- `ai/evaluation/reports/experiments/retrieval_threshold_scope_v1/summary.json`
- `ai/evaluation/reports/experiments/retrieval_threshold_scope_v1/failure_analysis.json`
- `ai/tests/unit/test_retrieval_threshold_scope_experiment_v1.py`

## 다음 순서

1. 가격·계약·상품 옵션 Query Intent 정책을 표현 변형 Dataset과 함께 설계
2. Keyword/BM25와 Dense의 실패 Case 차이 비교
3. 상위 조합에 Hybrid·Reranker를 순서대로 추가
4. Gold 2인 검수와 PM Gate 뒤 TEST Threshold를 고정하고 최초 실행

