# 최지용 Django·PostgreSQL 공유 패키지 인계서 v1.3

> 기준일: 2026-07-29
> 문서 상태: `HISTORICAL_20260729`
> 작성·유지 책임: 최지용
> 명령 실행 기준: 별도 표시가 없으면 저장소 루트
> 목적: 새 PC 설치, 기존 PC 갱신, PostgreSQL Migration, Django 실행과
> 팀 인계를 한 순서로 재현
> 실행 원칙: `대상 확인 → 작업 → 즉시 검증 → 증거 확인 → 다음 작업`

> **현행 실행 기준:** 2026-07-31부터 기본 PostgreSQL DB는
> `waterbridge`, Schema는 `public`이다. 현재 설치·환경 검사는
> [Backend README](../../../../backend/README.md)와
> [Backend `.venv` 재현 가이드](../technical/backend/backend_venv_reproducibility_guide.md),
> DB 전환·복구·32/13/19 범위·Seed·Importer·회귀는
> [WaterBridge DB 전환 및 Active 범위 검증](../technical/backend/20260731_waterbridge_database_transition_and_active_scope_validation.md)을
> 따른다. 아래 `watercare` DB명과 실행 수치는 2026-07-29 당시 증거다.

이 문서는 v1.1·v1.2의 유효한 환경 재현·실행·복구 절차와 당시 검증
증거를 통합하고, 2026-07-29 기본 `watercare` 개발 DB에 새 Migration을
적용한 실측 결과와 안전 규칙을 보존한 역사 원본이다. 이전 버전의
별도 파일은 유지하지 않으며, 버전별 검증 수치와 정책 변화는 15장에
보존한다.

로컬 검증 결과가 Git과 PM `main`에 자동으로 포함되는 것은 아니다.
팀원이 공용 기준으로 사용할 때는 PM이 병합 후 전달한 40자리 `main`
Commit SHA를 우선한다.

---

## 0. 먼저 읽을 결론

### 0.1 구성요소별 역할

| 구성요소 | 하는 일 | 하지 않는 일 |
| --- | --- | --- |
| `backend/.venv` | Python Interpreter와 Django·테스트 패키지 격리 | Docker 실행, `.env` 생성, Migration·Seed 적용 |
| `backend/.env` | Django·PostgreSQL 연결값과 로컬 비밀값 보관 | 패키지 설치, PostgreSQL Process 실행 |
| `docker-compose.yml` | PostgreSQL 16.14 Container 실행·상태 확인 | Django 서버 실행 |
| `manage.py migrate` | 현재 Git 기준의 Django Migration을 지정 DB에 적용 | 새 Migration 파일 생성 |
| `check_environment.py` | Python·패키지·Django·테스트·PostgreSQL 적용 상태 검사 | Seed·Importer·HTTP Smoke 실행 |
| `runserver` | Backend HTTP API 실행 | PostgreSQL 자동 시작 |
| `check_backend_auth.py` | 실행 중인 Backend의 Health·CORS·Auth 실제 HTTP 검사 | DB 읽기 전용 검사(Token Table을 변경함) |

`.venv`만 활성화해도 PostgreSQL과 Django가 자동으로 실행되는 구조가
아니다. Python 환경, `.env`, Docker PostgreSQL, Migration, Django를
순서대로 준비해야 한다.

### 0.2 팀에 공유하는 것과 공유하지 않는 것

공유 대상:

- Python 버전 파일
- requirements와 constraints
- bootstrap·검증 스크립트
- `.env.example`
- Docker Compose
- Migration 파일
- 이 문서와 검증 결과

공유 금지:

- `backend/.env`
- `backend/.venv`
- `backend/.runtime`
- PostgreSQL Password·전체 DSN
- Access·Refresh Token
- 로컬 PostgreSQL Docker Volume
- 실제 고객·개인정보

팀원은 `.venv`나 DB Volume을 전달받지 않는다. 같은 Git Commit을
받은 뒤 각자 환경과 로컬 DB를 재현한다.

### 0.3 이번 Migration 적용의 핵심 구분

1. 최지용은 승인된 기본 개발 DB에서 Migration을 먼저 적용하고
   Backend 전체 검증을 수행한다.
2. Migration 파일과 관련 코드가 `jiyong`에 Push되고 PM이 `main`에
   병합되기 전까지는 팀 공용 기준이 아니다.
3. 팀원은 PM의 `main` SHA를 받은 뒤 자기 로컬 DB에서
   `manage.py migrate`를 실행한다.
4. 팀원은 `makemigrations`로 새 Migration 파일을 만들지 않는다.
5. 여러 사람이 같은 공용 개발 DB를 사용한다면 지정된 적용 담당자
   한 명만 `migrate`를 실행한다.

---

## 1. 책임·협업·완료 기준

| 역할 | 담당자 | 책임 |
| --- | --- | --- |
| Backend·DB 구현 | 최지용 | Model·Migration·환경·API 실행 기준과 검증 |
| 통합·병합 | 윤승혁(PM) | 비작성자 검토 후 `main` 병합, 40자리 SHA 전달 |
| Data·통합 QA | 김은진 | 새 Pull 환경의 Migration·Seed·Data 검증 재현 |
| Web 소비 | 한예나 | 실제 Backend URL·Auth·CORS·오류 응답 확인 |
| Mobile 소비 | 양정현 | JWT·권한·오류·문의 API 소비 확인 |
| AI 경계 | 이동윤 | Backend↔AI URL·Schema·추적 계약 확인 |

환경·DB 인계 완료에는 다음 증거가 필요하다.

1. 사용 Branch와 40자리 Commit SHA
2. 대상 DB 이름과 DBMS 버전
3. 백업 필요 여부와 백업 검증 결과
4. Migration 적용 전·후 plan
5. 명령별 Exit code
6. Backend 전체 테스트와 PostgreSQL Gate 결과
7. Health·Auth Smoke 결과
8. 완료 범위·미구현 범위·후속 담당자

Password, Token, 전체 DSN은 증거에 포함하지 않는다.

---

## 2. 단일 원본

