# T-005 Wave 1B 문진·문의 동일 구독 복합 FK 구현·재현 가이드

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 작성·구현 책임: 최지용  
> 협업 검증: 김은진(Data·Migration·Seed 독립 QA), 윤승혁(PM·계약·병합 Gate)  
> 기준 Branch: `jiyong`  
> 작업 전 기준 Commit: `765047c2342bc30363a5c543a1f9ea324730d079`  
> Wave 당시 상태: `LOCAL_VERIFIED` — 복합 UNIQUE·FK 로컬 구현과 PostgreSQL 검증 완료, 독립 QA·PR·`main` 병합 전  
> Wave 당시 T-005 전체 판정: `NOT_READY`

> 역사 스냅샷: 이 문서의 13/32·428 passed 수치는 Wave 1B 직후
> 값이다. 현재 상태는
> [T-005 32개 테이블 최종 검증 보고서](t005_final_32_table_postgresql_seed_importer_validation_report.md)의
> `READY 32/32`, SQLite 740·PostgreSQL 751 결과를 우선한다.

## 1. 결론과 완료 경계

Wave 1A의 `support_questionnaire_session`은 Model 검증에서 문진과 문의의
구독 일치를 확인했지만, `QuerySet.update()`나 raw SQL은
`Model.clean()`을 우회할 수 있었다. 이번 Wave는 이 단일 P0 공백을
다음 두 물리 제약으로 닫았다.

| 위치 | 제약 | 정의 |
| --- | --- | --- |
| 부모 `support_inquiry` | `ux_inquiry_id_subscription` | `UNIQUE (id, subscription_id)` |
| 자식 `support_questionnaire_session` | `fk_questionnaire_inquiry_subscription` | `(inquiry_id, subscription_id) REFERENCES support_inquiry(id, subscription_id) MATCH SIMPLE ON DELETE RESTRICT` |

빈 PostgreSQL 16.14에서 전체 Migration, catalog, 정상 연결과 세 가지
우회 쓰기 차단, 역방향 Migration과 재적용, 기존 Seed 5종 2회,
Backend·Data 전체 회귀를 검증했다. 이번 변경은 새 계약 테이블을
추가하지 않으므로 T-005 매핑은 `13/32`, 미구현 19개로 유지한다.

| 구분 | 이번 Wave 판정 |
| --- | --- |
| 부모 복합 UNIQUE | 구현·PostgreSQL 실측 완료 |
| 자식 복합 FK | 구현·PostgreSQL 실측 완료 |
| ORM·raw SQL 우회 차단 | 실제 제약명까지 확인 |
| 빈 PostgreSQL 전체 Migration | 통과, 미적용 0 |
| 역방향·재적용 | 안전 순서로 통과 |
| Seed 5종 2회 | 2회차 신규 생성 0 |
| Backend 전체 회귀 | `428 passed, 1 skipped` |
| PostgreSQL 전용 통합 테스트 | `1 passed` |
| Data 전체 회귀 | `67 passed` |
| 독립 QA·PR·`main` 병합 | 미완료 |
| T-005 전체 | `NOT_READY` |

## 2. 포함·제외 범위

### 2.1 포함

- Inquiry Model의 부모 복합 UNIQUE 선언
- `inquiries.0005` 번호 Migration
- PostgreSQL 전용 문진 복합 FK와 reverse Migration
- SQLite의 PostgreSQL DDL 미실행 검증
- PostgreSQL catalog와 쓰기 우회 차단 통합 테스트
- Inquiry Model 변경에 따른 Data Crosswalk source hash 동기화
- 공식 Data QA 재생성과 전체 회귀
- 개발문서와 인계 링크 갱신

### 2.2 제외

- Questionnaire Serializer·Repository·Service·API Route
- 문진 생성·임시 저장·제출·문의 연결 상태 전이
- `session_no` 서버 생성 규칙
- `QUESTIONNAIRE_TYPE`, `QUESTIONNAIRE_STATUS` 공통코드·Seed
- 합성 Fixture 367건의 문진 입력 확대
- Importer의 문진 적재 지원
- Accounts 정수 PK 전환과 legacy JWT fallback 제거
- 나머지 19개 계약 테이블

