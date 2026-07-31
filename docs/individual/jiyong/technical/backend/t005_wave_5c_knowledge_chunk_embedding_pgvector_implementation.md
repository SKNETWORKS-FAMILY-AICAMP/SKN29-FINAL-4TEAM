# T-005 Wave 5C 청크 임베딩 pgvector 구현·검증

> 기준일: 2026-07-30  
> 담당: 최지용  
> 상태: `LOCAL_VERIFIED`  
> 대상 테이블: `knowledge_chunk_embedding`

## 1. 작업 목적

검수된 문서 청크와 임베딩 생성 당시의 본문 해시를 함께 고정하고,
`BAAI/bge-m3` 원본 출력과 같은 1024차원 벡터를 PostgreSQL
pgvector에 저장한다.

MVP 검색 정책은 Exact Search이다. HNSW·IVFFlat ANN Index는 생성하지
않았으며, 임베딩 모델·버전별 활성 레코드를 조회하는 일반 BTREE
Index만 생성했다.

## 2. 산출물

| 구분 | 산출물 | 역할 |
| --- | --- | --- |
| Model | [ChunkEmbedding](../../../../../backend/apps/evidence/models/chunk_embedding.py) | 1024차원 벡터와 모델·본문 버전 저장 |
| Runtime export | [Evidence Model export](../../../../../backend/apps/evidence/models/__init__.py) | Django Runtime Model 등록 |
| Migration | [evidence.0007](../../../../../backend/apps/evidence/migrations/0007_chunkembedding.py) | vector 확장·테이블·복합 FK 생성 |
| 집중 테스트 | [ChunkEmbedding 테스트](../../../../../backend/tests/unit/evidence/test_chunk_embedding_model.py) | 구조·제약·Exact Search·Catalog 검증 |
| Python 의존성 | [base requirements](../../../../../backend/requirements/base.txt) | `pgvector==0.5.0` 직접 의존성 |
| 버전 고정 | [Python 3.13 constraints](../../../../../backend/requirements/constraints-py313.txt) | 재현 가능한 pgvector 버전 고정 |
| PostgreSQL 실행 환경 | [Docker Compose](../../../../../docker-compose.yml) | `pgvector/pgvector:0.8.6-pg16-bookworm` |

## 3. 구현 계약

| 항목 | 구현 |
| --- | --- |
| 내부 식별자 | `id bigint` 자동 PK |
| 외부 식별자 | `public_id uuid UNIQUE` |
| 부모 참조 | `chunk_id bigint`, `DocumentChunk`, `PROTECT` |
| 벡터 타입 | `VectorField(dimensions=1024)` |
| 모델 버전 | `(chunk_id, embedding_model, embedding_model_version)` UNIQUE |
| 원문 버전 | `(chunk_id, source_text_sha256)` 복합 FK |
| 차원 검증 | `embedding_dimension=1024` 및 `vector_dims(embedding)=1024` |
| 해시 검증 | 소문자 SHA-256 64자리 |
| 검색 Index | `(embedding_model, is_active)` BTREE |
| ANN Index | 없음 |

`embedding_model`과 `embedding_model_version`은 임의 enum으로 닫지 않았다.
현재 저장 가능한 벡터 차원만 1024로 고정하며, 실제 사용 모델명과 배포
버전은 호출자가 명시한다.

## 4. 마이그레이션 안전성

공식 `VectorExtension` 동작을 사용하되 SQLite 역방향 Migration에서
PostgreSQL Catalog를 조회하지 않도록 `PortableVectorExtension`으로
역방향 vendor guard를 보강했다.

복합 원문 FK는 PostgreSQL에만 다음 형태로 생성한다.

```text
(chunk_id, source_text_sha256)
  -> knowledge_document_chunk(id, chunk_text_sha256)
```

SQLite 검증 환경에서는 단순 `chunk_id` FK와 Model `clean()`이 같은
의도를 검증한다. 운영 PostgreSQL에서는 복합 FK를 즉시 검사해, 잘못된
해시가 트랜잭션 종료까지 남지 않도록 했다.

## 5. 작업→검증 반복 기록

