# B1 청킹 비교 실험 김은진 재검증 공유본

> 실행일: 2026-08-12 KST
> 실행자 역할: 김은진 — 데이터·QA·DevOps
> 상태: `DRAFT_CHUNKING_EXPERIMENT_COMPLETE`
> 공식 성능 사용: 불가 — Gold 60건 2인 검수와 PM Gate 대기
> Source HEAD: `240d0a1b88c09bb5cd1150f4b38568ff38a6e3ce` (`eunjin`, Clean)

## 1. 공유 목적과 판정 범위

이 문서는 이동윤이 구현한 B1 청킹 비교 Runner를 김은진 로컬에서 다시 실행하고,
실행 원본과 해석을 팀에 공유하기 위한 재검증 기록이다.

2026-08-11 실행 문서의 Dirty HEAD `b5c324b...` 결과를 현재 결과로 재사용하지
않았다. 이번 결과는 수정된 Gold·Corpus와 Clean HEAD `240d0a1...`에서 새로
생성했다.

현재 수치로는 `parent_child_v1 + EXACT_PRODUCT_FILTER`가 1순위 검색과 순위
지표에서 가장 높은 후속 후보다. 그러나 Gold 미검수와 페이지 단위 Evidence ID
병합 문제가 남아 있으므로 운영 Profile 선정 결과가 아니다.

## 2. 고정 입력과 실행 조건

| 항목 | 고정값 |
|---|---|
| Python | `3.13.13` |
| OS·Device | Windows 11, CPU |
| Embedding | `BAAI/bge-m3` |
| Revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| Dimension | `1024`, Normalize |
| Retrieval | Dense Cosine Exact, Top-K 5, Threshold 0.4 |
| Filter | `NO_PRODUCT_FILTER`, `EXACT_PRODUCT_FILTER` |
| Gold | DEV 35건 |
| Corpus | JAC104 44쪽 + IAC425 52쪽 = 96 Source Page |
| 평가 조합 | 5 Profile × 2 Filter × 35 Case = 350건 |

입력 SHA-256:

- Gold: `9B52AF026B7C8F21AC4D59ECD4D0F2E1A528E78448225EBE1F5E542A71A8E54A`
- Corpus: `FE62AF6030045C532BC8E68D11C5461E8C65BD16DCD6758E0C2412C8C37C472C`
- Chunking Profile: `BADA1E1E22B52479C5ADD973641062E4F54FD2E2E7C15E842608AA267D4890F3`
- Baseline Profile: `E1B38207CD291B67CBF64155F11BCDF7DE308650C8E742CA4D332A2F6FA255EA`

## 3. 실행 명령

저장소 루트에서 실행했다.

```powershell
.\ai\.venv\Scripts\python.exe -B `
  -m ai.scripts.run_chunking_experiment_v1 `
  --allow-draft-gold `
  --output-directory data\.runtime\rag_experiments\b1_chunking_240d0a1_20260812_01
```

실행 결과:

- Exit code `0`
- `case_result_count=350`
- Runner 상태 `DRAFT_CHUNKING_EXPERIMENT_COMPLETE`
- 실행 Manifest의 Git 상태 `working_tree_clean=true`
- 실행 전후 HEAD 동일

단위 회귀:

```powershell
.\ai\.venv\Scripts\python.exe -B -m pytest `
  ai\tests\unit\test_chunking_experiment_v1.py -q -p no:cacheprovider
```

결과: `4 passed in 1.27s`

## 4. Exact Product Filter 결과

양성 Case는 27건이다.

| Profile | Hit@1 | Hit@3 | Hit@5 | MRR | nDCG@5 | Chunk | Lineage |
|---|---:|---:|---:|---:|---:|---:|---:|
| `current_chunking_full_corpus_v1` | 0.5926 | 0.9259 | 0.9259 | 0.7469 | 0.8036 | 96 | 1.0 |
| `page_v1` | 0.5926 | 0.9259 | 0.9259 | 0.7469 | 0.8036 | 96 | 1.0 |
| `fixed_512_v1` | 0.5926 | 0.9259 | 0.9259 | 0.7469 | 0.8036 | 98 | 1.0 |
| `section_v1` | 0.5556 | 0.8148 | 0.9259 | 0.7006 | 0.7478 | 56 | 1.0 |
| `parent_child_v1` | **0.6667** | **0.9259** | **0.9259** | **0.7840** | **0.8343** | 108 | 1.0 |

해석:

- `parent_child_v1`은 기준선보다 Hit@1이 `+0.0741`, MRR이 `+0.0371` 높다.
- Hit@5는 기준선과 같으므로 새로운 정답을 더 찾았다기보다 정답 순위를 올린
  결과에 가깝다.
- `current`와 `page_v1`은 Profile ID와 지연시간을 제외한 70개 결과가 동일하다.
- Exact Filter의 Wrong Product Hit는 모든 Profile에서 `0`이다.
- Exact Filter의 NO_EVIDENCE 정확도는 모든 Profile에서 `0.25`다.

제품 필터를 끄면 Wrong Product Hit 합계가 Profile별 `70~92`건 발생했다. 이 값은
Case 수가 아니라 35개 질의의 Top-K 결과 안에서 집계한 잘못된 제품 Hit 수다.

## 5. 결론에 영향을 주는 Case 검수