| 기준 | 파일 |
| --- | --- |
| Backend 실행 원본 | [Backend](<../../../../backend/>) |
| Backend 요약 안내 | [Backend README](<../../../../backend/README.md>) |
| Python 버전 | [`.python-version`](<../../../../backend/.python-version>) |
| 직접 의존성 | [`base.txt`](<../../../../backend/requirements/base.txt>), [`local.txt`](<../../../../backend/requirements/local.txt>) |
| 고정 패키지 해상도 | [`constraints-py313.txt`](<../../../../backend/requirements/constraints-py313.txt>) |
| 환경 생성·동기화 | [`bootstrap.py`](<../../../../scripts/development/bootstrap.py>) |
| 환경·회귀 검사 | [`check_environment.py`](<../../../../scripts/development/check_environment.py>) |
| 환경변수 예시 | [`.env.example`](<../../../../backend/.env.example>) |
| PostgreSQL Compose | [`docker-compose.yml`](<../../../../docker-compose.yml>) |
| DB 연결 검사 | [`check_postgresql_connection.py`](<../../../../scripts/database/check_postgresql_connection.py>) |
| Health·Auth Smoke | [`check_backend_auth.py`](<../../../../scripts/smoke/check_backend_auth.py>) |
| API 현재 지원 범위 | [API Runtime 구현 상태](<../../../api/runtime_implementation_status.md>) |
| 기계 API 계약 | [OpenAPI](<../../../../contracts/api/openapi.yaml>) |
| 환경 설계·복구 | [Backend `.venv` 재현 가이드](<../technical/backend/backend_venv_reproducibility_guide.md>) |
| API 계약 검증 | [Backend API 계약 정합화 검증보고서](<./20260729_최지용_Backend_API_계약_정합화_검증보고서_v1.0.md>) |
| `changed_at` 보정 | [`workflow.0003`](<../../../../backend/apps/workflow/migrations/0003_backfill_legacy_changed_at.py>) |
| 합성 Importer 상세 | [합성 Handoff Importer](<../technical/backend/20260729_synthetic_handoff_importer.md>) |
| 격리 DB Importer 실측 | [PostgreSQL 합성 Handoff Runtime 검증](<./20260729_postgresql_synthetic_handoff_runtime_verification.md>) |
| 팀 인계 진입점 | [팀 통합 인계 README](<../../../handoffs/README.md>) |

기계 실행 결과와 현재 코드가 이 문서의 과거 수치보다 우선한다.

---

## 3. 2026-07-29 현재 실측

| 검증 | 결과 | 해석 |
| --- | --- | --- |
| Python | `3.13.13` | 프로젝트 고정 버전 |
| pip | `26.0.1` | bootstrap 적용 버전 |
| PostgreSQL | `16.14` | Compose와 실제 연결 버전 |
| 기본 DB Migration | 기존 미적용 9개와 `workflow.0003` 적용 | 현재 로컬 `watercare` 적용 완료 |
| `workflow.0003` | Legacy `changed_at` 11건 보정 | `changed_at > created_at`인 식별 가능한 Legacy 행만 보정 |
| Django System Check | 오류 0 | 통과 |
| Migration drift | 없음 | 새 Migration 생성 필요 없음 |
| Backend 전체 테스트 | `397 passed` | `config.settings.test`의 SQLite 테스트 |
| PostgreSQL 적용 검사 | 미적용 Migration 없음 | 현재 `.env` 대상에 읽기 전용 연결·적용 상태 확인 |
| Health·Auth Smoke | Port `8001`, `status=PASSED` | Token은 출력하지 않음 |

`397 passed`와 PostgreSQL 검사는 같은 DB를 사용하는 단일 테스트가
아니다.

- `--full`은 `config.settings.test`에서 SQLite 기반 Backend pytest
  397개와 Migration drift를 검사한다.
- `--postgresql`은 현재 `backend/.env`가 가리키는 PostgreSQL에
  읽기 전용으로 연결하고 `migrate --check`로 적용 누락을 확인한다.
- 따라서 이 명령은 PostgreSQL에 Seed를 넣거나 API E2E를 수행하지
  않는다.

장기 정상 기준은 고정된 테스트 개수보다 Exit code `0`, 실패 `0`,
Migration drift 없음, 미적용 Migration 없음이다.

---

## 4. 절차 선택표

| 현재 상태 | 실행할 절차 |
| --- | --- |
| 처음 Pull했고 `.env`·`.venv`가 없음 | 5장부터 전체 실행 |
| `.env`는 있고 `.venv`만 없음 | 5.3부터 실행 |
| 기존 PC에서 새 PM `main` SHA를 받음 | 6장 전체 실행 |
| Git Commit은 같고 단순 재시작 | 7장 실행 |
| requirements fingerprint 불일치 | 11.1 |
| Migration 적용 실패 | 11.4 |
| 합성 Importer 검증 | 9장의 격리 DB 절차만 사용 |
| Web에서 실제 API 확인 | 8장까지 통과 후 10장 |

---

## 5. 새 PC 최초 설치

### 5.1 저장소와 Commit 확인

저장소 루트에서 실행한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

git status --short
git branch --show-current
git rev-parse HEAD
```

팀 작업은 PM이 전달한 40자리 `main` SHA가 자기 Branch에 반영된 뒤
시작한다. 미커밋 파일이 있으면 임의로 삭제·덮어쓰기·Branch 전환하지
말고 먼저 본인 변경을 분리한다.

### 5.2 `.env` 준비

`backend/.env`가 없을 때만 예시 파일을 복사한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

if (-not (Test-Path -LiteralPath .\backend\.env)) {
    Copy-Item `
        -LiteralPath .\backend\.env.example `
        -Destination .\backend\.env
}
```

다음 값은 프로젝트 성격과 자기 PC에 맞게 채운다.

- `DJANGO_SECRET_KEY`
- `DJANGO_TIME_ZONE=Asia/Seoul`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `AI_SERVICE_BASE_URL`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

실제 비밀값을 화면 캡처, 문서, 채팅, Git에 넣지 않는다.

Git 제외 상태를 확인한다.

```powershell
git check-ignore -v backend/.env
git status --short -- backend/.env backend/.venv backend/.runtime
```

