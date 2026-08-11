# B1 Chunking 비교 실험 v1 실행 결과

> 실행일: 2026-08-11 KST  
> 상태: `DRAFT_CHUNKING_EXPERIMENT_COMPLETE`  
> 공식 성능 사용: 불가 — Gold 60건 2인 검수 대기

## 결론

청킹을 바꾸면 1순위 검색 성능 차이는 생겼지만, 현재 가장 큰 실패 원인은 청킹이
아니다. 제품 필터를 적용해도 모든 Profile의 무근거 중단 정확도가 `0.25`에 그쳐
8건 중 6건에서 관련 없는 문서를 반환했다. 따라서 B1 결과만으로 운영 청킹을
바꾸지 않고, 다음 Draft 실험은 Retrieval Threshold·정책 차단·Reranker를 분리해
비교해야 한다.

`parent_child_v1`은 현재 DEV에서 Hit@1과 MRR이 가장 높아 후속 비교 후보로 남길
가치는 있다. 다만 Gold 미검수, IAC425 양성 문항 부재, Parent Context 전달 비용
미측정 상태이므로 최종 선정 결과가 아니다.

## 고정 조건

- Python `3.13.13`, Windows 11, CPU
- Embedding `BAAI/bge-m3`
- Revision `5617a9f61b028005a4858fdac845db406aefb181`
- Dimension `1024`, L2 Normalize
- Dense Cosine Exact, Top-K `5`, Threshold `0.4`
- Dataset `rag_gold_v1` DEV 35건
- Corpus JAC104 44쪽 + IAC425 52쪽, 총 96 Source Page
- Source HEAD `b5c324b8299866b465aceed06c322a872dc2353a`, Dirty

## Exact Product Filter 결과

| Profile | Hit@1 | Hit@3 | Hit@5 | MRR | nDCG@5 | Chunk | Max Token | 구조 중복률 | Cold Embed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `current_chunking_full_corpus_v1` | 0.629630 | 0.888889 | 0.888889 | 0.753086 | 0.771054 | 96 | 696 | 0.000000 | 138.503s |
| `page_v1` | 0.629630 | 0.888889 | 0.888889 | 0.753086 | 0.771054 | 96 | 696 | 0.000000 | 기준선 Vector 재사용 |
| `fixed_512_v1` | 0.629630 | 0.888889 | 0.888889 | 0.753086 | 0.771054 | 98 | 512 | 0.010231 | 123.480s |
| `section_v1` | 0.481481 | 0.777778 | 0.925926 | 0.648148 | 0.681860 | 56 | 1,112 | 0.000000 | 256.835s |
| `parent_child_v1` | 0.703704 | 0.888889 | 0.888889 | 0.790123 | 0.798392 | 108 | 256 | 0.030078 | 88.001s |

모든 Profile의 Wrong Product Hit는 Exact Product Filter에서 `0`이고 Evidence
Lineage 복원률은 `1.0`이다. 반대로 제품 필터를 끄면 Profile별 Wrong Product
Hit가 `70~92`건 발생했고 무근거 중단 정확도도 `0.0~0.125`로 떨어졌다. 제품
Metadata Filter는 선택 최적화가 아니라 필수 안전 경계로 유지한다.

## 해석

- `current`와 `page_v1`은 현재 Source 구조상 동일한 96개 텍스트다. 별도 기술
  후보처럼 세지 않고 대조군 동일성 확인으로 본다.
- `fixed_512_v1`은 최대 길이를 512 whitespace token으로 제한했지만 DEV 검색
  수치는 페이지 기준선과 같았다. 2개 청크와 1.02% 구조 중복만 늘었다.
- `section_v1`은 Hit@5만 `0.925926`으로 높고 Hit@1·MRR은 가장 낮았다. 최대
  1,112 token과 가장 긴 Cold Embedding 시간 때문에 현재 상위 후보 근거가 약하다.
- `parent_child_v1`은 기준선 대비 Hit@1이 `+0.074074`, MRR이 `+0.037037`이다.
  개선 Case는 `RAGV2-GOLD-0005`, `RAGV2-GOLD-0008` 두 건이다. 하지만 Context
  Payload는 합계 54,913 whitespace token이고 Generation 단계 비용은 아직
  측정하지 않았다.
- 동일 Gold Evidence의 여러 Child를 중복 정답으로 세지 않도록 nDCG는 Evidence
  최초 적중 1회만 Gain으로 계산한다.

## 실패 분류

Exact Product Filter의 `parent_child_v1` 자동 1차 분류는 다음과 같다.

| 분류 | 건수 | 의미 |
|---|---:|---|
| `RETRIEVAL_ERROR` | 6 | 양성 Top-5 미적중 또는 일반 무근거 질의의 오탐 |
| `RERANK_ERROR` | 5 | 근거가 Top-5에 있으나 1위가 아님 |
| `SCOPE_FILTER_ERROR` | 3 | JAC104에 없는 제빙 기능 질의가 검색 전에 차단되지 않음 |

무근거 실패 6건은 가격·렌탈료·색상 3건과 JAC104 제빙 기능 3건이다. 이 분류는
`AUTOMATED_TRIAGE_REVIEW_REQUIRED`이며 `CHUNKING_ERROR` 또는 `KNOWLEDGE_GAP`을
자동 확정하지 않는다. 데이터 추가보다 Retrieval·Scope Policy 검토가 먼저다.

## 실행·재현

```powershell
.\ai\.venv\Scripts\python.exe -B -m ai.scripts.run_chunking_experiment_v1 --allow-draft-gold
```

최초 Cold 실행은 고유 Vector 4종을 생성해 약 `608.879s`가 걸렸다. 완성된
콘텐츠 해시 Cache는 Git 제외 경로 `tmp/ai_chunking_experiment_cache`에 저장되며,
동일 입력 Warm 재실행은 약 `1.841s`였다. Cache 적중 여부와 최초 Embedding
시간은 Profile 구조 정보에 함께 남는다.

## Gate와 다음 순서

1. 김은진: Gold 60건 2인 검수와 IAC425 양성 평가 문항 보강
2. 이동윤: `parent_child_v1`과 페이지/Fixed 대조군으로 Dense·Keyword·Hybrid·
   Reranker·Threshold를 한 변수씩 비교
3. 이동윤: 가격·색상·제빙 무근거 Case의 정책 차단과 Unknown Payload 검증
4. 윤승혁: 상위 2개 Chunking Profile 채택 Gate 판정
5. 최지용·이동윤: 위 실험과 별개로 P0 Initial Symptom 공동 Mock 우선 유지

## 산출물

- `ai/configs/experiments/chunking_profiles.yaml`
- `ai/evaluation/chunking.py`
- `ai/scripts/run_chunking_experiment_v1.py`
- `ai/evaluation/reports/experiments/chunking_comparison_v1/manifest.json`
- `ai/evaluation/reports/experiments/chunking_comparison_v1/case_results.jsonl`
- `ai/evaluation/reports/experiments/chunking_comparison_v1/summary.json`
- `ai/evaluation/reports/experiments/chunking_comparison_v1/failure_analysis.json`
- `ai/tests/unit/test_chunking_experiment_v1.py`