이번 Wave는 제약 보강만 수행했다. API·Fixture·Importer를 함께
변경하면 담당 영역과 검토 단위가 섞이므로 다음 Wave로 넘긴다.

## 3. 기준 문서와 계약 해석

| 우선순위 | 기준 | 적용 |
| ---: | --- | --- |
| 1 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 내부 bigint PK와 공개 UUID 분리 |
| 2 | [T-005 결정 등록부 v0.3](<../../../../database/t-005/t005_decision_register_v0.3.json>) | 활성 결정과 완료 Gate |
| 3 | [T-005 기준 패키지](<../../../../database/t-005/README.md>) | Runtime 완료와 설계 완료 분리 |
| 4 | [WaterCare 테이블 명세](<../../../../database/watercare_table_dictionary.md>) | 복합 UNIQUE·FK 이름, 칼럼 순서, 삭제 정책 |
| 5 | [Wave 1A 구현 가이드](<t005_wave_1a_support_questionnaire_session_implementation.md>) | 선행 Model·Migration과 남은 P0 |

정확한 복합 FK 식은 활성 v1.2 JSON의 식별자 정책을 위반하지 않지만,
직접 출처는 테이블 명세의 `Design Draft`다. 따라서 이번 결과는
`v1.2 식별자 정책 + 테이블 명세의 복합 무결성 정의`를 로컬 구현한
상태이며, 비작성자 검토 전에는 팀 승인 완료로 표시하지 않는다.

## 4. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [Inquiry Model](<../../../../../backend/apps/inquiries/models/inquiry.py>) | 부모 `(id, subscription)` UNIQUE 선언 |
| [Inquiry 0005](<../../../../../backend/apps/inquiries/migrations/0005_inquiry_ux_inquiry_id_subscription.py>) | `ux_inquiry_id_subscription` 생성 |
| [Questionnaire 0001](<../../../../../backend/apps/questionnaires/migrations/0001_initial.py>) | Wave 1A 초기 테이블, `inquiries.0004` 의존 유지 |
| [Questionnaire 0002](<../../../../../backend/apps/questionnaires/migrations/0002_postgresql_inquiry_subscription_fk.py>) | PostgreSQL 복합 FK 생성·역방향 제거 |
| [문진 단위 테스트](<../../../../../backend/tests/unit/questionnaires/test_questionnaire_session_model.py>) | 부모 제약·Migration SQL·SQLite no-op 검증 |
| [PostgreSQL 통합 테스트](<../../../../../backend/tests/integration/questionnaires/test_questionnaire_subscription_fk_postgresql.py>) | 정상 연결·NULL 연결·세 가지 우회 차단 |
| [Backend Crosswalk](<../../../../../data/config/handoff/backend_import_crosswalk.json>) | 변경된 Inquiry Model의 LF canonical SHA-256 |
| [Source hash 갱신 도구](<../../../../../scripts/data/refresh_source_hashes.py>) | Crosswalk 해시 공식 갱신·stale 검사 |

## 5. Migration 설계

### 5.1 적용 순서

```text
inquiries.0004
├─ questionnaires.0001
└─ inquiries.0005
   └─ questionnaires.0002
```

`questionnaires.0001`을 Wave 1B의 `inquiries.0005`에 직접 연결하지
않았다. 초기 테이블의 Wave 경계를 보존하고, 새 복합 FK만
`questionnaires.0001 + inquiries.0005`에 의존한다.

### 5.2 Django 5.2 처리

Django 5.2의 표준 `ForeignKey`와 `OneToOneField`는 단일 칼럼 관계를
표현한다. 기존 ORM `OneToOneField(PROTECT)`는 유지하고, 복합 FK는
PostgreSQL vendor guard가 있는 증분 `RunPython` Migration으로
추가했다. 부모 UNIQUE는 Django `UniqueConstraint`로 Model state와
DB를 함께 관리한다.

SQLite에서는 복합 FK DDL을 실행하지 않는다. SQLite 테스트는 Model
검증과 SQL 형태만 확인하고, 물리 우회 차단 주장은 PostgreSQL
통합 테스트 결과로만 한다.

### 5.3 Rollback 순서

