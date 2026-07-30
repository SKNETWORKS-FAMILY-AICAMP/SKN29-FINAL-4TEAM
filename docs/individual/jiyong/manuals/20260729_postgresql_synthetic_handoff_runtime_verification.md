# PostgreSQL 합성 Handoff Runtime 검증·인계서

- 검증일: 2026-07-29
- 검증 상태: `DB_FULL_VERIFIED` — 빈 격리 DB 합성 Handoff 범위
- 데이터셋 버전: `0.9.0`
- Backend 매핑 버전: `2.0.0`
- DBMS: PostgreSQL 16.14
- 검증 대상: 합성 fixture 12종, source 367행
- 제외 범위: 실제 고객·운영 데이터, T-005 계약 32테이블 전체 구현

## 1. 최종 판정

정식 Django 관리 명령으로 `db-smoke` 37행과 `db-full` 367행을 각각
`dry-run → 1차 실제 적재 → 동일 입력 재실행` 순서로 검증했다.
두 프로필 모두 dry-run 쓰기 0건, 재실행 생성 0건·수정 0건을
확인했다. Full 적재에서는 문의 22건과 방문 4건의 최종 상태·버전이
최신 이력과 모두 일치했고, 감사 이벤트와 전이 이력 125쌍도
불일치가 없었다.

검증은 다음 두 격리 DB에서만 수행했다.

이 문서의 1~9장은 아래 격리 DB 검증 당시의 증거를 그대로 보존한다.
그 뒤 기본 `watercare`에 적용한 Migration·Demo Seed 실측은 기존
격리 검증을 덮어쓰지 않고 10장에 별도로 누적한다.

| 프로필 | 격리 DB | 기존 `watercare` DB 사용 |
|---|---|---|
| `db-smoke` | `watercare_synthetic_smoke_verify_20260729_mainv2` | 사용하지 않음 |
| `db-full` | `watercare_synthetic_full_verify_20260729_mainv2` | 사용하지 않음 |

이 격리 검증 당시에는 기존 `watercare` DB에 Migration·import·인증
검증 명령을 실행하지 않았다. 검증 명령의 `POSTGRES_DB`는 매 단계 위
격리 DB 중 하나로 명시했다. 그 시점의 기존 DB에는 존재 여부를 확인하는
읽기 전용 catalog 조회 외의 쓰기를 수행하지 않았다. 이후 기본 DB
Migration·Seed 검증은 10장의 별도 후속 작업이다.

## 2. 근거의 단일 원본

| 근거 | 용도 |
|---|---|
| [Backend Import Crosswalk](../../../../data/config/handoff/backend_import_crosswalk.json) | 매핑 12종, PostgreSQL 실제 결과, 검증 시각과 `DB_FULL_VERIFIED` 상태 |
| [Care 결과 코드 계약](../../../../contracts/codes/care-results.yaml) | Full 적재 결과값 `NORMAL`·`FILTER_REPLACED`·`ISSUE_RESOLVED`의 단일 원본 |
| [Consumer Handoff Manifest](../../../../data/processed/metadata/consumer_handoff_manifest.json) | `db-smoke`·`db-full` 소비 파일, 역할, 해시, readiness |
| [Final Dataset Manifest](../../../../data/processed/metadata/final_dataset_manifest.json) | 154개 데이터·메타데이터·스키마·도구·설정·검증·정책 항목의 최종 PASS |
| [정식 Import Service](../../../../backend/apps/operations/services/operations_service.py) | closure 선택, 적재 순서, 트랜잭션, 사후 검증 |
| [정식 Import Command](../../../../backend/apps/operations/management/commands/import_synthetic_handoff.py) | `smoke`, `full`, `--dry-run` CLI |
| [Import Ledger Model](../../../../backend/apps/operations/models/synthetic_import_ledger.py) | 배치·source 행별 provenance와 합계 제약 |
| [Importer 통합 테스트](../../../../backend/tests/integration/operations/test_synthetic_handoff_import.py) | dry-run, 반복 안전성, 전수 적재, 충돌 롤백 |
| [Importer Service](../../../../backend/apps/operations/services/operations_service.py) | 설계·필드 정책·트랜잭션 구현 |
| [Auth 단위 테스트](../../../../backend/tests/unit/accounts/test_auth_api.py) | `SYN-CUSTOMER-001` 공개 별칭과 직접 사용자명 차단 |
| [Operations 원장 Migration](../../../../backend/apps/operations/migrations/0001_initial.py) | 합성 Import 배치·항목 원장과 제약·인덱스 |
| [Workflow 시간 보정 Migration](../../../../backend/apps/workflow/migrations/0003_backfill_legacy_changed_at.py) | 기존 `workflow.0002` 이력의 잘못된 `changed_at` 보정 |
| [Backend README](../../../../backend/README.md) | 현재 기본 DB Migration·실행·검증 절차의 저장소 진입점 |