`backend/.env`가 Git 변경으로 나타나면 다음 단계로 진행하지 않는다.

### 5.3 Python 3.13.13과 `.venv` 재현

먼저 현재 `python`이 정확히 3.13.13인지 확인한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

python --version
python .\scripts\development\bootstrap.py --service backend
```

bootstrap은 다음 작업을 수행한다.

1. Python 3.13.13 확인
2. `backend/.venv` 생성 또는 현재 환경 재사용
3. pip 26.0.1 적용
4. requirements와 constraints 설치
5. `pip check`와 Django 기본 검사
6. requirements fingerprint 기록

bootstrap은 `.env`, Docker, PostgreSQL, Migration, Seed를 변경하지
않는다.

생성 결과를 확인한다.

```powershell
.\backend\.venv\Scripts\python.exe --version
.\backend\.venv\Scripts\python.exe -m pip --version
python .\scripts\development\check_environment.py --service backend
```

정상 기준:

- Python `3.13.13`
- pip `26.0.1`
- `pip check` 통과
- requirements fingerprint 일치
- `failures=0`
- Exit code `0`

### 5.4 Docker daemon과 PostgreSQL

Docker Desktop을 먼저 실행한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

docker version
docker compose --env-file .\backend\.env config --quiet
docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres
```

정상 기준:

- Docker Client와 Server가 모두 응답
- Compose 문법 오류 없음
- `postgres`가 `running`, `healthy`
- 실제 Compose Image `pgvector/pgvector:0.8.6-pg16-bookworm`

Client 정보만 있고 Server 정보가 없거나 `healthy`가 아니면 Migration을
실행하지 않는다.

### 5.5 대상 DB와 Writer 확인

Migration 전에 현재 Container가 실제로 연결하는 DB 이름·사용자·버전을
확인한다. Password는 출력하지 않는다.

```powershell
Set-Location (git rev-parse --show-toplevel)

docker compose --env-file .\backend\.env exec -T postgres `
    sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT current_database(), current_user; SHOW server_version;"'
```

출력된 DB가 의도한 로컬 `watercare` 또는 명시적으로 승인된 DB인지
확인한다. DB 이름이 예상과 다르면 즉시 중단한다.

적용 중에는 DB Writer가 없어야 한다.

1. 실행 중인 Django `runserver`에서 `Ctrl+C`
2. Seed·Importer·Data 적재 명령 중단
3. Web·Mobile의 쓰기 API 호출 중단
4. 별도 Worker가 있다면 중단

현재 DB의 다른 Session 수를 확인한다.

```powershell
docker compose --env-file .\backend\.env exec -T postgres `
    sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid();"'
```

0이 아니면 자동으로 Session을 종료하지 말고 어떤 프로그램이 연결되어
있는지 확인한 뒤 Writer를 정상 종료한다.

### 5.6 `pg_dump` 백업과 검증

기존 데이터가 있는 DB에 Migration을 적용하기 전에는 논리 백업을
만든다. 완전히 새로 만든 빈 격리 DB라면 “빈 DB라 백업 불필요”라고
실행 기록에 남긴다.

PowerShell의 바이너리 출력 Redirection으로 custom dump를 직접 만들지
않는다. Container 안에서 `pg_dump -Fc`를 실행한 뒤 호스트로 복사한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

$backupDir = ".\backend\.runtime\db-backups"
$backupName = "watercare_pre_migration_{0}.dump" -f `
    (Get-Date -Format "yyyyMMdd-HHmmss")
$backupPath = Join-Path $backupDir $backupName

New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

docker compose --env-file .\backend\.env exec -T postgres `
    sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/watercare_pre_migration.dump'
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump 백업 생성 실패"
}

docker compose --env-file .\backend\.env exec -T postgres `
    sh -lc 'pg_restore --list /tmp/watercare_pre_migration.dump >/dev/null'
if ($LASTEXITCODE -ne 0) {
    throw "pg_restore --list 백업 구조 검사 실패"
}

docker compose --env-file .\backend\.env cp `
    postgres:/tmp/watercare_pre_migration.dump `
    $backupPath
if ($LASTEXITCODE -ne 0) {
    throw "백업 파일 호스트 복사 실패"
}

Get-Item -LiteralPath $backupPath |
    Select-Object FullName, Length, LastWriteTime
```

`pg_restore --list`는 dump 목차를 읽는 검사일 뿐 데이터를 복원하지
않는다. Exit code `0`이어도 실제 복원 가능성을 완전히 증명하지 않는다.

실제 복원 검증은 명시적으로 승인된 새 격리 DB에만 수행한다.
기본 `watercare` DB 위에 덮어쓰지 않는다.

```powershell
Set-Location (git rev-parse --show-toplevel)

$restoreDb = "watercare_restore_check_{0}" -f `
    (Get-Date -Format "yyyyMMddHHmmss")

docker compose --env-file .\backend\.env exec -T `
    -e "RESTORE_DB=$restoreDb" postgres `
    sh -lc 'createdb -U "$POSTGRES_USER" "$RESTORE_DB"'
if ($LASTEXITCODE -ne 0) {
    throw "복원 검증용 격리 DB 생성 실패"
}

docker compose --env-file .\backend\.env cp `
    $backupPath `
    postgres:/tmp/watercare_restore_check.dump
if ($LASTEXITCODE -ne 0) {
    throw "복원 검증용 dump 복사 실패"
}

docker compose --env-file .\backend\.env exec -T `
    -e "RESTORE_DB=$restoreDb" postgres `
    sh -lc 'pg_restore --exit-on-error --no-owner --no-privileges -U "$POSTGRES_USER" -d "$RESTORE_DB" /tmp/watercare_restore_check.dump'
if ($LASTEXITCODE -ne 0) {
    throw "격리 DB 실제 복원 실패"
}

docker compose --env-file .\backend\.env exec -T `
    -e "RESTORE_DB=$restoreDb" postgres `
    sh -lc 'psql -U "$POSTGRES_USER" -d "$RESTORE_DB" -Atc "SELECT current_database();"'