1. `questionnaires.0002`를 `0001`로 되돌려 자식 FK를 제거한다.
2. `inquiries.0005`를 `0004`로 되돌려 부모 UNIQUE를 제거한다.
3. 재적용은 `inquiries.0005` 후 `questionnaires.0002` 순서다.

자식 FK가 남아 있는 상태에서 부모 UNIQUE부터 제거하면 PostgreSQL이
거부하므로 순서를 바꾸지 않는다. 공유된 Migration 파일은 수정하거나
삭제하지 않고 후속 번호 Migration으로 보정한다.

## 6. 작업 → 검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과·보정 |
| ---: | --- | --- | --- |
| 1 | 지침서·테이블 명세·Migration leaf 감사 | 제약명·칼럼 순서·삭제 정책 대조 | 단일 P0 Wave로 범위 고정 |
| 2 | Inquiry 부모 UNIQUE 구현 | `check`, Migration drift, Model Meta 검사 | 정확한 이름·칼럼 순서 확인 |
| 3 | 문진 PostgreSQL 복합 FK 구현 | Migration 의존성·SQL·SQLite no-op | `0001`의 기존 의존을 유지하고 `0002`에만 `0005` 의존 |
| 4 | 확대 집중 회귀 | 문진·문의·T-005·Importer 테스트 | `100 passed` |
| 5 | 빈 PostgreSQL 전체 Migration | plan·apply·`migrate --check`·catalog | 두 제약 적용·validated 확인 |
| 6 | 실제 우회 쓰기 검증 | ORM 자식 변경·raw SQL 구독 변경·부모 구독 변경 | 세 경우 모두 정확한 복합 FK에서 거부 |
| 7 | 역방향·재적용 | `0002 → 0001`, `0005 → 0004`, 정방향 재적용 | 모두 통과, 최종 미적용 0 |
| 8 | Seed 5종 2회 | 생성·갱신·최종 row count | 2회차 신규 0, 문진 0 |
| 9 | Backend 전체 회귀 | SQLite 전체 pytest | `428 passed, 1 skipped` |
| 10 | Data 전체 회귀 1차 | 67개 Data unittest | Inquiry source hash stale 1건과 샌드박스 임시 폴더 권한 2건 발견 |
| 11 | 공식 Crosswalk·QA 갱신 | hash refresh `changed=1`, 결정적 Pipeline QA 2회 | 두 실행 모두 오류·경고·drift 0 |
| 12 | Data 전체 회귀 재실행 | 권한 있는 격리 임시 폴더 | 갱신 직후와 결정적 QA 후 모두 `67 passed` |
| 13 | T-005 Validator·Auditor | 구조·구현 매핑 감사 | 구조 유효, `13/32`, 잔여 19, `NOT_READY` |

Data 1차 실패를 무시하거나 기대값을 완화하지 않았다. Inquiry Model의
의미 변경으로 발생한 source hash 1건은 공식 갱신 도구로 고쳤고,
권한 오류는 같은 테스트를 격리 임시 폴더에서 재실행해 코드 오류와
분리했다.

## 7. PostgreSQL 실측

검증 DB는 기존 DB와 분리한 `watercare_wave1b_20260730`이며 PostgreSQL
16.14, TimeZone UTC에서 실행했다. 비밀번호·DSN은 문서에 기록하지
않는다.

### 7.1 Constraint catalog

| 제약 | 유형 | validated | match | delete | 정의 |
| --- | --- | --- | --- | --- | --- |
| `ux_inquiry_id_subscription` | UNIQUE | `true` | - | - | `UNIQUE (id, subscription_id)` |
| `fk_questionnaire_inquiry_subscription` | FK | `true` | `s` | `r` | 동일 구독 복합 참조, `ON DELETE RESTRICT` |

PostgreSQL 내부 코드 `s`는 `MATCH SIMPLE`, `r`은 `RESTRICT`다.

### 7.2 쓰기 행위