| 순서 | 작업·검증 | 결과 |
| ---: | --- | --- |
| 1 | pgvector Python 의존성 dry-run | 추가 전이 의존성 없음 확인 |
| 2 | Python `pgvector==0.5.0` 설치·고정 | 성공 |
| 3 | PostgreSQL 이미지를 pgvector 0.8.6/PG16으로 교체 | health 정상 |
| 4 | 이미지 교체 전후 대표 DB 핵심 행 수 비교 | `20/22/125/125` 동일, 볼륨 보존 |
| 5 | Model·0007·집중 테스트 작성 | 완료 |
| 6 | Django system check | 0 issues |
| 7 | Evidence Migration drift | `No changes detected` |
| 8 | 빈 SQLite 전체 Migration | 성공 |
| 9 | SQLite `0007 → 0006 → 0007` | 성공 |
| 10 | SQLite 집중 테스트 | 14 passed, PG 전용 2 skipped |
| 11 | 빈 PostgreSQL 전체 Migration | 성공 |
| 12 | PostgreSQL 첫 집중 테스트 | 지연 복합 FK의 테스트 종료 시점 오류 발견 |
| 13 | 복합 FK를 즉시 검사로 변경 | `condeferrable=false`, `condeferred=false` |
| 14 | PostgreSQL `0007 → 0006 → 0007` | 성공 |
| 15 | PostgreSQL 집중 테스트 재실행 | 16 passed |
| 16 | Exact cosine search | 가장 가까운 1024차원 벡터 순서 확인 |
| 17 | PostgreSQL Catalog | `vector(1024)`, extension `0.8.6`, 복합 FK 확인 |
| 18 | ANN Index 부재 검사 | HNSW·IVFFlat 0개 |

## 6. 협업 인계

1. AI 담당자는 임베딩 생성 시 `embedding_model`,
   `embedding_model_version`, `embedding_dimension=1024`,
   `source_text_sha256`를 함께 전달해야 한다.
2. 청크 본문이 변경되면 기존 임베딩을 덮어쓰지 말고 청크 버전과
   임베딩 버전을 새로 생성하거나 기존 레코드를 비활성화해야 한다.
3. 검색은 [AIRetrievalRun](../../../../../backend/apps/audit/models/retrieval_run.py)에
   실제 모델·버전과 검색 설정을 기록하고, Exact Search 결과는
   [AIRetrievalHit](../../../../../backend/apps/audit/models/retrieval_hit.py)에
   저장해야 한다.
4. HNSW·IVFFlat 전환은 데이터 규모·거리함수·성능 기준을 팀에서 승인한
   뒤 별도 번호 Migration과 회귀 테스트로만 추가한다.
5. 새 개발환경은 Compose 이미지를 다시 pull하고 requirements를 설치한
   뒤 빈 PostgreSQL Migration을 실행해야 한다.

## 7. 확인된 운영 경계

1. SQLite에는 pgvector와 복합 FK가 없으므로 잘못된
   `source_text_sha256`는 `full_clean()`에서만 선검증한다. DB parity와
   성능 검증의 기준은 PostgreSQL 집중 테스트이다.
2. `VectorExtension`은 빈 DB와 현재 프로젝트 전용 DB에서는 가역적으로
   동작한다. 이미 다른 서비스가 vector 확장을 공유하는 DB에 적용할
   때는 extension 소유권과 rollback 정책을 DBA와 먼저 확정해야 한다.
3. 기존 DB에 더 낮은 vector extension이 설치돼 있으면
   `CREATE EXTENSION IF NOT EXISTS`가 자동 업그레이드하지 않는다. 적용
   전에 `pg_available_extensions`와 `pg_extension.extversion`을 비교하고,
   승인된 인프라 절차에서 업그레이드해야 한다.
4. 복합 FK 회귀 테스트는 이름뿐 아니라 참조 테이블·컬럼 순서,
   `ON DELETE RESTRICT`, non-deferrable 상태까지 확인한다.

## 8. 완료 기준

- Model·Migration·ERD 물리 테이블명이 일치한다.
- 내부 BigAuto PK, 공개 UUID, bigint FK가 분리된다.
- 1024차원과 청크 본문 해시가 DB에서 강제된다.
- SQLite와 PostgreSQL의 apply→rollback→reapply가 통과한다.
- PostgreSQL Exact Search와 pgvector Catalog 검증이 통과한다.
- MVP 범위를 넘는 ANN Index가 존재하지 않는다.
