# T-005 Wave 2C `knowledge_source_document` 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_DB_VERIFIED`  
> 기준 계약: T-005 Physical Contract v1.2

## 1. 결과 요약

공식 자료의 수집 배치, 원문 메타데이터, 파일 해시, 개정 계보와
soft delete 이력을 보존하는 `knowledge_source_document`를 Django Runtime
Model과 번호 Migration으로 구현했다.

역사 테이블명세서의 26개 필드를 보존하고 Physical Contract v1.2의 공개
식별자 `public_id`를 추가하여 Runtime 기준 27개 필드로 구성했다. 내부
조인은 `BigAutoField id`, 외부 공개 참조는 unique UUID `public_id`를
사용한다.

| 검증 항목 | 결과 |
| --- | --- |
| Django system check | 통과, 0 issues |
| Evidence Migration drift | 통과, `No changes detected` |
| SQLite 집중 테스트 | `10 passed`, PostgreSQL 전용 3건 SKIP |
| 빈 SQLite 전체 Migration | 통과 |
| SQLite `0002` rollback → reapply | 테이블 제거·복원 모두 통과 |
| 빈 PostgreSQL 전체 Migration | 통과 |
| PostgreSQL 집중 테스트 | `13 passed` |
| PostgreSQL 열 타입 | `id/FK bigint`, `public_id uuid` |
| PostgreSQL 복합 FK | 배치 범위·개정 범위 2개 존재 및 위반 INSERT 차단 |
| PostgreSQL `0002` rollback → reapply | 테이블 제거 후 복합 FK 2개 복원 |
| T-005 구현 매핑 | `knowledge_source_document` IMPLEMENTED |

이 결과는 해당 테이블 단위 결과이다. 다른 Evidence 자식 테이블, Seed,
중앙 readiness 판정은 이번 Wave에서 수정하거나 완료로 선언하지 않았다.

## 2. 기준 문서와 적용 우선순위

| 우선 | 기준 | 적용 내용 |
| ---: | --- | --- |
| 1 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 신규 주요 테이블의 bigint PK, 공개 UUID, 내부 bigint FK |
| 2 | [식별자 ADR 0010](<../../../../adr/0010-t005-three-layer-identifier-bridge.md>) | 내부·외부·업무 식별자 분리 |
| 3 | [테이블사전 `knowledge_source_document`](<../../../../database/watercare_table_dictionary.md>) | 역사 필드, UNIQUE, CHECK, Index, 계보·범위 정책 |
| 4 | [DATASET_SCOPE canonical YAML](<../../../../../contracts/codes/dataset-scopes.yaml>) | 승인된 `MVP`, `EXPANSION`만 고정 |
| 5 | 현재 Django 공통 Model·Accounts 0003 | timestamp, soft delete, 정수 사용자 FK |

역사 Snapshot의 UUID `id`보다 Physical v1.2의 최신 식별자 정책을
우선했다. 따라서 Snapshot의 나머지 25개 필드와 `id`의 역할은
보존하되, `id` 타입을 bigint로 전환하고 `public_id`를 추가했다.

## 3. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [SourceDocument Model](<../../../../../backend/apps/evidence/models/source_document.py>) | 27개 필드, 관계, 제약, Index, portable validation |
| [Evidence Model export](<../../../../../backend/apps/evidence/models/__init__.py>) | `SourceDocument` Runtime 공개 |
| [Evidence 0002 Migration](<../../../../../backend/apps/evidence/migrations/0002_sourcedocument.py>) | 테이블 생성 및 PostgreSQL 복합 FK 2개 설치 |
| [집중 단위 테스트](<../../../../../backend/tests/unit/evidence/test_source_document_model.py>) | 식별자·코드·UNIQUE·CHECK·PROTECT·복합 FK 검증 |

## 4. 27개 Runtime 필드

| 구분 | 필드 | 구현·무결성 |
| --- | --- | --- |
| 내부 식별자 | `id` | `BigAutoField`, PK |
| 공개 식별자 | `public_id` | UUID, UNIQUE, 자동 생성, 수정 불가 |
| 수집 배치 | `ingestion_batch_id` | `knowledge_ingestion_batch` PROTECT FK |
| 업무 식별자 | `document_code` | `varchar(80)`, UNIQUE |
| 데이터 범위 | `dataset_scope_code` | `MVP` 또는 `EXPANSION` |
| 개정 계보 | `supersedes_document_id` | nullable self PROTECT FK |
| 문서 설명 | `title`, `source_org`, `document_type_code` | 제목·제공기관·문서유형 |
| 공식 출처 | `official_source_url`, `usage_terms_url`, `license_note` | 출처·이용조건·라이선스 근거 |
| 원본 위치 | `original_file_uri` | object key/URI 메타데이터 |
| 파일 메타 | `file_name`, `mime_type`, `file_size_bytes` | 선택 메타데이터, 크기는 0 이상 |
| 변경 검출 | `sha256_hash` | 64자 소문자 16진수, UNIQUE |
| 개정 메타 | `revision_label`, `published_on` | nullable |
| 수집 이력 | `collected_at`, `collected_by_id` | 수집 시각·Accounts PROTECT FK |
| 처리 상태 | `status_code` | 기본값 `COLLECTED`, 승인 전 open code |
| 파서 정보 | `parser_version` | nullable |
| 공통 시각 | `created_at`, `updated_at` | 생성·최종 갱신 시각 |
| soft delete | `deleted_at`, `deleted_by_id` | 둘 다 NULL 또는 둘 다 설정 |

