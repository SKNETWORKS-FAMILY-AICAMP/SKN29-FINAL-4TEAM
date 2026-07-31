# T-005 Wave 2E 상태이력 계약 정렬 구현·검증·인계서

> 기준일: 2026-07-30  
> 문서 버전: v1.0  
> WBS: `T-005 데이터베이스 설계 및 구축`  
> 구현·독립 검토 책임: 최지용  
> 현재 상태: `LOCAL_DB_VERIFIED`  
> 기준 계약: T-005 Physical Contract v1.2, ADR 0011

> 후속 정정: 공유 이력 보호를 위해 `workflow.0004`는 원본 불변
> Migration으로 복원했고, 계약 정렬 보강은 새 번호
> `workflow.0005`에 증분 반영했다. 현재 Migration 그래프와 최종
> 검증 결과는
> [T-005 32개 테이블 PostgreSQL·Seed·Importer 최종 검증 보고서](t005_final_32_table_postgresql_seed_importer_validation_report.md)를
> 우선한다. 아래 `0004` 단독 설명은 Wave 2E 당시의 구현·검증
> 이력으로 보존한다.

## 1. 결과 요약

기존 Runtime 테이블 `workflow_transition_history`를 별도 중복 테이블 생성
없이 계약 테이블 `support_inquiry_status_history`로 전환했다. 기존 사전
문진 공개 UUID 브리지는 실제 `support_questionnaire_session` bigint
ForeignKey로 backfill하고, 문의·상담·방문과 함께 정확히 한 대상만
참조하도록 DB 제약을 적용했다.

독립 검토에서 데이터 전환 로직은 정상임을 확인했지만, 기존 Runtime
이름이 남은 CHECK·Index와 역사 계약의 일반 조회 Index 누락을 발견하여
0004 안에서 reversible하게 보강했다.

| 검증 항목 | 최종 결과 |
| --- | --- |
| Django system check | 통과, 0 issues |
| Workflow Migration drift | 통과, `No changes detected` |
| SQLite Wave 2E 집중 테스트 | `7 passed` |
| SQLite Workflow·Audit·API·Importer 회귀 | `103 passed` |
| SQLite 빈 DB 전체 Migration | 통과 |
| SQLite 0004 rollback → reapply | 이전·신규 테이블 및 inbound FK 왕복 통과 |
| PostgreSQL Wave 2E 집중 테스트 | `7 passed` |
| PostgreSQL 367건 전체 Importer | 통과, 상태이력 125건·AuditEvent 125건 |
| PostgreSQL 빈 DB 전체 Migration | 통과 |
| PostgreSQL 0004 rollback → reapply | 테이블·열·CHECK·Index·inbound FK 복원 |
| 기존 이력 보존 회귀 | 125개 이력과 125개 AuditEvent 식별자·버전·멱등키 보존 |

이 결과는 상태이력 테이블 계약 정렬의 완료를 의미한다. 중앙 T-005
readiness 고정 기대값과 다른 미구현 테이블은 이번 Wave에서 수정하지
않았다.

## 2. 기준과 우선순위

| 우선 | 기준 | 적용 내용 |
| ---: | --- | --- |
| 1 | [Physical Contract v1.2](<../../../../database/t-005/t005_physical_contract_v1.2.json>) | bigint 내부 PK/FK, 공개 UUID, 대상 무결성, target별 version·멱등 추적 Index |
| 2 | [ADR 0011](<../../../../adr/0011-t005-status-history-idempotency-scope.md>) | 이력 멱등키는 trace-only, 요청 멱등성은 별도 ledger 책임 |
| 3 | [테이블사전 상태이력](<../../../../database/watercare_table_dictionary.md>) | 열 이름, 대상·변경자·버전 CHECK, 조회 Index, append-only 정책 |
| 4 | [State Machine 이벤트](<../../../../../contracts/state-machine/inquiry-events.yaml>) | 실제 Runtime 이벤트명과 PM 소유 전이 규칙 |
| 5 | 기존 Runtime·Importer·AuditEvent | `status_history_code`, API 동작, 367건 Import 호환 보존 |