| Case | 경로 | 결과 |
| --- | --- | --- |
| 같은 구독 Inquiry 연결 | 정상 ORM create | 성공 |
| Inquiry 없는 문진 | 정상 ORM create | 성공, `MATCH SIMPLE` |
| 다른 구독 Inquiry로 교체 | `QuerySet.update(inquiry_id=...)` | `IntegrityError` |
| 연결 후 문진 구독 변경 | raw SQL `UPDATE subscription_id` | `IntegrityError` |
| 연결된 Inquiry 구독 변경 | 부모 `QuerySet.update()` | `IntegrityError` |
| 실패 후 원본 | `refresh_from_db()` | 기존 관계 유지 |

세 실패의 PostgreSQL `diag.constraint_name`은 모두
`fk_questionnaire_inquiry_subscription`이었다. 다른 CHECK나 단일 FK가
아니라 이번 복합 FK가 차단했음을 확인했다.

## 8. Seed·Data 경계와 연쇄 오류 보정

기존 Seed 5종을 같은 격리 DB에서 두 번 실행했다.

| 대상 | 최종 건수 | 2회차 신규 |
| --- | ---: | ---: |
| CommonCodeGroup | 10 | 0 |
| CommonCode | 43 | 0 |
| User | 4 | 0 |
| ProductModel | 1 | 0 |
| CustomerSubscription | 1 | 0 |
| CareRecord | 3 | 0 |
| QuestionnaireSession | 0 | 0 |

이번 Wave는 Fixture·Schema·레코드·Importer 로직을 변경하지 않았다.
다만 부모 UNIQUE를 Model에 선언하면서 Inquiry source hash가 바뀌어
Crosswalk가 stale이 됐다. 다음 공식 순서로 한 항목만 갱신했다.

```powershell
.\backend\.venv\Scripts\python.exe -B `
  .\scripts\data\refresh_source_hashes.py --check
.\backend\.venv\Scripts\python.exe -B `
  .\scripts\data\refresh_source_hashes.py
.\backend\.venv\Scripts\python.exe -B `
  .\data\tools\pipeline.py qa --verify-rebuild
.\backend\.venv\Scripts\python.exe -B `
  .\data\tools\pipeline.py qa --verify-rebuild
```

갱신 결과는 `inquiry_model`의 LF canonical SHA-256 한 건이며, 현재
Pipeline QA는 두 차례 모두 오류 0·경고 0·변경 파일 0·canonical
drift 0·48파일·740레코드다. 기존 팀원의
`data/**` 작업을 복원하거나 삭제하지 않았고, 생성 보고서는 현재
설정과 Crosswalk로 공식 재생성했다.

## 9. 재현 명령

저장소 루트에서 실행한다.

```powershell
Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python manage.py check --settings=config.settings.test
& $python manage.py makemigrations `
  --check --dry-run `
  --settings=config.settings.test
& $python -m pytest `
  .\tests\unit\questionnaires `
  .\tests\unit\inquiries `
  .\tests\unit\database\test_t005_implementation_readiness.py `
  .\tests\unit\database\test_t005_schema_validator.py `
  .\tests\integration\operations\test_synthetic_handoff_import.py `
  -q -p no:cacheprovider
```

PostgreSQL 전용 통합 테스트는 다른 팀 작업과 충돌하지 않는 DB 이름을
사용한다. pytest가 생성하는 test DB에는 운영 데이터를 넣지 않는다.

```powershell
$env:POSTGRES_DB = '<isolated-postgresql-test-db>'
& $python -m pytest `
  .\tests\integration\questionnaires\test_questionnaire_subscription_fk_postgresql.py `
  --ds=config.settings.local `
  --create-db `
  -q -p no:cacheprovider
```

전체 회귀와 T-005 감사는 저장소 루트에서 실행한다.

```powershell
& .\backend\.venv\Scripts\python.exe -m pytest `
  -q -p no:cacheprovider
& .\backend\.venv\Scripts\python.exe -B -m unittest `
  discover -s .\data\tools\tests -v
& .\backend\.venv\Scripts\python.exe `
  .\scripts\database\validate_t005_schema.py `
  --verify-postgresql
& .\backend\.venv\Scripts\python.exe `
  .\scripts\database\audit_t005_implementation_readiness.py `
  --settings config.settings.test
```

## 10. 최종 검증 결과

