# Django PostgreSQL TEAM_INTEGRATION DB 구축·공유·운영 가이드

## 1. 문서 목적과 현재 판정

- 대상: 비운영 팀 통합·QA PostgreSQL 환경
- DB 이름: `waterbridge_team_integration`
- Schema: `public`
- DB·Backend 담당: 최지용
- 독립 QA·DevOps 담당: 김은진
- 현재 판정: `PACKAGE_READY / LOCAL_INTEGRATION_VERIFIED / REMOTE_NOT_PROVISIONED`

이 문서는 팀원이 같은 Migration·Role·Seed 기준으로 DB를 안전하게 재현하고
사용하는 방법을 설명한다. 저장소에는 구축 도구와 검증 기준이 있지만, 원격
Host·DNS·방화벽·CA·비밀번호는 만들거나 공개하지 않는다. 원격 Endpoint가
준비되기 전에는 `TEAM_SHARED` 또는 운영 DB라고 부르지 않는다.

실제 개인정보·운영 Token·운영 Dump는 이 DB에 적재하지 않는다.

## 2. 32개 테이블과 Active 13·Target-only 19의 의미

| 구분 | 의미 |
| --- | --- |
| 물리 계약 32 | Django Model과 번호 Migration으로 관리하는 계약 테이블 |
| Active 13 | 2026-07-31 기준 업무 데이터가 1행 이상 있던 테이블 |
| Target-only 19 | 물리 테이블은 존재하지만 당시 업무 데이터가 0행이던 테이블 |

Active 13은 별도 Schema나 권한 묶음이 아니다. Target-only 19도 이미 물리
테이블이므로 활성화할 때마다 접속정보를 다시 배포하지 않는다. Schema가
바뀌면 새 Forward Migration, 데이터가 생기면 멱등 Seed·Importer, 기능이
열리면 API·권한·회귀 결과만 공지한다.

13/19는 과거 데이터 분포이며 새 DB의 행 수를 보장하지 않는다. 새 DB에서는
Migration 직후 32개 계약 테이블이 비어 있을 수 있다.

## 3. 상태 코드와 완료 경계

| 상태 | 의미 |
| --- | --- |
| `PACKAGE_READY` | 코드·예시·Unit Test·문서 준비 |
| `LOCAL_INTEGRATION_VERIFIED` | 로컬 격리 DB Migration·Seed·Role 검증 완료 |
| `TEAM_INTEGRATION_PRE_QA` | 원격 비운영 DB 작성자 구축·검증 완료 |
| `TEAM_INTEGRATION_VERIFIED` | 비작성자 QA가 TLS·권한·API를 독립 재현 |
| `BLOCKED` | Host·TLS·Migration·Seed·Role 중 하나 이상 실패 |

로컬 PASS는 원격 공유 완료를 뜻하지 않는다. 팀 공유 완료는 안정적인 원격
Endpoint와 TLS를 구성한 뒤 비작성자가 다시 검증했을 때만 주장한다.

## 4. Role Matrix

| Role | 용도 | 허용 | 금지 |
| --- | --- | --- | --- |
| `waterbridge_ti_migrator` | 지정 Migration 실행자 | Schema CREATE·Migration | 일반 Backend 실행 |
| `waterbridge_ti_runtime` | Django Backend | 업무 테이블 CRUD·Sequence | Schema CREATE·Migration 원장 쓰기 |
| `waterbridge_ti_readonly` | 신뢰된 QA | 현재·향후 테이블 SELECT | DML·DDL |
| `waterbridge_ti_ai_readonly` | AI 최소권한 예약 | DB CONNECT·Schema USAGE | 현재 모든 테이블 조회·변경 |
| Admin | 최초 구축·복구 | DB·Role·Extension 관리 | 앱 실행·일반 팀원 공유 |

- QA Readonly는 인증·기술 테이블도 읽을 수 있으므로 합성 데이터 환경에서
  신뢰된 QA에게만 제공한다.
