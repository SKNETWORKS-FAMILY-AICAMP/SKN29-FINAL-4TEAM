# 4주차 RAG 후보 기준선

> 실행일: 2026-08-07  
> 상태: Local 기준선 완료, 팀 DB 재검증 대기

## 1. 현재 판정

실제 온라인 검색 경로는 `AI_VECTOR_DSN`으로 지정된 PostgreSQL pgvector를
사용한다. 현재 작업에서는 팀 DB에 접속하지 않았으므로 저장된 격리 DB 이력을
현재 팀 DB 결과로 승격하지 않는다.

## 2. 데이터·인덱스 기준

| 항목 | 값 |
| --- | --- |
| 승인 입력 | `data/processed/structured/rag/mvp/rag_verified_sample.jsonl` |
| 승인 청크 | 7개 |
| 입력 파일 SHA-256 | `2BF3582E42A309D846BC383BE9C3E08874512318DD4046082498DBFBC8584DD0` |
| Canonical Chunk Set SHA-256 | `175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958` |
| Embedding | `BAAI/bge-m3` |
| Revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| Dimension | 1024, L2 Normalize |
| 검색 | Cosine Exact Search, Top-K 5, Threshold 0.4 |

승인 입력은 `scope_role=mvp`와
`verification_status=TEXT_AND_VISUAL_VERIFIED`를 모두 만족한다. 제품·D세대·공식
검증·사용 허용 조건은 SQL에서 먼저 제한하고 Runtime에서 다시 검증한다.

## 3. 결과 경계

### 현재 Offline 실행

Vector Store를 설정하지 않은 평가는 `vector_store_not_configured`다. 이때 저장된
Recall·MRR `0.0`은 검색 품질 수치가 아니며 외부에 공개하지 않는다.

### 개인 격리 pgvector 이력

[`pgvector_verification.json`](../../../ai/evaluation/reports/pgvector_verification.json)의
기록은 PostgreSQL 16.14·pgvector 0.8.6 Disposable DB에서 수행됐다.

- 전체 12/12 PASS
- 실제 `PGVECTOR_QUERY` 7건
- 검색 전 정책 차단 5건
- 양성 Recall@5 `1.0`
- 양성 MRR `0.885714...`
- 금지 Hit `0`

이는 제품 1종·D세대·공식 문서 1개·승인 청크 7개 범위의 이력이다.

### 개인 격리 지연시간 이력

[`pgvector_latency_baseline_20260806.json`](../../../ai/evaluation/reports/pgvector_latency_baseline_20260806.json)은
Warm 30회에서 검색 전체 p50 `237.797 ms`, p95 `270.373 ms`를 기록했다. 단일
사용자·로컬 DB 결과이며 FastAPI HTTP, Backend E2E, 네트워크와 동시 부하는
포함하지 않는다.

## 4. 재현 명령

DB가 없는 현재 후보 평가:

```powershell
.\ai\.venv\Scripts\python.exe -m ai.evaluation.evaluation_runner
```

Disposable DB 검증은 DB 이름에 `verify`, `test`, `tmp`, `disposable` 중 하나가
포함되고 `AI_VECTOR_DISPOSABLE_CONFIRM=DISPOSABLE_ONLY`를 명시한 경우에만 기존
검증 스크립트를 사용한다. 해당 스크립트는 금지 Fixture를 Transaction에
삽입하므로 팀 공용 DB에서 실행하지 않는다.

팀 DB에서는 Backend Migration 후 최소 권한 DSN으로 승인 청크 UPSERT와 검색만
수행하고, Fixture 검증은 별도 QA Transaction 또는 승인된 격리 DB에서 실행한다.
DSN과 비밀번호는 명령 출력·문서·Git에 기록하지 않는다.

## 5. 남은 Gate

- Backend 소유 pgvector Migration 적용 확인
- 팀 DB에 승인 청크 7개 멱등 UPSERT
- 팀 DB에서 양성 Query와 검색 전 정책 차단 재검증
- Data Owner 승인 후 13번째 검색 후 문서 정책 차단 Case 실행
- Batch 대상 ID 중복 0, 금지 Fixture 잔존 0 확인
- Branch, Commit SHA, Dirty, Python·PostgreSQL·pgvector Version을 결과에 기록
- Backend가 검색 결과를 저장하고 EvidenceCardDTO로 조립하는 E2E
