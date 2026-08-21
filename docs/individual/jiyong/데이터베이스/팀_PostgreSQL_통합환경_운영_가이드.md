# 팀 PostgreSQL 통합환경 운영 가이드

> 관련 업무: Backend·AI·QA 공용 PostgreSQL·pgvector
> 원칙: 공용환경은 기능 구현 환경과 검증 환경을 구분한다.

## 1. 역할

| 역할 | 허용 범위 |
| --- | --- |
| Migrator | 승인된 Migration·Seed·권한 재조정 |
| Backend Runtime | 업무 테이블의 승인된 DML |
| Readonly QA | 검증용 SELECT |
| AI Readonly | 승인된 RAG View SELECT만 |

Web·Mobile은 DB Credential을 가지지 않고 Backend API만 사용한다.

## 2. 비밀값 주입

Endpoint·DNS·CA·Password·DSN은 Git·문서·채팅에 기록하지 않는다. 승인된
보호 저장소나 Loader가 현재 Process의 환경변수로 주입한다. 결과에는 값이
아니라 주입 여부와 연결 성공 여부만 기록한다.

주요 환경변수 이름은 `backend/.env.example`과 배포 스크립트를 기준으로 한다.

## 3. 구축 순서

1. PM이 환경 용도와 단일 Migrator를 지정
2. 환경 담당자가 PostgreSQL·pgvector·DNS·TLS·Role 준비
3. 최지용이 Migration Plan과 Dry-run 확인
4. Migrator Role로 Migration·Seed·Crosswalk 적용
5. Runtime·Readonly·AI Role 권한 재조정
6. 김은진이 연결·Schema·Replay·권한 Matrix 독립 검증
7. PM이 통합환경 사용 가능 상태 판정

## 4. 검증 항목

| 항목 | 성공 조건 |
| --- | --- |
| TLS | 승인된 Mode·CA·DNS 일치 |
| Migration | 승인 Target pending 0, 예상 외 drift 0, `visits.0005` HOLD |
| Seed | Replay 비의도 생성 0 |
| Backend Role | 승인된 업무 DML 가능 |
| AI Role | RAG View SELECT 가능 |
| AI 제한 | Base Table SELECT·View DML·Schema CREATE 거부 |
| QA Role | 필요한 읽기 검증 가능 |
| 비밀값 | 로그·문서·Git 노출 0 |

## 5. 공용환경에서 금지

- pytest의 Flush·TransactionTestCase 실행
- 개인 개발용 Migration 실험
- `docker compose down -v`, Drop DB, 기존 Volume 삭제
- Runtime Process에 Migrator Credential 상시 주입
- AI Index Builder·UPSERT 명령을 Readonly Role로 실행

## 6. 환경 차단 판정

Connection Timeout, DNS·CA 불일치, Credential 미주입은 코드 실패가 아니라
`ENVIRONMENT_BLOCKED`다. Unit Test PASS로 실제 PostgreSQL Role·View·RAG
검증을 대체하지 않는다.

## 7. 완료 판정

동일 코드 기준에서 Migration·Seed·권한 Matrix·Backend API·AI Readonly 검색이
재현되어야 통합환경 준비 완료다. 전체 서비스 E2E 완료와는 별도다.

## 8. `visits.0005` 제외 Migration Allowlist

`scripts/database/migrate_team_integration_allowlist.py`가 현재 Graph Leaf를
명시적으로 고정한다. 새 Migration이 추가되거나 승인 Target의 의존성에
`visits.0005_replace_visit_result_assignment_fk`가 들어오면 Plan 단계에서 Exit 3으로
중단한다. `--fake`와 `django_migrations` 직접 수정 경로는 제공하지 않는다.

승인 Target과 Graph 기반 실행 순서는 다음과 같다.

| 순서 | App | Target |
| ---: | --- | --- |
| 1 | contenttypes | `0002_remove_content_type_name` |
| 2 | auth | `0012_alter_user_first_name_max_length` |
| 3 | token_blacklist | `0013_alter_blacklistedtoken_options_and_more` |
| 4 | products | `0001_initial` |
| 5 | subscriptions | `0002_add_synthetic_projection_fields` |
| 6 | care | `0002_add_imported_care_fields` |
| 7 | operations | `0002_consultant_dashboard_projection` |
| 8 | accounts | `0005_account_lifecycle_and_audit` |
| 9 | admin | `0003_logentry_add_action_flag_choices` |
| 10 | audit | `0005_airun_analyze_symptom_task` |
| 11 | common_codes | `0002_common_code` |
| 12 | consultations | `0002_consultation_runtime_fields` |
| 13 | evidence | `0011_cast_chunk_embedding_vector_dimensions` |
| 14 | inquiries | `0013_inquiry_priority_code` |
| 15 | questionnaires | `0002_postgresql_inquiry_subscription_fk` |
| 16 | sessions | `0001_initial` |
| 17 | visits | `0004_visit_runtime_fields` |
| 18 | workflow | `0005_status_history_contract_names_indexes` |

### 8.1 Plan-only

Provisioning 완료 뒤 Migrator Loader와 같은 Process에서 실행한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '& {
  . .\scripts\deployment\import_team_integration_env.ps1 -Role Migrator |
    Out-Null
  & .\backend\.venv\Scripts\python.exe -B `
    .\scripts\database\migrate_team_integration_allowlist.py
}'
```