- Web·Mobile·PM은 DB 계정을 받지 않고 Backend API를 사용한다.
- AI Role은 승인된 테이블 Allowlist 전까지 직접 조회하지 않는다.
- `default_transaction_read_only=on`은 보조 설정이다. 실제 차단 기준은
  Schema·Table·Sequence ACL이다.
- 기능 Role은 공용 계정이므로 개인별 감사 추적이 필요하면 추후 개인 Login과
  NOLOGIN Group Role로 전환한다.

## 5. 인프라와 비밀값 경계

1. 로컬 Compose는 `127.0.0.1` 전용이며 외부에 공개하지 않는다.
2. 원격 공유 DB는 전용 비운영 PostgreSQL Instance 또는 Cluster를 사용한다.
3. 기존 `waterbridge`, `watercare`, Volume, Container는 삭제·Rename하지 않는다.
4. Password·DSN·Token·Host·Dump는 Git, Markdown, Discord, 실행 로그에 넣지 않는다.
5. 실제 값은 Git 제외 파일 또는 Secret Manager에만 둔다.
6. 원격 연결은 `POSTGRES_SSLMODE=verify-full`과 신뢰 CA를 반드시 사용한다.
7. 인증서 DNS SAN과 `POSTGRES_HOST`가 일치해야 한다.
8. 비밀번호는 Role마다 다르게 발급하고 1회성 보안 전달 경로로 공유한다.

같은 PostgreSQL Cluster의 다른 DB가 `PUBLIC CONNECT`를 허용하면 개별 Role의
접속 경계를 완전히 분리하기 어렵다. 원격 공유 환경은 전용 Instance가 기본이다.
공유 Cluster를 써야 한다면 DevOps가 모든 DB ACL을 별도 점검해야 한다.

## 6. 제공 파일

- [환경변수 예시](../../../../backend/.env.example)
- [Role 비밀번호 예시](../../../../backend/.env.team-integration.example)
- [DB·Role Provisioning](../../../../scripts/database/provision_team_integration.py)
- [PostgreSQL 연결 점검](../../../../scripts/database/check_postgresql_connection.py)
- [Provisioning Unit Test](../../../../backend/tests/unit/database/test_team_integration_provision.py)
- [Role Matrix PostgreSQL Test](../../../../backend/tests/integration/database/test_team_integration_roles_postgresql.py)

Provisioning은 기본 실행에서 DB에 연결하거나 변경하지 않는 Plan이다. 실제 적용은
`--apply`와 정확한 DB명 확인이 모두 있어야 시작된다. DB·Role 삭제 기능은 없다.

## 7. Owner 최초 구축

저장소 루트에서 비밀 파일의 로컬 사본을 만든다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Copy-Item .\backend\.env.team-integration.example `
  .\backend\.env.team-integration
```

자리표시자를 서로 다른 강한 비밀번호로 교체한다. 실제 파일은 Git에 포함되지
않는다. Admin용 `POSTGRES_*`도 Secret Manager 또는 현재 Process에 주입한다.

Plan을 먼저 확인한다.

```powershell
& .\backend\.venv\Scripts\python.exe `
  .\scripts\database\provision_team_integration.py
```

기대값은 `status=PLAN_READY`, `mutates_database=false`다.

실제 적용은 다음과 같다.

```powershell
& .\backend\.venv\Scripts\python.exe `
  .\scripts\database\provision_team_integration.py `
  --apply `
  --confirm-database waterbridge_team_integration
```

도구는 관리자 capability와 pgvector 가용성을 먼저 확인한다. 안전 표식이 없는
동명 DB·Role, 관리자 권한 부족, Role membership, 원격 TLS 누락은 Fail-closed로
중단한다. 재실행 시 초과된 Runtime·Readonly·AI 권한을 회수하고 최소권한을
다시 적용한다.

## 8. Migration과 권한 재조정

새 PowerShell에서 Migrator 값을 안전하게 주입한다.

```powershell
$env:POSTGRES_DB = 'waterbridge_team_integration'
$env:POSTGRES_USER = 'waterbridge_ti_migrator'
# Password·Host·Port·TLS·CA는 Secret Manager에서 Process로 주입한다.

& .\backend\.venv\Scripts\python.exe .\backend\manage.py migrate --plan `
  --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe .\backend\manage.py migrate --noinput `
  --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe .\backend\manage.py migrate --check `
  --settings=config.settings.local