| 검증 | 결과 |
| --- | --- |
| Django system check | 0 issues |
| Migration drift | `No changes detected` |
| 확대 집중 회귀 | `100 passed` |
| SQLite의 PostgreSQL DDL | 미실행 확인 |
| 빈 PostgreSQL Migration | 전체 적용, 미적용 0 |
| Constraint catalog | 두 제약 존재·validated |
| PostgreSQL 우회 차단 | 3종 모두 정확한 복합 FK 위반 |
| PostgreSQL 전용 pytest | `1 passed` |
| 역방향·재적용 | 통과 |
| Seed 2회 | 2회차 신규 0 |
| Backend 전체 | `428 passed, 1 skipped` |
| Data Pipeline QA | 결정적 재생성 2회 PASS, 오류·경고·drift 0 |
| Data 전체 | `67 passed` |
| T-005 Schema validator | 구조·활성 계약 일치, PostgreSQL 연결·drift·Migration PASS |
| T-005 Auditor | `13/32`, 미구현 19, `NOT_READY` |

SQLite 전체 회귀의 1개 skip은 PostgreSQL 전용 통합 테스트다. 동일
테스트는 PostgreSQL 설정에서 별도로 1개 통과했다.

Validator의 실제 PostgreSQL 모드에서는
`django_model_migration_parity_verified=true`와
`postgresql_migration_verified=true`를 확인했다. 그러나 별도 completion
evidence와 비작성자 검토를 입력하지 않았으므로
`seed_idempotency_verified_on_postgresql=false`,
`non_author_review_confirmed=false`가 유지된다. 로컬 Seed 실측을
WBS 전체 완료 증거로 과대 해석하지 않는다.

## 11. 남은 공백

| 우선순위 | 공백 | 이유 | 다음 방향 |
| ---: | --- | --- | --- |
| P0 | `session_no` 생성 규칙 | 승인된 prefix·동시성 규칙 없음 | PM·API 계약 확정 후 서버 생성 |
| P0 | Questionnaire API·상태 전이 | 이번 Wave는 DB 제약 전용 | Service·Repository·Serializer·Route를 별도 Wave로 구현 |
| P0 | Inquiry·Workflow UUID Bridge | 기존 Runtime 전환 단계 | non-null 감사·Backfill·내부 FK·fallback 제거 |
| P1 | 문진 공통코드·Seed | 코드 Group Mapping 미확정 | 계약 확정 후 Registry·Seed 동시 갱신 |
| P1 | 문진 Fixture·Importer | 현재 상태 이력의 문진 대상 0 | 김은진 Data Wave에서 Schema·Manifest·Importer 함께 변경 |
| P1 | 19개 계약 테이블 | Model·Runtime·번호 Migration 없음 | 의존 순서에 따라 작은 Wave로 구현 |

복합 FK P0는 로컬에서 해결됐지만, 위 항목과 Accounts 정수 PK 전환,
legacy JWT fallback 제거, 비작성자 독립 PostgreSQL·Seed 재현이
남아 있으므로 T-005 완료를 선언하지 않는다.

## 12. 협업 인계

| 담당 | 확인 요청 | 완료 증거 |
| --- | --- | --- |
| 최지용 | Model·Migration·테스트·문서 유지 | 같은 SHA에서 본 문서 명령 재실행 |
| 김은진 | 빈 PostgreSQL Migration·Seed 2회·Data QA 독립 재현 | catalog·제약명·Seed 신규 0·Data PASS 회신 |
| 윤승혁(PM) | Design Draft 복합 제약과 후속 API·번호 정책 확인 | 계약 또는 PR Review·병합 증거 |
| 한예나 | 후속 Web 문진 흐름의 상태·멱등 소비 검토 | API Wave 소비 테스트 |
| 양정현 | 후속 Mobile DTO의 public UUID·`session_no` 검토 | API 계약 차이 회신 |

현재는 자기 검증 증거만 있으므로 `TEAM_REVIEWED`,
`INDEPENDENT_QA_VERIFIED`, `MAIN_MERGED`로 표시하지 않는다.

## 13. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | 부모 복합 UNIQUE·문진 복합 FK, PostgreSQL 우회·rollback·Seed·Data hash 연쇄 보정·전체 회귀·인계 기록 |