`collected_at`은 필수이고 기본값은 현재 시각이다. 역사 계약에 없는
상태별 시간 순서나 전이 조건은 임의로 만들지 않았다. 상태 lifecycle은
canonical 계약 승인 후 별도 번호 Migration에서 확정해야 한다.

## 5. 코드셋 확정 범위

| 코드 필드 | 현재 처리 | 이유 |
| --- | --- | --- |
| `dataset_scope_code` | `TextChoices` + DB allowed CHECK | canonical YAML이 `OWNER_BASELINE`으로 존재 |
| `document_type_code` | 일반 `CharField`, open code | 승인된 canonical YAML 부재 |
| `status_code` | 일반 `CharField`, open code | 승인된 canonical YAML 부재 |

테이블사전의 문서유형·상태 후보값은 설계 후보이며 승인된 enum 계약이
아니다. 그러므로 후보를 Django `TextChoices` 또는 DB allowed CHECK로
동결하지 않았다. `status_code="COLLECTED"` 기본값은 역사 필드 계약을
보존한 것이며, 허용집합 전체를 승인했다는 의미가 아니다.

계약 담당자가 두 코드셋을 canonical YAML로 승인하면 다음을 하나의 별도
변경으로 반영해야 한다.

1. 코드 YAML 및 소유자·버전 확정
2. Model `TextChoices` 추가
3. DB allowed CHECK를 새 번호 Migration으로 추가
4. API·Importer·Seed와 parity test 동시 갱신

## 6. 물리 무결성

| 제약·Index | 방지하거나 지원하는 내용 |
| --- | --- |
| `ux_source_document_code` | 업무 문서코드 중복 차단 |
| `ux_source_document_sha256` | 동일 원본 해시 중복 차단 |
| `ux_source_document_id_scope` | self 복합 FK 부모 후보키 |
| `ck_source_document_file_size` | 음수 파일 크기 차단 |
| `ck_source_document_sha256` | 64자 소문자 SHA-256 형식 강제 |
| `ck_source_document_not_self_supersede` | 자기 자신을 개정 전 문서로 지정하는 행 차단 |
| `ck_source_document_deleted_pair` | 삭제 시각·삭제자 불완전 기록 차단 |
| `ck_knowledge_source_document_dataset_scope_code_allowed` | 미승인 데이터 범위 차단 |
| `ix_source_document_status` | 유형·상태·최근 수집순 조회 |
| `ix_source_document_revision` | 공식 URL·개정 라벨 조회 |
| `ix_source_document_supersedes` | 개정 계보 조회 |
| `ix_source_doc_active_status` | 삭제되지 않은 행의 상태·최근순 조회 |
| `ix_source_document_batch` | 수집 배치별 문서 조회 |

역사 Index명 `ix_source_document_active_status`는 Django의 모든 지원 DB
공통 30자 제한을 넘는다. 동작과 필드·조건은 유지하면서 이식 가능한
`ix_source_doc_active_status`로 이름만 축약했다.

원본 파일 바이트를 DB에 저장하지 않는 정책, 절대 로컬 경로와 변경 가능한
URL을 `original_file_uri`에 넣지 않는 정책은 문자열 CHECK로 안전하게
판별할 수 없다. Importer/Service에서 object key 정책을 검증하고 통합
테스트로 보강해야 한다.

## 7. 동일 `dataset_scope` 복합 무결성

일반 FK만으로는 문서와 배치, 새 문서와 이전 개정 문서가 동일한 데이터
범위인지 보장하지 못한다. PostgreSQL에서는 0002가 다음 두 복합 FK를
설치한다.

```sql
FOREIGN KEY (ingestion_batch_id, dataset_scope_code)
REFERENCES knowledge_ingestion_batch (id, dataset_scope_code)
ON DELETE RESTRICT
```

```sql
FOREIGN KEY (supersedes_document_id, dataset_scope_code)
REFERENCES knowledge_source_document (id, dataset_scope_code)
MATCH SIMPLE
ON DELETE RESTRICT
```

검증에서 다른 범위의 배치 또는 이전 개정 문서를 연결한 ORM INSERT는 각각
`fk_source_document_batch_scope`,
`fk_source_document_supersedes_scope` 위반으로 차단되었다.