& .\backend\.venv\Scripts\python.exe .\backend\manage.py makemigrations `
  --check --dry-run --settings=config.settings.local
```

Migration 뒤 Admin PowerShell에서 Provisioning을 같은 인자로 한 번 더 실행한다.
신규 테이블 Grant와 `django_migrations` Runtime 쓰기 차단을 재조정한다.

적용된 Migration 파일은 수정·삭제하지 않는다. 변경은 새 번호 Forward
Migration으로만 추가한다.

## 9. 승인 Demo Seed 2회

권한 재조정 후 Runtime 전용 PowerShell에서 실행한다.

```powershell
$env:POSTGRES_DB = 'waterbridge_team_integration'
$env:POSTGRES_USER = 'waterbridge_ti_runtime'
# POSTGRES_PASSWORD와 연결값은 안전하게 Process로 주입한다.

foreach ($round in 1..2) {
  foreach ($command in @('seed_common_codes', 'seed_demo_accounts',
      'seed_demo_products', 'seed_demo_subscriptions', 'seed_demo_care_records')) {
    & .\backend\.venv\Scripts\python.exe .\backend\manage.py $command `
      --settings=config.settings.local
    if ($LASTEXITCODE -ne 0) { throw "Demo Seed failed: $command round=$round" }
  }
}
```

2회차 비의도 신규 생성은 0이어야 한다. `import_synthetic_handoff`와 운영 Dump
반입은 별도 승인 없이 실행하지 않는다. 미매핑 Common Code를 자동 추론하지 않는다.

## 10. 팀원에게 전달할 값

일반 안내 채널에는 다음 메타데이터만 공유한다.

- 환경명과 DB 이름
- TLS DNS Host와 Port
- 사용할 Role Username
- CA 전달 위치와 Fingerprint
- 발급·만료·교체 시각
- 장애 연락 담당과 사용 가능 범위

비밀번호는 별도 보안 경로로 전달한다. Runtime 형식은 다음과 같다.

```dotenv
POSTGRES_DB=waterbridge_team_integration
POSTGRES_USER=waterbridge_ti_runtime
POSTGRES_PASSWORD=<보안 경로로 받은 값>
POSTGRES_HOST=<인증서와 일치하는 DNS 이름>
POSTGRES_PORT=5432
POSTGRES_CONNECT_TIMEOUT=5
POSTGRES_SSLMODE=verify-full
POSTGRES_SSLROOTCERT=.runtime/certs/team-integration-ca.pem
```

이 블록은 형식 예시다. 실제 값이 있는 파일은 Git에 추가하지 않는다.

## 11. 검증 순서

```powershell
& .\backend\.venv\Scripts\python.exe -m pytest `
  .\backend\tests\unit\database\test_team_integration_provision.py `
  .\backend\tests\unit\database\test_postgresql_connection_check.py `
  .\backend\tests\unit\settings\test_env.py `
  .\backend\tests\unit\settings\test_runtime_environment.py `
  .\backend\tests\unit\common\test_env_example.py -q

& .\backend\.venv\Scripts\python.exe `
  .\scripts\database\check_postgresql_connection.py

& .\backend\.venv\Scripts\python.exe `
  .\scripts\database\audit_t005_implementation_readiness.py `
  --settings config.settings.local --require-ready
```

원격 연결 기대값은 `CONNECTED`, 대상 DB·`public`, PostgreSQL 16 이상,
`connection_ssl=true`다. Role 비밀번호 4개를 가진 지정 검증자만 다음을 실행한다.

```powershell
$env:TEAM_INTEGRATION_POSTGRES_TEST = '1'
& .\backend\.venv\Scripts\python.exe -m pytest `
  .\backend\tests\integration\database\test_team_integration_roles_postgresql.py `
  -q -p no:cacheprovider
