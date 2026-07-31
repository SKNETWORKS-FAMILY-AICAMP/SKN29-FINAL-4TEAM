# T-005 Wave 1A `support_questionnaire_session` Model·Migration 구현·재현 가이드

> 기준일: 2026-07-30
> 문서 버전: v1.1
> WBS: `T-005 데이터베이스 설계 및 구축`
> 작성·구현 책임: 최지용
> 협업 검증: 김은진(Data·Migration·Seed 독립 QA), 윤승혁(PM·계약 결정·병합 Gate)
> 기준 Branch: `jiyong`
> 작업 전 기준 Commit: `765047c2342bc30363a5c543a1f9ea324730d079`
> Wave 당시 상태: `LOCAL_VERIFIED` — Wave 1A 로컬 구현·자동 검증 완료, 독립 QA·PR·`main` 병합 전

> 역사 스냅샷: 이 문서의 13/32·426 passed 수치는 Wave 1A 직후
> 값이다. 현재 상태는
> [T-005 32개 테이블 최종 검증 보고서](t005_final_32_table_postgresql_seed_importer_validation_report.md)의
> `READY 32/32`, SQLite 740·PostgreSQL 751 결과를 우선한다.

## 1. 결론과 완료 경계

이번 Wave에서는 계약 테이블 하나인 `support_questionnaire_session`의
Django Model, App 등록, 번호 Migration과 집중 테스트를 구현했다.
빈 PostgreSQL 16.14에서 전체 Migration과 실제 CHECK를 검증했고,
기존 Seed 5종을 두 번 실행해 두 번째 실행의 신규 생성이 0건임을
확인했다.

T-005 Model·Runtime·Migration 매핑 감사 결과는 `12/32`에서
`13/32`로 증가했고 미구현 테이블은 20개에서 19개로 감소했다.
이 수치는 **테이블 매핑 수**이며 모든 컬럼·제약·API가 완성됐다는
뜻이 아니다. T-005 전체 판정은 계속 `NOT_READY`다.

| 구분 | 이번 Wave 판정 |
| --- | --- |
| `support_questionnaire_session` Model·App·Migration | 로컬 구현·검증 완료 |
| PostgreSQL JSON object CHECK | 물리 DB 우회 저장 거부 확인 |
| 빈 PostgreSQL 전체 Migration | 통과 |
| 기존 Seed 5종 2회 | 통과, 2회차 신규 0 |
| Backend 전체 회귀 | 통과 |
| Data 전체 회귀 | 통과, `data/**` 수정 없음 |
| 동일 구독 복합 FK | [Wave 1B](<t005_wave_1b_questionnaire_inquiry_composite_fk.md>)에서 로컬 구현·검증, 독립 QA 대기 |
| Questionnaire API·Service·상태 전이 | 미구현 |
| 독립 QA·PR·`main` 병합 | 미완료 |

## 2. 포함·제외 범위

### 2.1 포함

- `QuestionnairesConfig` 등록
- `QuestionnaireSession` Runtime Model 등록
- 내부 `bigint` PK, 공개 UUID, 업무 번호 분리
- Subscription·Inquiry 관계와 `PROTECT` 삭제 정책
- 문진 유형·상태·버전·JSON 답변·상태 버전·수명주기 시각
- 생성 멱등키와 주요 UNIQUE·CHECK·Index
- PostgreSQL `jsonb_typeof(answers_payload)='object'` CHECK
- SQLite 집중 테스트와 PostgreSQL 실제 제약 검증
- T-005 구현 매핑 회귀값 갱신

### 2.2 제외

- Questionnaire Serializer·Repository·Service·API Route
- `START_CARE_PRECHECK`, 임시 저장, 제출, `LINK_INQUIRY` 이벤트 처리
- `session_no` 서버 생성 규칙
- `QUESTIONNAIRE_TYPE`, `QUESTIONNAIRE_STATUS` 공통코드 계약·Seed
- Inquiry·Workflow의 기존 공개 UUID Bridge Backfill·제거
- `support_inquiry_status_history` 구현
- Data Fixture·Crosswalk·367건 importer 입력 확대
- 다른 19개 미구현 계약 테이블

