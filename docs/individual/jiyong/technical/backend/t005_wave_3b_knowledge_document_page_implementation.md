# T-005 Wave 3B `knowledge_document_page` 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_DB_VERIFIED`  
> 구현 기준: T-005 Physical Contract v1.2  
> 전체 T-005 상태: `NOT_READY`

## 1. 결과 요약

공식 원본 문서의 페이지별 추출 텍스트, 변경 검출 해시, 검수 기록과
RAG 사용 가능 여부를 보존하는 `knowledge_document_page`를 Django
Runtime Model과 `evidence.0004` 번호 Migration으로 구현했다.

설계 Snapshot의 UUID PK를 그대로 복제하지 않고 Physical Contract
v1.2의 현재 식별자 정책을 우선해 내부 조인용 `BigAutoField id`와
외부 공개용 UUID `public_id`를 분리했다. Snapshot의 13개 필드 구조에서
기존 UUID `id`를 bigint로 전환하고 `public_id`를 추가했으므로 Runtime
필드는 14개다.

| 검증 항목 | 결과 |
| --- | --- |
| Django system check | 통과, 0 issues |
| 전체 App Migration drift | 통과, `No changes detected` |
| SQLite 집중 테스트 | `22 passed`, PostgreSQL 전용 1건 skip |
| 빈 SQLite 전체 Migration | 통과 |
| SQLite `0004 → 0003 → 0004` | 테이블 `true → false → true` |
| 빈 PostgreSQL 16 전체 Migration | 통과 |
| PostgreSQL 집중 테스트 | `23 passed` |
| PostgreSQL 컬럼 타입 | `id/document_id/reviewer_id bigint`, `public_id uuid` |
| PostgreSQL 구조 | 계약 제약 5개와 partial RAG Index 확인 |
| PostgreSQL `0004 → 0003 → 0004` | 테이블 `true → false → true` |
| 관련 Evidence·Accounts·T-005 회귀 | `62 passed`, PostgreSQL 전용 4건 skip |
| Backend 전체 회귀 | `601 passed`, PostgreSQL 전용 7건 skip |
| 구현 준비도 감사 | 검증 시점 `25/32`, 본 테이블 `IMPLEMENTED`, 전체 `NOT_READY` |

위 수치는 이 문서에 기록한 로컬 작업 단위의 검증 결과다. 작성자 외
리뷰와 팀 공용 Branch 병합 증거가 아니며, 나머지 계약 테이블·Seed·
서비스가 남아 있으므로 T-005 전체 완료를 뜻하지 않는다.

## 2. 기준 문서와 적용 우선순위

| 우선순위 | 기준 | 이번 Wave 적용 |
| ---: | --- | --- |
| 1 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 신규 주요 테이블의 내부 bigint PK, 공개 UUID, 내부 bigint FK |
| 2 | [식별자 ADR 0010](<../../../../adr/0010-t005-three-layer-identifier-bridge.md>) | 내부 PK와 외부 공개 식별자 분리 |
| 3 | [설계 Snapshot](<../../../../database/t-005/watercare_schema_v3.json>) | nullable, 길이, 기본값, 부모 관계와 페이지 필드 구조 |
| 4 | [테이블 사전 24번](<../../../../database/watercare_table_dictionary.md>) | UNIQUE·CHECK·partial Index와 RAG 구조 제안 |
| 5 | [현재 `evidence.0003`](<../../../../../backend/apps/evidence/migrations/0003_documentmodelscope.py>) | 기존 Evidence Migration을 변경하지 않고 `0004`가 직접 후속하도록 구성 |

Physical Contract v1.2가 Snapshot보다 우선한다. 따라서 Snapshot의
`id uuid`는 `id bigint`와 `public_id uuid`로 분리했다. 나머지 필드는
Snapshot의 nullable·길이·기본값을 보존했다.

