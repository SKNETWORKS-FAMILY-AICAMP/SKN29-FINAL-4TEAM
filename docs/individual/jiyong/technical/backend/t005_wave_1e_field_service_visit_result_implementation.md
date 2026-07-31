# T-005 Wave 1E `field_service_visit_result` 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_DB_VERIFIED`  
> 기준 계약: T-005 Physical Contract v1.2

## 1. 결과

기사의 점검·조치·고객 안내·현장 해결·재방문 결과를 방문별 한 번만
저장하는 `field_service_visit_result`를 구현했다. 내부 정수 PK와 외부
UUID를 분리하고, 방문·제출자 `PROTECT` 관계, 방문별 UNIQUE, 멱등키,
재방문 사유 CHECK와 해결 상태 조회 Index를 적용했다.

PostgreSQL에서는 `(visit_id, submitted_by_id)`가 실제
`field_service_visit(id, technician_id)`를 참조하는 복합 FK를 생성한다.
따라서 TECHNICIAN 역할만으로는 부족하며 해당 방문에 배정된 기사만 결과를
제출할 수 있다.

| 검증 항목 | 최종 결과 |
| --- | --- |
| Django system check | 통과, 0 issues |
| Visits Migration drift | 통과, `No changes detected` |
| SQLite Visits 회귀 | `11 passed`, PostgreSQL 전용 2건 SKIP |
| 빈 PostgreSQL VisitResult 집중 테스트 | `8 passed` |
| PostgreSQL 식별자 타입 | `id/visit_id/submitted_by_id bigint`, `public_id uuid` |
| PostgreSQL 복합 FK | 존재 확인, 다른 기사 INSERT 차단 |
| PostgreSQL rollback·reapply | 결과 테이블 제거, 재적용 후 복합 FK 1개 복원 |
| Care UUID Bridge | 유지, `VisitResult.public_id` 연결 테스트 통과 |
| T-005 구현 매핑 | `field_service_visit_result` IMPLEMENTED |

## 2. 기준 문서와 우선순위

| 우선 | 기준 | 적용 |
| ---: | --- | --- |
| 1 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 신규 주요 테이블의 bigint PK·공개 UUID·내부 bigint FK |
| 2 | [식별자 ADR 0010](<../../../../adr/0010-t005-three-layer-identifier-bridge.md>) | 내부 PK, 공개 UUID, 업무 식별자 분리 |
| 3 | [테이블 사전 17·18번](<../../../../database/watercare_table_dictionary.md>) | Visit 부모 UNIQUE, VisitResult 필드·제약·Index |
| 4 | [API 명세 VisitResult](<../../../../api/watercare_api_specification.md>) | 요청·응답 필드와 조건부 재방문 사유 |
| 5 | [화면설계 TECH-03](<../../../../planning/md/화면설계서.md>) | 방문 결과·케어 이력·다음 케어 연결 |

테이블 사전의 역사 Snapshot `id uuid`보다 Physical v1.2의 전역 정책이
우선한다. Runtime은 역사 17개 필드의 `id`를 bigint로 전환하고
`public_id`를 추가한 18개 필드다.

## 3. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [VisitResult Model](<../../../../../backend/apps/visits/models/visit_result.py>) | 결과 필드·관계·제약·Index·portable validation |
| [Visit 부모 Model](<../../../../../backend/apps/visits/models/visit.py>) | 복합 FK 부모키 `ux_visit_id_technician` |
| [Visits Model export](<../../../../../backend/apps/visits/models/__init__.py>) | `VisitResult` Runtime 공개 |
| [Visits 0002 Migration](<../../../../../backend/apps/visits/migrations/0002_visitresult.py>) | 부모 UNIQUE·결과 테이블·PostgreSQL 복합 FK |
| [VisitResult 집중 테스트](<../../../../../backend/tests/unit/visits/test_visit_result.py>) | 계약·UNIQUE·CHECK·PROTECT·Care Bridge·PostgreSQL FK |
| [기존 Care Model](<../../../../../backend/apps/care/models/care_history.py>) | 이번 Wave에서 유지한 nullable UUID Bridge |

## 4. 계약 필드

| 구분 | Runtime 구현 | 필수·Null |
| --- | --- | --- |
| 내부 식별자 | `id BigAutoField` | PK, 필수 |
| 공개 식별자 | `public_id UUIDField` | UNIQUE, 필수 |
| 방문 | `visit_id bigint` | OneToOne·PROTECT, 필수 |
| 원인 범주 | `cause_category_code varchar(40)` | nullable, 승인 전 open code |
| 현장 결과 | `inspection_summary`, `action_summary` | text, 필수 |
| 부품·안내 | `parts_used_text`, `customer_guidance` | text, nullable |
| 해결·재방문 | `resolved_on_site`, `revisit_required` | boolean, 기본 false |
| 재방문 사유 | `revisit_reason` | text, 조건부 |
| 기사 메모 | `technician_note` | text, nullable |
| 제출자 | `submitted_by_id bigint` | Accounts PROTECT FK, 필수 |
| 중복 차단 | `idempotency_key varchar(128)` | UNIQUE, 필수 |
| 결과 시각 | `completed_at timestamptz` | 기본 현재 시각 |
| 다음 케어 | `next_care_on date` | nullable |
| 공통 시간 | `created_at`, `updated_at` | 필수 |