제외 항목은 의존 계약과 담당 영역이 달라 한 Migration에 섞으면
연쇄 오류가 발생할 수 있으므로 별도 Wave로 분리한다.

## 3. 기준 문서와 우선순위

| 우선순위 | 기준 | 적용 |
| ---: | --- | --- |
| 1 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 내부 정수 PK·공개 UUID·업무 식별자 분리 |
| 2 | [T-005 결정 등록부 v0.3](<../../../../database/t-005/t005_decision_register_v0.3.json>) | 승인 결정과 완료 Gate |
| 3 | [T-005 기준 패키지](<../../../../database/t-005/README.md>) | 활성 계약·검증 명령·진행 경계 |
| 4 | [WaterCare 테이블 명세](<../../../../database/watercare_table_dictionary.md>) | 문진 세션 필드·제약의 역사적 설계 입력 |
| 5 | [DB 스키마 개발·인계 가이드](<database_schema_handover_guide.md>) | Model → Migration → PostgreSQL → Seed → 문서 순서 |

테이블 명세의 문진 PK는 UUID이지만 활성 Physical Contract v1.2는 새
주요 테이블에 내부 자동 증가 `bigint id`와 외부 공개용
`UUID public_id`를 즉시 적용하도록 정한다. 따라서 이번 Model은
활성 계약을 우선해 16개 필드로 구현했다.

테이블 명세의 문진 절은 `Design Draft`이고 상태·이벤트·제약은 팀
승인 전이라고 명시돼 있다. 구현 가능한 데이터 무결성은 반영하되,
API와 공통코드처럼 승인 입력이 부족한 항목은 추정 구현하지 않았다.

## 4. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [App 설정](<../../../../../backend/apps/questionnaires/apps.py>) | `QuestionnairesConfig` 선언 |
| [Model 공개 목록](<../../../../../backend/apps/questionnaires/models/__init__.py>) | Runtime Model export |
| [QuestionnaireSession Model](<../../../../../backend/apps/questionnaires/models/questionnaire_session.py>) | 필드·관계·제약·Model 검증 |
| [0001 초기 Migration](<../../../../../backend/apps/questionnaires/migrations/0001_initial.py>) | 테이블·DB별 JSON object 표현식·제약·Index 생성 |
| [공용 JSON DB 표현식](<../../../../../backend/apps/common_codes/db_expressions.py>) | SQLite `JSON_TYPE`·PostgreSQL `jsonb_typeof` 분기 |
| [App 등록](<../../../../../backend/config/settings/base.py>) | `INSTALLED_APPS` 등록 |
| [문진 Model 테스트](<../../../../../backend/tests/unit/questionnaires/test_questionnaire_session_model.py>) | 식별자·기본값·제약·삭제·Index 검증 |
| [T-005 매핑 테스트](<../../../../../backend/tests/unit/database/test_t005_implementation_readiness.py>) | 13/32, 잔여 19 회귀 기준 |
| [T-005 Auditor](<../../../../../scripts/database/audit_t005_implementation_readiness.py>) | Model·App·Migration 매핑 실측 |

`questionnaire_answer.py`는 별도 답변 테이블로 구현하지 않았다.
현재 계약은 `answers_payload JSONB`를 문진 스냅샷 원장으로 사용한다.

## 5. Model·제약 결정

### 5.1 식별자와 필드

| 항목 | 구현 | 이유 |
| --- | --- | --- |
| 내부 PK | `BigAutoField id` | 활성 3계층 식별자 정책 |
| 공개 식별자 | `UUIDField public_id`, 자동 생성·UNIQUE | API 노출용 안정 식별자 |
| 업무 식별자 | `session_no varchar(40)`, UNIQUE, 기본값 없음 | 승인되지 않은 번호 형식 추정 금지 |
| 구독 | 필수 FK, `PROTECT` | 문진 대상 구독 보존 |
| 문의 | nullable One-to-One, `PROTECT` | 제출 후 한 문의에만 연결 |
| 답변 | `JSONField(default=dict)` | 질문 코드별 스냅샷 |
| 상태 버전 | 기본값 1, DB `> 0` | 낙관적 잠금 기반 |
| 생성 멱등키 | `varchar(128)`, UNIQUE | 중복 세션 생성 차단 |

