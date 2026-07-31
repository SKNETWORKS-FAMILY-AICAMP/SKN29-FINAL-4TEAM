# T-005 Wave 1 Canonical 코드 계약 보완·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 작업 상태: `LOCAL_VERIFIED`  
> 적용 범위: Wave 1 `aiops_ai_run`, `knowledge_ingestion_batch`

## 1. 결과

Wave 1 테이블의 Model과 DB CHECK에는 값이 확정되어 있었지만
`contracts/codes/*.yaml`과 공통코드 Seed에 없었던 여섯 코드군을
canonical 계약으로 등록했다.

| 구분 | 결과 |
| --- | --- |
| 신규 canonical YAML | 6개 |
| 신규 공통코드 그룹 | 6개 |
| 신규 코드 값 | 29개 |
| 전체 Seed 대상 | 10개 그룹에서 16개 그룹으로 확장 |
| YAML 구문·형식 | 기존 `load_contract_codes` 검증 통과 |
| YAML ↔ TextChoices ↔ Seed | 일치 |
| Seed 2회 실행 | 행 수·PK·Public UUID 유지 |
| 기존 Seed·도메인 회귀 | 통과 |

Model과 Migration은 변경하지 않았다.

## 2. 추가한 코드 계약

| Group | Canonical 파일 | 확정 값 |
| --- | --- | --- |
| `AI_TASK_TYPE` | [ai-task-types.yaml](<../../../../../contracts/codes/ai-task-types.yaml>) | STRUCTURE_SYMPTOM, GENERATE_QUESTIONS, ASSESS_RISK, RETRIEVE_EVIDENCE, GENERATE_GUIDANCE, SUMMARIZE_CONSULTATION, DRAFT_HANDOFF |
| `AI_SCHEMA_VALIDATION_STATUS` | [ai-schema-validation-statuses.yaml](<../../../../../contracts/codes/ai-schema-validation-statuses.yaml>) | NOT_RUN, PASSED, FAILED |
| `AI_RUN_STATUS` | [ai-run-statuses.yaml](<../../../../../contracts/codes/ai-run-statuses.yaml>) | QUEUED, RUNNING, SUCCEEDED, NO_EVIDENCE, FAILED, TIMED_OUT, RETRYING, CANCELLED |
| `DATASET_SCOPE` | [dataset-scopes.yaml](<../../../../../contracts/codes/dataset-scopes.yaml>) | MVP, EXPANSION |
| `INGESTION_SOURCE_TYPE` | [ingestion-source-types.yaml](<../../../../../contracts/codes/ingestion-source-types.yaml>) | LOCAL_FILE, HTTP_DOWNLOAD, WEB_PAGE, MANUAL_UPLOAD |
| `INGESTION_STATUS` | [ingestion-statuses.yaml](<../../../../../contracts/codes/ingestion-statuses.yaml>) | QUEUED, RUNNING, SUCCEEDED, PARTIAL, FAILED |

모든 계약은 기존 형식과 동일하게 `version: 1.0.0`,
`status: OWNER_BASELINE`, 순서가 보존되는 `codes` 목록을 사용한다.

## 3. 구현 파일

| 파일 | 변경 |
| --- | --- |
| [공통코드 Seed 명령](<../../../../../backend/apps/common_codes/management/commands/seed_common_codes.py>) | 여섯 `SeedSpec` 등록, 도움말의 대상 그룹 수를 16개로 갱신 |
| [Wave 1 코드 parity 테스트](<../../../../../backend/tests/unit/common_codes/test_wave1_code_contracts.py>) | YAML·TextChoices·Seed 순서 및 source metadata 일치, 2회 실행 식별자 보존 검증 |

Seed는 기존 `update_or_create` 정책을 유지한다. 계약에서 제거된 코드는
물리 삭제하지 않고 같은 source contract 범위에서 비활성화한다.

## 4. 작업-검증 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | Physical v1.2·테이블 사전·Runtime TextChoices 비교 | 값 집합·순서 대조 | 여섯 그룹 29값 확정 |
| 2 | YAML 6개 작성 | 기존 YAML loader 실행 | 6개 모두 통과 |
| 3 | `SeedSpec` 6개 등록 | Seed 대상·값 출력 | 16개 그룹, 신규 29값 확인 |
| 4 | 3계층 parity 테스트 추가 | 신규 테스트 | `2 passed` |
| 5 | 기존 Seed 회귀 | 공통코드 Seed 테스트 | `4 passed` |
| 6 | 기존 도메인 코드 회귀 | Care·Subscription parity | `6 passed` |
| 7 | 대상 Model 회귀 | AIRun·IngestionBatch 테스트 | `22 passed` |

## 5. 재현 명령

저장소의 `backend` 폴더에서 실행한다.

```powershell
$python = '.\.venv\Scripts\python.exe'

& $python -m pytest `
    .\tests\unit\common_codes\test_wave1_code_contracts.py `
    -q
& $python -m pytest `
    .\tests\unit\common_codes\test_seed_common_codes.py `
    .\tests\unit\care\test_code_contracts.py `
    .\tests\unit\subscriptions\test_code_contracts.py `
    .\tests\unit\audit\test_ai_run_model.py `
    .\tests\unit\evidence\test_ingestion_batch_model.py `
    -q
```

실제 Seed 검증은 빈 검증 DB에서 두 번 실행한 뒤 두 번째 실행의
`created=0`과 행 식별자 불변을 확인한다.

```powershell
& $python manage.py seed_common_codes `
    --settings=config.settings.local
& $python manage.py seed_common_codes `
    --settings=config.settings.local
```

## 6. `CAUSE_CATEGORY` 결정 대기

VisitResult의 `CAUSE_CATEGORY`는 이번 Wave에서 만들지 않았다.

| 확인 소스 | 상태 |
| --- | --- |
| [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 표준 코드 또는 override 없음 |
| T-005 Decision·Logical Contract | 확정 항목 없음 |
| `contracts/codes` | canonical YAML 없음 |
| [테이블 사전](<../../../../database/watercare_table_dictionary.md>) | PRODUCT, INSTALLATION, WATER_SUPPLY, USER_ENVIRONMENT, UNKNOWN 후보가 있으나 `Design Draft`이며 Enum 값 집합은 팀 결정 필요 |

따라서 `CAUSE_CATEGORY`의 현재 상태는
`BLOCKED_CONTRACT_DECISION`이다. PM·Data Owner가 후보 5값을
OWNER_BASELINE으로 승인한 뒤 YAML, VisitResult TextChoices·CHECK,
SeedSpec, parity 테스트를 한 번에 반영해야 한다.

## 7. 협업 인계

| 담당 | 인계 내용 |
| --- | --- |
| 최지용 | 새 코드 계약·Seed·테스트를 같은 변경 단위로 유지 |
| AI/API 담당 | 요청·응답에서 canonical 대문자 코드를 사용하고 임의 alias 추가 금지 |
| Data 담당 | Seed는 수동 INSERT가 아니라 `seed_common_codes`로 재현 |
| PM/계약 담당 | 코드 추가·삭제 시 YAML을 먼저 승인하고 TextChoices·CHECK·Seed를 함께 변경 |
| Visit 담당 | `CAUSE_CATEGORY` 승인 전 후보값을 Runtime에 고정하지 않음 |

## 8. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | Wave 1 AI·지식수집 canonical 코드 6그룹, Seed, parity·멱등 검증 및 CAUSE_CATEGORY 결정 대기 기록 |
