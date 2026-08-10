# A4 Experiment Playground v0 구현·실행 결과

> 실행일: 2026-08-10 KST  
> 상태: `DRAFT_RETRIEVAL_PLAYGROUND_COMPLETE`  
> 공식 성능 사용: 불가

## 결론

A3-1의 BGE-M3·페이지 Chunk·Dense Cosine 구성을 단일 Query로 실행할 수 있는
실험 전용 페이지를 구현했다. 운영용 관리자 화면에는 연결하지 않았고, AI FastAPI의
별도 `/experiments/playground` 경로에서만 제공한다.

A4 v0는 Retrieval 실험 시작에 필요한 최소 범위다. Generator 선택 영역은 화면에
표시하지만 실제 Generation·Grounding·Safety 실행은 아직 연결하지 않았으며 결과에도
`NOT_IMPLEMENTED_V0` 또는 `NOT_EXECUTED`로 명시한다.

## 실행 방법

기존 `test_env`에서 다음 명령을 실행한다.

```powershell
python -B -m uvicorn ai.app.main:app --host 127.0.0.1 --port 8001
```

브라우저에서 다음 주소를 연다.

```text
http://127.0.0.1:8001/experiments/playground
```

Docker와 DB는 필요하지 않다. BGE-M3 모델 Snapshot과 생성된 문서 Index를 로컬에서
사용한다.

## v0 입력

| 항목 | 지원 범위 |
|---|---|
| Product | `WPUJAC104DWH`, `WPUIAC425SNW` |
| Query | 자유 입력, 최대 4,000자 |
| Corpus | JAC104, IAC425, 통합 |
| Chunking | `current_source_page_v1` |
| Embedding | `bge_m3` |
| Retrieval | `dense_cosine_exact_v1` |
| Top-K | 1~10 |
| Product Filter | 적용/미적용 |
| Generator | `NOT_IMPLEMENTED_V0` |

## v0 출력

- 검색 Rank, 문서·페이지, Score, 본문 미리보기
- Query와 정확히 일치하는 Draft Gold가 있을 때 Gold Evidence와 PASS/FAIL
- Wrong Product Hit 수
- Query Embedding·Retrieval·전체 Latency
- Schema 상태
- Generation·Grounding·Safety 미실행 상태

## 실제 단일 Query 확인

```text
Product: WPUJAC104DWH
Query: 정수기 밑이 축축하고 물이 새는 것 같아요.
Corpus: JAC104_IAC425_COMBINED
Product Filter: true
Top-K: 5
```

| 결과 | 값 |
|---|---:|
| HTTP 상태 | 200 |
| 실행 상태 | `DRAFT_RETRIEVAL_COMPLETE` |
| 검색 결과 | 5건 |
| Gold Case | `RAGV2-GOLD-0021` |
| Gold Evidence | JAC104 p.38 |
| Gold 순위 | 2위 |
| Top-5 | PASS |
| Wrong Product Hit | 0 |
| Query Embedding | 22,669.05 ms |
| Dense Retrieval | 37.28 ms |
| 전체 | 22,706.37 ms |

첫 Query 시간에는 BGE-M3 모델 로딩이 포함된다. 같은 서버 프로세스의 후속 Query는
96개 문서를 다시 임베딩하지 않고 저장된 문서 Index를 재사용한다.

## 문서 Index

| 항목 | 값 |
|---|---|
| Index | `playground_bge_m3_page_v1` |
| Shape | 96 × 1024 |
| Dtype | float32 |
| Corpus SHA-256 | `6947CDE3543BB080394D4C953BE22A43A76ED80F4686ED5360B30628109AB240` |
| Model Revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| Build Time | 434.30초 |

## 테스트

| 검사 | 결과 |
|---|---:|
| Index 생성·재로딩 | PASS |
| 단일 Query Gold·제품 Filter 계산 | PASS |
| 페이지·API 연결 | PASS |
| A3-1 회귀 | PASS |
| 합계 | 7 통과 |

실제 HTTP POST도 별도로 실행하여 상태 200, Gold PASS, 결과 5건, Wrong Product Hit
0건을 확인했다. 로컬 브라우저 시각 검증은 실행 환경의 사용자 프로필 접근 권한으로
열리지 않았지만 HTML 페이지 응답과 API 연결 테스트는 통과했다.

## 산출물

- `ai/app/experiments/playground.py`
- `ai/app/interfaces/http/routes/experiment_playground_routes.py`
- `ai/app/interfaces/http/static/experiment_playground_v0.html`
- `ai/scripts/build_experiment_playground_index_v1.py`
- `ai/scripts/run_experiment_playground_query_v0.py`
- `ai/evaluation/indexes/playground_bge_m3_page_v1.npz`
- `ai/evaluation/indexes/playground_bge_m3_page_v1_manifest.json`
- `ai/evaluation/reports/experiments/playground_v0/single_query_result.json`
- `ai/tests/unit/test_experiment_playground_v0.py`

## 후속 범위

1. B1~B3에서 새 Chunking·Retrieval·Embedding Profile을 구현할 때 선택지에 연결한다.
2. B4 Generation Runner가 준비되면 Generation 결과와 Latency를 연결한다.
3. Safety·Grounding Runner가 준비되면 현재 `NOT_EXECUTED` 영역을 실제 결과로 교체한다.
4. Gold 2인 검수 전까지 모든 수치는 Draft로 유지한다.
