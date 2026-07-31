# T-005 공통코드 Registry 구현·재현 가이드

> 기준일: 2026-07-30
> 작성·구현 책임: 최지용
> 협업 검증: 김은진(Database·Seed·QA), 윤승혁(PM·병합 Gate)
> Wave 당시 상태: `LOCAL_VERIFIED` — 담당 Branch Push와 PM `main` 병합 전
> 적용 원칙: `작업 → 즉시 검증 → 다음 작업`

> 역사 스냅샷: 이 문서의 12/32·418 passed 수치는 공통코드 Wave
> 직후 값이다. 현재 상태는
> [T-005 32개 테이블 최종 검증 보고서](t005_final_32_table_postgresql_seed_importer_validation_report.md)의
> `READY 32/32`, SQLite 740·PostgreSQL 751 결과를 우선한다.

## 1. 이번 문서가 다루는 범위

이번 Wave는 T-005의 32개 계약 테이블 중 아래 두 테이블만 구현한다.

1. `common_code_group`
2. `common_code`

다음 범위는 함께 구현하지 않았다.

- 공통코드 조회·관리 API, Serializer, Service, Admin
- 업무 테이블의 `*_code`를 `common_code` 물리 FK로 바꾸는 작업
- `field_service_visit_result`
- 위험도 코드의 대소문자 계약 변경
- AI Stage의 공통코드 그룹 추론
- 다른 팀원이 소유한 Data Fixture·AI·State 계약 변경

두 테이블 구현 후 T-005 Model·Migration 대응은 `12/32`, 미구현은
`20개`다. T-005 전체 상태는 계속 `NOT_READY`다.

## 2. 기준 문서와 우선순위

| 구분 | 기준 |
| --- | --- |
| 활성 T-005 계약 | [T-005 기준 패키지](../../../../database/t-005/README.md) |
| 활성 물리 정책 | [Physical Contract v1.2](../../../../database/t-005/t005_physical_contract_v1.2.json) |
| 역사적 필드 입력 | [WaterCare 테이블 명세](../../../../database/watercare_table_dictionary.md) |
| 공통 코드 원본 | [코드 계약 디렉터리](../../../../../contracts/codes/) |
| 공통 DB 개발 절차 | [Database Schema 개발·인계 가이드](database_schema_handover_guide.md) |
| Backend 실행 | [Backend README](../../../../../backend/README.md) |

충돌 시 활성 Physical Contract와 공통 개발 규칙을 역사적 Snapshot보다
우선한다. 따라서 `CommonCodeGroup.group_code`는 명시된 안정적 자연키
예외를 유지하고, `CommonCode`는 내부 정수 PK와 공개 UUID를 분리했다.

## 3. 구현 구조

| 경로 | 역할 |
| --- | --- |
| [App 설정](../../../../../backend/apps/common_codes/apps.py) | 독립 Django App 등록 |
| [CommonCodeGroup Model](../../../../../backend/apps/common_codes/models/common_code_group.py) | 변경·물리 삭제를 금지한 그룹 자연키 |
| [CommonCode Model](../../../../../backend/apps/common_codes/models/common_code.py) | 표시명·정렬·메타데이터 Registry |
| [DB 표현식](../../../../../backend/apps/common_codes/db_expressions.py) | SQLite·PostgreSQL JSON object CHECK 호환 |
| [값 Validator](../../../../../backend/apps/common_codes/validators.py) | Model 수준 JSON object 검증 |
| [0001 Migration](../../../../../backend/apps/common_codes/migrations/0001_initial.py) | `common_code_group` 생성 |
| [0002 Migration](../../../../../backend/apps/common_codes/migrations/0002_common_code.py) | `common_code` 생성 |
| [Seed 명령](../../../../../backend/apps/common_codes/management/commands/seed_common_codes.py) | 확정 10개 그룹을 Upsert |
| [단위 테스트](../../../../../backend/tests/unit/common_codes/) | Model·제약·Seed·멱등성 검증 |

`backend/common/models/**`는 추상 공통 Model 계층이므로 구체 테이블을
넣지 않았다. API·Service가 없는 현재 단계에서는 빈 디렉터리도 만들지
않았다.

## 4. Model·제약

### 4.1 `common_code_group`

