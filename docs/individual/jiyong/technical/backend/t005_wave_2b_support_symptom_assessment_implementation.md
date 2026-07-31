# T-005 Wave 2B `support_symptom_assessment` 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현 책임: 최지용  
> 현재 상태: `LOCAL_DB_VERIFIED`  
> 구현 범위: 고객지원 묶음 1개 테이블

## 1. 결과 요약

문의별 위험도 판정 이력을 보존하는 `support_symptom_assessment`를
`inquiries` 앱의 Django Runtime Model과 번호 Migration으로 구현했다.
내부 관계에는 `BigAutoField id`, 외부 공개 참조에는 unique UUID
`public_id`를 사용한다.

역사 테이블사전의 13개 논리 필드는 유지하되 최신 계약과 충돌한 식별자
타입, 사용안내 필드 길이·nullable 정책은 Physical Contract v1.2를
우선했다. 공통 감사 규칙에 따라 `updated_at`을 추가하여 실제 Runtime
컬럼은 15개이다.

| 검증 항목 | 결과 |
| --- | --- |
| Django system check | 통과, 0 issues |
| Inquiries Migration drift | 통과, `No changes detected` |
| 신규 집중 테스트 | `19 passed` |
| Inquiry·AIRun 포함 집중 회귀 | `39 passed` |
| 빈 SQLite 전체 Migration | 통과 |
| SQLite `0006 → 0005 → 0006` | 테이블·트리거 제거와 복원 통과 |
| 빈 PostgreSQL 전체 Migration | 통과 |
| PostgreSQL 물리 Catalog | bigint PK/FK, UUID, JSONB, CHECK·UNIQUE·Index·복합 FK 확인 |
| PostgreSQL 위반 쓰기 | 잘못된 복합 관계·부모 변경·위험 코드·JSON 배열 모두 차단 |
| PostgreSQL `0006 → 0005 → 0006` | 테이블·복합 FK 제거와 복원 통과 |
| 임시 검증 DB 정리 | SQLite 파일 제거, PostgreSQL DB 부재 확인 |

이 결과는 `support_symptom_assessment` 한 테이블의 로컬 구현·검증
결과이다. 다른 Inquiry 자식, API, 정식 Importer, Seed, 중앙 readiness는
이번 Wave에서 수정하거나 완료로 선언하지 않았다.

## 2. 기준 문서 적용 우선순위

| 우선 | 기준 | 이번 구현의 적용 내용 |
| ---: | --- | --- |
| 1 | 현재 `Daily_Process/지침서` | 담당 경계, 번호 Migration, 작업 후 즉시 검증, 상대경로 문서화 |
| 2 | [식별자 ADR 0010](<../../../../adr/0010-t005-three-layer-identifier-bridge.md>) | 내부 bigint PK와 공개 UUID 분리, 내부 FK bigint 사용 |
| 3 | [상태이력 ADR 0011](<../../../../adr/0011-t005-status-history-idempotency-scope.md>) | 상태이력 테이블의 책임을 이 판정 이력으로 확장하지 않음 |
| 4 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | `usage_guidance_status varchar(32) NULL`, 최신 식별자 정책 |
| 5 | [테이블사전](<../../../../database/watercare_table_dictionary.md>) | 역사 필드, 버전 UNIQUE, 안전 CHECK, Index, AI 복합 관계 |
| 6 | [위험도 코드](<../../../../../contracts/codes/risk-levels.yaml>)·[사용안내 코드](<../../../../../contracts/codes/usage-guidance-statuses.yaml>) | 승인된 값만 TextChoices와 DB allowed CHECK로 고정 |
| 7 | [우선순위 코드](<../../../../../contracts/codes/priority-levels.yaml>) | 값 목록이 비어 있으므로 허용집합을 임의 확정하지 않음 |

과거 `watercare_schema_v3.json`은 비교 자료로만 사용했다. 최신 ADR,
Physical Contract와 canonical YAML이 충돌할 때 과거 Snapshot 후보를
Runtime 계약으로 승격하지 않았다.

## 3. 계약 충돌과 해소 결과