역사 테이블사전은 상태·이벤트 허용값이 팀 승인 전인 Design Draft이고,
Physical v1.2도 상태 전이 규칙은 PM 소유 범위로 분리한다. 따라서 최신
State Machine과 충돌할 수 있는 역사 후보값을 DB allowed CHECK로
고정하지 않았다.

## 3. 구현 파일

| 파일 | 역할 |
| --- | --- |
| [TransitionHistory Model](<../../../../../backend/apps/workflow/models/transition_history.py>) | 계약 테이블명·열·FK·CHECK·partial Index |
| [Workflow 0004 Migration](<../../../../../backend/apps/workflow/migrations/0004_align_contract_status_history.py>) | UUID→FK backfill, 제약·Index 정렬, 테이블 rename, reverse |
| [Operations Importer](<../../../../../backend/apps/operations/services/operations_service.py>) | 제거된 UUID 브리지 대신 실제 questionnaire FK 필드 사용 |
| [Wave 2E 집중 테스트](<../../../../../backend/tests/unit/workflow/test_status_history_contract.py>) | 물리 열·제약·partial DDL·125건·AuditEvent·양방향 Migration |
| [전체 Importer 통합 테스트](<../../../../../backend/tests/integration/operations/test_synthetic_handoff_import.py>) | 367건 적재와 상태이력·감사이력 125:125 대응 |
| [AuditEvent Model](<../../../../../backend/apps/audit/models/audit_event.py>) | 상태이력을 가리키는 inbound PROTECT OneToOne FK |

## 4. 테이블 전환 방식

별도의 `support_inquiry_status_history` 테이블을 새로 만든 뒤 복사하는
방식을 사용하지 않았다. 기존 행과 inbound FK를 유지하기 위해 0004가
기존 테이블 자체를 단계적으로 변경하고 마지막에 rename한다.

```text
workflow_transition_history
  ├─ questionnaire_session_id 실제 FK 추가
  ├─ questionnaire_session_public_id → 내부 bigint PK backfill
  ├─ 기존 UUID bridge 제약·필드 제거
  ├─ 계약 열 이름·CHECK·Index 적용
  └─ support_inquiry_status_history 로 rename
```

이 방식은 `id`, `public_id`, `status_history_code`, AuditEvent의
`transition_history_id`를 바꾸지 않는다. PostgreSQL과 SQLite 모두
table rename 시 기존 inbound FK가 새 테이블을 계속 가리키는 것을 직접
검증했다.

## 5. Questionnaire UUID 브리지 backfill

Forward Migration의 backfill은 다음을 선검사한다.

1. QUESTIONNAIRE가 아닌 행에 questionnaire UUID가 들어 있지 않은지
2. 기존 `event_code`가 새 계약 길이 60자를 초과하지 않는지
3. 모든 QUESTIONNAIRE 행에 공개 UUID가 존재하는지
4. 모든 공개 UUID가 unique `QuestionnaireSession.public_id`로
   해석되는지

하나라도 불일치하면 NULL FK로 계속 진행하지 않고 Migration을
`RuntimeError`로 중단한다. 정상 행은 공개 UUID를 내부 bigint PK로
변환하여 `questionnaire_session_id`에 기록한다.

Reverse Migration은 실제 FK가 가리키는 세션의 `public_id`를 다시
`questionnaire_session_public_id`로 복원한 뒤 실제 FK 필드를 제거한다.
집중 테스트에서 다음 왕복을 수행했다.

```text
public UUID bridge
  → questionnaire_session_id bigint FK
  → public UUID bridge
  → questionnaire_session_id bigint FK
```

## 6. Runtime 열과 호환 필드

