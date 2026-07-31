# T-005 Wave 2D `support_handoff_report` 구현·검증 인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_VERIFIED`  
> 구현 단위: Wave 2D, 부모 테이블 1개

## 1. 결과

상담 결과를 방문기사에게 전달하는 버전형 리포트
`support_handoff_report`를 Django Runtime Model과 번호 Migration으로
구현했다. AI 초안, 상담사 편집본, 제품·증상·조치·위험·근거 요약,
우선 점검 항목과 확정 메타데이터를 문의·상담·AI 실행 문맥 안에
보존한다.

| 검증 항목 | 결과 |
| --- | --- |
| Django system check | 통과, 0 issues |
| Visits migration drift | 통과, `No changes detected` |
| 신규 집중 테스트 | 통과, `15 passed` |
| Visits 전체 단위 테스트 | 통과, `26 passed`, PostgreSQL 전용 2건 skipped |
| Audit·Visits 최종 회귀 | 통과, `73 passed`, PostgreSQL 전용 2건 skipped |
| SQLite Migration 왕복 | 적용 → 롤백 → 재적용 통과 |
| PostgreSQL 빈 DB Migration 왕복 | 정상 모드 적용 → 롤백 → 재적용 통과 |
| PostgreSQL 무결성 실측 | Consultation·AIRun 문의 불일치와 불완전 확정 차단 |
| PostgreSQL 재적용 카탈로그 | CHECK 5개, FK 5개, 문맥 Trigger 2개 |
| 임시 검증 DB 정리 | `ABSENT` 확인 |
| Visit Bridge | 의도적으로 미적용, backfill 원본 부재 |
| T-005 전체 완료 선언 | 하지 않음. 이 문서는 Wave 2D만 판정 |

## 2. 구현 위치 판단

테이블의 업무 도메인은 고객 지원이지만, 현재 저장소에는
`apps/visits/models/technician_report.py`가 “AI 초안·기사용 사전
리포트 Model” 자리로 이미 예약되어 있다. 반면
`apps/consultations/models/consultation_summary.py`는 상담 요약용
자리다. 리포트를 소비하는 Visit와 후속 기사 화면의 응집도를 고려해
visits 앱의 기존 예약 파일을 사용했다.

| 후보 | 판단 | 이유 |
| --- | --- | --- |
| `apps/visits/models/technician_report.py` | 채택 | 기존 예약 목적이 기사 전달용 리포트와 일치 |
| `apps/consultations/models/consultation_summary.py` | 미채택 | 상담 자체의 요약 Model을 위한 별도 자리 |
| 신규 app | 미채택 | 테이블 1개 때문에 앱 경계를 추가할 근거 없음 |

## 3. 기준 문서와 결정

