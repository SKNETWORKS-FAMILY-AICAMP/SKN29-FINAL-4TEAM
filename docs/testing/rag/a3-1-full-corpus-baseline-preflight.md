# A3-1 Full Corpus Baseline 구현·실행 결과

> 실행일: 2026-08-11 KST
> Profile: `full_corpus_baseline_v1`  
> 상태: `DRAFT_BASELINE_COMPLETE_D01_D02_APPLIED`
> 적용 입력: Gold `1.0.0-draft.2`, Corpus `1.0.1`, 평가 계약 `d01_evidence_policy_v1`

## 결론

Full Corpus 생성과 BGE-M3 Dense Cosine Runner 실제 실행을 완료했다. 사용자 제공
`test_env`에서 CPU로 96개 문서 Chunk와 DEV 질의 35건을 임베딩하여 210개 Case
Result 및 요약 파일을 생성했다.

현재 결과는 Gold 2인 검수 전 Draft다. 또한 DEV Positive 27건이 모두 JAC104
문서에만 연결되어 있으므로 `IAC425_ONLY` 결과는 IAC425 검색 품질 평가값으로
사용할 수 없다.

## Full Corpus

A1에서 정비한 공식 매뉴얼 페이지를 현재 저장 단위 기준 검색 Chunk로 고정했다.

| Corpus | Chunk 수 |
|---|---:|
| JAC104/JCC104 | 44 |
| IAC425 | 52 |
| 통합 | 96 |

Chunking Profile:

```text
current_source_page_v1
```

페이지 레코드 1개를 검색 Chunk 1개로 사용한다. 이는 A3-1의 재현 가능한 시작
단위이며 Phase B에서 최종 청킹 전략으로 승인됐다는 뜻은 아니다.

Full Corpus SHA-256:

```text
FE62AF6030045C532BC8E68D11C5461E8C65BD16DCD6758E0C2412C8C37C472C
```

FAQ는 A3-1 수행 목록에 명시된 `JAC104/JCC104 + IAC425` 매뉴얼 비교 범위에서
제외했다. 조건부 FAQ는 이후 별도 Profile에서 비교한다.

## 구현된 실제 실행 경로

Runner는 다음 조합을 실행하도록 구현했다.

| 축 | 값 |
|---|---|
| Corpus | `JAC104_ONLY`, `IAC425_ONLY`, `JAC104_IAC425_COMBINED` |
| 제품 Filter | `NO_PRODUCT_FILTER`, `EXACT_PRODUCT_FILTER` |
| Dataset | Gold Draft `DEV` 35건 |
| Embedding | `BAAI/bge-m3` Revision 고정 |
| 검색 | In-memory Exact Dense Cosine |
| Top-K | 5 |
| Threshold | 0.4 |

기록 지표:

- Hit@1·3·5
- MRR
- nDCG@5 (`ALL` 3건은 정의 확정 전까지 제외)
- Wrong Product Hit
- No-evidence 빈 검색 결과율 (D-03 전까지 검색 진단값)
- 문서·질의 Embedding 및 검색 시간

정상 실행 시 `3 Corpus × 2 Filter × 35 Case = 210`개의 Case Result를 만든다.

## 실제 실행 결과

| 항목 | 결과 |
|---|---:|
| 실행 상태 | `DRAFT_BASELINE_COMPLETE` |
| Python / Device | 3.10.20 / CPU |
| 문서 Chunk | 96 |
| DEV Query | 35 |
| Case Result | 210 |
| 문서 Embedding | 447.59초 |
| 질의 Embedding | 6.06초 |
| 검색 | 0.31초 |
| 전체 | 453.96초 |

주요 Draft 지표:

| Corpus / Filter | Hit@1 | Hit@3 | Hit@5 | MRR | nDCG@5 | No-evidence 빈 결과율 |
|---|---:|---:|---:|---:|---:|---:|
| JAC104 / Filter | 0.5926 | 0.9259 | 0.9259 | 0.7469 | 0.8036 | 0.250 |
| JAC104 / No Filter | 0.5926 | 0.9259 | 0.9259 | 0.7469 | 0.8036 | 0.125 |
| 통합 / Filter | 0.5926 | 0.9259 | 0.9259 | 0.7469 | 0.8036 | 0.250 |
| 통합 / No Filter | 0.4444 | 0.8148 | 0.8519 | 0.6142 | 0.7148 | 0.000 |
| IAC425 / Filter | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 1.000 |
| IAC425 / No Filter | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.000 |

IAC425 0점은 실패가 아니라 해당 Corpus에 정답이 존재하는 DEV Positive 문항이
0건이기 때문이다. 반대로 통합 Corpus에서 제품 Filter를 제거하면 다른 제품 Chunk가
상위 결과에 섞여 JAC104 대비 Hit@1과 MRR이 하락했다. 이 수치는 평가 문항 검수 전
방향성 확인용이며 공식 성능으로 발표하지 않는다.

`nDCG@5` 평균은 `ANY` Positive 24건만 대상으로 하며 `ALL` 3건은 제외했다.
No-evidence 값은 D-03 Answerability Gate 정확도가 아니라 검색 결과가 비어 있는 비율이다.

## 테스트

실제 저장 결과와 혼동되지 않도록 테스트용 결정적 Embedder는 임시 디렉터리에서만
사용했다.

| 테스트 | 결과 |
|---|---:|
| 96개 Chunk Schema·건수 | PASS |
| Chunk Dataset 결정적 재생성 | PASS |
| 3 Corpus × 2 Filter Dense 계산 | PASS |
| 210개 Case Result·Summary 생성 | PASS |
| D-01·D-02 포함 AI 영향 범위 회귀 | 26 PASS |

테스트용 수치는 저장소의 Baseline 보고서에 기록하지 않았다.

## Gold 승인 제한

Gold 60건은 아직 모두 `UNREVIEWED_DRAFT`다. 실제 Draft Baseline 실행은
완료했지만 2인 검수와 IAC425 Positive 문항 보강 전까지 다음 상태를 유지한다.

```text
official_comparison_baseline=false
metrics_publishable_as_official=false
```

## 완료 판정과 남은 공식 승격 조건

A3-1의 구현·Draft 실행은 완료다. 공식 Phase B 비교 기준으로 승격하려면 다음 작업이
남아 있다.

1. Gold 60건을 2인이 검수한다.
2. IAC425 문서를 정답 근거로 갖는 Positive 평가 문항을 DEV/TEST에 보강한다.
3. 승인된 Gold와 IAC425 Positive 문항으로 동일 Profile을 다시 실행하고 공식 사용 가능 상태를 확인한다.

## 산출물

- `ai/evaluation/schemas/full_corpus_chunk_v1.schema.json`
- `ai/evaluation/corpora/full_corpus_chunks_v1.jsonl`
- `ai/evaluation/corpora/full_corpus_chunks_v1_manifest.json`
- `ai/configs/experiments/full_corpus_baseline_v1.yaml`
- `ai/scripts/build_full_corpus_chunks_v1.py`
- `ai/scripts/run_full_corpus_baseline_v1.py`
- `ai/tests/unit/test_full_corpus_baseline_v1.py`
- `ai/evaluation/reports/experiments/full_corpus_baseline_v1/preflight.json`
- `ai/evaluation/reports/experiments/full_corpus_baseline_v1/manifest.json`
- `ai/evaluation/reports/experiments/full_corpus_baseline_v1/case_results.jsonl`
- `ai/evaluation/reports/experiments/full_corpus_baseline_v1/retrieval_summary.json`
- `ai/evaluation/reports/experiments/full_corpus_baseline_v1/performance_summary.json`