| 구분 | 물리 열 | 처리 |
| --- | --- | --- |
| 내부 식별자 | `id bigint` | 기존 PK·행 식별자 보존 |
| 공개 식별자 | `public_id uuid` | UNIQUE, 외부 참조 |
| 업무 식별자 | `status_history_code` | 기존 Importer·보고서 호환 보존 |
| 대상 | `questionnaire_session_id`, `inquiry_id`, `consultation_id`, `visit_id` | nullable bigint PROTECT FK |
| 대상 유형 | `target_type_code` | 네 FK 중 실제 대상과 일치 |
| 이벤트 | `event_code varchar(60)` | 최신 State Machine 이벤트를 저장하는 open code |
| 상태 | `from_status_code`, `to_status_code` | 역사 후보값을 동결하지 않은 open code |
| 버전 | `state_version integer` | 1 이상, 대상별 partial UNIQUE |
| 변경자 | `changed_by_id bigint`, `changed_by_type_code` | USER는 사용자 필수, SYSTEM은 NULL |
| 추적 | `correlation_id`, `idempotency_key` | 상관관계·요청 추적 |
| 설명·시각 | `change_reason`, `changed_at` | nullable 사유, 필수 변경시각 |
| Runtime 공통 | `created_at`, `updated_at` | 기존 Django 호환 보존 |

기존 Model 속성 `actor`, `from_state`, `to_state`는 서비스 코드 호환을
위해 유지하되 각각 계약 DB 열 `changed_by_id`, `from_status_code`,
`to_status_code`로 매핑했다.

## 7. 대상과 버전 무결성

### 7.1 정확히 한 대상

`ck_status_history_exactly_one_target`은 네 대상 FK 중 하나만
NOT NULL이 되도록 강제한다.

`ck_status_history_target_type_matches_fk`는 그 FK가
`target_type_code`와 일치하도록 강제한다. 다음 잘못된 INSERT/UPDATE가
SQLite와 PostgreSQL에서 모두 차단됐다.

- 대상 FK가 하나도 없는 행
- QUESTIONNAIRE 행에 questionnaire와 inquiry를 동시에 지정한 행
- QUESTIONNAIRE 유형인데 inquiry FK만 지정한 행

### 7.2 target별 상태 버전

| 대상 | partial UNIQUE |
| --- | --- |
| QUESTIONNAIRE | `(questionnaire_session_id, state_version)` |
| INQUIRY | `(inquiry_id, state_version)` |
| CONSULTATION | `(consultation_id, state_version)` |
| VISIT | `(visit_id, state_version)` |

모든 UNIQUE는 해당 `target_type_code` predicate가 있는 partial
Index로 생성된다. 같은 questionnaire의 동일 version을 두 번 저장한
시도가 실제 DB에서 차단되는 것도 확인했다.

### 7.3 나머지 계약 CHECK

| 계약 CHECK | 내용 |
| --- | --- |
| `ck_status_history_version_positive` | `state_version > 0` |
| `ck_status_history_version_origin` | version 1은 from NULL, 이후 version은 from 필수 |
| `ck_status_history_changed_by` | USER는 changed_by 필수, SYSTEM은 NULL |

## 8. Index와 이름 이식성

Django는 지원 DB 전체를 고려하여 명시적 Index 이름을 30자 이내로
제한한다. Physical v1.2의 긴 논리 이름은 필드·predicate·unique 여부를
유지하고 다음 물리 이름으로 축약했다.

| Physical 논리 Index | Runtime 물리 Index |
| --- | --- |
| `ix_status_history_questionnaire_event_idempotency` | `ix_status_q_event_idem` |
| `ix_status_history_inquiry_event_idempotency` | `ix_status_inq_event_idem` |
| `ix_status_history_consultation_event_idempotency` | `ix_status_cons_event_idem` |
| `ix_status_history_visit_event_idempotency` | `ix_status_visit_event_idem` |

각 Index는 `(target FK, event_code, idempotency_key)`와 해당 target
predicate를 가지며 UNIQUE가 아니다. 요청 replay 차단 책임은
`workflow_idempotency_record(actor, operation_id, idempotency_key)`에
있기 때문이다.

독립 검토에서 추가·정렬한 일반 조회 Index는 다음과 같다.

| Index | 용도 |
| --- | --- |
| `ix_status_hist_target_event` | 대상유형·이벤트·최근 변경순 조회 |
| `ix_status_hist_correlation` | 요청·AI·로그 상관관계 조회 |

