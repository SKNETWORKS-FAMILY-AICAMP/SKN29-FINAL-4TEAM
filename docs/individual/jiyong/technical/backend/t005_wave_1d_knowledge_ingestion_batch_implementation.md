# T-005 Wave 1D `knowledge_ingestion_batch` 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_DB_VERIFIED`  
> 기준 계약: T-005 Physical Contract v1.2

## 1. 결과

공식 문서 수집·파싱·검수·적재 실행 단위를 보존하는
`knowledge_ingestion_batch`를 Django Runtime Model과 번호 Migration으로
구현했다. 내부 정수 PK, 외부 공개 UUID, 배치 업무번호, 멱등키,
상관관계 UUID, 실행 범위·소스·상태, 건수, 파이프라인 버전과 오류 요약을
분리했다.

| 검증 항목 | 최종 결과 |
| --- | --- |
| Django system check | 통과, 0 issues |
| Evidence Migration drift | 통과, `No changes detected` |
| SQLite 집중 테스트 | `9 passed` |
| 빈 PostgreSQL 집중 테스트 | `9 passed` |
| PostgreSQL 식별자 타입 | `id bigint`, `public_id uuid`, `started_by_id bigint` |
| PostgreSQL 역방향·재적용 | 테이블 제거 확인 후 0001 재적용·타입 복원 |
| T-005 구현 매핑 | `knowledge_ingestion_batch` IMPLEMENTED |
| T-005 전체 판정 | `NOT_READY`, 병렬 작업 포함 확인 시점 `16/32` |

`16/32`는 같은 작업 트리의 병렬 Wave를 포함한 관측값이다. 이 문서는
T-005 전체 완료나 팀 공용 `main` 반영을 선언하지 않는다.

## 2. 기준 문서와 우선순위

| 우선 | 기준 | 적용 |
| ---: | --- | --- |
| 1 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 신규 주요 테이블의 `BigAutoField id`·공개 `public_id`·내부 bigint FK |
| 2 | [식별자 ADR 0010](<../../../../adr/0010-t005-three-layer-identifier-bridge.md>) | 내부 PK, 외부 UUID, 업무 식별자 분리 |
| 3 | [테이블 사전 21번](<../../../../database/watercare_table_dictionary.md>) | 필드·관계·UNIQUE·CHECK·Index·삭제 정책 |
| 4 | [데이터 범위 코드](<../../../../../contracts/codes/dataset-scopes.yaml>) | `MVP`, `EXPANSION` |
| 5 | [수집 소스 코드](<../../../../../contracts/codes/ingestion-source-types.yaml>) | 4개 수집 소스 |
| 6 | [수집 상태 코드](<../../../../../contracts/codes/ingestion-statuses.yaml>) | 5개 실행 상태 |

테이블 사전의 역사 Snapshot `id uuid`보다 Physical v1.2의 전역 식별자
정책이 우선한다. 따라서 Runtime은 `id bigint`와 `public_id uuid`를 함께
가지며, 역사 18개 필드에 공개 UUID가 추가된 19개 필드다.

## 3. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [Evidence AppConfig](<../../../../../backend/apps/evidence/apps.py>) | `apps.evidence` Runtime App 등록 정보 |
| [IngestionBatch Model](<../../../../../backend/apps/evidence/models/ingestion_batch.py>) | 필드·TextChoices·제약·Index |
| [Evidence Model export](<../../../../../backend/apps/evidence/models/__init__.py>) | `IngestionBatch` 공개 및 Runtime 로딩 |
| [Evidence 0001 Migration](<../../../../../backend/apps/evidence/migrations/0001_initial.py>) | `knowledge_ingestion_batch` 생성 |
| [집중 단위 테스트](<../../../../../backend/tests/unit/evidence/test_ingestion_batch_model.py>) | 식별자·등록·FK·코드·건수·수명주기·멱등성 검증 |

## 4. 계약 필드

