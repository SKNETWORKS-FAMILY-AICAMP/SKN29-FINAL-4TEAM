# T-005 Wave 4A 문서 검색 청크 구현·검증

> 기준일: 2026-07-30  
> 담당: 최지용  
> 상태: `LOCAL_VERIFIED`  
> 대상 테이블: `knowledge_document_chunk`

## 1. 작업 목적

검수된 문서 페이지를 검색·인용 단위로 분리하고, 청킹 버전·본문 해시·문자
offset·토큰 정보·검색 메타데이터를 보존하는 정식 Django Model과 번호
Migration을 구현했다.

식별자와 FK는
[T-005 Physical Contract v1.2](../../../../database/t-005/t005_physical_contract_v1.2.json)에
따라 내부 bigint PK, 공개 UUID, 내부 bigint FK로 분리했다.

## 2. 산출물

| 구분 | 산출물 | 역할 |
| --- | --- | --- |
| Model | [DocumentChunk](../../../../../backend/apps/evidence/models/document_chunk.py) | 청크 본문·버전·해시·검색 메타데이터 |
| Runtime export | [Evidence Model export](../../../../../backend/apps/evidence/models/__init__.py) | Django Runtime Model 등록 |
| Migration | [evidence.0005](../../../../../backend/apps/evidence/migrations/0005_documentchunk.py) | 테이블·제약·생성형 검색 벡터·GIN Index |
| 집중 테스트 | [DocumentChunk 테스트](../../../../../backend/tests/unit/evidence/test_document_chunk_model.py) | 구조·제약·검색 벡터·보호 삭제 검증 |

## 3. 구현 구조

| 항목 | 구현 |
| --- | --- |
| 컬럼 수 | 20 |
| 식별자 | `id bigint` 자동 PK + `public_id uuid UNIQUE` |
| 부모 | `page_id bigint`, `DocumentPage`, `PROTECT` |
| 버전 유일성 | `(page_id, chunk_no, chunking_version)` |
| 활성 위치 유일성 | 활성 행의 `(page_id, chunk_no)` partial UNIQUE |
| Embedding 연결 키 | `(id, chunk_text_sha256)` UNIQUE |
| JSON | `symptom_tags` array, `metadata` object |
| 검색 벡터 | 본문에서 자동 생성하는 저장형 `search_vector` |
| PostgreSQL 검색 Index | `search_vector` GIN |

`CHUNK_TYPE` canonical YAML이 없으므로 `chunk_type_code`는 기본
`PARAGRAPH`를 보존하는 open code로 구현했고 전체 허용값 CHECK나
`TextChoices`를 만들지 않았다.

## 4. 이식 가능한 생성형 검색 벡터

[SimpleSearchVector](../../../../../backend/apps/evidence/models/document_chunk.py)는
같은 `GeneratedField`를 DB별로 다르게 컴파일한다.

| DB | 저장형 표현식 |
| --- | --- |
| PostgreSQL | `to_tsvector('simple', coalesce(chunk_text,''))` |
| SQLite 검증 | `coalesce(chunk_text,'')` |

따라서 ORM은 생성 컬럼에 값을 직접 INSERT하지 않고, PostgreSQL에서는
본문 변경 시 `tsvector`가 자동 갱신된다. GIN Index는
`SeparateDatabaseAndState`로 PostgreSQL에만 생성해 SQLite Migration을
깨뜨리지 않으면서 Django Migration state와 Runtime Model을 일치시켰다.

## 5. 제약조건

| 이름 | 역할 |
| --- | --- |
| `ux_document_chunk_version` | 같은 청킹 버전의 동일 위치 중복 차단 |
| `ux_document_chunk_active_position` | 현재 활성 위치 중복 차단 |
| `ux_document_chunk_id_hash` | Embedding 원천 해시 복합 FK 대상 |
| `ck_document_chunk_no` | 양수 청크 순번 |
| `ck_document_chunk_text` | 공백뿐인 본문 차단 |
| `ck_document_chunk_hash` | 소문자 SHA-256 64자리 |
| `ck_document_chunk_offsets` | 양쪽 NULL 또는 `0 <= start < end` |
| `ck_document_chunk_token_count` | nullable 또는 0 이상 |
| `ck_document_chunk_json` | 태그 array·메타데이터 object |

## 6. 작업·검증 결과

| 순서 | 검증 | 결과 |
| ---: | --- | --- |
| 1 | 집중 테스트 최초 실행 | 15 passed, 1 failed, PG 전용 1 skipped |
| 2 | 실패 원인 분석 | 한쪽 offset만 NULL일 때 SQL UNKNOWN이 CHECK를 통과 |
| 3 | offset 양쪽 `IS NOT NULL` 보강 | 잘못된 반쪽 범위 차단 |
| 4 | 집중 테스트 재실행 | 16 passed, PG 전용 1 skipped |
| 5 | Django system check | 0 issues |
| 6 | Evidence Migration drift | `No changes detected` |
| 7 | 빈 SQLite Migration | 적용 성공 |
| 8 | SQLite `0005 → 0004 → 0005` | 제거·재적용 성공 |
| 9 | 빈 PostgreSQL 16 Migration | 적용 성공 |
| 10 | PostgreSQL Catalog | 20컬럼, bigint FK, 9 계약 제약, partial UNIQUE 확인 |
| 11 | PostgreSQL 검색 구조 | 저장형 `tsvector`와 GIN Index 확인 |
| 12 | PostgreSQL 유효 데이터 | 청크 저장과 검색 벡터 자동 생성 성공 |
| 13 | 본문 변경 | 검색 벡터 자동 재계산 성공 |
| 14 | 반쪽 NULL offset 부정 테스트 | `ck_document_chunk_offsets` 차단 |
| 15 | PostgreSQL `0005 → 0004 → 0005` | 테이블·GIN Index 제거·복원 성공 |
| 16 | 임시 검증 자원 | 전용 PostgreSQL DB와 SQLite 파일 제거 |

## 7. 협업 인계

1. 활성 청크 세트를 교체할 때는 기존 버전을 비활성화하고 새 버전을
   활성화하는 작업을 한 transaction으로 처리해야 한다.
2. `chunk_text`가 바뀌면 `chunk_text_sha256`도 함께 갱신해야 하며 기존
   Embedding은 비활성화 또는 재생성해야 한다.
3. `chunk_type_code` 허용 집합은 계약 YAML 승인 후 `TextChoices`,
   DB CHECK, Seed parity 테스트를 한 변경으로 추가한다.
4. 후속 `knowledge_chunk_embedding`은 이 테이블의
   `(id, chunk_text_sha256)`를 복합 FK로 사용해야 한다.
5. MVP 검색은 지침서에 따라 pgvector Exact Search를 사용하며 HNSW·IVFFlat
   Index를 추가하지 않는다.