| 항목 | 역사 테이블사전 | 최신 적용 | 이유 |
| --- | --- | --- | --- |
| 기본 PK | UUID `id` | bigint 자동 증가 `id` | ADR 0010과 Physical v1.2 |
| 공개 식별자 | 별도 필드 없음 | unique UUID `public_id` | 내부 조인과 API 식별자 분리 |
| `inquiry_id` | UUID FK | bigint FK | 부모 `support_inquiry.id`의 현재 Runtime 타입 |
| `ai_run_id` | UUID FK | nullable bigint FK | 부모 `aiops_ai_run.id`의 현재 Runtime 타입 |
| 사용안내 타입 | `varchar(40)` | `varchar(32)` | Physical v1.2 override |
| 사용안내 nullability | NOT NULL | NULL 허용 | Physical v1.2 override |
| 공통 수정시각 | 없음 | `updated_at` | 프로젝트 `TimestampedModel` 공통 규칙 |
| 우선순위 허용값 | LOW/NORMAL/HIGH/URGENT 후보 | open `CharField` | canonical YAML의 `codes`가 비어 있음 |
| 판정주체 허용값 | RULE/AI/CONSULTANT 후보 | open `CharField`, 기본 RULE | 승인된 assessment-origin YAML 부재 |
| 위험 시 URGENT | CHECK 후보 | 이번 Migration에서 제외 | 미승인 우선순위 값을 DB 계약으로 동결하지 않기 위함 |

`priority_code`와 `assessed_by_type_code`는 역사 필드와 기본값을
보존했지만, 임의의 `TextChoices`나 allowed-value CHECK를 추가하지
않았다. 반면 `risk_level_code`와 `usage_guidance_status`는 현재 계약에
승인된 값이 있으므로 Model과 DB 양쪽에서 고정했다.

## 4. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [SymptomAssessment Model](<../../../../../backend/apps/inquiries/models/symptom_assessment.py>) | 필드, 승인 코드, 안전 CHECK, AI 실행 Application Policy |
| [Inquiries Model export](<../../../../../backend/apps/inquiries/models/__init__.py>) | Django Runtime Model registry에 공개 |
| [Inquiries 0006 Migration](<../../../../../backend/apps/inquiries/migrations/0006_symptomassessment.py>) | 테이블과 PostgreSQL·SQLite 복합 무결성 설치 |
| [집중 단위 테스트](<../../../../../backend/tests/unit/inquiries/test_symptom_assessment_model.py>) | 식별자, 코드, 안전 규칙, 버전, FK, DDL, 삭제 보호 검증 |
| [부모 AIRun 구현서](<t005_wave_1c_aiops_ai_run_implementation.md>) | `ai_run_id` 부모 계약과 선행 Migration 인계 |

## 5. Runtime 필드

| 구분 | 필드 | 구현·무결성 |
| --- | --- | --- |
| 내부 식별자 | `id` | `BigAutoField`, PK |
| 공개 식별자 | `public_id` | UUID 자동 생성, UNIQUE, 수정 불가 |
| 대상 문의 | `inquiry_id` | `support_inquiry.id`, bigint, PROTECT |
| 판정 버전 | `assessment_version` | 양의 정수, 문의별 UNIQUE |
| 규칙 재현성 | `ruleset_version` | `varchar(40)`, 필수 |
| 위험도 | `risk_level_code` | general/caution/danger |
| 우선순위 | `priority_code` | 필수 open code, 승인 전 허용집합 미고정 |
| 사용안내 | `usage_guidance_status` | nullable `varchar(32)`, 승인 코드 4종 |
| 상담 전환 | `requires_consultation` | boolean, 기본 false |
| 판정 설명 | `reason` | 필수 text |
| 규칙 결과 | `rule_result` | JSON object, 기본 `{}` |
| 판정 주체 | `assessed_by_type_code` | 필수 open code, 기본 RULE |
| AI 실행 | `ai_run_id` | nullable `aiops_ai_run.id`, bigint, PROTECT |
| 감사 시각 | `created_at`, `updated_at` | 자동 생성·갱신 |

판정 이력은 같은 문의에서 `assessment_version`을 증가시키는
append-only 사용을 전제로 한다. 현재 Model이 일반 `save()` 업데이트를
물리적으로 금지하지는 않으므로 Service 계층은 기존 버전 수정 대신 새
버전을 생성해야 한다.

## 6. 승인 코드와 보류 코드

| 코드 필드 | 기준 상태 | 현재 구현 | 후속 조건 |
| --- | --- | --- | --- |
| `risk_level_code` | YAML과 Physical v1.2에 값 존재 | TextChoices + DB CHECK | 값 변경 시 YAML·Model·Migration·API 동시 변경 |
| `usage_guidance_status` | OWNER_BASELINE v1.0.0 | TextChoices + nullable DB CHECK | legacy `USE_ALLOWED`는 Importer에서 `NORMAL`로 매핑 |
| `priority_code` | YAML `codes: []` | open `CharField` | OWNER가 값·버전 승인 후 새 Migration |
| `assessed_by_type_code` | canonical YAML 부재 | open `CharField`, 기본 RULE | OWNER가 코드 파일을 승인한 후 새 Migration |

