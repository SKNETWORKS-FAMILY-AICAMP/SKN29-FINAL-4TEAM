# Django·PostgreSQL 로컬 개발환경 설치·실행·복구 가이드

> 기준일: 2026-08-02
> 유지 책임: Backend·Database 담당
> 대상: Windows PowerShell, Django Backend, PostgreSQL `waterbridge/public`
> 원칙: 저장소 상대경로만 사용하고 `.env`·Password·Token·DSN·dump를 Git에 추가하지 않는다.

## 1. 이 문서의 책임

이 문서는 팀원이 새 PC 또는 갱신된 저장소에서 다음 작업을 반복할 때
사용하는 현행 실행 절차다.

1. Backend Python 환경 설치·동기화
2. 로컬 PostgreSQL 시작·연결 확인
3. Migration 계획·적용·누락 확인
4. Demo Seed 2회 멱등성 검증
5. 전체 환경·T-005·회귀 검증
6. Django 서버 실행·중지
7. 실패 계층 분리와 승인된 복구

Python 환경 생성·검사·안전 재생성 절차는 이 문서의 11장을 따른다.
현행 실행 명령에는 `waterbridge` 기준만 사용한다. 32개 테이블 구현
근거는
[T-005 테이블 구현 및 변경 이력](../데이터베이스/Django_PostgreSQL_테이블_구현_변경이력_20260730.md),
현재 DB 전환·백업·Restore·최종 수치는
[T-005 워터브리지 PostgreSQL 통합 검증 보고서](../데이터베이스/PostgreSQL_통합검증_보고서_20260731.md)를
따른다.

## 2. 단일 원본

| 확인 목적 | 원본 |
| --- | --- |
| Backend 설치·실행 개요 | [Backend README](../../../../backend/README.md) |
| Python 버전 | [`backend/.python-version`](../../../../backend/.python-version) |
| Python 의존성 | [`backend/requirements`](../../../../backend/requirements) |
| 환경 변수 이름 | [`backend/.env.example`](../../../../backend/.env.example) |
| PostgreSQL 서비스 | [`docker-compose.yml`](../../../../docker-compose.yml) |
| DB 스키마 변경 절차 | [T-005 데이터베이스 스키마 변경 실행 가이드](../데이터베이스/Django_PostgreSQL_스키마_변경_가이드.md) |
| T-005 기계 계약 | [T-005 Database 패키지](../../../database/t-005/README.md) |
| API 기계 계약 | [`contracts/api/openapi.yaml`](../../../../contracts/api/openapi.yaml) |

설명 문서와 기계 계약이 충돌하면 `contracts/**`와 Django Migration을
우선한다. PostgreSQL 스키마를 수동 SQL로 맞추지 않는다.

## 3. 실행 전 안전 확인

저장소 루트에서 실행한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
git status --short
git branch --show-current
git rev-parse HEAD
```

다음 조건을 확인한다.

- 작업 중인 변경을 임의로 폐기하지 않는다.
- `backend/.env`는 존재하지만 Git에 추적되지 않는다.
- 기본 개발 DB 이름은 `waterbridge`, Schema는 `public`이다.
- Docker Volume `watercare-postgres-data`는 이름을 바꾸거나 삭제하지
  않는다.
- 기존 데이터 DB에 Migration을 적용하기 전 Backend·Importer·Job 등
  Writer를 중지하고 백업·대상 DB·Migration plan을 확인한다.

환경 파일이 없는 최초 설치에서만 예시를 복사하고 각 자리표시자를
로컬 값으로 바꾼다. 실제 값을 문서·Issue·PR·채팅에 붙이지 않는다.

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

필수 이름은 다음과 같다.

- `DJANGO_SETTINGS_MODULE`
- `DJANGO_SECRET_KEY`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `DJANGO_DEMO_LOGIN_ENABLED`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `POSTGRES_HOST`, `POSTGRES_PORT`

## 4. 새 PC 최초 설치

### 4.1 Python 환경 생성

호스트 Python은 [`backend/.python-version`](../../../../backend/.python-version)과
같아야 한다. 저장소 공용 Bootstrap이 `backend/.venv`를 만들고 고정
의존성을 설치·검증한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
python .\scripts\development\bootstrap.py --service backend
if ($LASTEXITCODE -ne 0) {
    throw 'Backend 가상환경 생성 실패'
}
```

기존 `.venv`의 Python 버전이 다른 경우 실행 중인 `.venv` 밖의
기준 Python으로 다음 명령을 사용한다.

