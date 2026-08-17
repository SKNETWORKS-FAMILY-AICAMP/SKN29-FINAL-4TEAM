# 백엔드·AI Trace·Evidence Lineage 가이드

> 관련 업무: T-024 AI·RAG·행위 추적
> 갱신일: 2026-08-17
> 경계: Backend가 상태·감사 원장을 소유하고 AI는 계약에 있는 분석 결과만 반환한다.

## 1. 구현 결과

```text
고객 요청
→ Backend 업무 Transaction Commit
→ transaction.on_commit Callback
→ FastAPI /api/v1/ai/analyze
→ 성공 계약·Echo 식별자 검증
→ AIRun 저장
→ 검증된 Crosswalk로 AIRetrievalRun·AIRetrievalHit 저장
→ EvidenceLink Snapshot
→ Backend State Event 재검증
→ TransitionHistory 기록
```

T-024 Backend 단독 범위에서 다음 연결을 구현했다.

- `AIRun → AIRetrievalRun → AIRetrievalHit → EvidenceLink → TransitionHistory`
- 같은 Inquiry와 `correlation_id`를 실행·검색·상태 이력에 유지
- AI 응답 순서를 관측 Rank로, `similarity_score`를 Cosine Score로 저장
- 활성·검증 완료 Crosswalk의 Embedding Model·Revision·Index Version만 저장
- 같은 AI 요청 Replay는 Retrieval Run·Hit·EvidenceLink를 추가 생성하지 않음
- 상담·방문·완료 Action은 공통 Workflow Service가 Correlation·Idempotency·History를 기록

## 2. 계약 경계

현재 `SymptomAnalysisResponse v3.0.0`이 제공하는 Retrieval 정보는 다음뿐이다.

- `evidence_references` 배열 순서
- Canonical `chunk_id`
- nullable `similarity_score`
- 검증 상태

따라서 Backend는 반환되지 않은 전체 후보, Reranker 점수, 검색 단계별 Latency,
공식 `top_k` 설정을 추정하지 않는다. 저장된 `top_k`와
`observed_selected_count`는 이번 응답에서 실제 관측한 선택 근거 수다.

Score가 없거나 Crosswalk의 Model·Revision·Index 정체성이 서로 다르면 검색
Lineage는 만들지 않는다. 이 경우에도 검증된 기존 `EvidenceLink`는 보존하여
고객 안내를 불필요하게 실패시키지 않는다.

## 3. 저장 원칙

| 원장 | 저장 내용 |
| --- | --- |
| `AIRun` | 호출 상태, 계약·모델·Prompt 버전, 입력 Hash, Correlation |
| `AIRetrievalRun` | 내부 Query, Query SHA-256, 제품 Filter, Index·Embedding 정체성 |
| `AIRetrievalHit` | 관측 Rank, Cosine Score, Chunk, 선택 시각, 검증 상태 |
| `EvidenceLink` | 문서·페이지·요약·인용 Snapshot과 Retrieval FK |
| `TransitionHistory` | 적용 Event, Actor, State Version, Correlation |
| `IdempotencyRecord` | 최초 요청·응답과 Replay |

`query_text`는 재현을 위한 내부 감사 DB 값이며 고객 응답이나 구조화 로그로
노출하지 않는다. Prompt·Token·증상 원문·Authorization·Cookie·Secret·내부 경로도
로그에 기록하지 않는다.

## 4. 주요 구현 경로

- `backend/apps/inquiries/services/inquiry_ai_service.py`
- `backend/apps/audit/models/ai_run.py`
- `backend/apps/audit/models/retrieval_run.py`
- `backend/apps/audit/models/retrieval_hit.py`
- `backend/apps/evidence/models/evidence_link.py`
- `backend/apps/workflow/services/transition_history_service.py`
- `backend/tests/unit/evidence/test_ai_chunk_crosswalk.py`
- `backend/tests/integration/test_t024_request_trace_security.py`

## 5. Transaction·오류 처리

- 고객 입력과 State를 먼저 Commit한다.
- 동일 Idempotency-Key Replay는 AI와 Lineage 추가 실행 0회다.
- 같은 Key의 다른 Payload는 AI 호출 전 409다.
- Schema·Echo·Crosswalk 검증은 Fail-closed다.
- Retrieval Lineage 저장만 실패하면 안전 식별자와 실패 유형만 Warning으로 남긴다.
- 503·Timeout은 업무 Commit을 보존하며 Backend 자동 재시도는 0회다.
- Stale Version은 최신 Snapshot을 덮어쓰지 않는다.

## 6. 2026-08-17 자체 검증

```text
T-024 관련 AI·Retrieval·Evidence·상담·방문·완료 회귀
= 142 passed / 1 PostgreSQL 전용 Row-lock skipped / 0 failed

Django system check
= no issues

Migration drift
= no changes detected
```

검증 항목:

1. 실제 Crosswalk Metadata와 Score가 Run·Hit에 저장됨
2. AIRun부터 State History까지 Correlation이 일치함
3. Replay 후 Run·Hit·Link가 각 1건으로 유지됨
4. Score가 null이면 가짜 Lineage 없이 기존 검증 Evidence만 저장됨
5. 404·500 응답과 로그에 Query·Header·Cookie·Body·예외 원문이 남지 않음
6. 상담·방문·완료 Action의 Replay가 추가 History를 만들지 않음

## 7. 남은 외부 Gate

이번 구현은 T-024의 Backend 최소 Runtime이다. Task 전체 완료 판정에는 다음이 남는다.

- 이동윤: 전체 Retrieval 후보·실제 Model/Revision/Index·Rerank Metadata 제공
- 김은진: 동일 Inquiry의 PostgreSQL 전체 Lineage 독립 QA
- 실제 AI Provider·pgvector·상담·방문을 잇는 공동 E2E

현재 결과만으로 실제 AI 전체 후보 재현이나 전체 E2E PASS를 선언하지 않는다.