SQLite는 기존 테이블에 복합 FK를 사후 추가하는 방식이 제한되므로
Migration DDL은 clean no-op이고, Model `clean()`이 양쪽 범위 일치를
검증한다. SQLite 기반 Service는 저장 전에 `full_clean()`을 호출해야
하며 운영 무결성의 최종 보장은 PostgreSQL 복합 FK가 담당한다.

## 8. Migration 순서와 rollback

`evidence.0002_sourcedocument`의 직접 의존성은 다음과 같다.

```text
accounts.0003_promote_integer_primary_keys
evidence.0001_initial
  └─ evidence.0002_sourcedocument
```

Accounts 0003을 명시적으로 선행해야 `collected_by_id`,
`deleted_by_id`가 legacy 문자열이 아니라 bigint로 생성된다.

rollback은 복합 self FK, 배치 복합 FK 순으로 제거한 후 테이블을 제거한다.
SQLite와 PostgreSQL에서 모두 `0002 → 0001 → 0002` 왕복을 실행했다.
PostgreSQL 재적용 후 아래 항목을 직접 확인했다.

```text
id=bigint
ingestion_batch_id=bigint
public_id=uuid
supersedes_document_id=bigint
fk_source_document_batch_scope=present
fk_source_document_supersedes_scope=present
```

## 9. 작업→검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 지침·ADR·Physical v1.2·테이블사전 대조 | 필드·관계·승인 코드 분류 | 역사 26 + 공개 UUID = 27 확정 |
| 2 | Model·export 구현 | Django system check | 0 issues |
| 3 | 0002 및 복합 FK 작성 | Migration drift | `No changes detected` |
| 4 | 식별자·코드·UNIQUE·CHECK·PROTECT 테스트 | SQLite 집중 테스트 | `10 passed`, PG 전용 3 SKIP |
| 5 | 빈 SQLite 전체 Migration | 전체 앱 Migration | 통과 |
| 6 | SQLite 0002 왕복 | rollback → reapply | 통과 |
| 7 | 격리된 빈 PostgreSQL 전체 Migration | 전체 앱 Migration | 통과 |
| 8 | 동일 테스트를 PostgreSQL에서 실행 | catalog·위반 INSERT 포함 | `13 passed` |
| 9 | PostgreSQL 0002 왕복 | 테이블 부재·타입·FK 재확인 | 통과 |

## 10. 재현 명령

저장소 루트 기준 SQLite Gate:

```powershell
& .\backend\.venv\Scripts\python.exe backend\manage.py check
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    makemigrations evidence --check --dry-run
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\evidence\test_source_document_model.py -q
```

PostgreSQL Gate는 `backend/.env`의 연결정보를 사용하되, 기존 개발 DB가
아닌 빈 격리 DB를 지정하여 실행한다.

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings.base'
$env:POSTGRES_DB = '<isolated-empty-database>'

& .\backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\evidence\test_source_document_model.py `
    -q --ds=config.settings.base
```

## 11. 협업 인계

| 담당 | 인계 내용 |
| --- | --- |
| 최지용 | Evidence 0002와 Accounts 0003 의존성, 복합 FK 2개, 축약 Index명 유지 |
| PM·계약 담당 | 문서유형·문서상태 canonical YAML과 허용값·소유자·버전 승인 |
| 데이터·Importer 담당 | 배치와 문서의 `dataset_scope_code` 동일성 보장, SHA-256 소문자 저장, object key URI 정책 준수 |
| API 담당 | 외부 응답·요청에는 `public_id`, 내부 조인에는 `id` 사용 |
| 운영 담당 | 삭제 시 `deleted_at`과 `deleted_by_id`를 같은 트랜잭션에서 함께 기록 |
| AI/RAG 담당 | Page·Chunk 구현 시 이 문서의 bigint `id`와 동일 scope를 부모 참조로 사용 |
| 통합 담당 | 남은 Evidence 자식 구현 후 중앙 readiness·Seed·빈 DB 전체 Gate를 다시 실행 |

## 12. 잔여 위험과 이번 Wave 제외 범위

- 문서유형·문서상태 canonical enum은 미승인 상태이다.
- `original_file_uri` 저장정책은 Importer/Service 검증이 아직 필요하다.
- SourcePage, Chunk 등 다른 Evidence 자식 테이블은 이번 Wave에서
  구현하지 않았다.
- 정식 importer와 367건 운영 적재, Seed는 이번 Wave 범위가 아니다.
- 중앙 T-005 readiness의 고정 기대값은 병렬 Wave 종료 후 한 번에
  갱신해야 하므로 이번 Wave에서 수정하지 않았다.
- 따라서 이 문서는 `knowledge_source_document` 단위 구현 완료만
  증명하며 T-005 전체 완료 선언이 아니다.

## 13. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | Model·0002·복합 FK·SQLite/PostgreSQL·rollback 검증 및 협업 인계 |