```powershell
python .\scripts\development\bootstrap.py --service backend --recreate
if ($LASTEXITCODE -ne 0) {
    throw 'Backend 가상환경 안전 재생성 실패'
}
```

가상환경을 수동 복사하거나 Git에 추가하지 않는다. 문제 분석은 이 문서
11장 `Python 가상환경 재현·복구` 절차를 따른다.

### 4.2 PostgreSQL 시작

```powershell
Set-Location (git rev-parse --show-toplevel)

docker compose --env-file .\backend\.env up -d postgres
if ($LASTEXITCODE -ne 0) {
    throw 'PostgreSQL 시작 실패'
}

docker compose --env-file .\backend\.env ps postgres
```

`healthy`가 되기 전에 Migration·Seed·테스트를 시작하지 않는다.

### 4.3 연결과 Migration 계획

```powershell
Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python ..\scripts\database\check_postgresql_connection.py
if ($LASTEXITCODE -ne 0) {
    throw 'PostgreSQL 연결 확인 실패'
}

& $python manage.py showmigrations
& $python manage.py migrate --plan
```

기존 데이터 DB에서 미적용 Migration이 보이면 자동 적용하지 않는다.
현재 DB 이름·Host·Port, Writer 중지, 백업과 plan을 확인한다. 새 빈
로컬 DB이거나 적용 승인을 받은 경우에만 실행한다.

```powershell
& $python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) {
    throw 'Migration 적용 실패'
}

& $python manage.py migrate --check
if ($LASTEXITCODE -ne 0) {
    throw '미적용 Migration 존재'
}
```

이미 적용된 Migration 파일을 수정하거나 삭제하지 않는다. 변경은 새
번호 Forward Migration으로 누적한다.

## 5. Demo Seed 반복 검증

기본 `waterbridge`에는 아래 5종 Demo Seed만 실행한다. 각 명령은
`update_or_create` 기반이며 두 번 실행해 두 번째 실행의 비의도 신규
생성이 0인지 확인한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

foreach ($round in 1..2) {
    Write-Host "Demo Seed round $round"
    & $python manage.py seed_common_codes
    if ($LASTEXITCODE -ne 0) { throw '공통코드 Seed 실패' }

    & $python manage.py seed_demo_accounts
    if ($LASTEXITCODE -ne 0) { throw 'Demo Account Seed 실패' }

    & $python manage.py seed_demo_products
    if ($LASTEXITCODE -ne 0) { throw 'Demo Product Seed 실패' }

    & $python manage.py seed_demo_subscriptions
    if ($LASTEXITCODE -ne 0) { throw 'Demo Subscription Seed 실패' }

    & $python manage.py seed_demo_care_records
    if ($LASTEXITCODE -ne 0) { throw 'Demo Care Seed 실패' }
}
```

`BLOCKED_CONTRACT_MAPPING`은 미승인 코드 매핑을 숨기지 않는 정상
경고다. 경고를 없애기 위해 값을 임의 대문자화하거나 계약을 추론하지
않는다.

기본 `waterbridge`와 legacy 기본명 `watercare`에서는
`import_synthetic_handoff`와 `--dry-run`을 실행하지 않는다. dry-run도
Sequence에 영향을 줄 수 있다. 367건 Importer는 새 빈 격리 PostgreSQL
전용이며 정확한 생성·Replay·정리 절차는
[통합 검증 보고서](../데이터베이스/PostgreSQL_통합검증_보고서_20260731.md)의
격리 Importer 절을 따른다.

## 6. 전체 검증

### 6.1 한 번에 실행하는 환경 Gate

```powershell
Set-Location (git rev-parse --show-toplevel)

& .\backend\.venv\Scripts\python.exe `
  .\scripts\development\check_environment.py `
  --service backend `
  --full `
  --postgresql
if ($LASTEXITCODE -ne 0) {
    throw 'Backend 전체 환경 Gate 실패'
}
```

이 Gate는 Python·패키지·Django check·Migration drift·전체 pytest·
PostgreSQL 연결·미적용 Migration·가상환경 Git 제외를 확인한다.

### 6.2 T-005 Gate

```powershell
Set-Location (git rev-parse --show-toplevel)

& .\backend\.venv\Scripts\python.exe `
  .\scripts\database\validate_t005_schema.py
if ($LASTEXITCODE -ne 0) {
    throw 'T-005 Schema 검증 실패'
}

& .\backend\.venv\Scripts\python.exe `
  .\scripts\database\audit_t005_implementation_readiness.py
