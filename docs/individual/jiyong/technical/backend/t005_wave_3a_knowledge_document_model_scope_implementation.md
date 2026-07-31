# T-005 Wave 3A 문서 적용 제품 범위 구현·검증

> 기준일: 2026-07-30  
> 담당: 최지용  
> 상태: `LOCAL_VERIFIED`  
> 대상 테이블: `knowledge_document_model_scope`

## 1. 작업 목적

공식 원본 문서와 제품 모델의 적용 관계, 적용 기간, 사람 검증 상태를
정식 Django Model과 번호 Migration으로 구현했다.

식별자는 [T-005 Physical Contract v1.2](../../../../database/t-005/t005_physical_contract_v1.2.json)의
정책을 우선 적용했다.

- 내부 PK: `BigAutoField`
- 외부 공개 식별자: 고유 `public_id` UUID
- 업무 FK: 내부 정수 PK
- 삭제 정책: 적용 근거를 보존하기 위한 `PROTECT`

## 2. 구현 산출물

| 구분 | 산출물 | 구현 내용 |
| --- | --- | --- |
| Model | [DocumentModelScope](../../../../../backend/apps/evidence/models/document_model_scope.py) | 문서·제품·적용기간·검증 묶음 저장 |
| Runtime export | [Evidence Model 공개 목록](../../../../../backend/apps/evidence/models/__init__.py) | `INSTALLED_APPS` Runtime Model 로딩 보장 |
| Migration | [evidence.0003](../../../../../backend/apps/evidence/migrations/0003_documentmodelscope.py) | 테이블·FK·UNIQUE·CHECK·Index 생성 |
| 집중 테스트 | [DocumentModelScope 테스트](../../../../../backend/tests/unit/evidence/test_document_model_scope.py) | 필드·식별자·관계·제약·보호 삭제 검증 |

## 3. 물리 구조

| 항목 | 구현 |
| --- | --- |
| 테이블 | `knowledge_document_model_scope` |
| 컬럼 수 | 12 |
| 내부 식별자 | `id bigint` 자동 PK |
| 공개 식별자 | `public_id uuid NOT NULL UNIQUE` |
| 부모 문서 | `document_id bigint`, `knowledge_source_document`, `PROTECT` |
| 제품 모델 | `product_model_id bigint`, `catalog_product_model`, `PROTECT` |
| 검증자 | `verified_by_id bigint NULL`, `accounts_user`, `PROTECT` |
| 적용 기간 | `applicable_from`, `applicable_to` nullable date |
| 검증 상태 | `is_verified`, `verified_by_id`, `verified_at` 일괄 묶음 |

## 4. 제약조건과 인덱스

| 이름 | 종류 | 역할 |
| --- | --- | --- |
| `ux_document_model_scope` | UNIQUE | 같은 문서·제품 관계의 중복 등록 차단 |
| `ck_model_scope_period` | CHECK | 종료일이 시작일보다 빠른 기간 차단 |
| `ck_model_scope_verification` | CHECK | 검증 여부·검증자·검증시각을 함께 설정하거나 함께 비움 |
| `ix_model_scope_model` | BTREE | 제품·검증 여부·적용 기간 기반 검색 |

FK에 Django 기본 단일 Index를 중복 생성하지 않도록 `db_index=False`를
명시했다. 문서·제품 관계는 UNIQUE Index, 제품 기준 조회는 계약 Index로
각각 충족한다.

## 5. 작업·검증 결과

| 순서 | 검증 | 결과 |
| ---: | --- | --- |
| 1 | 신규 집중 테스트 최초 실행 | 7 passed, 5 failed |
| 2 | 실패 원인 분석 | 동일 번호 운영자를 두 번 생성한 테스트 fixture 충돌 |
| 3 | fixture 식별자 분리 후 재실행 | 12 passed |
| 4 | Evidence 전체 회귀 | 31 passed, PostgreSQL 전용 3 skipped |
| 5 | Django system check | 0 issues |
| 6 | Migration drift | `No changes detected in app 'evidence'` |
| 7 | 빈 SQLite Migration | 적용 성공 |
| 8 | SQLite `0003 → 0002 → 0003` | 테이블 제거·복원 성공 |
| 9 | 빈 PostgreSQL 16 Migration | 적용 성공 |
| 10 | PostgreSQL Catalog | 12컬럼, 3 FK, 2 CHECK, UNIQUE, Index 모두 확인 |
| 11 | PostgreSQL 유효 데이터 | 미검증 문서·제품 관계 저장 성공 |
| 12 | 기간 역전 부정 테스트 | `ck_model_scope_period`가 차단 |
| 13 | 불완전 검증 부정 테스트 | `ck_model_scope_verification`이 차단 |
| 14 | 동일 문서·제품 중복 테스트 | `ux_document_model_scope`가 차단 |
| 15 | PostgreSQL `0003 → 0002 → 0003` | 테이블 제거·복원 성공 |
| 16 | 임시 검증 자원 | 전용 PostgreSQL DB와 SQLite 파일 제거 완료 |

최초 5건 실패는 운영 Model이나 Migration 오류가 아니었다. 매개변수 테스트가
검증자와 문서 수집자에게 같은 고유 username·employee number를 배정한 것이
원인이었고, 문서 수집자 fixture 번호 영역을 분리해 해결했다.

## 6. 협업 인계

1. 검증 전 관계는 `is_verified=false`로 저장되며 제품 필터링 근거로 사용하면
   안 된다.
2. 검증 완료 시 `is_verified`, `verified_by`, `verified_at` 세 값을 한
   transaction에서 함께 갱신해야 한다.
3. 문서·제품 한 쌍에는 한 행만 허용된다. 기간별 이력을 여러 행으로 분리해야
   한다면 현재 UNIQUE 계약 변경을 먼저 승인받아야 한다.
4. 다음 자식 테이블인 `knowledge_document_page`와
   `knowledge_document_chunk`는 문서 FK를 사용하되 이 적용 범위를 자동
   확정해서는 안 된다.
5. 관련 원본 구조는 [테이블 사전](../../../../database/watercare_table_dictionary.md)과
   [T-005 Schema v3](../../../../database/t-005/watercare_schema_v3.json)에서
   확인할 수 있다.