| 항목 | 구현 |
| --- | --- |
| PK | `group_code varchar(40)` 자연키 |
| 형식 | `^[A-Z][A-Z0-9_]*$` |
| 표시 순서 | 0 이상 |
| Index | `is_active`, `display_order` |
| 변경 정책 | instance `save()`와 QuerySet `update()`에서 자연키 변경 차단 |
| 삭제 정책 | instance·QuerySet 물리 삭제 차단, `is_active=False` 사용 |

### 4.2 `common_code`

| 항목 | 구현 |
| --- | --- |
| 내부 PK | `id bigint`, 자동 증가, API 비노출 |
| 공개 ID | `public_id uuid`, 자동 생성·고유 |
| 그룹 관계 | `group_code` 물리 FK, `PROTECT` |
| 업무 유일성 | `(group_code, code)` UNIQUE |
| 코드 형식 | `^[A-Z][A-Z0-9_]*$` |
| 표시 순서 | 0 이상 |
| Metadata | 최상위 JSON object만 허용 |
| Index | `group_code`, `is_active`, `display_order` |

업무 Model의 `role_code`, `status_code` 같은 필드는 기존
`TextChoices`와 DB CHECK를 계속 사용한다. Registry는 표시·정렬·
확장속성 원본이며, 개별 `*_code` 컬럼의 물리 FK가 아니다.

## 5. Seed 범위와 차단 범위

### 5.1 이번 Wave에서 적재하는 확정 그룹

| Group | 계약 파일 |
| --- | --- |
| `USER_ROLE` | `user-roles.yaml` |
| `MANAGEMENT_TYPE` | `management-types.yaml` |
| `SUBSCRIPTION_STATUS` | `subscription-statuses.yaml` |
| `CARE_TYPE` | `care-types.yaml` |
| `CARE_STATUS` | `care-statuses.yaml` |
| `DATA_SOURCE` | `data-sources.yaml` |
| `CARE_RESULT` | `care-results.yaml` |
| `INQUIRY_CANCELLATION_REASON` | `inquiry-cancellation-reasons.yaml` |
| `USAGE_GUIDANCE_STATUS` | `usage-guidance-statuses.yaml` |
| `VISIT_STATUS` | `visit-statuses.yaml` |

현재 계약 기준 결과는 Group 10개, Code 43개다. Seed는
`update_or_create`를 사용한다. 같은 계약에서 제거된 기존 코드는
물리 삭제하지 않고 `is_active=False`로 바꾼다.

### 5.2 자동 적재하지 않는 계약

| 대상 | 이유 | 현재 조치 |
| --- | --- | --- |
| `risk-levels.yaml` | `general/caution/danger`가 DB 대문자 CHECK와 충돌 | `BLOCKED_CONTRACT_MAPPING` |
| `ai-stages.yaml` | 확정된 `common_code` Group Mapping이 없음 | 자동 추론 금지 |
| `data-classifications.yaml`, `product-scopes.yaml` | 소문자 값이며 현행 Registry 대문자 계약과 충돌 | 자동 변환 금지 |
| 빈 `codes: []` 계약 | 아직 실제 코드 집합이 없음 | 빈 Group 자동 생성 금지 |
| deprecated 계약 | canonical 계약과 중복될 수 있음 | canonical만 사용 |

소문자를 임의로 대문자로 바꾸거나 DB CHECK를 완화하면 Web·Mobile·
Data·AI 소비 코드까지 연쇄 변경될 수 있다. 별도 계약 결정 전에는
현재 차단을 유지한다.

## 6. 팀원 실행 순서

PM이 이 변경을 `main`에 병합하고 40자리 SHA를 공유한 뒤 저장소
루트에서 실행한다. 실제 `.env`와 `.venv`는 Git으로 공유하지 않는다.

```powershell
Set-Location (git rev-parse --show-toplevel)
docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres

Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python ..\scripts\database\check_postgresql_connection.py
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL 연결 확인 실패"
}

& $python manage.py migrate --plan --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "Migration 계획 확인 실패"
}
```

기존 데이터가 있는 DB는 Backend·Importer·Job Writer를 중지하고,
DB 이름·Host·Port와 백업 필요 여부를 확인한 뒤에만 적용한다.

```powershell
& $python manage.py migrate --noinput --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "Migration 적용 실패"
}

& $python manage.py migrate --check --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "미적용 Migration 존재"
}
```