if ($LASTEXITCODE -ne 0) {
    throw 'T-005 Runtime 준비도 검증 실패'
}
```

기대 구조는 계약 테이블 `32/32`, 승인 Runtime 지원 테이블 5개,
unknown 0, blocker 0이며 구현 준비 완료(`READY`)다. 이 판정은 공식
리뷰 완료를 의미하지 않는다.

### 6.3 문서·공백 Gate

```powershell
git diff --check
if ($LASTEXITCODE -ne 0) {
    throw 'Git whitespace 검사 실패'
}
```

## 7. 매일 다시 실행

환경과 Migration이 이미 준비된 PC에서는 다음 순서만 반복한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres

Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python ..\scripts\database\check_postgresql_connection.py
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL 연결 실패' }

& $python manage.py migrate --check
if ($LASTEXITCODE -ne 0) {
    throw '미적용 Migration 존재: plan·백업·승인 확인 필요'
}

& $python manage.py runserver 127.0.0.1:8000 --noreload
```

Health는 `http://127.0.0.1:8000/health`에서 확인한다. Demo Login을
사용할 때만 로컬 `.env`의 `DJANGO_DEMO_LOGIN_ENABLED`를 활성화하며,
운영·공유 환경에서 임의로 활성화하지 않는다.

서버는 실행 터미널에서 `Ctrl+C`로 중지한다. PostgreSQL 데이터를
보존한 중지는 저장소 루트에서 다음 명령만 사용한다.

```powershell
docker compose --env-file .\backend\.env stop postgres
```

## 8. 오류별 복구

| 증상 | 먼저 확인 | 안전한 조치 |
| --- | --- | --- |
| `.venv` 없음 | `backend/.python-version`과 호스트 Python | Bootstrap 재실행 |
| Python 버전 불일치 | `.venv` 밖의 기준 Python | `bootstrap.py --recreate` |
| PostgreSQL 연결 실패 | Container health·환경 변수 이름·Host·Port | `docker compose ps`, 연결 검사 재실행 |
| `migrate --check` 실패 | 대상 DB·Writer·백업·`migrate --plan` | 승인 후 `migrate --noinput`; 수동 SQL 금지 |
| Migration rollback 실패 | 적용 Migration 파일 in-place 변경 여부 | 파일 원복 후 새 Forward Migration; 사고 보고서 확인 |
| Seed UNIQUE 충돌 | Upsert 자연키·부모 FK·기존 공개 UUID | 원인 테이블을 조회하고 Seed 로직 수정; 임의 삭제 금지 |
| `BLOCKED_CONTRACT_MAPPING` | 미승인 코드 Mapping | 정상 경고로 유지, 계약 결정 요청 |
| Importer 실행 차단 | DB명이 `waterbridge` 또는 `watercare`인지 | 새 빈 격리 DB에서만 실행 |
| Demo Login 401 | Demo Login 설정·합성 고객 Alias·Seed | 설정과 Demo Login 가이드 확인 |
| 테스트 수 불일치 | 같은 Commit·설정·DB인지 | 실패 테스트와 환경을 기록해 재실행 |

Migration 불변성 문제는
[T-005 Migration 불변성 사고 및 복구 보고서](../데이터베이스/PostgreSQL_마이그레이션_불변성_사고_복구_보고서.md),
Demo 로그인은
[합성 고객 Demo 로그인 가이드](../인증_권한/Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md)를
참고한다.

## 9. 백업과 복구 경계

기존 데이터 DB에 Migration을 적용하기 전에는 Writer를 중지하고
PostgreSQL custom-format dump를 만든 뒤 파일 크기·SHA-256·
`pg_restore --list`를 확인한다. dump는 저장소 밖 또는 Git 제외
경로에 보관한다.

복구는 다음 원칙을 따른다.

1. 단순 테스트 실패만으로 rollback하지 않고 환경·Migration·Seed·
   Importer·API 계층을 먼저 분리한다.
2. DB 이름 전환이 원인이라고 확인된 경우에만 Writer와 Session을
   모두 중지하고 PM 승인 후 이름 rollback을 수행한다.
3. Dump Restore는 SHA-256이 일치하는 파일로 **새 빈 DB**에 실행한다.
4. 기존 `waterbridge`에 dump를 덮어쓰지 않는다.
5. Restore 뒤 Migration·T-005·Seed·전체 회귀와 표본 행 수를 다시
   검증한다.
6. `docker compose down -v`와 Volume 삭제는 복구 절차가 아니다.