```

공유 DB에서 Rollback·파괴 Test·Test DB 생성은 하지 않는다. 빈 DB Forward,
Rollback, Restore 검증은 QA가 별도 격리 DB에서 수행한다.

## 12. Target-only 순차 활성화

1. 담당 기능·계약·대상 테이블을 확정한다.
2. Schema 변경이면 새 Forward Migration을 작성한다.
3. 기존 데이터가 있으면 Backup과 Writer 중지를 확인한다.
4. 멱등 Seed·Importer를 격리 DB에서 먼저 검증한다.
5. Migrator로 적용하고 Provisioning을 재실행한다.
6. Drift·T-005·API·Role Matrix를 검증한다.
7. 활성화 테이블·행 수·API 영향·복구법·검증 결과를 공지한다.

Host·DB명·Role·비밀번호가 바뀌지 않았다면 접속정보는 다시 배포하지 않는다.
Credential을 다시 전달하는 경우는 Rotation·유출·Role 변경·Endpoint 변경뿐이다.

## 13. Backup·복구·Rotation

Migration·대량 Seed 전에는 저장소 밖에 Custom-format Dump를 만든다.

```powershell
pg_dump --format=custom --file <저장소_밖_백업파일.dump> `
  --dbname waterbridge_team_integration
Get-FileHash -Algorithm SHA256 -LiteralPath <저장소_밖_백업파일.dump>
pg_restore --list <저장소_밖_백업파일.dump>
```

- Restore는 기존 공유 DB가 아닌 새 빈 DB에서 먼저 검증한다.
- 장애는 적용 Migration 수정 대신 새 Forward Migration으로 복구한다.
- `docker compose down -v`, DB·Volume·Role 삭제는 금지한다.
- 유출 시 새 비밀번호를 준비하고 유지보수 창에서 명시적으로 교체한다.

```powershell
& .\backend\.venv\Scripts\python.exe `
  .\scripts\database\provision_team_integration.py `
  --apply --confirm-database waterbridge_team_integration --rotate-passwords
```

교체 후 소비자 Secret을 갱신하고 기존 Process를 재시작한다.

## 14. 2026-08-09 로컬 작성자 검증 결과

- 별도 DB 최초 Provisioning 및 재적용: PASS
- 전체 Forward Migration: PASS
- Migration Check: 미적용 0, Drift 0
- T-005 Model·Migration Mapping: `READY`, 계약 32/32
- Demo Seed 2회: 2회차 비의도 신규 생성 0
- PostgreSQL Role Matrix: PASS
- 전체 Backend 회귀: 882 passed, 14 skipped, 0 failed
- 로컬 Compose SSL: `false`가 정상이며 원격 공유 증거로 사용하지 않음

이 결과는 `LOCAL_INTEGRATION_VERIFIED` 증거다. 원격 Host가 아직 없으므로
`TEAM_INTEGRATION_VERIFIED` 증거는 아니다.

## 15. QA 인계 최소 항목

- Candidate Label·변경 파일·PostgreSQL Version·DB명·Schema
- Migration plan·미적용·Drift·T-005 32/32 결과
- Seed 1·2회 집계·Role Matrix·Exit Code
- 실제 TLS 적용 여부·실패·잔여 Issue

QA는 자신의 격리 DB에서 빈 DB Forward·Rollback을 재현하고, 공유 DB에서는
Readonly 점검과 API E2E만 수행한다. 비밀번호·DSN·Dump는 증거 문서에 넣지 않는다.

## 16. 참고 문서

- [WBS](../../../planning/md/WBS.md) · [T-005 패키지](../../../database/t-005/README.md)
- [DB 저장소 설계](../../../submission/database-storage-design.md) · [스키마 변경 가이드](Django_PostgreSQL_스키마_변경_가이드.md)
- [Migration 불변성 복구 보고서](PostgreSQL_마이그레이션_불변성_사고_복구_보고서.md) · [합성데이터 적재 가이드](PostgreSQL_합성데이터_적재_통합검증_가이드.md)
- [로컬 설치·복구 가이드](../개발환경/Django_PostgreSQL_로컬개발환경_설치_실행_복구_가이드.md) · [Backend 실행 가이드](../../../../backend/README.md)