## 9. 독립 검토에서 수정한 결함

| 우선 | 발견 내용 | 원인 | 수정 |
| ---: | --- | --- | --- |
| P1 | 역사 계약의 `target_type_code, event_code, changed_at DESC` Index 누락 | 기존 Runtime에는 correlation Index만 존재 | `ix_status_hist_target_event` 추가 |
| P1 | correlation Index가 이전 테이블 계열 이름 `ix_transition_correlation` 유지 | table rename 중심 구현에서 이름 정렬 누락 | reversible `RenameIndex`로 `ix_status_hist_correlation` 정렬 |
| P2 | version positive CHECK가 `ck_transition_*` 이름 유지 | 기존 0001 제약 재사용 | 계약명 `ck_status_history_version_positive`로 교체 |
| P2 | 변경자·version-origin CHECK가 `ck_hist_*` 이름 유지 | 기존 0002 제약 재사용 | 계약명 `ck_status_history_changed_by`, `ck_status_history_version_origin`으로 교체 |
| P1 | 1개 questionnaire만 Migration 회귀 검증 | 대량 보존·inbound FK 증거 부족 | 기존 125행+AuditEvent 125행 양방향 보존 테스트 추가 |
| P1 | partial Index의 이름만 Model metadata에서 검사 | 실제 DB predicate·unique 여부 미검증 | SQLite DDL·PostgreSQL catalog 기반 검증 추가 |

## 10. 기존 125건과 AuditEvent 보존

Migration 회귀 테스트는 0003 상태에서 125개의 기존 상태이력과 각각을
가리키는 125개의 AuditEvent를 생성한 뒤 0004를 적용한다. 다음 값이
forward·reverse·reapply 전 과정에서 동일함을 비교했다.

- 내부 PK
- 공개 UUID
- `status_history_code`
- `state_version`
- `idempotency_key`
- AuditEvent의 `transition_history_id`

별도로 실제 `db-full` Importer를 PostgreSQL에서 실행하여 367개 원천
항목이 적재되고 상태이력 125건과 AuditEvent 125건이 모두 생성되며,
이벤트·version·actor·멱등키·correlation·시각이 1:1 일치함을 확인했다.

## 11. AuditEvent inbound FK

`audit_event.transition_history_id`는 기존부터 상태이력을 가리키는
PROTECT OneToOne FK이다. 0004는 AuditEvent Migration을 다시 만들지
않는다. 테이블 자체 rename을 통해 기존 FK와 125개 연결을 보존한다.

| 단계 | AuditEvent FK 대상 |
| --- | --- |
| workflow 0003 | `workflow_transition_history(id)` |
| workflow 0004 | `support_inquiry_status_history(id)` |
| 0004 rollback | `workflow_transition_history(id)` |
| 0004 reapply | `support_inquiry_status_history(id)` |

SQLite `PRAGMA foreign_key_list`와 PostgreSQL `pg_constraint`에서 위
변화를 직접 확인했고, ORM 삭제 시에도 `ProtectedError`가 발생했다.

## 12. 작업→검증 반복 기록

| 순서 | 작업 | 즉시 검증 | 결과 |
| ---: | --- | --- | --- |
| 1 | 지침서·Physical v1.2·ADR 0011·역사사전 대조 | 필드·우선 계약·호환 범위 표 작성 | target·idempotency 책임 확정 |
| 2 | 기존 Model·0004·Importer 독립 검토 | Migration 순방향·역방향 추적 | UUID backfill·reverse 순서 정상 |
| 3 | CHECK 계약명·일반 Index 보강 | system check·Migration drift | 0 issues, drift 없음 |
| 4 | 대상·version·물리열·partial DDL 테스트 보강 | SQLite 집중 테스트 | `7 passed` |
| 5 | 125 이력·125 AuditEvent 양방향 회귀 | SQLite 0003↔0004 | 모든 식별·연결 보존 |
| 6 | 기존 Workflow·Audit·API·Importer 회귀 | SQLite 관련 묶음 | `103 passed` |
| 7 | 빈 SQLite 전체 Migration | 전체 Migration | 통과 |
| 8 | SQLite 명시적 rollback·reapply | 테이블·Index·inbound FK 조회 | 통과 |
| 9 | 격리 빈 PostgreSQL 전체 Migration | 전체 Migration | 통과 |
| 10 | 동일 집중 테스트 PostgreSQL 실행 | 실제 partial DDL·125행 왕복 | `7 passed` |
| 11 | PostgreSQL 367건 Importer | 상태이력·AuditEvent 125:125 | `1 passed` |
| 12 | PostgreSQL 명시적 rollback·reapply | catalog 열·CHECK·Index·FK | 통과 |