```

복원 검증 DB 삭제는 이 표준 절차에 포함하지 않는다. 삭제가 필요하면
대상 이름을 다시 확인하고 별도 승인된 정리 작업으로 수행한다.

### 5.7 Migration 사전 검사와 Plan

백업 판단이 끝난 뒤 실행한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend

$python = ".\.venv\Scripts\python.exe"

& $python manage.py check --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "Django local 설정 검사 실패"
}

& $python manage.py makemigrations --check --dry-run `
    --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "Migration drift 검사 실패"
}

& $python manage.py showmigrations --plan `
    --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "현재 Migration 적용 상태 확인 실패"
}

& $python manage.py migrate --plan `
    --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "Migration 적용 Plan 생성 실패"
}
```

2026-07-29 적용 전에는 다음 9개와 추가 보정 Migration 1개가 대상이었다.

| 구분 | Migration |
| --- | --- |
| 기존 미적용 1 | `inquiries.0003_add_synthetic_handoff_fields` |
| 기존 미적용 2 | `visits.0001_initial` |
| 기존 미적용 3 | `consultations.0001_initial` |
| 기존 미적용 4 | `workflow.0002_expand_transition_targets` |
| 기존 미적용 5 | `audit.0001_initial` |
| 기존 미적용 6 | `care.0002_add_imported_care_fields` |
| 기존 미적용 7 | `inquiries.0004_followup_confirmation` |
| 기존 미적용 8 | `subscriptions.0002_add_synthetic_projection_fields` |
| 기존 미적용 9 | `operations.0001_initial` |
| 추가 보정 | `workflow.0003_backfill_legacy_changed_at` |

표의 순서를 수동 실행 순서로 사용하지 않는다. 실제 적용 순서는 Django
Migration dependency graph와 `migrate --plan`이 결정한다.

예상하지 않은 앱·Migration, 삭제성 작업 또는 대량 데이터 변환이
Plan에 있으면 적용하지 말고 코드·Commit·대상 DB를 다시 확인한다.

### 5.8 Migration 적용과 즉시 검증

Plan과 백업이 확인된 같은 PowerShell에서 실행한다.

```powershell
& $python manage.py migrate --noinput `
    --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "Migration 적용 실패"
}

& $python manage.py migrate --check `
    --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "미적용 Migration 검사 실패"
}

& $python manage.py showmigrations --plan `
    --settings=config.settings.local
if ($LASTEXITCODE -ne 0) {
    throw "Migration 적용 후 상태 확인 실패"
}
```

정상 기준:

- 위 10개 Migration이 모두 `[X]`
- `migrate --check` Exit code `0`
- 새 Migration 생성 요구 없음
- `workflow.0003` 적용

`workflow.0003`은 `workflow.0002`가 기존 Transition History의
`changed_at`을 Migration 실행 시각으로 덮어쓴 Legacy 사례를
보정한다. `changed_at > created_at`이고 Legacy 식별 규칙이 일치하는
행만 `created_at`으로 복원한다. 이번 기본 DB에서는 11건이 보정됐다.

### 5.9 기본 `watercare`의 Demo Seed

기본 개발 DB에는 다음 네 Demo Seed만 사용한다.

1. Accounts
2. Products
3. Subscriptions
4. Care

Accounts Seed가 생성·갱신하는 공개 Demo 식별자는 다음과 같다. 비밀번호는
각 PC의 로컬 `.env`에서만 관리하고 문서나 Git에 기록하지 않는다.

| 역할 | 사용자 코드 | 고객 프로필 |
| --- | --- | --- |
| 고객 | `DEMO-CUSTOMER-001` | `DEMO-CUS-001` |
| 상담사 | `DEMO-CONSULTANT-001` | 해당 없음 |
| 방문기사 | `DEMO-TECHNICIAN-001` | 해당 없음 |
| 운영자 | `DEMO-OPERATOR-001` | 해당 없음 |

각 명령을 두 번 실행해 멱등성을 확인한다.

```powershell
& $python manage.py seed_demo_accounts `
    --settings=config.settings.local
& $python manage.py seed_demo_products `
    --settings=config.settings.local
& $python manage.py seed_demo_subscriptions `
    --settings=config.settings.local
& $python manage.py seed_demo_care_records `
    --settings=config.settings.local

& $python manage.py seed_demo_accounts `
    --settings=config.settings.local
& $python manage.py seed_demo_products `
    --settings=config.settings.local
& $python manage.py seed_demo_subscriptions `
    --settings=config.settings.local
& $python manage.py seed_demo_care_records `
    --settings=config.settings.local
```

각 명령 뒤 `$LASTEXITCODE`를 확인한다. 두 번째 실행에서 비의도 중복이
생기면 다음 단계로 넘어가지 않는다.

`seed_demo_accounts`의 현재 회귀 기준은 첫 실행 출력에 `created=4`,
두 번째 실행 출력에 `updated=4`가 포함되는 것이다. 다른 Seed는
각 Command의 검증 결과와 DB 행 수를 함께 확인한다.

기본 `watercare`에는 `import_synthetic_handoff`를 실행하지 않는다.
그 이유와 격리 절차는 9장에서 설명한다.

### 5.10 Migration 이후 읽기 전용 Gate

저장소 루트로 돌아가 실행한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

python .\scripts\development\check_environment.py `
    --service backend `
    --full `
    --postgresql
if ($LASTEXITCODE -ne 0) {
    throw "Backend 전체·PostgreSQL Gate 실패"
}
```

이 명령의 범위:

| 옵션 | 실제 검사 |
| --- | --- |
| 기본 | Python·pip·constraints·fingerprint·`pip check`·Django check |
| `--full` | SQLite 테스트 설정의 Migration drift와 Backend 전체 pytest, Git 제외 |
| `--postgresql` | 현재 `.env` PostgreSQL 읽기 전용 연결과 `migrate --check` |

이 명령은 Seed, Importer, `runserver`, HTTP Smoke를 실행하지 않는다.

2026-07-29 실측은 다음과 같다.

```text
Backend 전체 pytest: 397 passed
PostgreSQL: 16.14
Migration drift: 없음
Applied Migration failure: 0
failures=0
warnings=0
```

---

## 6. 기존 PC에서 PM `main` 갱신 후 실행

### 6.1 Git 기준 확인

