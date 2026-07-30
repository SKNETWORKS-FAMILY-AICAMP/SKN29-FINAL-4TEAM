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

- DB 적재는 사용자 확인상 성공했으나 commit·Migration·건수·재적재
  증빙이 없어 `DOCUMENTED_NOT_DB_VERIFIED`를 유지한다.
- RAG는 승인 청크 7건과 평가 계약을 제공하며 실제 Index 결과는
  `PENDING_AI_OWNER`다.
- Backend Model·Migration·Service와 Vector Runtime 구현 완료를 이
  문서만으로 주장하지 않는다.