Crosswalk의 최신 main 기준 PostgreSQL 재검증 시각은
`2026-07-29T20:01:04+09:00`이며, 데이터베이스 버전은
`PostgreSQL 16.14 (Debian 16.14-1.pgdg12+1)`로 기록되어 있다.
현재 실행 중인 컨테이너 이미지와 live `SELECT version()` 결과도
동일했다.

Crosswalk의 `verification.actual.evidence`에는 두 격리 DB 이름,
최초·재실행 batch code와 완료 시각, fixture-set SHA-256, 재현 명령,
이 문서의 semantic text SHA-256을 함께 기록했다. 검증 기준 Git
Commit은 `0bcb8b514f2b0d1476882d926b667dbdb5d8c06a`이고, 검증 대상 변경은
아직 커밋되지 않았으므로 `worktree_state`를
`UNCOMMITTED_VERIFIED_CHANGES`로 명시한다. 따라서 이 증적은 특정
Commit에 이미 포함됐다는 뜻이 아니라, 해당 Commit을 기준으로 한
현재 작업본의 검증 결과다.

| 프로필 | 실행 | Batch code | 완료 시각(UTC) |
|---|---|---|---|
| `db-smoke` | 최초 | `SYN-IMPORT-6ADD1A8220654C28B40EC6A8A0908EFC` | `2026-07-29T10:58:01.967425+00:00` |
| `db-smoke` | Replay | `SYN-IMPORT-7617F68A827A4CF1B4C875E618967D77` | `2026-07-29T10:58:15.486953+00:00` |
| `db-full` | 최초 | `SYN-IMPORT-22B7EA784F88432399625A6E6E4C4C1C` | `2026-07-29T11:00:02.490369+00:00` |
| `db-full` | Replay | `SYN-IMPORT-1C0E022644654F2BBFF84B2DF5F3BAD3` | `2026-07-29T11:00:24.370239+00:00` |

## 3. 프로필별 실측

### 3.1 Dry-run·1차·재실행

| 프로필 | source | dry-run 저장<br>도메인/배치/원장 | 1차 결과<br>생성/수정/무변경/투영 | 재실행 결과<br>생성/수정/무변경/투영 |
|---|---:|---:|---:|---:|
| `db-smoke` | 37 | `0 / 0 / 0` | `31 / 0 / 0 / 6` | `0 / 0 / 31 / 6` |
| `db-full` | 367 | `0 / 0 / 0` | `355 / 0 / 0 / 12` | `0 / 0 / 355 / 12` |

`customer_products` 12행은 별도 Backend 테이블을 만들지 않고
`CustomerSubscription`에 투영하므로 `PROJECTED`로 집계한다.
문의 fixture 한 행은 `Inquiry`와 결정적 UUID v5를 사용하는
`SymptomEntry` 한 행을 생성한다. 이 파생 행 때문에 Full의 source는
367행이지만 실제 합성 도메인 행 합계는 377행이다.

### 3.2 실제 DB 행 수