`PARSE_STATUS`, `REVIEW_STATUS`의 승인된 canonical YAML은 현재
저장소에 없다. 테이블 사전에 적힌 후보값 전체는 승인된 코드 계약이
아니므로 Django `TextChoices`와 전체 allowed CHECK를 만들지 않았다.

## 3. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [`DocumentPage` Model](<../../../../../backend/apps/evidence/models/document_page.py>) | 14개 필드, 관계, portable validation, UNIQUE·CHECK·Index |
| [Evidence Model export](<../../../../../backend/apps/evidence/models/__init__.py>) | `DocumentPage` Runtime 등록·공개 |
| [`evidence.0004` Migration](<../../../../../backend/apps/evidence/migrations/0004_documentpage.py>) | `knowledge_document_page` 생성 |
| [집중 테스트](<../../../../../backend/tests/unit/evidence/test_document_page_model.py>) | 식별자·열린 코드·제약·PROTECT·PostgreSQL catalog 검증 |

## 4. Runtime 필드

| 구분 | 필드 | 구현·정책 |
| --- | --- | --- |
| 내부 식별자 | `id` | `BigAutoField`, PK, API 비노출 |
| 공개 식별자 | `public_id` | UUID, UNIQUE, 자동 생성, 수정 불가 |
| 부모 문서 | `document_id` | `knowledge_source_document.id` bigint PROTECT FK |
| 페이지 위치 | `page_no` | 정수, `page_no > 0` |
| 추출 결과 | `extracted_text` | nullable text |
| 변경 검출 | `text_sha256` | nullable `varchar(64)`, 값이 있으면 소문자 SHA-256 |
| 파싱 상태 | `parse_status_code` | `varchar(40)`, 기본값 `PENDING`, 승인 전 open code |
| 검수 상태 | `review_status_code` | `varchar(40)`, 기본값 `PENDING`, 승인 전 open code |
| 검색 사용 | `is_rag_eligible` | boolean, 기본값 `false` |
| 검색 제외 | `exclusion_reason` | nullable text |
| 검수자 | `reviewer_id` | nullable Accounts bigint PROTECT FK |
| 검수 시각 | `reviewed_at` | nullable timestamptz |
| 공통 시각 | `created_at`, `updated_at` | 생성·최종 수정 시각 |

## 5. 승인된 범위만 적용한 제약

| 제약·Index | 적용 내용 |
| --- | --- |
| `ux_document_page_no` | 같은 문서에서 동일 `page_no` 중복 금지 |
| `ck_document_page_no` | `page_no > 0` |
| `ck_document_page_sha256` | `text_sha256 IS NULL` 또는 소문자 16진수 64자 |
| `ck_document_page_review_bundle` | `reviewer_id`와 `reviewed_at`을 함께 설정하거나 함께 비움 |
| `ck_document_page_rag_eligibility` | RAG 사용 가능일 때만 확정된 양의 조건을 모두 요구 |
| `ix_document_page_rag` | `is_rag_eligible=true`인 행의 `(document_id, page_no)` partial Index |

RAG 사용 가능 행에는 다음 조건을 모두 적용한다.

1. `parse_status_code='PARSED'`
2. `review_status_code='APPROVED'`
3. `extracted_text IS NOT NULL`
4. `text_sha256 IS NOT NULL`
5. `reviewer_id IS NOT NULL`
6. `reviewed_at IS NOT NULL`
7. `exclusion_reason IS NULL`

이 조건은 `PARSED`와 `APPROVED`를 전체 허용값 집합으로 승인한 것이
아니다. 검색 사용을 `true`로 올릴 때 필요한 최소 양의 Gate만 고정한다.
`is_rag_eligible=false`인 기본·파싱·검수 대기 행에는 상태 후보값이나
제외 사유를 과도하게 강제하지 않는다.

## 6. 의도적으로 만들지 않은 제약