### 5.2 무결성

| 규칙 | SQLite·Model | PostgreSQL 물리 DB |
| --- | --- | --- |
| 허용 문진 유형 | TextChoices + CHECK | CHECK |
| 허용 상태 | TextChoices + CHECK | CHECK |
| `state_version > 0` | CHECK | CHECK |
| 제출 전 `submitted_at IS NULL` | `clean()` + CHECK | CHECK |
| 제출 시각 ≥ 시작 시각 | `clean()` + CHECK | CHECK |
| 문의 연결 시 SUBMITTED·시각 순서 | `clean()` + CHECK | CHECK |
| 답변 최상위 JSON object | `clean()` | `ck_questionnaire_answers_object` |
| 문진·문의의 동일 구독 | `clean()` | [Wave 1B](<t005_wave_1b_questionnaire_inquiry_composite_fk.md>)의 PostgreSQL 복합 FK로 보강 |

`Model.clean()`은 `QuerySet.update()`와 raw SQL에서 호출되지 않는다.
따라서 JSON object 규칙은 Model Meta와 `0001_initial`에
`IsJSONObject` CHECK로 함께 선언했다. 같은 Migration state가
SQLite에서는 `JSON_TYPE`, PostgreSQL에서는 `jsonb_typeof`로
컴파일되므로 실제 DB와 Django state가 분리되지 않는다.

## 6. 작업 → 검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과·보정 |
| ---: | --- | --- | --- |
| 1 | 계약·현재 App·Migration leaf 감사 | 테이블 사전, Physical Contract, Auditor 비교 | 단일 테이블 Wave로 확정 |
| 2 | App·Model·등록 구현 | `manage.py check`, 문진 집중 테스트 | 합성 User ID가 기존 정규식과 불일치한 테스트 입력을 `DEMO-QUSR-*`·`DEMO-QCUS-*`로 보정 후 8 passed |
| 3 | `0001_initial` 생성 | `makemigrations --check --dry-run`, Migration plan | drift 0, 번호 Migration 인식 |
| 4 | JSON object 물리 CHECK 추가 | 빈 PostgreSQL Migration·catalog·우회 update | PostgreSQL CHECK 이름 확인, JSON 배열 update 거부 |
| 5 | Auditor 기대값 갱신 | 문진+T-005 집중 회귀 | 기존 12/32 고정 assertion을 13/32로 갱신 후 50 passed |
| 6 | 전체 회귀 | Backend·Data 전체 테스트 | Backend 426 passed, Data 67 passed·4 subtests passed |
| 7 | 개발문서·인덱스 갱신 | 상대 링크·절대경로·Git diff 검사 | 이 문서와 README·T-005 현황에 반영 |

Data 전체 테스트의 첫 실행은 샌드박스 임시 폴더에서 2건이
`PermissionError`로 실패했다. 이는 assertion 실패가 아니었다.
쓰기 가능한 격리 임시 폴더에서 같은 전체 범위를 다시 실행해
67개와 subtest 4개가 모두 통과했다.

## 7. 재현 명령

저장소 루트에서 실행한다. 실제 비밀번호나 DSN은 문서에 기록하지
않고 `backend/.env` 또는 CI Secret을 사용한다.

```powershell
Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python manage.py check --settings=config.settings.test
& $python manage.py makemigrations `
    --check --dry-run `
    --settings=config.settings.test
& $python -m pytest `
    .\tests\unit\questionnaires `
    .\tests\unit\database\test_t005_implementation_readiness.py `
    .\tests\unit\database\test_t005_schema_validator.py `
    -q -p no:cacheprovider
```