Plan은 실제 DB·User·적용 이력과 전체 의존 Graph를 확인하지만 DB를 변경하지 않는다.
다음 중 하나면 적용 요청을 만들지 않고 `BLOCKED` 결과를 전달한다.

- Graph Leaf 변경 또는 승인 Target 누락
- `visits.0005`가 적용됐거나 Plan 의존성에 포함됨
- 승인 Closure 밖 Migration 적용·계획
- Target까지 가기 위해 Reverse Migration이 필요함
- 대상 DB·Migrator Role·TLS 환경 불일치

### 8.2 승인 후 Apply

PM 승인 SHA의 Clean Worktree에서만 아래 확인값을 함께 제공한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '& {
  $sha = git rev-parse HEAD
  . .\scripts\deployment\import_team_integration_env.ps1 -Role Migrator |
    Out-Null
  & .\backend\.venv\Scripts\python.exe -B `
    .\scripts\database\migrate_team_integration_allowlist.py `
    --apply `
    --confirm-database waterbridge_team_integration `
    --confirm-source-sha $sha `
    --confirm-hold visits.0005=P1_HOLD_EXCLUDED
}'
```

실행기는 PostgreSQL Advisory Lock을 획득하고 Target을 Graph 순서로 적용한다. 적용 후
전체 승인 Closure, 예상 외 Migration 0, 남은 승인 Plan 0과 아래 상태를 재검증한다.

```ini
operations.0002=APPLIED
visits.0004=APPLIED
visits.0005=NOT_APPLIED_P1_HOLD
approved_targets=APPLIED
unexpected_migrations=0
remaining_approved_plan=0
```

검증 성공 뒤 `provision_team_integration.py --apply`를 다시 실행해 신규 Table·View
권한을 정합화한다. Seed·Evidence Import·Crosswalk·Readiness는 별도 승인 단계다.

### 8.3 2026-08-18 작성자 격리 검증

```ini
source_main=d00fca53fa024dd50624a42adb1e78c9582fd0eb
environment=LOCAL_ISOLATED_DOCKER
image=pgvector/pgvector:0.8.6-pg16-bookworm
approved_migration_count=85
remaining_plan_before=85
remaining_plan_after=0
visits.0004=APPLIED
visits.0005=NOT_APPLIED_P1_HOLD
unexpected_migrations=0
allowlist_unit_and_related_tests=48_PASSED
```

금지 Migration을 격리 DB에 의도적으로 적용한 반대 검증에서는 Plan이
`forbidden_migration_already_applied`, Exit 3으로 중단됐다. 검증용 Container와
Volume은 종료 후 삭제했다. 이 결과는 AWS RDS 적용 승인이나 독립 QA가 아니다.

### 8.4 2026-08-19 `operations.0002` Graph 정합화

상담사 Dashboard Projection이 추가된 최신 Graph의 `operations` Leaf는
`0002_consultant_dashboard_projection`이다. Allowlist와 최종 검증 출력도 이 Target을
명시하며 `visits.0005` 제외 경계는 바꾸지 않았다. 작성자 표적 테스트는 13건 모두
통과했다. 공용 PostgreSQL 적용은 PM 승인과 QA 실행 전까지 HOLD다.

## 9. 2026-08-21 Web G4 DB 증거 수집

`collect_web_g4_db_evidence`는 합성 Inquiry 한 건의 Consultation·상태 이력·멱등
원장과 Migration·Schema 상태를 읽기 전용으로 수집한다. 업무 원문·사용자명·전화번호,
Secret·DSN·절대경로는 출력하지 않으며 파일별 SHA-256과 정제 검사도 생성한다.

```powershell
.\backend\.venv\Scripts\python.exe .\backend\manage.py `
  collect_web_g4_db_evidence --inquiry-id <합성 문의 UUID> `
  --run-id <실행 ID> --source-ref <40자리 main SHA> `
  --phase <단계> --output-dir <새 증거 폴더>
```

- 과거 r3는 `r3-final`만 허용하며 Replay 전후·Schema 전후를 소급 주장하지 않는다.
- 신규 r4는 `before-first-write → after-first-write → after-replay → before-conflict →
  after-conflict → compare` 순서로 같은 Inquiry·run_id·source-ref만 허용한다.
- Replay는 같은 Key·같은 Payload의 추가 행 0과 기존 행 Timestamp·내용 Snapshot
  Hash 불변을 판정한다. 409는 오래된 `state_version`의 `STATE-CONFLICT-01`,
  추가 행 0, Snapshot Hash 불변을 판정한다.
- 상태 이력은 event/from/to/state_version과 함께 SYSTEM·USER 및 actor 역할을
  정제된 형태로 기록한다.
- 첫 단계와 409 뒤에 `showmigrations visits`, `migrate --plan`, Schema Fingerprint를
  수집하며 `visits.0005` 적용 또는 예상 밖 Pending·Applied를 차단한다.
- 작성자 검증은 신규·기존 감사·재문의 표적 12건과 관련 회귀 50건 PASS,
  PostgreSQL Row Lock 전용 1건 SKIP이며 Django Check와 Migration Drift도 PASS다.
  이 PC에는 실행 중인 PostgreSQL·Docker가 없어 실제
  보존 Volume 수집은 `ENVIRONMENT_BLOCKED`이고, 해당 환경에서 재실행해야 한다.