| 구분 | Runtime 구현 | 계약 의미 |
| --- | --- | --- |
| 내부 식별자 | `id BigAutoField` | DB 내부 조인 전용, API 비노출 |
| 공개 식별자 | `public_id UUIDField UNIQUE` | 외부 API와 팀 간 공개 참조 |
| 업무 식별자 | `batch_no varchar(50)` | 보고서·로그용 배치번호 |
| 범위 | `dataset_scope_code varchar(30)` | `MVP`, `EXPANSION` |
| 소스 | `source_type_code varchar(40)` | 로컬·HTTP·웹·수동 업로드 |
| 상태 | `status_code varchar(40)` | QUEUED부터 terminal 상태까지 |
| 중복·추적 | `idempotency_key`, `correlation_id` | 중복 실행 차단과 로그 연결 |
| 실행자 | `started_by_id bigint NULL` | Accounts 사용자 `PROTECT` FK |
| 시간 | `started_at`, `completed_at` | 시작·완료와 상태 정합성 |
| 건수 | `total_count`, `success_count`, `failure_count` | 비음수 처리 결과 |
| 재현 정보 | `pipeline_version`, `log_uri` | 실행 코드·상세 로그 위치 |
| 실패 정보 | `error_summary` | 민감정보를 제거한 오류 요약 |
| 공통 시간 | `created_at`, `updated_at` | 생성·최종 수정 일시 |

`started_by`는 자동 작업을 허용하기 위해 nullable이다. 값이 있으면
`accounts_user` 삭제를 `PROTECT`한다.

## 5. 코드·제약·Index

### 5.1 승인 코드

| 그룹 | 값 |
| --- | --- |
| `DATASET_SCOPE` | `MVP`, `EXPANSION` |
| `INGESTION_SOURCE_TYPE` | `LOCAL_FILE`, `HTTP_DOWNLOAD`, `WEB_PAGE`, `MANUAL_UPLOAD` |
| `INGESTION_STATUS` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `PARTIAL`, `FAILED` |

세 그룹 모두 canonical YAML이 `OWNER_BASELINE`이므로 Django
`TextChoices`와 DB allowed CHECK를 함께 적용했다.

### 5.2 물리 제약

| 제약 | 방지하는 문제 |
| --- | --- |
| `ux_ingestion_batch_no` | 같은 업무 배치번호 중복 |
| `ux_ingestion_batch_idempotency` | 같은 실행 요청 중복 |
| `ux_ingestion_batch_id_scope` | 후속 복합 FK의 범위 불일치 |
| `ck_ingestion_counts` | 음수 건수와 처리 합계 초과 |
| `ck_ingestion_time_order` | 시작 전 완료 |
| `ck_ingestion_terminal` | 상태·시각·성공/실패 건수 모순 |
| `ck_ingestion_error_summary` | PARTIAL·FAILED인데 오류 요약 누락 |
| 세 allowed CHECK | canonical YAML 밖 코드의 DB 우회 입력 |

조회 Index는 상태·생성일 역순의 `ix_ingestion_batch_status`와
상관관계 조회용 `ix_ingestion_batch_correlation`이다.

## 6. Migration 의존성

`evidence.0001_initial`은
`accounts.0003_promote_integer_primary_keys`에 직접 의존한다.

```text
accounts.0002
  → accounts.0003_promote_integer_primary_keys
    → evidence.0001_initial
```

이 순서를 지켜야 빈 PostgreSQL의 `started_by_id`가 legacy
`varchar(48)`가 아니라 `bigint`로 생성된다. Migration 파일명 변경이나
Accounts 0003 분할 시 Evidence 의존성도 같은 PR에서 갱신해야 한다.