## 5. 제약과 Index

| 이름·구현 | 목적 |
| --- | --- |
| Visit OneToOne UNIQUE | 한 방문에 결과 한 건만 허용 |
| `ux_visit_result_idempotency` | 완료 요청 재전송의 중복 결과 차단 |
| `ck_visit_result_revisit_reason` | 재방문 필요인데 사유가 NULL인 row 차단 |
| `ux_visit_id_technician` | 부모 `(id, technician_id)`를 복합 FK 후보키로 제공 |
| `fk_visit_result_assigned_technician` | 배정 기사와 제출자 불일치 차단 |
| `ix_visit_result_resolution` | 해결·재방문·완료일시 조건 조회 |
| 각 `PROTECT` FK | 방문·제출자 참조 중 물리 삭제 차단 |

### 5.1 PostgreSQL 복합 FK

Django의 일반 `ForeignKey` 두 개는 “존재하는 방문”과 “존재하는 사용자”만
각각 확인하며, 둘의 배정 관계는 확인하지 못한다. 0002에서 먼저 부모
UNIQUE를 만든 뒤 PostgreSQL 전용 DDL을 실행한다.

```sql
FOREIGN KEY (visit_id, submitted_by_id)
REFERENCES field_service_visit (id, technician_id)
ON DELETE RESTRICT
```

SQLite에는 사후 복합 FK 추가 기능이 없어 Model `clean()`이 동일 규칙을
검사한다. 서비스 계층은 저장 전 `full_clean()`을 호출해야 하며,
최종 운영 보장은 PostgreSQL 복합 FK가 담당한다.

## 6. `CAUSE_CATEGORY` 계약 보류

테이블 사전에는 다음 다섯 값이 설계 후보로 적혀 있다.

```text
PRODUCT, INSTALLATION, WATER_SUPPLY, USER_ENVIRONMENT, UNKNOWN
```

그러나 현재 [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>),
Decision Register와 `contracts/codes/`에는 OWNER 승인된
`CAUSE_CATEGORY` canonical YAML이 없다. 테이블 사전 자체도 값 집합을
팀 결정 필요로 표시한다.

따라서 이번 구현은 아래 원칙을 따른다.

- `cause_category_code`는 계약의 nullable `varchar(40)`만 구현한다.
- 후보 5값을 Django `TextChoices`나 DB allowed CHECK로 동결하지 않는다.
- fixture의 `"PRODUCT"`는 저장 예시일 뿐 승인 코드 선언이 아니다.
- 승인 전에는 임의 문자열을 DB가 거부한다고 가정하지 않는다.
- OWNER가 canonical YAML을 승인하면 Model TextChoices, DB CHECK,
  계약 parity test와 별도 번호 Migration을 같은 변경으로 추가한다.

이 판단으로 미승인 enum을 확정해 후속 데이터·API와 연쇄 충돌하는 문제를
피했다.

## 7. Migration 의존성

`visits.0002_visitresult`는 다음 두 Migration 뒤에 실행된다.

```text
visits.0001_initial
accounts.0003_promote_integer_primary_keys
  → visits.0002_visitresult
```

Accounts 0003 의존성이 없으면 빈 PostgreSQL의 `submitted_by_id`가 legacy
문자 PK 상태를 참조할 수 있다. 최종 검증에서는 `submitted_by_id bigint`를
직접 확인했다.

0002의 작업 순서는 다음과 같다.

1. Visit에 `ux_visit_id_technician` 추가
2. `field_service_visit_result` 생성
3. PostgreSQL에 `fk_visit_result_assigned_technician` 추가

역방향은 복합 FK 제거, 결과 테이블 제거, 부모 UNIQUE 제거 순으로 실행된다.

## 8. Care Bridge 유지와 후속 전환

기존 `CareRecord.visit_result_public_id`는 nullable UUID이며 Django
관계 필드가 아니다. 이번 Wave에서는 이를 삭제하거나 실제 FK로 바꾸지
않았다.

| 현재 연결 | 이유 |
| --- | --- |
| `CareRecord.visit_result_public_id = VisitResult.public_id` | 기존 Care Migration과 순환 의존성을 만들지 않고 공개 UUID로 결과를 연결 |
| `CareRecord.visit = Visit` | 같은 방문·구독·문의 연결을 기존 Runtime에서 유지 |

집중 테스트는 Care row에 새 `VisitResult.public_id`를 저장하고 동일 Visit을
가리키는지 확인한다. 실제 FK 전환은 Care 담당과 아래 항목을 함께 결정한
후 별도 Migration으로 진행한다.