실제 검증된 백업·Restore 증거와 승인 전용 명령은
[통합 검증 보고서](../데이터베이스/PostgreSQL_통합검증_보고서_20260731.md)의
백업·Rollback 절을 따른다.

## 10. 인계 체크리스트

- [ ] 저장소 Commit과 Branch를 기록했다.
- [ ] `.env`·Password·Token·DSN·dump를 공유하지 않았다.
- [ ] Python 버전과 `backend/.venv`를 재현했다.
- [ ] PostgreSQL `waterbridge/public` 연결을 확인했다.
- [ ] Migration plan을 검토하고 미적용 0을 확인했다.
- [ ] Demo Seed 5종을 두 번 실행하고 2회차 신규 0을 확인했다.
- [ ] 기본 DB에서 Importer와 dry-run을 실행하지 않았다.
- [ ] 전체 환경 Gate와 T-005 구현 준비 완료(`READY`, `32/32`)를 확인했다.
- [ ] 실패가 있으면 명령·Exit code·설정 이름·대상 DB를 기록했다.
- [ ] 복구가 필요하면 Writer·백업·Session·승인을 먼저 확인했다.
- [ ] 비작성자 재현과 PM 리뷰 전 공식 완료로 표기하지 않았다.

## 11. Python 가상환경 재현·안전 재생성

Backend Python 환경의 단일 위치는 `backend/.venv`다. 저장소 루트에
공용 `.venv`를 만들거나 다른 서비스의 환경을 복사하지 않는다.

| 목적 | 기준 파일·명령 |
| --- | --- |
| Python 버전 | `backend/.python-version` — Python 3.13 계열 |
| 직접 의존성 | `backend/requirements/base.txt`, `backend/requirements/local.txt` |
| 간접 의존성 | `backend/requirements/constraints-py313.txt` |
| 생성·동기화 | `python .\scripts\development\bootstrap.py --service backend` |
| 빠른 검사 | `python .\scripts\development\check_environment.py --service backend` |
| 전체·PostgreSQL 검사 | `python .\scripts\development\check_environment.py --service backend --full --postgresql` |
| 안전 재생성 | `python .\scripts\development\bootstrap.py --service backend --recreate` |

`--recreate`는 기존 환경을 즉시 삭제하지 않고
`backend/.runtime/venv-backups/<timestamp>/.venv`로 이동한 뒤 새 환경을
생성한다. 생성·설치·검사가 실패하면 새 환경을 완료본으로 취급하지
않는다. `.venv`, `.runtime`, `.env`는 Git 공유 대상이 아니다.

재현 순서는 다음과 같다.

1. 저장소 루트에서 Python 버전을 확인한다.
2. `bootstrap.py --service backend`로 생성 또는 동기화한다.
3. 빠른 환경 검사를 통과시킨다.
4. PostgreSQL을 기동한 뒤 `--full --postgresql`을 실행한다.
5. Migration·Seed·Health·Auth·업무 API 검증으로 이동한다.
6. 실행 Python, 명령, Exit code, 후보 SHA를 기록한다.

Python 버전이나 requirements fingerprint가 다를 때만 안전 재생성을
사용한다. 폴더 수동 삭제, 다른 PC의 `.venv` 복사, 시스템 Python과
가상환경 패키지 혼용은 금지한다.

## 12. 유지보수 원칙과 완료 조건

- Python 버전은 `backend/.python-version`, 의존성은
  `backend/requirements/**`, 환경 변수 이름은 `backend/.env.example`,
  PostgreSQL 서비스는 `docker-compose.yml`을 source of truth로 삼는다.
- Model·Migration·Seed·테이블 수는 이 문서에 임의로 고정하지 않고
  T-005 기계 계약과 Django Migration, 검증 보고서의 같은 기준 시점
  증거를 따른다.
- 명령·스크립트·환경 변수 이름·DB 이름이 바뀌면 관련 source of truth와
  이 실행 절차를 같은 변경 묶음에서 갱신한다.
- 새 환경에서 Python 검사, PostgreSQL 연결, Migration, Seed 2회,
  환경 Gate, T-005 Gate, Health·Auth·업무 API 검증을 통과해야 작성자
  재현 완료로 표시한다.
- `.env`·비밀값·dump 비공유, 복구 전 Writer·Session·백업 확인,
  비작성자 재현과 PM 리뷰가 충족된 뒤에만 팀 기준선 재현 완료로
  표시한다. 보조 상태 코드 `READY`는 이 완료 조건을 대체하지 않는다.