팀원이 직접 `jiyong` Branch를 공용 기준으로 확정하지 않는다.
PM이 병합한 `main` 40자리 SHA를 받은 뒤 자기 Branch에 반영한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

git status --short
git fetch --prune origin main
git rev-parse HEAD
git rev-parse origin/main
```

미커밋 변경이 있으면 자동으로 버리거나 덮어쓰지 않는다. 팀 Git 규칙에
따라 자기 변경을 먼저 Commit·인계한 뒤 PM `main`을 반영한다.

### 6.2 환경 동기화

```powershell
python --version
python .\scripts\development\bootstrap.py --service backend
python .\scripts\development\check_environment.py --service backend
```

Python이 3.13.13이 아니거나 빠른 검사가 실패하면 DB로 넘어가지 않는다.

### 6.3 팀원 로컬 DB 적용

1. Docker PostgreSQL을 `healthy`로 만든다.
2. 자기 로컬 DB 이름을 확인한다.
3. 기존 데이터가 있으면 5.6의 `pg_dump` 백업을 만든다.
4. 5.7의 `showmigrations`·`migrate --plan`을 확인한다.
5. `manage.py migrate --noinput`을 실행한다.
6. 팀원은 `makemigrations`를 실행하지 않는다.
7. 5.9의 Demo Seed 네 종류를 필요한 경우 두 번 실행한다.
8. 5.10의 전체 Gate를 실행한다.

공용 DB라면 전원이 같은 명령을 반복하지 않고 지정된 담당자 한 명만
적용한다. 다른 팀원은 `migrate --check`와 읽기 전용 Gate만 실행한다.

---

## 7. 설치·Migration 완료 후 매일 다시 켜기

같은 Commit이고 새 Migration이 없을 때 사용하는 절차다.

### 7.1 PostgreSQL 시작

```powershell
Set-Location (git rev-parse --show-toplevel)

docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres
```

### 7.2 적용 상태 확인

```powershell
Set-Location .\backend

.\.venv\Scripts\python.exe manage.py migrate --check `
    --settings=config.settings.local
```

미적용 Migration이 있으면 일상 실행 절차에서 자동 적용하지 않는다.
서버를 켜지 말고 6장의 Git 갱신·대상 DB·백업·Plan 절차로 돌아간다.

### 7.3 Django 실행

기본 Port 8000의 사용 여부를 먼저 확인한다.

```powershell
$listener8000 = Get-NetTCPConnection `
    -LocalPort 8000 `
    -State Listen `
    -ErrorAction SilentlyContinue

if ($listener8000) {
    $listener8000 |
        Select-Object LocalAddress, LocalPort, OwningProcess
} else {
    "PORT_8000_AVAILABLE"
}
```

권한 때문에 `Get-NetTCPConnection` 결과를 읽지 못하면 다음 대체 명령으로
PID를 확인한다.

```powershell
netstat -ano -p tcp | Select-String ':8000'
```

8000이 비어 있으면 첫 번째 PowerShell에서 실행한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend

.\.venv\Scripts\python.exe manage.py runserver `
    127.0.0.1:8000 `
    --noreload `
    --settings=config.settings.local
```

8000을 공식 Backend가 이미 사용 중이면 새 서버를 중복 실행하지 않는다.
다른 Process가 사용 중이고 대체 Port가 필요하면 8001도 먼저 확인한다.

```powershell
$listener8001 = Get-NetTCPConnection `
    -LocalPort 8001 `
    -State Listen `
    -ErrorAction SilentlyContinue

if ($listener8001) {
    $listener8001 |
        Select-Object LocalAddress, LocalPort, OwningProcess
} else {
    "PORT_8001_AVAILABLE"
}
```

같은 방식으로 결과를 읽지 못하면 다음을 사용한다.

```powershell
netstat -ano -p tcp | Select-String ':8001'
```

8001은 AI 개발 주소와 겹칠 수 있다. AI가 실행 중이지 않고 8001이
비어 있는 경우에만 대체 Backend로 사용한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend

.\.venv\Scripts\python.exe manage.py runserver `
    127.0.0.1:8001 `
    --noreload `
    --settings=config.settings.local
```

### 7.4 Health 확인

두 번째 PowerShell에서 실제 실행 Port에 맞춰 확인한다.

Port 8000:

```powershell
$health = Invoke-WebRequest `
    -UseBasicParsing `
    -Uri 'http://127.0.0.1:8000/health'

$health.StatusCode
$health.Headers['X-Correlation-ID']
```

Port 8001:

```powershell
$health = Invoke-WebRequest `
    -UseBasicParsing `
    -Uri 'http://127.0.0.1:8001/health'

$health.StatusCode
$health.Headers['X-Correlation-ID']
```

정상 기준은 HTTP 200과 UUID 형식의 `X-Correlation-ID`다.

### 7.5 Auth Smoke

Auth Smoke는 읽기 전용이 아니다. Demo 로그인, Refresh rotation,
Logout과 Token revoke를 검증하므로 DB의 Token 관련 Table을
변경한다. 기본 Demo Accounts Seed가 준비된 개발 DB에서만 실행한다.

Port 8000:

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend

.\.venv\Scripts\python.exe `
    ..\scripts\smoke\check_backend_auth.py `
    --base-url http://127.0.0.1:8000
```

Port 8001:

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend

.\.venv\Scripts\python.exe `
    ..\scripts\smoke\check_backend_auth.py `
    --base-url http://127.0.0.1:8001
```

정상 기준:

- JSON `status=PASSED`
- Health·CORS·Demo Login·`/me` 통과
- Refresh Token rotation·replay 차단
- Logout·폐기 Token replay 차단
- 실제 Token 출력 없음
- Exit code `0`

2026-07-29에는 Port 8001에서 `status=PASSED`를 확인했다.

### 7.6 종료

Django 실행 PowerShell에서:

```text
Ctrl+C
```