## 13. 재현 명령

저장소 루트 기준 SQLite:

```powershell
& .\backend\.venv\Scripts\python.exe backend\manage.py check
& .\backend\.venv\Scripts\python.exe backend\manage.py `
    makemigrations workflow --check --dry-run
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\workflow\test_status_history_contract.py -q
```

관련 Runtime 회귀:

```powershell
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\workflow `
    backend\tests\unit\audit\test_models.py `
    backend\tests\api\test_t022_create_inquiry.py `
    backend\tests\api\test_t023_cancel_inquiry.py `
    backend\tests\integration\operations\test_synthetic_handoff_import.py `
    -q
```

PostgreSQL은 기존 개발 DB를 삭제하거나 재사용하지 않고 별도의 빈 DB를
지정한다.

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings.base'
$env:POSTGRES_DB = '<isolated-empty-database>'

& .\backend\.venv\Scripts\python.exe backend\manage.py migrate --noinput
& .\backend\.venv\Scripts\python.exe -m pytest `
    backend\tests\unit\workflow\test_status_history_contract.py `
    -q --ds=config.settings.base
```

## 14. 협업 인계

| 담당 | 인계 내용 |
| --- | --- |
| 최지용 | workflow 0004의 reversible 순서와 계약명·축약 Index명 유지 |
| PM·State Machine 담당 | 이벤트·from/to 상태의 최종 허용집합과 전이 그래프 계속 소유 |
| Questionnaire 담당 | 외부에는 세션 `public_id`, 내부 상태이력 FK에는 bigint `id` 사용 |
| API·Workflow 담당 | Aggregate 변경과 상태이력 INSERT를 한 transaction에서 실행 |
| 데이터·Importer 담당 | `questionnaire_session` 실제 FK 필드 사용, 제거된 UUID 브리지에 쓰지 않음 |
| Audit 담당 | `transition_history_id` inbound FK와 1:1 대응 유지 |
| 운영·DBA | 상태이력 INSERT 전용 권한과 UPDATE/DELETE 제한을 운영 권한으로 적용 |
| 통합 담당 | 모든 병렬 Wave 종료 후 중앙 readiness 기대값과 빈 DB 전체 Gate 갱신 |

## 15. 잔여 위험과 제외 범위

- append-only는 Model 이름만으로 강제되지 않는다. 운영 PostgreSQL
  권한에서 UPDATE/DELETE를 제한해야 한다.
- DB partial UNIQUE는 같은 version 중복은 막지만 version의 무간격
  연속성과 PM 전이 그래프 전체를 대신하지 않는다.
- 이벤트·상태 allowed CHECK는 승인되지 않은 역사 후보를 동결하지 않기
  위해 추가하지 않았다. State Machine 승인 변경은 별도 Migration과
  parity test로 반영해야 한다.
- 미해석 questionnaire UUID 또는 60자 초과 기존 이벤트가 있으면
  Migration은 의도적으로 중단한다. 배포 전 preflight 결과를 확인해야
  한다.
- 중앙 T-005 readiness, 다른 미구현 테이블, 운영 DB 권한은 이번 Wave
  범위가 아니다.

## 16. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-30 | 기존 테이블 계약 정렬, UUID→FK backfill, 독립 결함 수정, 125건·AuditEvent·SQLite/PostgreSQL 왕복 검증 |
