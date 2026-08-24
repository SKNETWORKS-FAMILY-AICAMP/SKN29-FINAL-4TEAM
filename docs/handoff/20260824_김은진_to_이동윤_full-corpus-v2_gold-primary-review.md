# Full Corpus v2·Gold 1차 검수 이동윤 인계

> 인계자: 김은진 — 데이터·QA·DevOps
> 인수자: 이동윤 — AI 담당·독립 2차 검수자
> 인계 브랜치: `eunjin`
> 작업 기준 HEAD: `e99cf78faa58a40f2cec49281119c437b594e470`
> 작성일: 2026-08-24 KST

## 1. 인계 결론

Full Corpus v2 데이터 인계본과 Gold 질문·라벨 1차 검수를 완료했다. 1차 검수
미결 항목은 0건이지만 Gold 원본 병합, 독립 2차 검수, 사람 최종 서명, Full B1
재실행과 AI Runner 연결은 수행하지 않았다.

현재 상태는 다음으로 제한한다.

- `FULL_CORPUS_V2_DATA_HANDOFF_READY`
- `GOLD_POST_QUERY_LABEL_PRIMARY_REVIEW_COMPLETED_HUMAN_SIGNOFF_PENDING`
- `IAC425_GOLD_CANDIDATES_READY`

이동윤은 이 인계본의 독립 2차 검수자다. 자동 판정이나 김은진의 1차 결정과
독립적으로 질문 의미, Evidence 계보, `ANY/ALL/NONE`, 위험도와 안내 정책을
확인해야 한다.

## 2. 고정 입력

| 입력 | SHA-256 |
|---|---|
| `ai/evaluation/corpora/full_corpus_chunks_v1.jsonl` | `4B0890BC079207C8F9AA9DB1208D371F295BD53537A9B692FA6B7D686333FABC` |
| `ai/evaluation/datasets/gold/rag_gold_v1.jsonl` | `9B52AF026B7C8F21AC4D59ECD4D0F2E1A528E78448225EBE1F5E542A71A8E54A` |

Gold 원본은 김은진 작업에서 수정하지 않았다. 다른 SHA의 Gold와 검수 결과를
혼합하면 안 된다.

## 3. Full Corpus v2 결과

| 구분 | 건수 |
|---|---:|
| 기존 Source Page | 91 |
| JAC104 Child | 15 |
| 보존 Chunk | 5 |
| 검색 후보 합계 | 111 |
| JAC104 검색 후보 | 59 |
| IAC425 검색 후보 | 52 |
| Context 전용 Parent | 5 |

JAC104 5·7·37·38·39쪽을 교체했고 Coverage Map에서 모든 행을 `CHILD`,
`PRESERVATION`, `NON_SEARCHABLE_STRUCTURE` 중 하나로 분류했다. Parent 5건은
`CONTEXT_ONLY`이며 111건에 포함하지 않았다.

주요 파일:

- `data/processed/structured/rag/experimental/full_corpus_chunks_v2.jsonl`
- `data/processed/structured/rag/experimental/full_corpus_v2_coverage.json`
- `data/processed/metadata/full_corpus_v2_handoff_manifest.json`
- `data/processed/validation/rag_experiments/full_corpus_v2_qa.json`

## 4. Gold 질문·라벨 1차 검수 결과

질문 60건은 제안문 승인 23건, 문구 변경 36건, 질문 제외 제안 1건으로
정리했다. `RAGV2-GOLD-0040`은 제외 제안일 뿐 원본에서 삭제하지 않았다.

질문 확정 후 라벨 처리 경로는 다음과 같다.

| 처리 경로 | 건수 |
|---|---:|
| 김은진 직접 결정 | 8 |
| AI 근거 대조 처리 | 18 |
| 기존 라벨 유지 | 33 |
| 질문 제외 제안 | 1 |
| 합계 | 60 |
| 1차 미결 | 0 |

중요 변경은 다음과 같다.