| 우선순위 | 기준 | 이번 Wave 적용 |
| ---: | --- | --- |
| 1 | 현재 `Daily_Process/지침서` | 작업·검증 반복, 번호 Migration, 빈 PostgreSQL·rollback 실측 |
| 2 | [ADR 0010](<../../../../adr/0010-t005-three-layer-identifier-bridge.md>) | 내부 bigint PK + 공개 UUID + 내부 bigint FK |
| 3 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | 신규 주요 테이블 식별자 정책과 코드 원본 정책 |
| 4 | [공개 테이블 사전](<../../../../database/watercare_table_dictionary.md#16-support_handoff_report--방문기사-인계-리포트>) | 필드·관계·버전·확정·JSON 설계 |
| 5 | [과거 Schema v3](<../../../../database/t-005/watercare_schema_v3.json>) | 역사 필드 비교와 bridge 후보 확인 |

### 3.1 식별자 전환

과거 Schema v3의 UUID PK를 그대로 복제하지 않았다. ADR 0010에 따라
내부 PK는 `BigAutoField id`, 외부 공개 식별자는 UNIQUE
`UUIDField public_id`로 분리했다. Inquiry, Consultation, AIRun,
확정자는 모두 현재 Runtime의 bigint PK를 내부 FK로 사용한다.

### 3.2 미승인 상태 코드 처리

테이블 사전에는 `DRAFT`, `CONFIRMED`, `SUPERSEDED`가 설계 제안으로
기록되어 있지만 동시에 팀 결정 필요로 표시되어 있다. Physical
Contract v1.2는 교차 서비스 코드의 원본을 `contracts/codes/*.yaml`로
정했으며, 현재 `HANDOFF_STATUS` 계약은 없다.

따라서 이번 Wave에서는 다음을 임의 확정하지 않았다.

- Django `TextChoices`
- 허용값 목록 CHECK
- `'DRAFT'` 기본값
- `CONFIRMED -> SUPERSEDED` 상태 전이

`report_status_code`는 비어 있지 않은 필수 문자열로만 저장한다. 코드
계약이 승인되면 YAML·TextChoices·DB CHECK·Seed·전이 테스트를 같은
변경 단위로 추가해야 한다.

### 3.3 확정 제약의 현재 범위

상태 값과 결합하지 않고 확정 메타데이터의 구조만 강제한다.

```text
(confirmed_by_id IS NULL AND confirmed_at IS NULL)
OR
(confirmed_by_id IS NOT NULL
 AND confirmed_at IS NOT NULL
 AND consultant_final IS NOT NULL)
```

확정자는 Model validation에서 `CONSULTANT` 역할만 허용한다. “완료된
상담만 확정”, “실제 담당 상담사만 확정”, “확정본에서만 폐기본으로
전환”은 PM 상태 규칙과 승인된 상태 코드가 필요한 Application
Policy이므로 이번 DB Wave에서 임의 구현하지 않았다.

## 4. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [HandoffReport Model](<../../../../../backend/apps/visits/models/technician_report.py>) | 필드·관계·CHECK·Index·portable validation |
| [Visits Model export](<../../../../../backend/apps/visits/models/__init__.py>) | Runtime registry에 `HandoffReport` 공개 |
| [Visits 0003 Migration](<../../../../../backend/apps/visits/migrations/0003_handoffreport.py>) | 테이블, 양 DB 문의 문맥 무결성과 rollback |
| [집중 테스트](<../../../../../backend/tests/unit/visits/test_handoff_report.py>) | 식별자·버전·JSON·확정·문맥·삭제 보호·Migration SQL 검증 |

Migration 순서는 다음과 같다.

```text
visits.0001_initial
  -> visits.0002_visitresult
  -> visits.0003_handoffreport
```

`visits.0003`은 `audit.0003`, `consultations.0001`,
`inquiries.0006`과 현재 User Model에도 의존한다.

## 5. 필드 구현

| 구분 | 필드 | 구현·제약 |
| --- | --- | --- |
| 식별자 | `id` | `BigAutoField`, 내부 PK |
| 식별자 | `public_id` | UUID 자동 생성, UNIQUE, 외부 공개용 |
| 문의 문맥 | `inquiry_id` | `support_inquiry.id`, `PROTECT` |
| 상담 문맥 | `consultation_id` | `support_consultation.id`, `PROTECT` |
| 버전 | `report_version` | 기본 1, 문의 안에서 UNIQUE, 0 초과 |
| 상태 | `report_status_code` | 필수 열린 문자열, 빈 값 차단 |
| 요약 | `product_summary` | 제품·설치·구독·케어 요약 |
| 요약 | `symptom_summary` | 원문·구조화 증상 요약 |
| 요약 | `action_summary` | 자가조치·상담 처리 결과 |
| 요약 | `risk_summary` | 위험·사용 제한·안전 주의 |
| 요약 | `evidence_summary` | 공식 근거 요약, NULL 가능 |
| 현장 점검 | `priority_check_items` | JSON array, 기본 빈 배열 |
| AI | `ai_draft` | AI 초안, NULL 가능 |
| 상담사 | `consultant_final` | 상담사 편집·확정본, NULL 가능 |
| AI 추적 | `generated_by_ai_run_id` | `aiops_ai_run.id`, NULL 가능, `PROTECT` |
| 확정 | `confirmed_by_id` | `accounts_user.id`, NULL 가능, `PROTECT` |
| 확정 | `confirmed_at` | 확정 시각, NULL 가능 |
| 감사 | `created_at` | 공통 `TimestampedModel` |
| 감사 | `updated_at` | 공통 `TimestampedModel` |

## 6. 무결성 구현

| 제약·보호 | 차단하는 문제 |
| --- | --- |
| `ux_handoff_report_version` | 같은 문의의 같은 리포트 버전 중복 |
| `ux_handoff_id_inquiry` | 후속 Visit·Evidence 복합 참조 후보 누락 |
| `ck_handoff_report_version` | 0 이하 버전 |
| `ck_handoff_status_nonempty` | 빈 상태 코드 |
| `ck_handoff_report_confirmation` | 확정자·확정시각 일부만 있거나 최종본 없는 확정 |
| `ck_handoff_priority_items_array` | object·문자열 형태의 우선 점검 항목 |
| `fk_handoff_ai_run_inquiry` | 다른 문의의 AIRun 초안 연결 |
| Consultation context trigger | 다른 문의의 상담 연결과 부모 문의 변경 |
| 4개 기본 FK | 존재하지 않는 Inquiry·Consultation·AIRun·User와 부모 삭제 |

PostgreSQL에서는 AIRun이 이미 `(id, inquiry_id)` UNIQUE를 제공하므로
실제 복합 FK를 사용한다. 현재 Consultation Runtime에는
`(id, inquiry_id)` UNIQUE가 없고, 이번 작업은 다른 앱 변경을 금지한
단일 Wave다. 따라서 Consultation은 기본 FK와 자식·부모 Trigger로
같은 문의를 DB에서 강제했다.

SQLite는 테이블 생성 후 복합 FK를 추가할 수 없어 Consultation 문맥
3개, AIRun 문맥 3개 등 총 6개 Trigger로 같은 규칙을 강제한다.

후속 Consultation 정합화 Wave에서 `ux_consultation_id_inquiry`를
Runtime Model과 Migration에 추가하면, PostgreSQL의 Consultation
Trigger를 실제 복합 FK로 교체할 수 있다. 이 전환은 별도 Migration과
rollback으로 수행해야 하며 현재 Trigger를 조용히 삭제하면 안 된다.

## 7. Visit Bridge를 보류한 이유

계약상 `field_service_visit.handoff_report_id`는 비NULL이고 같은 문의의
확정 리포트만 가리켜야 한다. 그러나 현재 Visit Model, 367건 합성
handoff importer, visits fixture와 Crosswalk에는 리포트 식별자 또는
생성 가능한 원본 데이터가 없다.

| 검토 항목 | 확인 결과 | 판단 |
| --- | --- | --- |
| 현재 `Visit` Model | `handoff_report` 필드 없음 | 기존 Runtime은 bridge 전 상태 |
| Visit importer | visit code·inquiry·technician·상태 중심 | 리포트 backfill 원본 없음 |
| Visit fixture·Crosswalk | handoff report key 없음 | 결정적 매핑 불가 |
| 계약 필드 | 비NULL FK | nullable 임시 필드를 임의 추가하면 계약 이중화 |
| 기존 데이터 | Visit가 이미 존재할 수 있음 | 단일 AddField로는 안전한 backfill 불가 |

따라서 이번 Wave는 부모 리포트 테이블까지만 구현했다. Bridge 전환에는
다음 승인 자료가 먼저 필요하다.

1. 기존 Visit별로 어떤 Consultation 버전에서 리포트를 생성할지 정한
   backfill source
2. report version과 status 생성 규칙
3. AI 초안이 없는 기존 Visit의 수동 생성 정책
4. 확정 담당 상담사와 확정 시각의 증거
5. backfill 후 `handoff_report_id NOT NULL`과 동일 inquiry 복합 FK를
   적용하는 단계형 Migration

## 8. 작업·검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | Wave 2A 교정 후 공유 트리 재확인 | system check·Audit drift·47 tests | 모두 통과 |
| 2 | visits·consultations placeholder와 관계 조사 | 테이블 사전·Physical·Runtime 비교 | visits app으로 위치 확정 |
| 3 | 상태 코드 원본 조사 | `contracts/codes`와 Physical 정책 비교 | 미승인 상태를 열린 문자열로 보존 |
| 4 | Visit importer·fixture 조사 | handoff key 검색 | backfill 원본 없음 확인 |
| 5 | Model·export 작성 | system check | 0 issues |
| 6 | `visits.0003` 작성 | migration drift | 0 |
| 7 | 집중 테스트 작성 | 신규 테스트 | 15 passed |
| 8 | SQLite 적용 | 테이블·Trigger 조회 | 테이블 1, Trigger 6 |
| 9 | SQLite 롤백 | 재조회 | 테이블·Trigger 0 |
| 10 | SQLite 재적용 | 재조회 | 테이블 1, Trigger 6 복원 |
| 11 | 빈 PostgreSQL 정상 적용 | Catalog·실제 INSERT/UPDATE | DDL과 차단 동작 확인 |
| 12 | PostgreSQL 롤백 | table·function·trigger 조회 | 모두 제거 |
| 13 | PostgreSQL 재적용 | 제약·Trigger 재조회 | CHECK 5, FK 5, Trigger 2 |
| 14 | Visits 회귀 테스트 | `tests/unit/visits` | 26 passed, 2 skipped |
| 15 | 임시 DB 정리 | `pg_database` 재조회 | ABSENT |
| 16 | Audit·Visits 최종 회귀 | 양 Wave 관련 단위 테스트 | 73 passed, 2 skipped |

PostgreSQL 검증용 DB는
`watercare_t005_wave2d_verify_20260730_01`로만 생성했고 검증 직후
삭제했다. 기본 `watercare` 데이터베이스는 수정하지 않았다.

## 9. 재현 명령

저장소 루트에서 실행한다.

```powershell
Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python manage.py check --settings=config.settings.test
& $python manage.py makemigrations visits `
    --check --dry-run `
    --settings=config.settings.test
& $python -m pytest `
    .\tests\unit\visits\test_handoff_report.py `
    -q
& $python -m pytest `
    .\tests\unit\visits `
    -q
```

빈 PostgreSQL에서는 대상 DB를 명시적으로 분리한 뒤 다음 순서를
재현한다.

```powershell
& $python manage.py showmigrations visits `
    --plan `
    --settings=config.settings.local
& $python manage.py migrate visits 0003 `
    --settings=config.settings.local
& $python manage.py migrate visits 0002 `
    --settings=config.settings.local
& $python manage.py migrate visits 0003 `
    --settings=config.settings.local
```

## 10. 협업 인계

| 담당 | 인계 내용 |
| --- | --- |
| 최지용 | `visits.0003` 의존성·rollback, 공개 UUID와 문의 문맥 제약 유지 |
| 윤승혁(PM) | Handoff 상태 값·전이, 완료 상담·담당 상담사 확정 정책 승인 |
| 이동윤 | `DRAFT_HANDOFF` 출력과 `ai_draft`, AIRun·문의 문맥 일치 확인 |
| 김은진 | 빈 PostgreSQL 왕복, 향후 Visit backfill 원본·재현 결과 검수 |
| API 담당 | 외부 식별자는 `public_id`, 내부 조인은 bigint PK 사용 |
| 기사 화면 담당 | Visit Bridge 전에는 HandoffReport를 Visit의 확정 필드로 가정하지 않음 |

## 11. 다음 작업 조건

이 Wave 다음에 바로 Visit FK를 추가해서는 안 된다. 먼저 승인된
Handoff 상태 코드 계약과 기존 Visit backfill source를 확보해야 한다.
조건이 충족되면 다음 묶음에서 아래를 함께 처리한다.

1. Handoff 상태 TextChoices·허용 CHECK·전이 Service
2. 완료 Consultation·실제 담당 상담사 확정 정책
3. 기존 Visit용 HandoffReport 생성 backfill
4. nullable bridge 생성 → backfill 검증 → NOT NULL 전환
5. `(handoff_report_id, inquiry_id)` 복합 FK
6. importer·fixture·Crosswalk·Data QA 동시 갱신

## 12. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | HandoffReport Model·Migration·양 DB 왕복·무결성 실측·Visit Bridge 보류 근거·협업 인계 작성 |