Migration이 통과한 뒤 Seed를 두 번 실행한다.

```powershell
& $python manage.py seed_common_codes --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "공통코드 Seed 1차 실패"
}

& $python manage.py seed_common_codes --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "공통코드 Seed 2차 실패"
}
```

기대 결과:

- 1차: Group `created=10`, Code `created=43`
- 2차: Group `created=0, updated=10`, Code
  `created=0, updated=43`
- 두 실행 모두 `deactivated=0`은 현재 계약에 제거된 기적재 Code가
  없을 때의 값이다.
- `BLOCKED_CONTRACT_MAPPING` 경고는 알려진 위험도 계약 충돌을 숨기지
  않는 정상 출력이다.

## 7. 개발자 검증

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python manage.py check --settings=config.settings.test
& $python manage.py makemigrations `
    --check --dry-run `
    --settings=config.settings.test
& $python -m pytest `
    .\tests\unit\common_codes `
    .\tests\unit\database\test_t005_implementation_readiness.py `
    .\tests\unit\database\test_t005_schema_validator.py `
    -q -p no:cacheprovider

Set-Location ..
& .\backend\.venv\Scripts\python.exe `
    .\scripts\database\validate_t005_schema.py
& .\backend\.venv\Scripts\python.exe `
    .\scripts\database\audit_t005_implementation_readiness.py `
    --settings config.settings.test
```

감사 결과의 기대값:

- 계약 테이블: 32
- Model·Migration 구현: 12
- 미구현: 20
- 전체 상태: `NOT_READY`

## 8. 2026-07-30 작성자 검증 결과

| 검사 | 결과 |
| --- | --- |
| PostgreSQL | 16.14, UTC |
| 빈 격리 DB 전체 Migration | 성공 |
| 기본 `watercare` Migration | 백업 후 `0001`, `0002` 적용 성공 |
| PK 정책 | `id bigint`, `public_id uuid unique` 확인 |
| Seed 2회 | 10 Group·43 Code, 2차 신규 0 |
| 대문자 제약 | 소문자 적재 0 |
| 위험도 차단 | `RISK_LEVEL` Group 적재 0 |
| 관련 테스트 | 63 passed |
| 전체 T-005 | `12/32`, 잔여 20, `NOT_READY` |

전체 Backend 회귀 수치는 같은 변경 단위의 최종 실행 결과로 별도
보고서와 PR에 기록한다. 위 63건은 공통코드·T-005 관련 범위다.

## 9. 인계와 후속 작업

| 순서 | 담당 | 할 일 | 완료 증거 |
| ---: | --- | --- | --- |
| 1 | 최지용 | 변경을 `jiyong`에 Push하고 구현·Migration·문서를 같은 SHA로 고정 | 40자리 `jiyong` SHA |
| 2 | 김은진 | 빈 PostgreSQL에서 Migration과 Seed 2회를 독립 재현 | Exit code, 10 Group·43 Code, 중복 0 |
| 3 | 윤승혁(PM) | 리뷰 후 `main` 병합, 팀 기준 SHA 공유 | 40자리 `main` SHA |
| 4 | 전 팀원 | PM SHA를 반영하고 자기 소비 코드 회귀 | 담당 영역 테스트 결과 |
| 5 | 계약 담당자 | 위험도 대소문자와 AI Stage Group Mapping을 별도 결정 | 계약 Diff와 소비자 검토 |

`field_service_visit_result`는 기존 `Visit` 결과 필드, CareRecord UUID
Bridge, 완료 상태·Backfill과 연결된다. 공통코드 Wave와 묶지 않고
해당 입력을 확정한 뒤 별도 Migration으로 진행한다.

## 10. 롤백 원칙

- 공유 전 로컬 검증에서만, 새 테이블을 참조하는 외부 FK가 0이고
  백업이 있을 때 `common_codes` Migration만 되돌릴 수 있다.
- PM `main` 병합 후에는 이미 배포된 Migration 파일을 수정하거나
  삭제하지 않는다. 변경이 필요하면 새 Forward Migration을 만든다.
- Seed 데이터는 계약에서 재생성할 수 있지만, 임의 SQL 삭제 대신
  비활성화 정책을 사용한다.
- `down -v`는 PostgreSQL Volume을 삭제하므로 이 작업의 롤백 명령이
  아니다.
