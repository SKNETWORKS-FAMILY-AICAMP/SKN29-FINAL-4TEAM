# WaterCare 데이터베이스·저장소 설계

## 저장소 책임

| 영역 | 책임 |
|---|---|
| PostgreSQL | 고객·구독·문의·상담·방문·상태이력·감사 관계 |
| Vector Store | 승인된 공식 문서 청크의 embedding과 검색 |
| 외부 원본 저장소 | 공식 PDF·FAQ 원본, Git 비추적 |
| Git data | 합성 fixture, Schema, expected data, manifest·QA |

## 식별자·적재 원칙

- fixture 정수 `id`는 로컬 관계용이며 Backend PK로 직접 주입하지 않는다.
- `public_id`와 업무키로 Backend row를 조회한 뒤 실제 DB FK를 사용한다.
- 업무 코드는 Public API ID나 DB FK로 사용하지 않는다.
- 미확정 Care mapping은 직접 load 대상에서 제외한다.
- 원본 24개 중 활성 22개만 계약 정합 load 후보로 제공한다.

## 현재 검증 상태

- Backend 기본 `watercare` DB는 PostgreSQL 16.14 연결, 적용
  Migration, Demo Seed 4종과 읽기 전용 PostgreSQL Gate 증거를
  별도로 관리한다.
- 합성 Handoff는 기본 DB가 아닌 빈 격리 PostgreSQL에서 12종·367
  Source의 최초 적재와 Replay를 검증해 `DB_FULL_VERIFIED`다.
- RAG는 별도 PostgreSQL 16.14·pgvector 0.8.6에 승인 청크 7건을
  적재했고 12개 검색 평가를 모두 통과해
  `APPROVED_FOR_MVP_INGEST`다.
- 합성 Handoff 격리 DB, AI pgvector 격리 DB와 Backend 기본 DB의
  적재·Migration·운영 범위를 서로 승계하거나 혼합하지 않는다.
- Backend Model·Migration·Service와 Vector Runtime 구현 완료를 이
  문서만으로 주장하지 않는다.

RAG 승인은 JAC104D D세대 REV.00 37~39쪽 7개 증상에 한정하며,
누수 검색 5위와 지침서 3.3 v2 평가 포맷은 후속 개선 대상이다.