승인되지 않은 두 코드의 과거 후보는 데이터 예시일 뿐 현재 허용집합이
아니다. 따라서 아래 제약은 의도적으로 존재하지 않는다.

```text
ck_assessment_danger_priority
ck_support_symptom_assessment_priority_code_allowed
ck_support_symptom_assessment_assessed_by_type_code_allowed
```

## 7. DB 무결성과 Application Policy

| 제약·Index | 방지하거나 지원하는 내용 |
| --- | --- |
| `ux_assessment_version` | 한 문의의 같은 판정 버전 중복 차단 |
| `ck_assessment_version_positive` | 0 이하 버전 차단 |
| `ck_assessment_rule_result_object` | JSON 배열·문자열 등 object 아닌 값 차단 |
| `ck_assessment_ai_origin` | AI 판정인데 AI 실행이 없는 행 차단 |
| `ck_assessment_danger_safety` | danger에서 TOTAL_STOP·상담 전환 누락 차단 |
| `ck_assessment_caution_safety` | caution에서 안전 제한 상태 누락 차단 |
| `ck_assessment_pending_consultation` | 상담 대기인데 상담 전환 false인 행 차단 |
| 위험도 allowed CHECK | 미승인 위험 코드 차단 |
| 사용안내 allowed CHECK | NULL 또는 승인된 네 값만 허용 |
| `ix_assessment_risk` | 위험도·최근 판정 조회 |
| `ix_assessment_ai_run` | AI 실행·문의별 판정 추적 |

PostgreSQL에서는 다음 복합 FK가 `ai_run_id`와 `inquiry_id`의 문맥을
같이 강제한다.

```sql
FOREIGN KEY (ai_run_id, inquiry_id)
REFERENCES aiops_ai_run (id, inquiry_id)
MATCH SIMPLE
ON DELETE RESTRICT
```

SQLite는 기존 테이블에 같은 복합 FK를 사후 추가할 수 없으므로 다음 세
트리거로 동등한 쓰기 경계를 만든다.

```text
fk_assessment_context_child_insert
fk_assessment_context_child_update
fk_assessment_context_parent_update
```

Model `clean()`은 같은 문의인지 확인하는 것에 더해 AI 실행이
`task_type_code=ASSESS_RISK`,
`schema_validation_status_code=PASSED`인지 검증한다. 이 두 값은 다른
행의 속성이라 단순 CHECK로 표현할 수 없으므로 Application Policy로
유지한다. Service·Serializer는 저장 전에 `full_clean()`을 호출해야 한다.

## 8. Migration 순서와 rollback

직접 의존성은 다음과 같다.

```text
inquiries.0005_inquiry_ux_inquiry_id_subscription
audit.0002_airun
  └─ inquiries.0006_symptomassessment
```

`audit.0003_airetrievalrun`과 `inquiries.0006`은 같은 `audit.0002` 이후의
병렬 자식이며 서로 직접 의존하지 않는다.

현재 전체 Migration graph에서 `workflow.0004_align_contract_status_history`
가 `inquiries.0006`을 선행 조건으로 사용한다. 따라서 검증용
`migrate inquiries 0005`는 Django가 `workflow.0004`도 함께 역적용했다.
재적용 검증에서는 반드시 아래 순서를 지켰다.

```text
inquiries.0006 재적용
workflow.0004 재적용
전체 migrate --check
```

운영·공유 DB에서 이 rollback을 단독으로 실행하면 상태이력 Migration도
영향을 받으므로, 데이터 백업과 별도 점검 없이 실행하면 안 된다.

## 9. 작업→검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 지침·ADR·Physical v1.2·테이블사전·YAML 대조 | 필드·관계·승인/보류 코드 분류 | 구현 범위 1개 테이블로 고정 |
| 2 | Model·export 구현 | `manage.py check` | 0 issues |
| 3 | 번호 Migration `inquiries.0006` 작성 | `makemigrations inquiries --check --dry-run` | drift 0 |
| 4 | 식별자·CHECK·UNIQUE·PROTECT·복합 관계 테스트 | 신규 집중 테스트 | `19 passed` |
| 5 | Inquiry·AIRun 회귀 테스트 | 관련 세 파일 실행 | `39 passed` |
| 6 | 격리된 빈 SQLite 전체 Migration | 컬럼·8개 명시 CHECK·2 Index·3 Trigger Catalog 조회 | 통과 |
| 7 | SQLite rollback → reapply | 테이블·Trigger 부재 후 복원 확인 | 통과 |
| 8 | 격리된 빈 PostgreSQL 전체 Migration | bigint/uuid/jsonb·CHECK·UNIQUE·FK·Index Catalog 조회 | 통과 |
| 9 | PostgreSQL 유효 판정 저장 | `full_clean()` 후 INSERT | 통과 |
| 10 | PostgreSQL 위반 쓰기 4종 | 복합 자식 불일치, 부모 변경, UNKNOWN 위험도, JSON 배열 | 모두 `IntegrityError` |
| 11 | PostgreSQL rollback → reapply | `to_regclass`와 복합 FK 재조회 | 통과 |
| 12 | 임시 자원 정리 | SQLite 파일·`pg_database` 재조회 | 모두 부재 |