- Visit 완료·VisitResult INSERT·CareRecord 생성·상태 이력 INSERT의
  `transaction.atomic()` 서비스
- 기존 UUID Bridge row의 bigint FK backfill
- 동일 subscription·inquiry·visit 정합성 검증
- Migration 순환과 rollback 경로

## 9. 작업-검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | Physical v1.2·Visit·Care Bridge·테이블 사전 대조 | 필드·관계·후보키 확인 | 부모 UNIQUE 필요 확인 |
| 2 | VisitResult·export 구현 | Django check | Runtime 로딩 통과 |
| 3 | 부모 UNIQUE·0002·복합 FK 작성 | Migration drift | drift 0 |
| 4 | UNIQUE·CHECK·PROTECT·clean·Care 테스트 | SQLite Visits 회귀 | `11 passed`, PG 전용 2 SKIP |
| 5 | 초기 PostgreSQL Gate | Accounts 0003 선행 오류 검출 | `accounts_user_groups` 오류를 Accounts Wave에 전달 |
| 6 | Accounts 0003 수정 후 재검증 | 빈 PostgreSQL 전체 Migration | 선행 오류 해소 |
| 7 | PG 구조·위반 테스트 | 타입·constraint catalog·잘못된 제출 | `8 passed` |
| 8 | 0002 rollback·reapply | 테이블 부재·복합 FK 개수 | `True`, `1` |
| 9 | P1 enum 계약 재검토 | Physical·Decision·YAML 비교 | 미승인 TextChoices·CHECK 제거 |
| 10 | enum 제거 후 SQLite·PG 재실행 | drift·회귀·복합 FK | 모두 통과 |
| 11 | T-005 Auditor 실행 | Model·App·Migration 3계층 | IMPLEMENTED |

## 10. 재현 명령과 관측 결과

SQLite Gate:

```powershell
Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python manage.py check --settings=config.settings.test
& $python manage.py makemigrations visits `
    --check --dry-run `
    --settings=config.settings.test
& $python -m pytest .\tests\unit\visits -q
```

최종 결과:

```text
System check identified no issues
No changes detected in app 'visits'
11 passed, 2 skipped
```

두 SKIP은 PostgreSQL catalog·복합 FK 위반 전용 테스트다.

PostgreSQL Gate는 `backend/.env`를 Process 환경에 로드하고 임시 DB를
사용했다. 비밀값은 문서에 기록하지 않는다.

```powershell
docker compose --env-file .\backend\.env up -d postgres

Set-Location .\backend
$env:DJANGO_SETTINGS_MODULE = 'config.settings.base'
& .\.venv\Scripts\python.exe -m pytest `
    .\tests\unit\visits\test_visit_result.py `
    -q `
    --ds=config.settings.base
```

최종 결과는 `8 passed`다. 구조 테스트는 아래를 확인한다.

```text
id=bigint
public_id=uuid
visit_id=bigint
submitted_by_id=bigint
fk_visit_result_assigned_technician=present
unassigned technician insert=blocked
```

별도 Migration roundtrip 결과:

```text
rollback_table_absent=True
reapply_fk_count=1
```

## 11. 협업 인계

| 담당 | 후속 작업 |
| --- | --- |
| 최지용 | Visits 0002·Accounts 0003 의존성, 부모 UNIQUE·복합 FK 유지 |
| PM/계약 담당 | `CAUSE_CATEGORY` 값·명칭·버전·소유자를 canonical YAML로 승인 |
| API 담당 | `VisitResult.public_id`만 외부 노출하고 internal id 비노출 |
| Backend Workflow 담당 | Visit 전이·결과·Care·상태 이력을 한 transaction으로 저장 |
| Care 담당 | UUID Bridge backfill과 실제 FK 전환을 별도 Migration으로 공동 검토 |
| 데이터 담당 | 승인 전 원인 코드를 확정 기준정보로 간주하거나 Seed하지 않음 |
| 통합 담당 | readiness 고정 기대값을 병렬 Wave 완료 수에 맞춰 갱신 |

## 12. 잔여 위험

- Visit 기존 inline `confirmed_cause`·`action_taken`과 새 VisitResult의
  점검·조치 필드가 함께 존재한다. 소비자 전환과 backfill 전에는 기존
  필드를 제거하지 않는다.
- `policy_visit_result_completion_transaction`을 수행하는 Service·API는
  아직 이 테이블 구현 범위에 포함되지 않는다.
- SQLite는 DB 복합 FK가 아니라 `full_clean()` 검증이므로 서비스가 이를
  우회하지 않아야 한다.
- Care UUID Bridge는 호환용이며 최종 물리 FK 완료를 뜻하지 않는다.
- `CAUSE_CATEGORY`는 canonical 계약 승인 전 open code다.
- T-005 전체는 아직 `NOT_READY`다.

## 13. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | `field_service_visit_result` Model·Migration·복합 FK·Care Bridge·SQLite/빈 PostgreSQL·rollback 검증 및 미승인 enum 인계 |