- `0001`: `caution / PARTIAL_STOP` 유지
- `0016`, `0017`, `0028`, `0033`: 조건에 맞춰 `PENDING_CONSULTATION`
- `0039`: `COMPOUND → DIRECT`, 무출수 Evidence 1건을 `ANY`
- `0043`: 위험 행동을 전제로 하지 않도록 플러그 주변 물기·전원 코드 과열 질문으로 교정
- `0045`: P004·P005를 `ALL`, `danger / TOTAL_STOP`
- `0047`: 사고 후 전면 중단이 아닌 예방 질문으로 `caution / PARTIAL_STOP`
- `0049`: 정수기에서 타는 냄새가 나는 것으로 질문을 명확히 하고 P004·P005를 `ALL`
- `0052`: 구매 경로와 혼합되지 않게 현재 필터 판매 가격만 묻는 `NO_EVIDENCE` 질문으로 교정
- `0051~0060`: 가격·실시간 정보·교차 제품·금지 모델을 `NONE / CONSULTATION_ONLY`로 유지

검수 파일:

- `data/config/rag/gold_v1_query_rewrite_proposals.json`
- `data/processed/validation/rag_experiments/gold_v1_query_human_review_working.json`
- `data/processed/validation/rag_experiments/gold_v1_post_query_label_revalidation_packet.json`
- `data/processed/validation/rag_experiments/gold_v1_post_query_label_human_review_working.json`

모든 사람 서명 상태는 `PENDING`이다. 이 파일은 Gold 원본이나 최종 승인본이
아니다.

## 5. IAC425 후보

기존 3모델 평가 Case 19건 중 양성 18건만 Gold 후보로 재사용했다. 나머지 1건은
부정 Case이므로 양성 후보로 바꾸지 않았다. 따라서 후보 수는 계획 문구의 19건이
아니라 18건이다.

- 파일: `data/config/rag/iac425_gold_candidates.json`
- Split: `DEV`
- 상태: `HUMAN_REVIEW_PENDING`
- Gold 원본 병합: 미수행

## 6. 이동윤 2차 검수 순서

1. Gold 원본 SHA-256이 고정값과 같은지 확인한다.
2. `gold_v1_post_query_label_revalidation_packet.json`의 60건과 확정 질문을 대조한다.
3. 변경 제안 7건과 `0040` 질문 제외 제안을 독립적으로 승인·반려한다.
4. P004·P005를 함께 쓰는 `0045`, `0049`의 `ALL` 정책을 원본 화면과 대조한다.
5. `0051~0060`이 정확 모델 필터와 금지 문서 조건에서도 무근거인지 재확인한다.
6. 검수자 ID, Case별 결정과 검수 시각을 기록한다.
7. 승인된 변경만 `ai/evaluation/**` Gold 소유 영역에서 별도 반영한다.
8. Dataset Version과 최종 Case ID를 정한 뒤 Full B1을 재실행한다.

2차 검수 완료 전 `TWO_PERSON_APPROVED`, Gold 병합 완료 또는 B1 성능 개선을
선언하지 않는다.

## 7. 재현·검증 명령

저장소 루트에서 실행한다.

```powershell
.\ai\.venv\Scripts\python.exe -B `
  -m data.tools.rag_experiments.build_full_corpus_v2_review

.\ai\.venv\Scripts\python.exe -B `
  -m data.tools.rag_experiments.build_gold_query_label_revalidation

.\ai\.venv\Scripts\python.exe -B `
  -m data.tools.rag_experiments.qa_full_corpus_v2_review

.\ai\.venv\Scripts\python.exe -B -m unittest discover `
  -s data\tools\tests -v

.\ai\.venv\Scripts\python.exe -B data\tools\pipeline.py qa --verify-rebuild

.\ai\.venv\Scripts\python.exe -m pytest `
  ai\tests\unit\test_chunking_experiment_v1.py `
  ai\tests\unit\test_row_child_partial_experiment_v2.py `
  -q -p no:cacheprovider
```

김은진 최종 실행 결과는 데이터 단위 테스트 135건 통과, Pipeline QA 오류·경고
0건, canonical drift 0건, AI 청킹 표적 테스트 6건 통과다.

## 8. 인계 후 이동윤 산출물

- 독립 2차 검수 결과와 검수자 기록
- 승인·반려된 필드별 Gold 변경 목록
- Gold 원본 병합 Commit과 Dataset Version
- Full B1 결과 Manifest와 고정 Corpus·Model Revision
- AI Runner 연결 결과 또는 연결 보류 사유

운영 청킹 Profile 선정과 Parent 제한 Context 설계는 B1 결과가 나온 뒤 별도
의사결정으로 진행한다.