저장소 루트에서 계약 Validator·Auditor와 전체 회귀를 실행한다.

```powershell
& .\backend\.venv\Scripts\python.exe `
    .\scripts\database\validate_t005_schema.py
& .\backend\.venv\Scripts\python.exe `
    .\scripts\database\audit_t005_implementation_readiness.py `
    --settings config.settings.test

Set-Location .\backend
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

PostgreSQL은 기존 운영·개발 DB와 분리한 새 DB에서 검증한다.
새 DB 이름은 팀원이 충돌하지 않는 값으로 정하고, 그 PowerShell
프로세스에서만 `POSTGRES_DB`를 교체한다.

```powershell
docker compose --env-file .\backend\.env up -d postgres

Set-Location .\backend
$env:POSTGRES_DB = '<new-empty-verification-db>'
$python = '.\.venv\Scripts\python.exe'

& $python ..\scripts\database\check_postgresql_connection.py
& $python manage.py migrate --plan --settings=config.settings.local
& $python manage.py migrate --noinput --settings=config.settings.local
& $python manage.py migrate --check --settings=config.settings.local
```

이번 로컬 실측은 PostgreSQL `16.14`, TimeZone `UTC`에서 수행했다.

## 8. 검증 결과

| 검증 | 결과 |
| --- | --- |
| Django system check | 0 issues |
| Migration drift | `No changes detected` |
| 문진·T-005 집중 회귀 | `50 passed in 12.69s` |
| 문진 Model 자체 테스트 | 8개 통과 |
| T-005 Schema validator | `structure_valid=true`, 활성 계약 일치 |
| T-005 Auditor | 13/32 구현 매핑, 19개 미구현, 전체 `NOT_READY` |
| Backend 전체 | `426 passed in 90.19s` |
| Data 전체 | `67 passed, 4 subtests passed in 12.79s` |
| 빈 PostgreSQL Migration | 전체 적용 성공, 미적용 0 |
| PostgreSQL JSON 우회 저장 | `ck_questionnaire_answers_object` 위반으로 거부 |
| 기존 Seed 1차 | Group 10·Code 43·User 4·Product 1·Subscription 1·Care 3 생성 |
| 기존 Seed 2차 | 신규 0, 기존 항목 update만 수행 |
| Seed 후 문진 행 | 0 |

Auditor의 13/32는 Model 선언·Runtime 등록·번호 Migration 존재를
확인한 결과다. 모든 필드와 제약 parity를 검사하는 도구는 아니므로
아래 알려진 공백을 별도로 유지한다.

## 9. Seed·Fixture·Importer 경계

Wave 1A 실행 당시에는 문진 전용 Fixture와
`QUESTIONNAIRE_TYPE`·`QUESTIONNAIRE_STATUS` 코드 YAML이 없다.
따라서 이번 Wave에서는 다음을 지켰다.

- Wave 1A 변경으로 `data/**`를 수정하지 않았다.
- 기존 367건 importer의 12개 입력 Fixture를 변경하지 않았다.
- Crosswalk와 Manifest를 문진 Model만으로 억지 갱신하지 않았다.
- 문진 코드를 기존 Registry에 임의 추가하지 않았다.
- 테스트 객체는 운영 Seed로 사용하지 않는다.

현재 상태 이력 Fixture 125건의 문진 대상은 0건이다. 향후 문진
Fixture를 추가할 때는 Fixture·Schema·Pipeline count·Manifest·
Consumer profile·Importer·Crosswalk·Ledger 기대값을 김은진의
Data Wave에서 함께 변경해야 한다.

## 10. 알려진 공백과 다음 Wave 후보

