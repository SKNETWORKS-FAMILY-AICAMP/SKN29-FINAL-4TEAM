# B2-4 Alias Query Expansion Draft 비교 실험 v1

> 실행일: 2026-08-12 KST
>
> 상태: `DRAFT_ALIAS_CANDIDATE_PARTIALLY_SUPPORTED_PENDING_REVIEW`
>
> 공식 성능 사용: 불가 — Gold 60건 2인 검수와 Data Owner Alias 검수 대기

## 결론

Alias Query Expansion 가설은 현재 DEV에서 부분적으로만 지지됐다. 누수 표현을
공식 용어로 보조 확장한 `ALIAS-JAC104-LEAK-001`은
`RAGV2-GOLD-0027`을 Top-5 밖에서 3위로 복구했고, 이미 검색되던
`RAGV2-GOLD-0021`을 2위에서 1위로 개선했다. 반면 무출수 표현을 확장한
`ALIAS-JAC104-NO-WATER-001`은 `RAGV2-GOLD-0025`를 복구하지 못했다.

전체 DEV Positive Hit@5는 `0.925926`에서 `0.962963`, MRR은 `0.783951`에서
`0.814815`로 증가했다. Positive 회귀, 무근거 8건 회귀, 잘못된 제품 Hit는
없었고 문맥·부정형 Hard Negative 7건에서도 예상하지 않은 Alias 활성화가 없었다.

이 결과는 운영 Query Expansion 승인 근거가 아니다. 누수 Alias만 Data Owner
검수 후보로 남기고 무출수 Alias는 현재 Draft에서 채택하지 않는다. 운영
`retrieval_policy.yaml`, FastAPI Pipeline, RAG Chunk·Evidence와 Backend 계약은
변경하지 않았다.

## B2-3과 현재 기준선 차이

B2-3은 Dataset Hash
`DDB20527D452E1C246CA821CFA7D4EC159B13E24597FDEF685C19136065E50FD`에서
실행됐고, B2-4는 D-02 Gold Evidence 보정 이후 Hash
`9B52AF026B7C8F21AC4D59ECD4D0F2E1A528E78448225EBE1F5E542A71A8E54A`에서
실행됐다. 따라서 B2-3의 누락 3건을 그대로 현재 누락 3건이라고 재사용하지 않았다.

같은 B2-4 실행 안에서 원문 Dense 대조군을 다시 측정한 결과는 다음과 같다.

| Case | B2-4 원문 Dense | Alias Dense | 현재 판정 |
| --- | --- | --- | --- |
| `RAGV2-GOLD-0004` | Hit@1 | Hit@1 | 현재 Dataset에서는 이미 복구됨 |
| `RAGV2-GOLD-0025` | Top-5 Miss | Top-5 Miss | 무출수 Alias 미지원 |
| `RAGV2-GOLD-0027` | Top-5 Miss | Hit@3 | 누수 Alias 복구 |

Dataset Hash가 다른 B2-3 수치와 B2-4 수치를 같은 기준선처럼 직접 비교하지 않는다.

## 실험 구성

- Python `3.13.13`, Windows 11, CPU
- Source HEAD `692ccd5b430ad6caf6f220a26ca8957f1d8716b8`, Dirty
- Gold DEV 35건: Positive 27, 무근거·제품 범위 8
- 추가 Hard Negative 7건
- Corpus 원천 96쪽, Parent/Child 검색 Chunk 108개
- 모델 `BAAI/bge-m3`
- Revision `5617a9f61b028005a4858fdac845db406aefb181`
- Dense Cosine Exact, Exact Product Filter, Top-K `5`, Threshold `0.5`
- Scope `MODEL_CAPABILITY_SCOPE_V1`
- Intent `MANUAL_DOMAIN_INTENT_V1`
- 비교군: 원문 Query Dense / Draft Alias 확장 Query Dense
- 총 DEV Case Result 70건, Hard Negative Result 14건

Alias는 Corpus나 Evidence 원문을 바꾸지 않고 Query 뒤에 검수 가능한 공식 용어를
보조 추가했다. Draft Alias 실행은 `--allow-draft-aliases`를 명시해야 하며,
승인되지 않은 Alias가 실수로 일반 실행되는 것을 차단했다.

## 전체 결과