| Case | 결과 | 해석 |
|---|---|---|
| `RAGV2-GOLD-0004` 누수 | Exact Filter 전 Profile Hit@1 | 수정된 누수 페이지 계보가 평가에 반영됨 |
| `RAGV2-GOLD-0025` 무출수 구어체 | 전 Profile Hit@5 실패 | 페이지 37의 무출수 행이 다른 증상 문장에 희석됨 |
| `RAGV2-GOLD-0027` 바닥 누수 구어체 | 전 Profile Hit@5 실패 | 33쪽 물받이 등 일반 물 표현이 먼저 검색됨 |
| `RAGV2-GOLD-0036` 복합 | Exact 전 Profile ALL 완료 | 냉수 온도와 저출수 Evidence 모두 검색 |
| `RAGV2-GOLD-0037` 복합 | Exact 전 Profile ALL 완료 | 누수와 소음 Evidence 모두 검색 |
| `RAGV2-GOLD-0038` 복합 | Exact 전 Profile ALL 완료 | 냄새와 저출수 Evidence 모두 검색 |

`ALL` 정책 0036~0038은 nDCG를 계산하지 않으며, Hit@5 성공인데 Evidence
Completion Rank가 없는 결과는 `0건`이었다.

## 6. 데이터 전처리 제한

현재 Full Corpus 생성기는 37쪽 전체에 무출수·냉수 온도·소음 Evidence ID를,
38쪽 전체에 누수·맛/냄새·저출수·순간온수 Evidence ID를 함께 부여한다.
`section_v1`은 연속 Section의 Evidence ID를 합치므로 하나의 Section Chunk가 여러
근거를 동시에 만족할 수 있다.

따라서 다음 보완 전에는 `section_v1`의 복합 질문 성능과 최종 Profile 순위를
공식 결론으로 사용하지 않는다.

1. 37~39쪽을 증상·원인·조치 행 단위 Child Chunk로 분리
2. 각 Child에 자기 Evidence ID만 부여
3. 페이지 Parent는 문맥 제공용, Child는 검색·평가용으로 분리
4. 기존 검증 데이터 `data/processed/structured/rag/mvp/rag_verified_sample.jsonl`
   7건을 Full Corpus에 결합
5. 누수 5·7·38쪽을 하나의 Evidence Group 아래 개별 Source Variant로 보존
6. 행 경계가 준비된 후 `table_row_v1`을 실행

행 단위 검증 샘플만 사용한 추가 진단에서는 0025 정답이 2위, 0027 누수 정답이
5위였다. 0027과 누수 문장의 유사도는 38쪽 정규화 요약 `0.4467`, 5쪽 원문
`0.5022`, 7쪽 원문 `0.5139`로 확인됐다. 이는 Gold 문장을 Corpus에 주입할 근거가
아니라, 실제 5·7쪽 Source Variant를 누락하지 않아야 한다는 근거다.

## 7. 공유 산출물과 무결성

Git 추적용 원본은 다음 경로에 고정했다.

- [preflight.json](../../../data/processed/validation/rag_experiments/b1_chunking_240d0a1_20260812_01/preflight.json)
- [manifest.json](../../../data/processed/validation/rag_experiments/b1_chunking_240d0a1_20260812_01/manifest.json)
- [case_results.jsonl](../../../data/processed/validation/rag_experiments/b1_chunking_240d0a1_20260812_01/case_results.jsonl)
- [summary.json](../../../data/processed/validation/rag_experiments/b1_chunking_240d0a1_20260812_01/summary.json)
- [failure_analysis.json](../../../data/processed/validation/rag_experiments/b1_chunking_240d0a1_20260812_01/failure_analysis.json)

로컬 Runner는 Windows CRLF로 파일을 생성했고 저장소 `.gitattributes`는 공유
텍스트를 LF로 정규화한다. 내용 변경과 줄바꿈 정규화를 구분할 수 있도록 두 Hash를
함께 기록한다. GitHub에서 내려받은 LF 파일은 `Git LF SHA-256`으로 확인한다.

| 파일 | 로컬 실행본 CRLF SHA-256 | Git LF SHA-256 |
|---|---|---|
| `case_results.jsonl` | `390C3972B5893692E226262C72AADD03D4996055F6AAE51FACE8F8587228547A` | `D9F56716C4FAED47B8F69F76C9068571A4D8C17F163269BD2339921DD1BDACFE` |
| `failure_analysis.json` | `22F8F2FE5CEA4527ED2C7B6ADC5E97E8A79A106F1AA7730A772CACF312EF7EB9` | `0CF706B740C615314C3C527C5373FCC08208E988D4259DBD2F191857FFFDFD4E` |
| `manifest.json` | `9426C3779B02F1389D5F83773388A7E208944F9FFFFFF3BD4B00994CB80148BC` | `065D81949FAC98FE48A2F6C611CE47D22CC4D6DBF69533E4E367ADEAF025E1AA` |
| `preflight.json` | `63663A952FA39C25F5696F27D79B7A6307FA0F555DFF4F9DA684F1E0FD9F64AC` | `61A6DABF69AB6D69818A1092EE1BB0AC080D66AEC7A9F9E731DF330605987F69` |
| `summary.json` | `960D2D845EBFB9E67FB3B91F5FF1C9BF489C797B91DA2CDF5D69557FAB78F03B` | `A5055582ADA00BE9BEC026505DE487633B5CA4CB507372C12F40109829D0207E` |

## 8. 남은 Gate와 담당자 논의

1. 김은진: 행 단위 전처리 데이터·계보·QA 제안 작성
2. 이동윤: 행 단위 Corpus 소비 방식과 Evidence 병합 평가 로직 검토
3. 이동윤: 0025·0027을 Query/Rerank 실험으로 재검증
4. 이동윤: Runtime Identity Retrieval Policy SHA 불일치 정리
5. 윤승혁: Gold 승인 후 상위 2개 Profile 선정 Gate 판정

Runtime Identity SHA 불일치는 이번 B1 계산에 직접 사용되지 않았지만 전체 AI
Unit Gate의 알려진 실패이므로 공식 결과 승격 전 해결해야 한다.