| 우선순위 | 공백 | 원인 | 해결 방향 |
| ---: | --- | --- | --- |
| 해결 | 동일 구독 복합 FK | Wave 1A에는 부모 UNIQUE가 없어 DB 우회 가능 | [Wave 1B](<t005_wave_1b_questionnaire_inquiry_composite_fk.md>)에서 부모 UNIQUE → 문진 PostgreSQL 복합 FK 순서로 로컬 구현·검증 |
| P0 | `session_no` 생성 규칙 없음 | API 입력에도 없고 승인 prefix도 없음 | PM·API Owner가 서버 생성 규칙과 DTO 노출을 확정 |
| P0 | Questionnaire API·상태 전이 없음 | 이번 Wave는 Model·Migration 전용 | Service·Repository·Serializer·API를 별도 Wave로 구현 |
| P0 | Inquiry·Workflow UUID Bridge | 기존 Runtime이 공개 UUID만 보유 | 실제 non-null 감사 → Backfill → 내부 FK → Bridge 제거 |
| P1 | 문진 공통코드 계약·Seed 없음 | 코드 YAML과 Group Mapping 미확정 | 계약 확정 후 Registry Seed 추가 |
| P1 | 일부 물리 이름이 설계안과 다름 | Django portable Index 이름 제한과 자동 UNIQUE 이름 | PM이 exact-name 요구를 확정하면 PostgreSQL Forward Migration으로 정렬 |
| P1 | API DTO의 `started_at` nullable 차이 | DB는 NOT NULL | API 명세와 DTO 정합화 |

Wave 1A만 적용한 환경에서는 `clean()`을 거치지 않는 bulk update·raw
SQL이 서로 다른 구독의 Inquiry를 연결할 수 있다. 현재 작업본은
Wave 1B의 복합 FK로 이 위험을 로컬 해결했지만, Wave 1A 자체의 역사적
완료 경계와 문진 API·상태 전이 공백은 그대로 유지한다.

T-005 전체에는 이 테이블 외에도 Accounts 정수 PK 전환, legacy JWT
fallback 제거, 전체 빈 PostgreSQL Migration·Seed 독립 검증과
19개 계약 테이블 구현이 남아 있다.

## 11. 협업 인계

| 담당 | 확인 요청 | 완료 증거 |
| --- | --- | --- |
| 최지용 | Model·Migration·PostgreSQL CHECK·회귀 결과 유지 | 동일 SHA에서 이 문서의 명령 재실행 |
| 김은진 | `data/**` 무변경, 빈 PostgreSQL·Seed 독립 재현 | Migration drift 0, Seed 2회차 신규 0, Data 전체 PASS |
| 윤승혁(PM) | Wave 1B 복합 FK 검토, 문진 번호·상태·공통코드 결정 | PR Review와 결정 등록부 또는 승인 계약 갱신 |
| 양정현 | 후속 고객 앱 DTO에서 public UUID·`session_no` 노출 검토 | API 계약 차이 회신 |
| 한예나 | 후속 Web 문진 흐름에서 상태·멱등키 소비 검토 | API 구현 Wave의 소비 테스트 |

독립 검토와 PM 병합 증거가 없으므로 현재 상태를
`INDEPENDENT_QA_VERIFIED` 또는 `MAIN_MERGED`로 표시하지 않는다.

## 12. Rollback 원칙

- 아직 공유되지 않은 로컬 검증 DB는 명시한 전용 DB만 제거한다.
- 실제 개발 DB에 적용한 뒤에는 기존 번호 Migration을 수정·삭제하지
  않고 새 Forward Migration으로 보정한다.
- `support_questionnaire_session`에 업무 데이터가 생긴 뒤에는
  `migrate questionnaires zero`를 실행하지 않는다.
- JSON object CHECK를 완화하거나 복합 FK를 제거하는 변경은
  Data·PM 검토 없이 수행하지 않는다.
- 기존 `data/**` 미커밋 변경은 이번 Wave 소유가 아니므로 복원·삭제·
  덮어쓰지 않는다.

## 13. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.1 | 2026-07-30 | 동일 구독 복합 FK 공백을 Wave 1B 로컬 해결 상태와 연결하고 독립 QA 경계 유지 |
| v1.0 | 2026-07-30 | Wave 1A Model·App·Migration·PostgreSQL CHECK·Seed·회귀·인계 기록 |