| PostgreSQL 테이블 | Smoke | Full | 설명 |
|---|---:|---:|---|
| `accounts_user` | 8 | 16 | 합성 사용자 |
| `customers_customer_profile` | 6 | 12 | 합성 고객 프로필 |
| `catalog_product_model` | 1 | 1 | MVP 제품 |
| `subscriptions_customer_subscription` | 6 | 12 | 구독과 CustomerProduct 투영 |
| `support_inquiry` | 6 | 22 | 문의 aggregate |
| `support_inquiry_symptom` | 6 | 22 | 문의에서 파생된 대표 증상 |
| `support_consultation` | 3 | 12 | 상담 |
| `field_service_visit` | 1 | 4 | 방문 |
| `support_followup_confirmation` | 0 | 1 | 후속 확인 |
| `subscriptions_care_record` | 0 | 25 | Import source 케어 |
| `workflow_transition_history` | 0 | 125 | 문의·방문 상태 이력 |
| `audit_event` | 0 | 125 | 상태 이력 1:1 감사 |
| **도메인 합계** | **37** | **377** | 원장·Django 내부 테이블 제외 |
| `operations_synthetic_import_batch` | 2 | 2 | 1차·재실행 배치 |
| `operations_synthetic_import_item` | 74 | 734 | `source × 2회` |

배치 원장의 `dataset_version=0.9.0`,
`mapping_version=2.0.0`도 두 DB에서 동일하게 확인했다.

## 4. 상태·감사 정합성

Full 격리 DB를 읽기 전용 SQL로 다시 확인한 결과다.

| 검증 | 검사 건수 | 불일치 |
|---|---:|---:|
| Inquiry 최종 상태·버전 ↔ 최신 TransitionHistory | 22 | 0 |
| Visit 최종 상태·버전 ↔ 최신 TransitionHistory | 4 | 0 |
| AuditEvent ↔ 연결 TransitionHistory | 125 | 0 |
| **Aggregate 검증 합계** | **26** | **0** |

감사 비교 필드는 이벤트, actor, `state_version`,
`idempotency_key`, `correlation_id`, 발생 시각이다. 한 항목이라도
다르면 Import Service가 배치 원장을 기록하기 전에 전체 트랜잭션을
롤백한다.

## 5. 합성 고객 Auth Runtime

Full 격리 DB에서 다음 관계를 확인했다.

```text
CustomerProfile.customer_no = SYN-CUSTOMER-001
→ User.username = CUS-0001
→ role_code = CUSTOMER
→ user active + synthetic profile active
```

아래 HTTP 결과는 2026-07-29의 선행 격리 검증 증거다. 이번
`_mainv2` Crosswalk 재검증에서는 서버를 새로 띄워 HTTP 요청을
반복하지 않았으며, 별칭·차단 동작은 Auth 단위 테스트 20개와 Backend
전체 회귀에 포함해 확인했다.

| 요청 `demo_user_code` | HTTP | 판정 |
|---|---:|---|
| `SYN-CUSTOMER-001` | 200 | 고객 프로필을 안전한 공개 별칭으로 해석 |
| `CUS-0001` | 401 | 내부 사용자명 직접 사용을 접두사 정책으로 차단 |

로컬 구조화 요청 로그에서는 2026-07-29 14:48:59 KST에 같은
Demo Login route의 200과 401을 각각 확인했다. correlation ID는
`255b681b-05ac-45a4-8b03-cbac82adf4ec`,
`087c5209-b444-46a5-bbe4-e66ac4dab564`다. 요청 payload와 JWT는
로그·문서에 저장하지 않았다.

이 동작은 공개 Demo 환경 전용이다. 운영 환경은 Demo Login 비활성화를
기본값으로 유지해야 한다.

### 5.1 최신 main 기준 통합 게이트

| 게이트 | 최신 main 재검증 실측 |
|---|---:|
| Data unittest | 61/61 PASS |
| Backend pytest | 397/397 PASS |
| Django system check | 오류 0 |
| Migration drift | 없음 |
| Final Dataset Manifest | 154 entries, PASS |
| Crosswalk 집중 검증 | 30/30 PASS |
| PostgreSQL dry-run | Smoke·Full 모두 도메인/배치/원장 0행 |
| HTTP Auth | 이번 재검증 범위 제외, 선행 증거 200/401 유지 |

Final Manifest 154개는 `data_files 34 + metadata_files 15 +
schema_files 38 + build_tools 26 + config_files 10 + template_files 4 +
validation_reports 19 + policy_files 8`의 합계다.

## 6. 재현 명령

모든 명령은 저장소 루트에서 실행한다. 실제 비밀번호는 출력하거나
명령 이력에 직접 넣지 않고 [Backend 환경변수 예시](../../../../backend/.env.example)를
따른다.