PostgreSQL을 유지하면 다음 실행이 빠르다. 사용하지 않을 때만 저장소
루트에서 중지한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
docker compose --env-file .\backend\.env stop postgres
```

`docker compose down -v`는 DB Volume을 삭제하므로 이 실행 절차에서
사용하지 않는다.

---

## 8. 서버 변경 뒤 다시 검증하는 최소 순서

Backend 코드를 수정한 경우 다음 순서를 사용한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

python .\scripts\development\check_environment.py `
    --service backend `
    --full `
    --postgresql
```

Gate가 통과하면 서버를 실행하고 실제 Port에 맞춰 Health·Auth Smoke를
수행한다. Auth 또는 Workflow 기능을 수정했다면 관련 집중 테스트도
같은 Commit에서 추가로 실행한다.

실패한 상태에서 Web·Mobile·AI 담당자에게 API 완료로 인계하지 않는다.

---

## 9. 합성 Handoff Importer의 별도 경계

### 9.1 기본 DB에서 실행하지 않는 이유

`import_synthetic_handoff`는 승인된 합성 fixture 12종을 정식 도메인
Model과 Import Ledger에 적재하는 검증용 관리 명령이다.

현재 기본 `watercare` DB에는 Demo Seed와 기존 데이터가 있으므로
Importer의 공개 UUID·업무 키·Auto Increment sequence와 충돌할 수
있다. 따라서 다음 명령은 기본 DB에서 실행하지 않는다.

```text
manage.py import_synthetic_handoff
```

기본 `watercare`에는 5.9의 Demo Seed 네 종류만 적용한다.

### 9.2 빈 격리 DB에서만 실행

Canonical Importer 재현은 새 이름의 빈 PostgreSQL 격리 DB에서만
수행한다.

권장 순서:

1. 새 격리 DB 이름 지정
2. 빈 DB 생성
3. 해당 PowerShell Process에서 `POSTGRES_DB`를 격리 DB로 명시
4. Migration 적용
5. `smoke --dry-run`
6. 실제 `smoke` 2회
7. `full --dry-run`
8. 실제 `full` 2회
9. 원장·도메인·상태·감사 결과 확인

상세 명령과 기대 건수는
[PostgreSQL 합성 Handoff Runtime 검증](<./20260729_postgresql_synthetic_handoff_runtime_verification.md>)을
따른다.

### 9.3 `--dry-run` 주의

PostgreSQL Sequence는 일반 Transaction rollback 대상이 아니다.
Importer가 `--dry-run`에서 Transaction을 롤백해 도메인 행과 원장 행이
남지 않더라도 Auto Increment sequence 값은 증가할 수 있다.

따라서:

- Dry-run DB가 “행 0건”이라고 해서 완전히 사용 전 상태와 같다고
  판단하지 않는다.
- PK sequence까지 동일한 재현이 필요하면 dry-run용 DB와 실제
  적재용 DB를 각각 새로 만든다.
- 기본 `watercare`에서 안전 확인 목적으로 dry-run을 실행하지 않는다.
- UUID·Serial 충돌이 나면 기본 DB 데이터를 수정해 맞추지 말고 새
  격리 DB에서 다시 시작한다.

---

## 10. Web·Mobile 실제 소비 확인

Backend Health·Auth Smoke 통과는 Backend 인증 API가 동작한다는
증거다. Web·Mobile 화면이 실제 Backend를 소비한다는 증거는 별도다.

소비 담당자에게 전달할 항목:

1. PM `main` 40자리 SHA
2. Backend Base URL
3. 실행 Port
4. 지원 Runtime API와 OpenAPI-only 미구현 범위
5. CORS 허용 Origin
6. Demo 사용자 코드
7. 정상·오류 JSON 예시
8. Migration·Smoke 결과

Web·Mobile 담당자는 자기 PC의 로컬 DB에 Migration을 적용한 뒤 실제
Network 요청, HTTP 상태, 오류 Wrapper와 Correlation ID를 확인한다.
Mock 응답만으로 Backend 연동 완료를 판정하지 않는다.

Web은 기본적으로 Mock API를 사용한다. 실제 Backend 소비를 검증할
PowerShell에서 다음 값을 명시한다.

```powershell
Set-Location .\web
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
$env:VITE_USE_MOCK_API = "false"
npm.cmd run dev
```

Backend가 다른 Port에서 실행 중이면 `VITE_API_BASE_URL`의 Port도 같은
값으로 바꾼다. 위 환경변수는 현재 PowerShell Process에만 적용된다.

---

## 11. 오류별 복구

### 11.1 requirements fingerprint 불일치

```powershell
Set-Location (git rev-parse --show-toplevel)

python .\scripts\development\bootstrap.py --service backend
python .\scripts\development\check_environment.py --service backend
```

패키지를 개별 `pip install`로 맞추지 않는다. requirements와 constraints를
기준으로 bootstrap을 재실행한다.

### 11.2 Python 버전 또는 `.venv` 손상

교체 대상 `.venv` 밖의 Python 3.13.13으로 실행한다.

```powershell
python --version
python .\scripts\development\bootstrap.py `
    --service backend `
    --recreate
```

새 환경이 성공해도 전체 Gate와 Smoke가 통과하기 전에는 백업된 기존
환경을 삭제하지 않는다.

`--recreate`는 기존 환경을 다음 경로로 먼저 이동한다.

```text
backend/.runtime/venv-backups/<timestamp>/.venv
```

새 환경 생성이나 경량 검증이 실패하면 bootstrap이 위 백업을
`backend/.venv`로 자동 복원한다. 성공한 경우 출력된
`rollback_backup` 경로를 기록하고, 전체 Gate·PostgreSQL·Health·Auth
Smoke가 모두 통과한 뒤에만 백업 삭제 여부를 판단한다.

### 11.3 Docker daemon·PostgreSQL 오류

```powershell
docker version
docker compose --env-file .\backend\.env ps postgres
docker compose --env-file .\backend\.env logs --tail 100 postgres
```

다음 사항을 확인한다.

- Docker Server가 응답하는가
- PostgreSQL이 `healthy`인가
- Port 5432가 충돌하지 않는가
- 기존 Volume을 둔 채 `.env` Password만 바꾸지 않았는가

Password와 전체 DSN을 오류 보고에 넣지 않는다.

### 11.4 Migration 실패

다음 행동을 금지한다.

- Migration 파일 삭제·번호 변경
- `--fake` 적용
- 기본 DB 초기화
- `down -v`
- 새 `makemigrations`
- 실패한 DB에서 Importer·Seed 계속 실행

다음 정보를 기록하고 최지용에게 전달한다.

1. Commit SHA
2. 대상 DB 이름
3. `migrate --plan`
4. 실패 Migration 이름
5. 첫 오류
6. Exit code
7. 백업 파일 존재·`pg_restore --list` 결과

복원이 필요하면 기존 DB 위에 바로 덮어쓰지 않고 5.6처럼 새 격리
복원 DB에서 먼저 검증한다.

### 11.5 Migration 적용 후에도 미적용으로 표시

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend

.\.venv\Scripts\python.exe manage.py showmigrations --plan `
    --settings=config.settings.local