PostgreSQL 재적용 직후 마지막 호스트 연결 한 번은 Docker 컨테이너가
재시작된 동안 connection timeout이 발생했다. 컨테이너 uptime이
23초인 것을 확인하고 `pg_isready`가 accepting connections를 반환한 뒤
컨테이너 내부 Catalog 조회를 재실행하여 테이블과 복합 FK 복원을
확인했다. Migration·DDL 자체 실패로 판정하지 않았으며 실패를 숨기기
위해 명령의 마지막 exit code만 사용하지 않았다.

## 10. 재현 명령

저장소 루트 기준 SQLite 집중 Gate:

```powershell
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    check --settings=config.settings.test
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    makemigrations inquiries --check --dry-run `
    --settings=config.settings.test
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\inquiries\test_symptom_assessment_model.py `
    backend\tests\unit\audit\test_ai_run_model.py `
    backend\tests\unit\inquiries\test_t022_models.py -q
```

PostgreSQL Gate는 기존 개발 DB가 아닌 새 빈 격리 DB에서 실행한다.
검증 종료 후에는 자신이 만든 정확한 DB 이름만 제거한다.

```powershell
$env:POSTGRES_DB = '<isolated-empty-database>'

& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate --noinput --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate inquiries 0005 --noinput --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate inquiries 0006 --noinput --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate workflow 0004 --noinput --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    migrate --check --settings=config.settings.local
```

## 11. 협업 인계

| 담당 | 인계 내용 |
| --- | --- |
| 최지용 | `inquiries.0006` 번호·직접 의존성, 복합 FK/Trigger 이름, open code 경계를 유지 |
| PM·계약 담당 | priority 값 집합과 assessment-origin YAML의 OWNER 승인 필요 |
| API 담당 | 외부 응답·경로에는 `public_id`, 내부 조인에는 bigint `id` 사용 |
| AI 담당 | AI 판정 저장 전 PASSED 상태의 ASSESS_RISK `AIRun`을 같은 문의로 생성 |
| Service 담당 | 기존 판정 수정 대신 버전 증가 INSERT, 저장 전 `full_clean()` 호출 |
| 데이터·Importer 담당 | `USE_ALLOWED → NORMAL` legacy alias 적용, 미승인 코드 임의 변환 금지 |
| Workflow 담당 | `workflow.0004`의 `inquiries.0006` 의존성을 유지하고 rollback 연쇄를 인지 |
| QA 담당 | PostgreSQL에서 네 위반 쓰기와 rollback 왕복을 독립 재검증 |
| 통합 담당 | 나머지 Inquiry 자식과 Seed가 끝난 뒤 중앙 readiness 기대값을 한 번에 갱신 |

## 12. 잔여 위험과 제외 범위

- priority와 assessment-origin 허용값은 아직 canonical 계약이 아니다.
- append-only는 현재 Service 정책이며 DB가 기존 행 UPDATE 자체를 막지는
  않는다.
- ASSESS_RISK/PASSED 검증은 교차 행 Application Policy이므로 raw SQL
  Importer는 같은 검증을 별도로 수행해야 한다.
- `support_inquiry_symptom`, `support_inquiry_qa`, `support_guidance` 등
  다른 Inquiry 자식은 이번 Wave 범위가 아니다.
- API/Serializer/정식 Importer, 367건 운영 적재와 Seed는 이번 Wave에서
  구현하지 않았다.
- 중앙 T-005 readiness의 고정 테이블 수는 병렬 Wave 종료 후 통합
  검증에서 갱신해야 하며 이번 변경에는 포함하지 않았다.
- 따라서 이 문서는 해당 테이블 단위 구현 완료를 증명하며 T-005 전체
  완료 선언이 아니다.

## 13. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | Model·0006·복합 FK/Trigger·SQLite/PostgreSQL·rollback 검증과 협업 인계 |