### 6.1 PostgreSQL 확인과 격리 DB 생성

```powershell
docker compose --env-file .\backend\.env up -d postgres
docker ps --filter "name=watercare-local-postgres-1"

docker exec watercare-local-postgres-1 psql `
  -U watercare_app `
  -d postgres `
  -c "SELECT version();"
```

DB가 이미 존재하는지 먼저 확인한다.

```powershell
docker exec watercare-local-postgres-1 psql `
  -U watercare_app `
  -d postgres `
  -c "SELECT datname FROM pg_database WHERE datname LIKE 'watercare_synthetic_%_verify_20260729';"
```

새 검증이 필요할 때만 새 격리 DB 이름으로 `createdb`를 실행한다.
기존 검증 DB나 `watercare`를 덮어쓰거나 삭제하지 않는다.

```powershell
docker exec watercare-local-postgres-1 createdb `
  -U watercare_app `
  watercare_synthetic_smoke_verify_20260729_mainv2

docker exec watercare-local-postgres-1 createdb `
  -U watercare_app `
  watercare_synthetic_full_verify_20260729_mainv2
```

### 6.2 Smoke: Migration → dry-run → 1차 → 재실행

```powershell
Set-Location .\backend
$previousDatabase = $env:POSTGRES_DB

try {
  $env:DJANGO_SETTINGS_MODULE = 'config.settings.local'
  $env:POSTGRES_DB = 'watercare_synthetic_smoke_verify_20260729_mainv2'

  .\.venv\Scripts\python.exe manage.py check
  .\.venv\Scripts\python.exe manage.py migrate --noinput
  .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run

  .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
    --profile smoke --dry-run
  .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
    --profile smoke
  .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
    --profile smoke
}
finally {
  $env:POSTGRES_DB = $previousDatabase
}
```

첫 실제 실행은 `31 CREATED + 6 PROJECTED`, 재실행은
`0 CREATED + 0 UPDATED + 31 UNCHANGED + 6 PROJECTED`가 정상이다.

### 6.3 Full: Migration → dry-run → 1차 → 재실행

```powershell
$previousDatabase = $env:POSTGRES_DB

try {
  $env:DJANGO_SETTINGS_MODULE = 'config.settings.local'
  $env:POSTGRES_DB = 'watercare_synthetic_full_verify_20260729_mainv2'

  .\.venv\Scripts\python.exe manage.py check
  .\.venv\Scripts\python.exe manage.py migrate --noinput
  .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run

  .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
    --profile full --dry-run
  .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
    --profile full
  .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
    --profile full
}
finally {
  $env:POSTGRES_DB = $previousDatabase
}
```

첫 실제 실행은 `355 CREATED + 12 PROJECTED`, 재실행은
`0 CREATED + 0 UPDATED + 355 UNCHANGED + 12 PROJECTED`가 정상이다.
결과 JSON의 `source_items=367`, `projection_checks=12`,
`aggregate_checks=26`, `audit_history_checks=125`도 함께 확인한다.

### 6.4 Auth HTTP 확인

Full 격리 DB를 사용하는 로컬 Backend에서 Demo Login을 명시적으로
활성화한 뒤 응답 body를 저장하지 않고 상태 코드만 확인한다.

```powershell
curl.exe -s -o NUL -w "%{http_code}" `
  -H "Content-Type: application/json" `
  -d "{\"demo_user_code\":\"SYN-CUSTOMER-001\"}" `
  http://127.0.0.1:8000/api/v1/auth/demo-login

curl.exe -s -o NUL -w "%{http_code}" `
  -H "Content-Type: application/json" `
  -d "{\"demo_user_code\":\"CUS-0001\"}" `
  http://127.0.0.1:8000/api/v1/auth/demo-login
```

기대값은 차례대로 `200`, `401`이다. 토큰 응답을 파일이나 Git에
저장하지 않는다.

## 7. 안전 주의사항

1. `POSTGRES_DB`를 출력해 격리 DB인지 확인하기 전에는 Migration이나
   import를 실행하지 않는다.
2. `watercare`와 이름이 같은 DB를 검증 대상으로 사용하지 않는다.
3. `docker compose down -v`, `dropdb`, Volume 삭제는 이 재현 절차에
   포함하지 않는다.