.\.venv\Scripts\python.exe manage.py migrate --check `
    --settings=config.settings.local
```

확인 순서:

1. 실행 Settings가 `config.settings.local`인가
2. process environment가 `.env`보다 우선해 다른 DB를 가리키는가
3. Docker Container의 DB 이름과 Django 대상 DB가 같은가
4. 팀원이 PM 병합 전 Commit을 사용하고 있지 않은가

### 11.6 Port 8000·8001 충돌

```powershell
Get-NetTCPConnection `
    -LocalPort 8000,8001 `
    -State Listen `
    -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess
```

공식 Backend Process라면 중복 실행하지 않는다. 알 수 없는 Process를
자동 종료하지 말고 소유 프로그램을 먼저 확인한다. 8001은 AI 개발
주소와 겹칠 수 있다.

### 11.7 Health·Auth Smoke 실패

확인 순서:

1. Smoke의 `--base-url` Port와 실제 `runserver` Port 일치
2. `/health` HTTP 200
3. PostgreSQL `healthy`
4. Migration 누락 없음
5. Demo Accounts Seed 존재
6. `DJANGO_CORS_ALLOWED_ORIGINS`에 검사 Origin 포함
7. 첫 실패 HTTP 상태와 Correlation ID 기록

Auth Smoke는 Token Table을 변경한다. 실패 후 DB를 임의 초기화하지
말고 같은 Demo 사용자로 재실행 가능한지 원인을 먼저 확인한다.

### 11.8 Importer UUID·Serial 충돌

기본 DB 데이터나 fixture UUID를 임의 수정하지 않는다.

1. 실행 DB 이름 확인
2. 기본 `watercare`라면 즉시 중단
3. 새 빈 격리 DB 생성
4. Migration 적용
5. dry-run부터 재시작
6. sequence까지 동일해야 하면 dry-run DB와 실제 적재 DB 분리

---

## 12. 팀원별 인계

| 순서 | 대상 | 최지용 전달 내용 | 다음 행동 | 완료 증거 |
| ---: | --- | --- | --- | --- |
| 1 | 윤승혁(PM) | `jiyong` SHA, Migration 10개, v1.3, 전체 Gate·Smoke 결과 | 비작성자 검토 후 `main` 병합 | PM `main` 40자리 SHA |
| 2 | 김은진 | PM SHA, DB 대상·백업·Migration·Seed 2회 절차 | 새 Pull·빈/로컬 PostgreSQL에서 독립 재현 | 명령·Exit code·테스트·DB 결과 |
| 3 | 한예나 | Base URL, CORS, Auth Route, Migration 완료 범위 | 자기 로컬 DB 적용 후 실제 Web API 호출 | Network·오류 처리·Web 테스트 |
| 4 | 양정현 | Base URL, JWT·권한·오류·문의 Runtime 경계 | 자기 로컬 DB 적용 후 Mobile 소비 확인 | Mobile 요청·응답 호환 결과 |
| 5 | 이동윤 | Backend 8000, 대체 8001 충돌 가능성, AI Schema 경계 | AI Port·환경 확정 후 Adapter 검사 | AI 단독 실행·Schema·Smoke |

팀원이 회신할 양식:

```text
[Backend·PostgreSQL 재현 결과]
- 담당자:
- Branch:
- Commit SHA(40자리):
- OS:
- Python:
- pip:
- 대상 DB 이름:
- PostgreSQL:
- 백업 필요 여부:
- pg_dump:
- pg_restore --list:
- Migration plan:
- migrate --check:
- Backend 전체 테스트:
- Health:
- Auth Smoke:
- 실행 Port:
- Exit code:
- 미완료·오류:
- Correlation ID(오류 시):
```

Password, Token, 전체 DSN, 실제 고객정보는 넣지 않는다.

---

## 13. 팀 공유 메시지 예시

```text
[Backend 환경·PostgreSQL 실행 매뉴얼 v1.3 공유]

1. PM이 병합한 main 40자리 SHA를 먼저 확인해 주세요.
2. docs/individual/jiyong/manuals/
   20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md를
   기준으로 실행해 주세요.
3. 새 PC는 5장, 기존 PC의 새 Pull은 6장, 단순 재시작은 7장을
   사용합니다.
4. 팀원은 makemigrations를 실행하지 않고, 확정된 Migration을 자기
   로컬 DB에 migrate로 적용합니다.
5. 공용 DB는 지정된 담당자 한 명만 Migration을 적용합니다.
6. 기본 watercare에는 Demo Seed 네 종류만 사용하고 합성 Importer는
   빈 격리 DB에서만 실행합니다.