| Variant | Hit@1 | Hit@3 | Hit@5 | MRR | nDCG@5 | 무근거 중단 | 잘못된 제품 Hit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 원문 Dense | 0.666667 | 0.925926 | 0.925926 | 0.783951 | 0.834322 | 1.0 | 0 |
| Alias Dense | 0.703704 | 0.962963 | 0.962963 | 0.814815 | 0.870533 | 1.0 | 0 |
| 변화 | +0.037037 | +0.037037 | +0.037037 | +0.030864 | +0.036211 | 0 | 0 |

지연시간은 48개 JAC104 후보를 메모리에서 비교한 검색 구간 진단값이며, 운영 DB
지연이나 동시성 성능으로 확대하지 않는다.

## Rule별 판정

### `ALIAS-JAC104-LEAK-001`

- 상태: `SUPPORTED_ON_DRAFT_DEV_PENDING_REVIEW`
- 보조 용어: `누수`, `제품 누수 발생`
- 활성화: `0004`, `0021`, `0027`
- 복구: `0027` Top-5 Miss → 3위
- 순위 개선: `0021` 2위 → 1위
- Positive 회귀: 0
- 예상 밖 DEV 활성화: 0
- Hard Negative 활성화: 0

위 결과는 Data Owner 승인 완료가 아니라 검수 후보로 보낼 근거다.

### `ALIAS-JAC104-NO-WATER-001`

- 상태: `NOT_SUPPORTED_ON_CURRENT_DRAFT_DEV`
- 보조 용어: `출수되지 않음`, `물 출수`
- 활성화: `0025`
- 복구: 0
- Positive 회귀: 0
- 예상 밖 DEV 활성화: 0
- Hard Negative 활성화: 0

Alias를 추가해도 `0025`의 기대 Evidence가 Top-5에 들어오지 않았으므로 채택하지
않는다. Parameter를 즉시 추가 조정하면 동일 DEV 한 건에 과적합될 위험이 있어
이번 실험에서 중단한다.

## Hard Negative 보강

부정형만 검사하면 과확장을 놓칠 수 있어 다음 범위를 포함한 7건을 사용했다.

- 누수가 아니거나 물이 새지 않는다는 명시적 부정
- 기사 도착 시간을 묻는 무출수 부정
- 생수병을 비운다는 비제품 문맥
- 정수기가 아닌 옆 생수병 누수
- 청소 중 쏟은 물로 바닥이 젖은 문맥
- 수도꼭지 단수이고 정수기는 정상인 문맥

초기 Rule은 마지막 세 문맥에서 예상하지 않은 활성화가 발생했다. `정수기가
아니라`, `정수기는 정상`, `청소 중 쏟`, `수도꼭지` 제외 조건을 명시한 뒤 최종
7건 모두 예상 밖 활성화 0, Alias로 인한 신규 검색 결과 0을 확인했다.

## 판정과 다음 순서

- Query Expansion 접근: `PARTIALLY_SUPPORTED_ON_DRAFT_DEV`
- 누수 Alias: `DATA_OWNER_REVIEW_CANDIDATE`
- 무출수 Alias: `REJECTED_ON_CURRENT_DRAFT_DEV`
- 운영 Query Expansion 연결: `BLOCKED`
- Hybrid·Reranker 착수: `DEFERRED`
- 공식 성능 발표: `BLOCKED_GOLD_TWO_PERSON_REVIEW`

다음 순서는 누수 Alias의 표현·제외 조건을 Data Owner가 검수하고, Gold가 승인된
뒤 손대지 않은 TEST와 SAFETY에서 독립 검증하는 것이다. 무출수 Case는 Alias를 더
붙이기보다 기대 Evidence·Chunk Lineage와 Query 표현의 관계를 별도 분석해야 한다.

## 재현 명령

```powershell
.\ai\.venv\Scripts\python.exe -B -m ai.scripts.run_alias_query_expansion_v1 `
  --allow-draft-gold --allow-draft-aliases
```

## 산출물

- `ai/configs/experiments/alias_query_expansion_profiles.yaml`
- `ai/evaluation/query_expansion.py`
- `ai/scripts/run_alias_query_expansion_v1.py`
- `ai/evaluation/reports/experiments/alias_query_expansion_v1/`
- `ai/tests/unit/test_alias_query_expansion_v1.py`