4. 격리 DB 삭제가 필요하면 팀 승인·대상명 재확인 후 별도 작업으로
   수행한다.
5. fixture 정수 `id`를 Backend PK에 직접 주입하지 않는다.
6. 식별자 충돌을 자동 병합하거나 오류 행만 건너뛰지 않는다.
7. dry-run도 실제 검증 경로를 끝까지 실행하지만 결과는 반드시
   도메인·배치·원장 모두 0행이어야 한다.
8. 실제 고객 정보·운영 dump·비밀번호·JWT를 합성 검증 DB에 넣지
   않는다.
9. dry-run에서 도메인·배치·원장 행이 롤백돼도 PostgreSQL Sequence가
   실행 전 값으로 돌아간다고 가정하지 않는다. 새 빈 격리 DB만 사용한다.

## 8. 완료 범위와 남은 범위

| 범위 | 상태 | 해석 |
|---|---|---|
| 합성 handoff 12종 PostgreSQL 적재 | `DB_FULL_VERIFIED` | 이 문서의 완료 범위 |
| Smoke·Full 반복 안전성 | 완료 | 같은 입력 재실행 생성·수정 0 |
| Aggregate·감사 이력 | 완료 | 26·125건 불일치 0 |
| 합성 고객 Demo Login | 완료 | 별칭 200, 직접 사용자명 401 |
| 실제 고객·운영 데이터 Import | 미수행 | 합성 전용 명령으로 검증하지 않음 |
| T005(T-005) 계약 32테이블 전체 | `NOT_READY` | 현재 10/32 구현, 22개 미구현 |
| Web·Mobile 전체 업무 E2E | 후속 | 소비 앱에서 별도 검증 필요 |

## 9. 팀 인계와 반환 순서

현재 결과는 최신 `main` 기준의 **검증 완료 후보**다. Backend와
PostgreSQL 검증은 최지용이 완료했지만, Data 소유 파일은 김은진의
검토를 거쳐야 최종 공유 기준으로 확정된다. 현재 단계에서 반드시
왕복 인계해야 하는 협업자는 김은진이다.

| 순서 | 발신 → 수신 | 전달 내용 | 수신자가 반환할 내용·완료 기준 |
|---:|---|---|---|
| 1 | 최지용 → 김은진 | Crosswalk v2의 17개 Backend Source, 12개 Fixture Mapping, Consumer Profile, 관련 Schema·Test, 생성된 Manifest·QA 보고서, 이 문서의 PostgreSQL 증거 | Data 소유 범위 검토 결과, 승인 또는 수정 Diff, `eunjin`의 40자리 Commit SHA/PR, Data 61건 PASS, QA 2회 연속 PASS와 Manifest Hash |
| 2 | 김은진 → 최지용 | 승인된 Data 변경 또는 수정 사항과 재현 명령·결과 | 최지용이 승인된 변경만 반영한 뒤 Source Hash 검사, Data 61건, Backend 397건, PostgreSQL 적용 상태를 같은 기준선에서 재검증 |
| 3 | 최지용·김은진 → 윤승혁 | Backend 소유 Commit과 Data 소유 Commit을 분리한 SHA, 변경 범위, 테스트 결과, 미구현 범위 | PM 검토·병합 후 팀원이 반영할 40자리 `main` SHA |
| 4 | 윤승혁 → 한예나·양정현 | PM이 확정한 `main` SHA, 공개 합성 고객 코드, 지원 API·오류 계약 | Web·Mobile API Smoke 결과. Backend 결함이면 최지용에게 재현 요청을 반환하고, 소비 코드 결함이면 각 담당자가 수정 |
| 5 | 이동윤 → 최지용 | AI Runtime Commit, 요청·응답 Schema, 실행 명령과 재현 증거 | 자료 수신 후에만 Backend AI Client를 구현하고 통합 결과를 이동윤·PM에게 반환 |

인계할 때는 개인 PC의 작업트리 절대경로를 공유하지 않는다. 먼저
각 주담당자의 Branch Commit을 만들고 PM이 병합한 뒤, 팀원은 PM이
전달한 `main` SHA를 기준으로 작업한다. 따라서 한예나·양정현은
현재 검증 후보를 미리 Pull할 필요가 없다.