| 보류 항목 | 보류 이유 | 승인 후 작업 |
| --- | --- | --- |
| Parse `TextChoices`·allowed CHECK | canonical YAML 부재 | 코드 YAML 승인 후 Model·DB·Importer parity Migration |
| Review `TextChoices`·allowed CHECK | canonical YAML 부재 | 코드 YAML 승인 후 상태별 검수 bundle 규칙 확정 |
| 모든 비대상 행의 `exclusion_reason` 필수화 | 기본 `false`는 아직 파싱·검수 전 상태일 수 있음 | 제외 상태와 단순 대기 상태를 구분하는 계약 필요 |
| 부모 문서 승인·soft delete·dataset scope를 DB CHECK로 결합 | 다른 테이블을 참조하는 CHECK는 불가하고 현재 application policy | RAG QuerySet/Service에서 부모 문서와 검증된 `DocumentModelScope` 조인 |
| 자동 RAG 활성화 | 검수·제품 적용 범위 확인 전 자동 승인은 위험 | 명시적 검수 Service·권한·감사 이력과 함께 구현 |

## 7. 부모 문서와 `DocumentModelScope` 경계

페이지의 물리 부모는 `SourceDocument`이고 삭제 정책은 `PROTECT`다.
RAG 조회에서는 페이지 행만 보고 사용 가능 여부를 결정하면 안 된다.
후속 QuerySet·Service는 다음 부모 조건을 함께 적용해야 한다.

1. 부모 `SourceDocument`가 활성 상태이고 soft delete되지 않았는지
2. 요청의 dataset scope와 문서 scope가 일치하는지
3. 적용 기간 안에 있는지
4. 요청 제품에 대응하는 `DocumentModelScope`가 존재하는지
5. 해당 `DocumentModelScope.is_verified=true`인지

이번 Wave는 페이지 저장 무결성까지 담당한다. 제품별 최종 검색 포함
정책과 QuerySet은 AI/RAG 소비 계약 승인 후 별도 Wave로 구현한다.

## 8. Migration과 rollback

직접 의존성은 다음과 같다.

```text
accounts.0003_promote_integer_primary_keys
evidence.0003_documentmodelscope
  └─ evidence.0004_documentpage
```

`evidence.0003`을 수정하거나 초기 Migration을 다시 만들지 않았다.
Accounts 0003을 명시해 `reviewer_id`가 legacy 문자열이 아니라 bigint로
생성되게 했다.

Rollback은 `evidence 0004 → 0003`으로 수행한다. 이때
`knowledge_document_page`와 그 데이터가 제거되므로 운영 데이터가
있는 환경에서는 먼저 페이지·검수·RAG 사용 이력을 내보내야 한다.
검증용 빈 SQLite와 PostgreSQL에서는 rollback 후 테이블 부재,
reapply 후 타입·제약·Index 복원을 확인했다.

## 9. 작업·검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 지침·Physical v1.2·Snapshot·0003 대조 | 필드·식별자·코드 승인 상태 분류 | open code와 구조 제약 범위 확정 |
| 2 | Model·export 구현 | system check | 0 issues |
| 3 | `evidence.0004` 작성 | Migration drift | `No changes detected` |
| 4 | 집중 테스트 작성 | SQLite | `22 passed`, PG 전용 1 skip |
| 5 | 빈 SQLite 전체 Migration | 테이블 존재 조회 | `true` |
| 6 | SQLite rollback·reapply | 테이블 존재 조회 | `false → true` |
| 7 | 빈 PostgreSQL 16 전체 Migration | catalog 조회 | bigint/uuid 타입·5개 제약·partial Index 확인 |
| 8 | 유효·위반 데이터와 PROTECT | PostgreSQL 집중 테스트 | `23 passed` |
| 9 | PostgreSQL rollback·reapply | `to_regclass` 조회 | `false → true` |
| 10 | 관련 회귀 | Evidence·Accounts·T-005 | `62 passed`, 4 skip |
| 11 | 전체 회귀 | Backend 전체 | `601 passed`, 7 skip |
| 12 | 구현 매핑 감사 | T-005 Auditor | 본 테이블 `IMPLEMENTED`, 전체 `NOT_READY` |