## 7. 작업-검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | Physical v1.2·테이블 사전·canonical YAML 대조 | 필드·코드·관계 표 작성 | 단일 테이블 범위 확정 |
| 2 | AppConfig·Model·export 구현 | Django check | Runtime Model 정상 로딩 |
| 3 | Evidence 0001 작성 | `makemigrations evidence --check --dry-run` | drift 0 |
| 4 | 코드·건수·수명주기·멱등성 테스트 | SQLite 집중 테스트 | `9 passed` |
| 5 | Accounts 0003 의존성 확정 | 빈 PostgreSQL 전체 Migration | `started_by_id bigint` |
| 6 | 같은 테스트를 PostgreSQL에서 실행 | 격리 test DB | `9 passed` |
| 7 | 0001 역방향·재적용 | 테이블 부재·타입 직접 조회 | 제거·복원 모두 통과 |
| 8 | T-005 Auditor 실행 | Model·App·Migration 3계층 | IMPLEMENTED |

## 8. 재현 명령과 관측 결과

저장소 루트에서 SQLite Gate를 실행한다.

```powershell
Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python manage.py check --settings=config.settings.test
& $python manage.py makemigrations evidence `
    --check --dry-run `
    --settings=config.settings.test
& $python -m pytest `
    .\tests\unit\evidence\test_ingestion_batch_model.py `
    -q
```

관측 결과는 `No changes detected`와 `9 passed`다.

PostgreSQL Gate는 `backend/.env`를 Process 환경에 로드하고 임시
`POSTGRES_DB`를 만든 뒤 실행했다. 값 자체는 문서에 기록하지 않는다.

```powershell
docker compose --env-file .\backend\.env up -d postgres

Set-Location .\backend
$env:DJANGO_SETTINGS_MODULE = 'config.settings.base'
& .\.venv\Scripts\python.exe -m pytest `
    .\tests\unit\evidence\test_ingestion_batch_model.py `
    -q `
    --ds=config.settings.base
```

격리 PostgreSQL 결과는 `9 passed`다. 별도 roundtrip에서
`migrate evidence zero` 후 `knowledge_ingestion_batch` 부재를 확인했고,
`migrate evidence 0001` 재적용 후 아래 타입을 확인했다.

```text
rollback_table_absent=True
reapply_types=id,bigint;public_id,uuid;started_by_id,bigint
```

T-005 매핑은 저장소 루트에서 확인한다.

```powershell
& .\backend\.venv\Scripts\python.exe `
    .\scripts\database\audit_t005_implementation_readiness.py `
    --settings config.settings.test
```

## 9. 협업 인계

| 담당 | 후속 작업 |
| --- | --- |
| 최지용 | Evidence Migration 번호·Accounts 0003 의존성 유지 |
| 데이터 담당 | 실제 수집 실행 시 `batch_no`·멱등키 생성 규칙과 `pipeline_version` 기록 |
| AI/RAG 담당 | SourceDocument·Page·Chunk가 이 Batch를 내부 bigint FK로 참조하도록 구현 |
| API 담당 | 외부 응답에는 `public_id`, 내부 조인에는 `id` 사용 |
| 운영 담당 | `log_uri`에 비밀값·원문 개인정보를 저장하지 않고 오류 요약을 비식별화 |
| 통합 담당 | 병렬 Wave 반영 후 readiness 고정 기대값을 현재 구현 수로 갱신 |

## 10. 잔여 위험

- 이 테이블은 배치 원장만 제공하며 실제 importer·수집 Service·재시도
  orchestration은 포함하지 않는다.
- SourceDocument 이하 테이블이 아직 모두 구현된 것은 아니다.
- Seed 대상 기준정보가 아니라 실행 중 생성되는 원장이므로 정적 Seed에
  배치 row를 추가하지 않는다.
- T-005 전체는 아직 `NOT_READY`이며 빈 PostgreSQL 전체 Migration,
  Seed 2회와 전체 32개 테이블 Gate가 최종적으로 다시 필요하다.

## 11. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | `knowledge_ingestion_batch` Model·App·Migration·SQLite/빈 PostgreSQL·rollback 검증 및 인계 |