7. .env·.venv·Password·Token·DB Volume은 공유하지 않습니다.
8. 실패 시 Commit SHA·대상 DB·명령·Exit code·첫 오류를 전달해 주세요.
```

---

## 14. 최종 체크리스트

- [ ] PM이 전달한 40자리 `main` SHA를 확인했다.
- [ ] Python 3.13.13·pip 26.0.1 환경을 재현했다.
- [ ] `.env`와 `.venv`가 Git에서 제외됐다.
- [ ] Docker PostgreSQL 16.14가 `healthy`다.
- [ ] Migration 대상 DB 이름을 확인했다.
- [ ] DB Writer를 중단했다.
- [ ] 기존 데이터 DB의 `pg_dump`를 만들었다.
- [ ] `pg_restore --list`와 실제 복원의 차이를 구분했다.
- [ ] `migrate --plan`을 검토했다.
- [ ] 기존 9개와 `workflow.0003`이 모두 `[X]`다.
- [ ] `changed_at` Legacy 11건 보정 범위를 기록했다.
- [ ] 기본 DB에는 Demo Seed 네 종류만 두 번 실행했다.
- [ ] 합성 Importer를 기본 DB에서 실행하지 않았다.
- [ ] `--full --postgresql`의 SQLite 테스트와 PostgreSQL 검사를 구분했다.
- [ ] Backend 전체 Gate가 Exit code 0이다.
- [ ] 실제 Port에서 Health가 HTTP 200이다.
- [ ] Auth Smoke의 DB Token 변경 특성을 이해하고 `PASSED`를 확인했다.
- [ ] Django 서버를 `Ctrl+C`로 정상 종료했다.
- [ ] 비밀값 없이 팀 인계 결과를 남겼다.

---

## 15. v1.1·v1.2 통합 버전 이력

> 2026-07-30부터 이 파일만 공유 패키지 인계서의 단일 원본으로
> 유지한다. v1.1·v1.2의 현재 유효한 절차는 0~14장에 흡수했으며,
> 아래 수치는 당시 검증 증거다. 실행 명령이나 정책이 충돌하면
> 0~14장의 현재 절차와 실제 코드·기계 검증 결과를 우선한다.

### 15.1 문서 계보

| 버전 | 날짜 | 통합 상태 | 핵심 변경 |
| --- | --- | --- | --- |
| v1.0 | 2026-07-27 | v1.3에 통합 | `.env`·PostgreSQL·Migration·Seed·Smoke·공유 경계 수립 |
| v1.1 | 2026-07-28 | v1.3에 통합 | Python 3.13.13·pip 26.0.1·constraints·bootstrap·VS Code·안전 재생성·일상 실행 추가 |
| v1.2 | 2026-07-29 | v1.3에 통합 | requirements fingerprint·Docker·PostgreSQL·Health·Auth 실검증과 오류 복구·Web 실제 API 절차 상세화 |
| v1.3 | 2026-07-29 | `CURRENT_SINGLE_SOURCE` | 기본 DB Migration 9개와 `workflow.0003`, Legacy `changed_at` 11건 보정, 397 테스트, Port 8001 Auth Smoke, Writer 중단·백업·복원 검증·Importer 격리 원칙 반영 |
| v1.3 단일화 | 2026-07-30 | `CURRENT_SINGLE_SOURCE` | v1.1·v1.2 별도 파일 제거, 유효 절차·검증 스냅샷·정책 변경 이력을 이 문서에 통합 |

### 15.2 이전 버전 내용의 현재 위치

| 이전 버전 내용 | 현재 단일 원본 위치 |
| --- | --- |
| `.venv`·`.env`·Docker·Django·검사기 역할 구분 | 0.1 |
| 공유 대상과 Secret·Token·Volume 제외 원칙 | 0.2 |
| Python·pip·constraints·bootstrap과 환경 검사 | 5.3 |
| 안전한 `.venv` 재생성·자동 복원·백업 유지 | 11.2 |
| PostgreSQL 시작·연결·Migration·Seed | 5.4~5.10 |
| 설치 후 일상 시작·종료·재검증 | 6~8장 |
| Web 실제 Backend 전환과 Mobile 소비 확인 | 10장 |
| 오류별 복구 | 11장 |
| 담당자별 인계와 반환 증거 | 12~14장 |

### 15.3 당시 검증 스냅샷

| 버전 | 환경·테스트 증거 | DB·API 증거 | 현재 해석 |
| --- | --- | --- | --- |
| v1.1 | Python 3.13.13, pip 26.0.1, constraints 31개 일치, 추가 패키지 0개, 새 `.venv`에서 `239 passed` | PostgreSQL·Migration·Seed·HTTP 결과는 2026-07-27 기록, 당시 Model 2/32·Health 1개·Auth 4개 | 최초 서비스별 환경 재현 기준. 제3자 재현·PM 병합 증거는 당시 미확인 |
| v1.2 | fingerprint `60a914129e00735559d54b1429d76933cee4817a1c62bc968dd8808ab085c758`, `353 passed` | PostgreSQL 16.14 `healthy`, 미적용 Migration 없음, Health·Auth `PASSED`, OpenAPI 9개 중 Runtime 7개 | 2026-07-29 당시 기준. Web 22 Suite 중 14개 통과·8개는 `inquiry_id/public_id` 정합화 대기 |
| v1.3 | 3장의 현재 실측 참조 | Migration 10개, Legacy `changed_at` 11건 보정, Port 8001 Smoke | 현재 실행 기준. 고정 테스트 수보다 Exit code 0과 실패 0을 우선 |

과거 테스트 수치는 해당 날짜와 Commit의 증거일 뿐 현재 합격 기준으로
재사용하지 않는다. 이후 테스트가 추가되면 개수는 달라질 수 있다.

### 15.4 안전 정책 변경 기록

| 항목 | v1.1·v1.2 당시 기준 | 현재 v1.3 기준 |
| --- | --- | --- |
| 새 Migration 발견 | 일상 실행 중 적용 절차로 이어질 수 있음 | 서버를 시작하지 않고 대상 DB·Writer·백업·Plan 절차로 복귀 |
| Migration 대상 | 로컬 PostgreSQL 중심 | DB 이름·사용자·활성 Session·Writer를 먼저 확인 |
| 백업 | 선택적 설명 | 기존 데이터 DB는 `pg_dump`와 백업 구조 검사를 먼저 수행 |
| `.venv` 교체 | 안전 재생성 도입 | 자동 복원 경로를 확인하고 전체 Gate·Smoke 전까지 백업 유지 |
| 합성 Importer | 별도 실행 경계가 없음 | 기본 `watercare` 실행 금지, 빈 격리 DB 전용 |
| Smoke Port | 8000 중심 | 실제 Port 8000·8001과 AI Port 충돌을 구분 |
| 공용 기준 | 작성자 로컬 검증 중심 | PM이 병합해 전달한 `main` 40자리 SHA 우선 |
