# A3 Experiment Runner 계약 구현·QA 결과

> 실행일: 2026-08-10 KST  
> Profile: `experiment_runner_contract_v1`  
> 판정: `RUNNER_CONTRACT_COMPLETE`

## 범위

UI나 실제 모델 실행 전에 동일 입력으로 재현 가능한 CLI와 결과 파일 계약을
구현했다. A3에서는 검색 결과를 흉내 내지 않고 `VALIDATE_ONLY` 모드만 제공한다.

포함 범위:

- Profile·Dataset Alias·Split 입력 검증
- Gold Draft Dataset과 A1 Corpus 파일 Hash 기록
- DEV·TEST·SAFETY Split 선택
- Manifest Runtime·Git·Profile·Dataset·Corpus Lineage 기록
- Case Result와 Retrieval·Generation·Safety·Performance Summary 생성
- 공통 Result Bundle Schema 검증
- 실제 실행 전 성능 수치 생성 차단

제외 범위:

- Chunk 생성
- Embedding 모델 적재
- Vector DB 검색
- Reranker·Generator 실행
- 성능 지표 계산
- Full Corpus Baseline
- Playground UI

## 실행 명령

```powershell
python -m ai.scripts.run_rag_experiment `
  --profile experiment_runner_contract_v1 `
  --dataset rag_gold_v1 `
  --split DEV `
  --mode validate-only `
  --run-id a3_runner_contract_smoke_v1
```

## 생성 결과

| 항목 | 결과 |
|---|---:|
| 전체 Gold Draft Case | 60 |
| 선택 Split | `DEV` |
| 선택 Case | 35 |
| 실행 Case | 0 |
| Result 파일 | 6 |
| Runner 전용 테스트 | 3 통과 |
| Gold 2인 승인 | 0 |

생성 파일:

```text
ai/evaluation/reports/experiments/a3_runner_contract_smoke_v1/
├─ manifest.json
├─ case_results.jsonl
├─ retrieval_summary.json
├─ generation_summary.json
├─ safety_summary.json
└─ performance_summary.json
```

## Manifest 기록 범위

Manifest에는 다음 항목을 기록한다.

- Dataset Version·Hash·Manifest Hash·Split·검수 상태
- Corpus Version·개별 파일 Hash·통합 Hash
- Chunking Profile과 Parameter
- Embedding Model·Revision·Dimension
- Retrieval Profile·Top-K·Threshold·Reranker
- Generator·Prompt Version·Temperature
- Python·OS·CPU·GPU·RAM·VRAM
- Git Commit·Branch·Working Tree 상태
- 시작·종료 시각과 실행 시간
- 산출물 경로와 발표 제한

A3에서는 아직 정해지지 않은 Embedding·Generator·GPU·VRAM 값 등을 `null` 또는
`NOT_CONFIGURED_UNTIL_A3_1`로 명시한다. 값을 추정해서 채우지 않는다.

## 가짜 성능 수치 차단

각 Case Result는 다음 상태다.

```text
execution_status=NOT_EXECUTED_VALIDATION_ONLY
actual=null
metrics=null
error=null
```

네 Summary도 `executed_case_count=0`, `metrics={}`를 유지한다. 따라서 이 결과는
CLI·입력·산출물 계약 검증 근거이지 검색 Baseline이 아니다.

## 판정

```text
CLI Contract: READY
Result Schema: READY
Manifest Generation: READY
Model/DB Execution: NOT_STARTED
Performance Publication: BLOCKED
```

다음 A3-1에서 실제 Chunking·Embedding·검색 Adapter를 연결하고 Full Corpus
Baseline을 실행해야 성능 지표를 생성할 수 있다.

## 산출물

- `ai/configs/experiments/experiment_runner_contract_v1.yaml`
- `ai/evaluation/schemas/experiment_result_bundle_v1.schema.json`
- `ai/scripts/run_rag_experiment.py`
- `ai/tests/unit/test_rag_experiment_runner.py`
- `ai/evaluation/reports/experiments/a3_runner_contract_smoke_v1/`