최지용의 다음 주담당은 T-005 잔여 Model·Migration을 작은 Wave로
구현하는 일이다. 다만 `audit`·`operations`·`workflow`의 최종 물리
테이블과 State·Terminal·Reopen 정책은 윤승혁의 계약 결정을 먼저
받고, AI 관련 테이블·Client는 이동윤의 Runtime Schema를 받은 뒤
시작한다. 각 Wave는 `작업 → Migration·Test 검증 → 다음 작업`
순서를 지킨다.

이 문서의 `DB_FULL_VERIFIED`는 합성 handoff 367행에 한정한다.
T-005 전체 완료나 운영 배포 완료 표식으로 확장해서 사용하면 안 된다.

## 10. 기본 `watercare` 후속 Migration·Seed 실측

이 절은 1~9장의 빈 격리 DB Import 검증을 변경하거나 대체하지 않는다.
2026-07-29에 현재 `.env`가 가리키는 기본 `watercare` PostgreSQL
16.14의 기존 데이터를 보존하면서 Migration과 Demo Seed만 별도로
검증한 누적 기록이다. 현재 절차의 저장소 진입점은
[Backend README](../../../../backend/README.md)다.

### 10.1 적용 Migration과 데이터 보존

적용 전에 미적용이었던 합성 Handoff 관련 9개 Migration과 후속 보정
Migration은 다음과 같다.

1. `inquiries.0003_add_synthetic_handoff_fields`
2. `visits.0001_initial`
3. `consultations.0001_initial`
4. `workflow.0002_expand_transition_targets`
5. `audit.0001_initial`
6. `care.0002_add_imported_care_fields`
7. `inquiries.0004_followup_confirmation`
8. `subscriptions.0002_add_synthetic_projection_fields`
9. [`operations.0001_initial`](../../../../backend/apps/operations/migrations/0001_initial.py)
10. [`workflow.0003_backfill_legacy_changed_at`](../../../../backend/apps/workflow/migrations/0003_backfill_legacy_changed_at.py)

적용 전후 기존 테이블별 row count는 같았다. `workflow.0002`가 Migration
실행 시각으로 채운 기존 TransitionHistory 11건은 `workflow.0003`에서
원래 `created_at`으로 보정했다. 보정 전 조건 일치 11건, 적용 후
`changed_at > created_at` 0건, `changed_at = created_at` 11건이었다.

### 10.2 현재 통합 Gate와 Demo Seed

| 검증 | 현재 실측 | 해석 |
|---|---|---|
| DBMS | PostgreSQL 16.14 | 기본 `watercare` 연결 |
| Backend pytest | `397 passed` | `config.settings.test`의 SQLite 테스트 |
| PostgreSQL Gate | 읽기 전용 연결 통과·미적용 Migration 0 | 397개 테스트를 PostgreSQL에서 실행했다는 뜻이 아님 |
| Migration drift | 없음 | 현재 Model과 Migration 일치 |
| Demo Seed | 4종 명령 2회 실행, 비의도 중복 0 | 기본 DB의 기존 row count 보존 |
| Workflow 시간 보정 | 11건 | `workflow.0003` 적용 결과 |

### 10.3 기본 DB Import 금지

기본 `watercare`의 `SYN-CUSTOMER-001` 관련 기존 레코드와 canonical
fixture는 공개 UUID가 다르다. 따라서 이 DB에서 합성 Importer
`--dry-run`을 실행하면 `public UUID mismatch`로 실패하는 것이 예상
결과다. 이 충돌은 Importer의 silent merge 차단이 작동한 것이며 UUID를
바꾸거나 검사를 우회하지 않는다.

기본 DB에서는 importer와 그 dry-run을 모두 실행하지 않는다. 합성
Importer는 새 빈 격리 PostgreSQL DB 전용이다. dry-run도 같은 쓰기
경로를 통과하므로 행은 롤백되더라도 PostgreSQL Sequence 값은 변할 수
있다. 기본 DB의 Migration·Demo Seed 검증과 격리 DB의 합성 Import
검증을 하나의 절차로 합치지 않는다.