초기 병렬 작업 중 Model export와 Migration 파일 생성 사이의 짧은
중간 상태에서 `knowledge_document_page`가 없다는 테스트 오류가
발생했다. `0004`를 즉시 추가해 Model·export·Migration을 원자 상태로
맞춘 뒤 같은 검증을 처음부터 다시 실행했다.

또한 첫 PostgreSQL PROTECT 검사 시 다른 병렬 Wave의
`support_guidance` Model이 export됐지만 해당 Migration이 아직
생성되기 전이라 `User.delete()` 수집기가 존재하지 않는 테이블을
조회했다. 해당 Wave의 Migration이 추가된 최종 원자 상태에서 실제
`SourceDocument.delete()`와 `User.delete()`가 모두 `ProtectedError`로
차단됨을 SQLite와 PostgreSQL에서 다시 확인했다.

## 10. 재현 명령

저장소 루트 기준 SQLite Gate:

```powershell
& .\backend\.venv\Scripts\python.exe backend\manage.py check `
  --settings=config.settings.test

& .\backend\.venv\Scripts\python.exe backend\manage.py makemigrations `
  evidence --check --dry-run --settings=config.settings.test

& .\backend\.venv\Scripts\python.exe -m pytest `
  backend\tests\unit\evidence\test_document_page_model.py -q
```

PostgreSQL Gate는 운영 DB가 아니라 별도 빈 DB를 지정해 실행한다.
비밀번호·DSN·실제 DB명은 문서나 로그에 저장하지 않는다.

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings.base'
$env:POSTGRES_DB = '<isolated-empty-database>'

& .\backend\.venv\Scripts\python.exe backend\manage.py migrate `
  --noinput --settings=config.settings.base

& .\backend\.venv\Scripts\python.exe -m pytest `
  backend\tests\unit\evidence\test_document_page_model.py `
  -q --ds=config.settings.base
```

## 11. 협업 인계

| 담당 | 인계 내용 |
| --- | --- |
| 최지용 | `evidence.0004` 번호·부모 의존성 유지, 후속 Evidence FK는 내부 bigint `id` 사용 |
| 윤승혁(PM) | `PARSE_STATUS`, `REVIEW_STATUS` 상태·전이·승인 권한 확정 |
| 이동윤 | RAG QuerySet이 페이지 Gate와 부모 문서·검증된 `DocumentModelScope`를 함께 적용하도록 소비 계약 확정 |
| 김은진 | 페이지 번호·정규화 텍스트·소문자 SHA-256·검수 bundle Importer/QA 규칙 작성 |
| API 담당 | 외부 응답은 `public_id`, 내부 FK와 조인은 `id` 사용 |
| 운영 담당 | 페이지 rollback 전 데이터 내보내기, 승인·제외 변경 감사 이력 보존 |

## 12. 잔여 위험과 다음 작업

- canonical Parse·Review 코드 YAML과 상태 전이 규칙이 아직 없다.
- Page 생성·검수·RAG 승인 Service와 권한·멱등성 API는 이번 Wave 범위가
  아니다.
- 부모 문서·제품 적용 범위를 함께 거르는 RAG QuerySet이 필요하다.
- 정식 importer와 검수 Seed가 없으므로 이 Migration은 빈 스키마
  재현만 증명하며 운영 페이지 데이터 적재를 증명하지 않는다.
- 다음 `knowledge_document_chunk`는 `DocumentPage.id` bigint를 부모
  FK로 사용해야 하며, Page 승인 상태를 임의로 복제하면 안 된다.
- 전체 T-005는 검증 시점 25/32로 `NOT_READY`다. 남은 계약 테이블,
  전체 Seed 2회, 소비자 검토와 작성자 외 리뷰가 끝난 뒤 중앙 완료
  판정을 다시 실행해야 한다.

## 13. 변경 이력

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | Model·export·0004·열린 상태 코드 정책·SQLite/PostgreSQL·rollback·회귀·협업 인계 기록 |
