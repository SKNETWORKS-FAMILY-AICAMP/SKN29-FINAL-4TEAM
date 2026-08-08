# 5주차 Data·QA 인계 Hub

> 작성일: 2026-08-07 KST
> 기준 Commit: `71754053868233d6913538f70e6e78ecaa8584c9`
> 작성자: 김은진 — Data·QA·DevOps
> 수신 상태: 전 담당자 `PENDING`

이 문서는 김은진이 독립적으로 준비할 수 있는 입력과 차단 조건을 연결한다.
수신 확인·후속 구현·PM 승인을 대신하지 않는다.

## 1. 공통 기준선

| 항목 | 값 |
| --- | --- |
| Dataset Version | `0.9.0` |
| Data 단위 테스트 | `69/69 PASS` |
| QA | 오류 0, 경고 0, Canonical Drift 0 |
| 대표 E2E | `17/17 PASS` |
| Synthetic Fixture | 367 |
| 승인 RAG Chunk | 7 |
| Retrieval Case | 12, 13번째 Case 미승인 |
| 평가 Dataset SHA-256 | `6E9F202F902F965B0C6875D8FCDF26333651E680019CC8B34416E8A444A12E4F` |
| Chunk Set SHA-256 | `175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958` |
| Embedding Revision | `5617a9f61b028005a4858fdac845db406aefb181` |

## 2. 담당자별 전달 준비 상태

| 수신자 | 제공 가능한 입력 | 현재 요청·차단 | 수신 |
| --- | --- | --- | --- |
| 이동윤 | Retrieval Dataset, 승인 Chunk, Index·평가 Hash, 금지 모델 정책 | 승인 가능한 13번째 원천 후보 제시 후 Dataset·Runner 반영 | `PENDING` |
| 최지용 | Synthetic Fixture 367건, Backend Crosswalk, Data QA 기준선 | T-017B 후보 Commit·Migration·기대 건수·Rollback 목표와 정식 RAG Mapping·최소 권한 경계 제공 | `PENDING` |
| 한예나 | 대표 상태·문의·근거 Fixture, 공개 Evidence 경계 | 실제 Runtime Operation만 소비하고 Contract-only·Mock을 구분 | `PENDING` |
| 양정현 | 대표 상태·문의·방문 Fixture, 역할·공개 필드 | 실제 Runtime Operation과 Mobile Demo·Fake Repository를 구분 | `PENDING` |
| 윤승혁 | 최종 QA 요약, Action Crosswalk 23개, T-017A PM 결정 반영 상태 | Crosswalk와 WBS·가이드 상태 동기화 및 5주차 기준선 승인 | `PENDING` |

## 3. 전달 파일

- `data/config/handoff/backend_import_crosswalk.json`
- `data/config/rag/jac104_retrieval_cases.json`
- `data/processed/structured/rag/mvp/rag_verified_sample.jsonl`
- `data/processed/validation/latest_qa_summary.json`
- `contracts/api/action-operation-crosswalk.yaml`
- `docs/testing/results/week4-data-qa-baseline.md`
- `docs/testing/results/week4-final-qa-summary.md`

실제 비밀번호·DSN·Token·`.env`, DB Dump, 모델 Weight·Cache, 공식 원문은
전달 파일에 포함하지 않는다.

## 4. 5주차 착수 Gate

### 독립 완료

- 현재 Main Data Gate 로컬 재현
- 실제 검증 의존 경로의 Data CI Trigger 반영
- 4주차 최종 QA와 본 인계 Hub 작성

### 협업 대기

- 13번째 RAG Case 원천·정책 승인과 AI Runner 반영
- 정식 `knowledge_*` Adapter·최소 권한 AI Role
- 공식 팀 DB 식별 후 승인 Chunk 7건 UPSERT·Replay·검색
- T-017B 후보 Migration·Admin 구현 후 독립 QA
- 담당자별 수신 확인과 PM 기준선 승인

## 5. 수신 기록

| 담당자 | 전달 시각 | 회신 | 질문·변경 요청 | 상태 |
| --- | --- | --- | --- | --- |
| 이동윤 | — | — | — | `PENDING` |
| 최지용 | — | — | — | `PENDING` |
| 한예나 | — | — | — | `PENDING` |
| 양정현 | — | — | — | `PENDING` |
| 윤승혁 | — | — | — | `PENDING` |
