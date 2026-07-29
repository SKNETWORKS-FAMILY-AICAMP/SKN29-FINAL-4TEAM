# 최지용 Django·PostgreSQL 공유 패키지 인계서 v1.2

> 문서 상태: `SUPERSEDED`
> 현재 실행 기준: [Django·PostgreSQL 공유 패키지 인계서 v1.3](<./20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md>)

> 기준일: 2026-07-29
> 명령 실행 기준: 별도 표시가 없으면 저장소 루트
> 목적: 팀원이 Git Pull 후 Backend 환경을 재현하고 PostgreSQL·Django·API를 같은 순서로 검증하도록 지원
> 실행 원칙: `작업 → 즉시 검증 → 증거 확인 → 다음 작업`

## 0. 먼저 읽을 결론

이 프로젝트의 로컬 Backend는 한 도구가 전부 실행하는 구조가 아니다.
각 구성요소의 책임은 다음과 같이 분리돼 있다.

| 구성요소 | 담당하는 일 | 담당하지 않는 일 |
| --- | --- | --- |
| `backend/.venv` | Python Interpreter와 Django·테스트 패키지 격리 | Docker 실행, `.env` 생성, Migration·Seed 자동 적용 |
| `backend/.env` | Django·PostgreSQL 연결값과 로컬 비밀값 보관 | Python 패키지 설치, PostgreSQL Process 실행 |
| 루트 `docker-compose.yml` | PostgreSQL 16.14 Container 실행·상태 확인 | Django·Web Container 실행 |
| Django `runserver` | `127.0.0.1:8000`에서 Backend HTTP API 실행 | PostgreSQL 자동 시작 |
| `check_environment.py` | Python·패키지·fingerprint·Django·테스트·PostgreSQL 검사 | Seed와 실제 HTTP API 호출 |
| `check_backend_auth.py` | 실행 중인 Backend의 Health·CORS·Auth 실제 HTTP 검사 | Web 화면 전체 E2E 검사 |

따라서 `.venv`만 복사하거나 활성화해서는 PostgreSQL과 API가 실행되지
않는다. 각 PC는 `.venv`를 직접 재현하고, `.env`를 준비한 뒤 Docker
PostgreSQL과 Django를 순서대로 실행해야 한다.

팀에 공유하는 대상은 `.venv` 폴더가 아니라 다음 재현 입력이다.

- Python 버전 파일
- requirements와 constraints
- bootstrap·검증 스크립트
- `.env.example`
- Compose
- 이 인계서와 검증 결과

실제 `.env`, `.venv`, Token, PostgreSQL Password와 로컬 DB Volume은
공유하거나 Git에 Commit하지 않는다.

## 1. 책임·협업·완료 기준

| 항목 | 내용 |
| --- | --- |
| 작성·유지 책임 | 최지용 — Backend·DB 실행 기준, 문서와 재현 명령 갱신 |
| Backend·API OWNER | 최지용 — ERD·테이블·API 명세, Django·PostgreSQL 구현 |
| 통합·병합 | 윤승혁(PM) — 비작성자 검토 후 `main` 통합 |
| 재현·통합 QA | 김은진 — 새 Pull 환경에서 Python·Docker·DB·Migration·Smoke 재현 |
| Web 소비 확인 | 한예나 — 실제 Backend URL·Auth·CORS·오류 응답 소비 |
| Mobile 소비 확인 | 양정현 — Backend URL·JWT·권한·오류 응답 소비 |
| AI 경계 확인 | 이동윤 — Backend↔AI URL·Schema·오류·추적 계약 소비 |

문서 작성과 Backend 구현은 최지용의 주담당 작업이다. 팀원 검토는
작성 허가를 받는 절차가 아니라, 다른 PC 재현과 서비스 간 호환성을
확인하는 후속 품질 게이트다.

완료는 “문서를 읽었다”가 아니라 다음 증거가 남았을 때 판정한다.

1. 사용한 Commit SHA
2. 실행한 명령
3. Exit code
4. 테스트 또는 Smoke 결과
5. 불일치가 있으면 실제 오류와 담당 영역

## 2. 현재 단일 원본

| 기준 | 파일 |
| --- | --- |
| Backend 실행 원본 | [Backend](<../../../../backend/>) |
| Backend 실행 안내 | [Backend README](<../../../../backend/README.md>) |
| Python | [`.python-version`](<../../../../backend/.python-version>) |
| 직접 의존성 | [`base.txt`](<../../../../backend/requirements/base.txt>), [`local.txt`](<../../../../backend/requirements/local.txt>) |
| 고정 해상도 | [`constraints-py313.txt`](<../../../../backend/requirements/constraints-py313.txt>) |
| 환경 생성·동기화 | [`bootstrap.py`](<../../../../scripts/development/bootstrap.py>) |
| 환경·회귀 검사 | [`check_environment.py`](<../../../../scripts/development/check_environment.py>) |
| 환경변수 예시 | [`.env.example`](<../../../../backend/.env.example>) |
| PostgreSQL Compose | [`docker-compose.yml`](<../../../../docker-compose.yml>) |
| DB 연결 검사 | [`check_postgresql_connection.py`](<../../../../scripts/database/check_postgresql_connection.py>) |
| 실제 Health·Auth Smoke | [`check_backend_auth.py`](<../../../../scripts/smoke/check_backend_auth.py>) |
| API 현재 지원 범위 | [API Runtime 구현 상태](<../../../api/runtime_implementation_status.md>) |
| 기계 API 계약 | [OpenAPI](<../../../../contracts/api/openapi.yaml>) |
| 환경 설계·복구 | [Backend `.venv` 재현 가이드](<../technical/backend/backend_venv_reproducibility_guide.md>) |
| API 계약 검증 | [Backend API 계약 정합화 검증보고서](<./20260729_최지용_Backend_API_계약_정합화_검증보고서_v1.0.md>) |

API는 현재 OpenAPI Operation 9개 중 Django Runtime 7개를 지원한다.
실제 Runtime은 Health 1개, Auth 4개, 문의 생성 1개, 문의 취소 1개다.
나머지 2개는 OpenAPI에만 있는 미구현 범위이므로 Web·Mobile이 구현
API로 호출하지 않는다.

## 3. 정상 판정 기준

2026-07-29 작성자 PC에서 같은 작업 순서로 확인한 기준은 다음과 같다.

| 항목 | 정상 기준 | 2026-07-29 결과 |
| --- | --- | --- |
| Python | `3.13.13` | 통과 |
| pip | `26.0.1` | 통과 |
| constraints | 31개 모두 일치 | 통과 |
| 누락·버전 불일치 | 각각 0개 | 통과 |
| constraints 밖 추가 패키지 | pip 제외 0개 | 통과 |
| requirements fingerprint | 저장값과 현재 입력값 동일 | `60a914129e00735559d54b1429d76933cee4817a1c62bc968dd8808ab085c758` |
| `pip check` | broken requirement 없음 | 통과 |
| Django System Check | 오류 0건 | 통과 |
| Migration drift | 새 Migration 필요 없음 | 통과 |
| Backend 전체 테스트 | Exit code 0 | `353 passed` |
| Docker daemon | Client·Server 모두 응답 | 통과 |
| PostgreSQL Container | `running`, `healthy` | 통과 |
| PostgreSQL | 16.14, UTC, 읽기 전용 연결 성공 | 통과 |
| 적용 Migration | 미적용 Migration 없음 | 통과 |
| Health·Auth Smoke | JSON `status=PASSED`, Exit code 0 | 통과 |

`353 passed`는 이 날짜와 Commit의 실행 증거다. 이후 테스트가 추가되면
개수는 달라질 수 있다. 장기 정상 기준은 고정 숫자가 아니라 Exit code
`0`, 실패 `0`, Migration drift 없음이다.

## 4. 어떤 절차를 선택해야 하는가

| 현재 PC 상태 | 실행할 절차 |
| --- | --- |
| 처음 Pull했고 `.env`·`.venv`가 없음 | 5장 전체 |
| `.env`는 있고 `.venv`만 없음 | 5.2부터 진행 |
| `.env`·`.venv`가 모두 있음 | 6장 일상 실행 |
| fingerprint 불일치 | 7.1 절차 |
| Python 버전 또는 `.venv` 손상 | 7.2 안전 재생성 |
| Backend만 검증 | 5.5~5.8 |
| Web에서 실제 Backend 호출까지 확인 | Backend 통과 후 8장 |

## 5. 새 PC 최초 구성

### 5.1 `.env` 준비

저장소 루트에서 실행한다.

```powershell
if (Test-Path .\backend\.env) {
    Write-Host "backend/.env가 이미 있으므로 기존 비밀값을 유지합니다."
} else {
    Copy-Item .\backend\.env.example .\backend\.env
    Write-Host "backend/.env를 생성했습니다. replace-with-* 값을 교체하세요."
}
```

이 단계의 목적은 공개 가능한 예시를 로컬 실행 설정으로 복사하는
것이다. 이미 `.env`가 있으면 위 명령은 덮어쓰지 않으므로 팀원이 전달한
비밀값을 잃지 않는다. 새로 생성한 경우 다음 두 `replace-with-*` 값은
각 PC에서 새 값으로 교체한다.

```text
DJANGO_SECRET_KEY
POSTGRES_PASSWORD
```

`.env`에는 총 18개 키가 있어야 한다. 실제 값은 채팅·문서·화면 캡처·
Git Diff·오류 보고에 기록하지 않는다.

확인:

```powershell
git check-ignore -v .\backend\.env
```

정상 기준은 `backend/.gitignore` 규칙이 출력되는 것이다. 아무것도
출력되지 않으면 `.env`를 Commit하지 말고 Git 제외 규칙부터 확인한다.

### 5.2 Python과 `.venv` 재현

저장소 루트에서 실행한다.

```powershell
python --version
python .\scripts\development\bootstrap.py --service backend
```

첫 번째 명령은 현재 PowerShell의 Python을 확인한다. 정확히
`Python 3.13.13`이어야 한다. 다른 버전이면 bootstrap을 반복하지 말고
Python 실행 경로부터 수정한다.

두 번째 명령은 다음 순서로 동작한다.

1. 실행 Python과 `.python-version` 비교
2. `backend/.venv`가 없으면 생성
3. pip 26.0.1 적용
4. `local.txt`와 constraints로 패키지 동기화
5. 패키지 집합·`pip check`·Django check 실행
6. 현재 requirements fingerprint를 `.venv` 내부 상태파일에 기록

정상 출력의 핵심:

```text
[PASS] Backend 환경 재현 및 경량 검증 완료
python=3.13.13
pip=26.0.1
fingerprint=<64자리 SHA-256>
```

bootstrap은 `.env`, Docker, PostgreSQL, Migration, Seed를 변경하지
않는다. 따라서 bootstrap 통과만으로 DB와 API가 정상이라고 판정하지
않는다.

### 5.3 빠른 환경 검사

```powershell
python .\scripts\development\check_environment.py --service backend
```

이 단계는 서버를 켜기 전에 Python 환경만 빠르게 검사한다.

정상 기준:

```text
failures=0
warnings=0
[PASS] 요청한 환경 점검 완료
```

PowerShell의 Exit code도 확인할 수 있다.

```powershell
$LASTEXITCODE
```

정상은 `0`이다. `1`이면 출력된 첫 번째 `[FAIL]`부터 해결하고 Docker나
Migration으로 넘어가지 않는다.

### 5.4 Docker daemon과 PostgreSQL

먼저 Docker Desktop을 실행한다. 저장소 루트에서 다음 순서로 실행한다.

```powershell
docker version
docker compose --env-file .\backend\.env config --quiet
docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres
```

각 명령의 의미:

| 명령 | 확인하는 것 | 정상 기준 |
| --- | --- | --- |
| `docker version` | Docker Client와 daemon Server 연결 | Client와 Server 정보가 모두 출력 |
| `config --quiet` | Compose와 필수 환경변수 문법 | 출력 없이 Exit code 0 |
| `up -d postgres` | PostgreSQL Container 생성 또는 재사용 | 오류 없이 완료 |
| `ps postgres` | Process·Health·Port | `running`, `healthy`, `127.0.0.1:5432` |

현재 Compose 기준:

| 항목 | 값 |
| --- | --- |
| Image | `postgres:16.14-bookworm` |
| Compose project | `watercare-local` |
| Service | `postgres` |
| Host | `127.0.0.1` |
| Port | `5432` |
| Volume | `watercare-postgres-data` |
| DB timezone | UTC |

### 5.5 전체 Backend와 PostgreSQL 연결 사전 검사

PostgreSQL이 `healthy`인 상태에서 저장소 루트에서 실행한다.

```powershell
python .\scripts\development\check_environment.py --service backend --full
if ($LASTEXITCODE -ne 0) {
    throw "Backend 전체 환경·회귀 검사 실패"
}

Set-Location .\backend
.\.venv\Scripts\python.exe ..\scripts\database\check_postgresql_connection.py
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL 읽기 전용 연결 실패"
}
Set-Location ..
```

첫 번째 명령은 다음을 순서대로 확인한다.

1. `.venv` 격리
2. Python·pip 버전
3. constraints 31개·추가 패키지 0개
4. requirements fingerprint
5. `pip check`
6. Django System Check
7. Migration drift
8. Backend 전체 pytest
9. `.venv` Git 추적 여부

두 번째 명령은 현재 `.env`로 PostgreSQL에 읽기 전용 연결이 가능한지만
확인한다. 새 DB에는 아직 Migration이 적용되지 않았으므로 이 단계에서
`--postgresql` 옵션을 사용하지 않는다. 적용 Migration 검사는 5.6의
Migration 적용 뒤 5.7에서 실행한다.

사전 검사 핵심 판정값이다. 아래 블록은 여러 명령의 실제 전체 출력을
그대로 복사한 것이 아니라, 팀원이 확인할 값을 한 형식으로 정규화한
요약이다. 실제 DB 연결 검사기는 JSON을 출력하며 `server_version`에는
16.14와 배포판 Build 문자열이 함께 표시될 수 있다.

```text
353 passed
status=CONNECTED
vendor=PostgreSQL
server_version=16.14
database_timezone=UTC
failures=0
warnings=0
```

테스트 수가 늘어난 경우 `353`이라는 숫자보다 Exit code `0`과
`failures=0`을 우선한다. `status=CONNECTED`는 DB 접속 성공만 의미하며
Schema 준비 완료를 의미하지 않는다.

### 5.6 Migration과 Demo Seed

전체 검사가 통과한 뒤 실행한다.

```powershell
Set-Location .\backend
$python = ".\.venv\Scripts\python.exe"

& $python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -ne 0) { throw "Migration drift 검사 실패" }

& $python manage.py migrate --plan
if ($LASTEXITCODE -ne 0) { throw "Migration plan 생성 실패" }

& $python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { throw "Migration 적용 실패" }

& $python manage.py migrate --check
if ($LASTEXITCODE -ne 0) { throw "미적용 Migration 검사 실패" }

& $python manage.py seed_demo_accounts
if ($LASTEXITCODE -ne 0) { throw "Accounts Seed 1차 실패" }

& $python manage.py seed_demo_products
if ($LASTEXITCODE -ne 0) { throw "Products Seed 1차 실패" }

& $python manage.py seed_demo_subscriptions
if ($LASTEXITCODE -ne 0) { throw "Subscriptions Seed 1차 실패" }

& $python manage.py seed_demo_care_records
if ($LASTEXITCODE -ne 0) { throw "Care Seed 1차 실패" }

# 같은 순서로 한 번 더 실행해 중복 생성이 없는지 검증한다.
& $python manage.py seed_demo_accounts
if ($LASTEXITCODE -ne 0) { throw "Accounts Seed 2차 실패" }

& $python manage.py seed_demo_products
if ($LASTEXITCODE -ne 0) { throw "Products Seed 2차 실패" }

& $python manage.py seed_demo_subscriptions
if ($LASTEXITCODE -ne 0) { throw "Subscriptions Seed 2차 실패" }

& $python manage.py seed_demo_care_records
if ($LASTEXITCODE -ne 0) { throw "Care Seed 2차 실패" }

Set-Location ..
```

각 명령 다음의 `if`는 Exit code가 `0`이 아닐 때 즉시 중단한다. 앞 단계가
실패했는데 다음 Seed나 서버 실행까지 이어지는 연쇄 오류를 막기 위한
Fail-fast Gate다.

작업 순서의 의미:

| 순서 | 작업 | 이유 |
| ---: | --- | --- |
| 1 | Migration drift 검사 | 코드 변경이 Migration 파일로 남지 않았는지 확인 |
| 2 | Migration plan 확인 | 적용될 작업을 DB 변경 전에 확인 |
| 3 | Migration 적용 | 현재 Commit의 Schema를 PostgreSQL에 반영 |
| 4 | 미적용 Migration 검사 | 실제 적용 누락이 없는지 확인 |
| 5 | 1차 Accounts → Products → Subscriptions → Care Seed | 역할별 Demo 사용자, 제품, 활성 구독, 문의·상담 기초 데이터 준비 |
| 6 | 2차 Seed 재실행 | 같은 자연키의 행이 중복 생성되지 않는 멱등성 검증 |

Seed는 Upsert 방식이어야 한다. 같은 명령을 다시 실행했을 때 중복
행이 생기지 않고 기존 Demo 데이터가 갱신되는지가 정상 기준이다.

### 5.7 최종 PostgreSQL 적용 게이트

Migration과 Seed 2회 실행이 끝난 뒤 저장소 루트에서 실행한다.

```powershell
python .\scripts\development\check_environment.py `
  --service backend `
  --full `
  --postgresql
if ($LASTEXITCODE -ne 0) {
    throw "Backend·PostgreSQL 최종 게이트 실패"
}
```

이 명령은 5.5의 전체 Backend 검사를 다시 실행한 뒤 다음 두 DB 검사를
추가한다.

1. PostgreSQL 읽기 전용 연결
2. `manage.py migrate --check`를 이용한 적용 Migration 누락 검사

정상 기준은 Exit code `0`, `failures=0`, `warnings=0`,
`status=CONNECTED`, 미적용 Migration 없음이다. 이 단계가 실패하면
서버나 Web을 켜지 말고 첫 번째 `[FAIL]`부터 해결한다.

### 5.8 Django 실행과 실제 Health·Auth Smoke

첫 번째 PowerShell에서 실행한다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

이 PowerShell은 Django 서버가 실행되는 동안 계속 사용한다. 다음 문구가
보이면 HTTP 요청을 받을 준비가 된 것이다.

```text
Starting development server at http://127.0.0.1:8000/
```

두 번째 PowerShell에서 저장소 루트 기준으로 실행한다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe ..\scripts\smoke\check_backend_auth.py
```

Health·Auth Smoke가 실제 HTTP로 확인하는 범위:

| 기능 | Method·Path | 정상 기준 |
| --- | --- | --- |
| Liveness | `GET /health` | 200, 빈 본문, Correlation ID |
| CORS | `GET /health` + Origin | 허용 Origin만 응답 Header |
| Demo Login | `POST /api/v1/auth/demo-login` | 200, Token 수명 3600/604800 |
| 현재 사용자 | `GET /api/v1/me` | 200, 민감 필드 없음 |
| Refresh | `POST /api/v1/auth/refresh` | Token rotation, 절대 만료 유지 |
| Refresh Replay | 기존 Refresh 재사용 | 401 |
| Logout | `POST /api/v1/auth/logout` | 폐기 성공 |
| Logout Replay | 폐기 Token 재사용 | 401 |
| 미인증·미허용 Demo | Auth 오류 | 401 `AUTH_REQUIRED` |

최종 정상 출력의 핵심 필드 발췌:

```json
{
  "status": "PASSED",
  "base_url": "http://127.0.0.1:8000"
}
```

실제 Access·Refresh Token은 출력되지 않는다. Exit code `0`까지
확인해야 Health·Auth Smoke 통과다.

검증이 끝나면 첫 번째 PowerShell에서 `Ctrl+C`로 Django 서버를
종료한다. PostgreSQL은 계속 사용할 수 있다.

## 6. 설치 완료 후 일상 실행

`.env`와 `.venv`가 이미 준비된 PC에서는 설치·Seed를 매번 반복하지
않는다.

### 6.1 매일 시작

저장소 루트:

```powershell
docker compose --env-file .\backend\.env up -d postgres
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL 시작 실패" }

docker compose --env-file .\backend\.env ps postgres
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL 상태 확인 실패" }
```

이어서 Migration을 먼저 확인한다. 아래 블록은 미적용 Migration이
있으면 적용하고 다시 검사한다.

```powershell
Set-Location .\backend
$python = ".\.venv\Scripts\python.exe"

& $python manage.py migrate --check
if ($LASTEXITCODE -ne 0) {
    & $python manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw "Migration 적용 실패" }

    & $python manage.py migrate --check
    if ($LASTEXITCODE -ne 0) { throw "미적용 Migration 재검사 실패" }
}
```

두 번째 `migrate --check`까지 통과한 뒤 저장소 루트로 돌아가
PostgreSQL 적용 상태를 검사한다.

```powershell
Set-Location ..
python .\scripts\development\check_environment.py `
  --service backend `
  --postgresql
if ($LASTEXITCODE -ne 0) {
    throw "Backend·PostgreSQL 일상 시작 검사 실패"
}
```

검사가 통과하면 서버를 시작한다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

이 순서를 지키면 Pull로 새 Migration이 들어온 날에도 적용 검사에서
먼저 중단되는 연쇄 오류를 피할 수 있다.

### 6.2 매일 종료

Django를 실행한 PowerShell:

```text
Ctrl+C
```

PostgreSQL 데이터를 보존하며 중지한다. 다음 명령은 저장소 루트에서
실행한다.

```powershell
docker compose --env-file .\backend\.env stop postgres
```

다시 시작:

```powershell
docker compose --env-file .\backend\.env start postgres
```

`docker compose down -v`는 Volume 데이터를 삭제한다. DB 초기화가
명확히 결정되지 않았다면 사용하지 않는다.

## 7. 오류별 복구

### 7.1 requirements fingerprint 불일치

증상:

```text
[FAIL] requirements fingerprint 불일치. bootstrap.py를 실행하세요.
```

의미는 requirements 파일이 반드시 잘못됐다는 뜻이 아니다. 현재
requirements 입력과 `.venv` 내부에 기록된 상태값이 다르다는 뜻이다.

저장소 루트에서 다음 순서로 해결한다.

```powershell
python .\scripts\development\bootstrap.py --service backend
python .\scripts\development\check_environment.py --service backend
```

정상 패키지가 이미 설치돼 있으면 bootstrap은 필요한 동기화와 경량
검사만 수행한다. 정상 기준은 같은 64자리 fingerprint와
`failures=0`, Exit code `0`이다.

### 7.2 Python 불일치 또는 `.venv` 손상

현재 `.venv` 밖의 Python 3.13.13으로 실행한다.

```powershell
python .\scripts\development\bootstrap.py --service backend --recreate
```

기존 환경은 `backend/.runtime/venv-backups/<timestamp>/.venv`로
이동된다. 새 환경이 실패하면 자동 복원된다. 새 환경이 성공해도
`--full --postgresql`과 Health·Auth Smoke가 모두 통과하기 전에는 백업을
삭제하지 않는다.

### 7.3 Docker daemon 또는 named pipe 오류

증상:

```text
failed to connect to the docker API
permission denied ... dockerDesktopLinuxEngine
```

확인:

```powershell
docker context show
docker version
```

Docker Desktop을 실행하고 Linux Container Context가 준비됐는지
확인한다. Client 정보만 있고 Server 정보가 없으면 PostgreSQL 단계로
넘어가지 않는다.

### 7.4 PostgreSQL이 `healthy`가 아님

```powershell
docker compose --env-file .\backend\.env ps postgres
docker compose --env-file .\backend\.env logs --tail 100 postgres
```

오류 보고에는 비밀번호와 전체 DSN을 넣지 않는다. 기존 Volume을 둔 채
`.env`의 비밀번호만 변경하면 DB 내부 사용자 비밀번호는 자동으로
바뀌지 않는다.

### 7.5 8000 포트 충돌

```powershell
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen
$listener
Get-Process -Id $listener.OwningProcess
```

어떤 Process인지 확인하기 전에 강제 종료하지 않는다. 이미 실행 중인
공식 Django라면 새 서버를 하나 더 실행하지 않고 Health·Auth Smoke부터
확인한다.

### 7.6 Health·Auth Smoke 연결 거부

```text
ConnectError
WinError 10061
```

순서대로 확인한다.

1. Django 실행 PowerShell이 종료되지 않았는지 확인
2. `http://127.0.0.1:8000/health` 확인
3. Django가 `config.settings.local`로 실행됐는지 확인
4. PostgreSQL Container가 `healthy`인지 확인
5. Migration 누락이 없는지 확인

## 8. Web 담당자의 실제 API 확인

Backend Health·Auth Smoke 통과는 해당 인증 API가 정상이라는 증거다. Web 화면이
실제로 Backend를 소비한다는 증거는 별도다.

현재 Web 기본값은 Mock이며 Vite proxy가 없으므로, 실제 연동 시
상대경로 `/api/v1`만 사용하면 Vite 5173으로 요청될 수 있다. Web
담당자는 실행 PowerShell에서 다음 값을 명시한다.

```powershell
Set-Location .\web
$env:VITE_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
$env:VITE_USE_MOCK_API = "false"
npm.cmd run dev
```

이 값은 현재 PowerShell Process에만 적용된다. 실제 Backend가
`127.0.0.1:8000`에서 실행 중이어야 한다.

Web 검증 순서:

1. Backend 전체 환경·PostgreSQL 검사 통과
2. Django 서버 실행
3. Backend Health·Auth Smoke 통과
4. Web Mock 비활성화
5. Web Demo Login·`/me`·Refresh·Logout 확인
6. Browser Network에서 요청 URL·상태·응답 Wrapper 확인
7. 불일치가 있으면 Backend와 Web 중 어느 계약이 다른지 기록

2026-07-29 현재 Backend Health·Auth Smoke는 통과했다. Web 자동 테스트는
22개 Suite 중 14개 통과, 8개가 문의 Fixture의 `inquiry_id`와
`public_id` 불일치로 import 단계에서 실패했다. 이 실패는 Backend
환경 실패가 아니라 Web·Data 소비 Schema 정합화 후속 항목이다.

## 9. 공유하지 않는 항목

- `backend/.env`
- `backend/.venv`
- `backend/.runtime`
- Django Secret Key
- PostgreSQL Password
- Access·Refresh Token
- 실제 고객정보
- 개인 DB Dump
- 로컬 PostgreSQL Volume

팀원은 `.venv`를 전달받지 않는다. 각자 같은 Git Commit에서 bootstrap을
실행하고 검증 결과만 공유한다.

## 10. 담당자별 인계 순서

| 순서 | 대상 | 전달 내용 | 다음 행동 | 완료 증거 |
| ---: | --- | --- | --- | --- |
| 1 | 윤승혁(PM) | `jiyong` Commit SHA, v1.2, 현재 Runtime 7·미구현 2 경계 | 문서·공통 Workspace 검토 후 `main` 병합 | 병합 Commit과 공유된 40자리 `main` SHA |
| 2 | 김은진 | Python·constraints·Compose·Migration·Seed·Health·Auth Smoke 전체 순서 | 새 Pull 환경에서 5장 재현 | 사용 Commit·명령·Exit code·테스트 수 |
| 3 | 한예나 | Backend URL, CORS, Auth 4개 Route, Web 실제 연동 8장 | Mock을 끄고 Backend 응답 소비 | Network·오류 처리·Web 테스트 결과 |
| 4 | 양정현 | Backend URL, JWT·권한·오류·문의 Runtime 지원 경계 | Mobile 소비 코드와 실제 계약 비교 | Mobile 요청·응답 호환 결과 |
| 5 | 이동윤 | Backend↔AI 개발 주소와 아직 별도인 AI Runtime | AI Manifest 확정 후 Adapter 검증 | AI 단독 환경·Schema·Smoke 결과 |

팀원은 최지용의 `jiyong` SHA를 최종 공용 기준으로 직접 확정하지 않는다.
PM이 병합한 `main`의 40자리 SHA를 받은 뒤 그 Commit에서 재현한다.

## 11. 팀 공유 메시지 예시

```text
[Backend 환경·PostgreSQL 실행 매뉴얼 v1.2 공유]

1. PM이 공유한 main 40자리 SHA를 Pull해 주세요.
2. docs/individual/jiyong/manuals/
   20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.2.md를
   기준으로 실행해 주세요.
3. 새 PC는 5장, 설치 완료 PC는 6장만 순서대로 실행합니다.
4. 정상 기준은 failures=0, Backend 전체 테스트 Exit 0,
   PostgreSQL healthy, Health·Auth Smoke status=PASSED입니다.
5. .env·.venv·Token은 공유하거나 Commit하지 않습니다.
6. 실패 시 실행한 SHA·명령·Exit code·첫 오류를 담당자에게 전달해 주세요.
```

## 12. 변경 이력

| 버전 | 날짜 | 변경 |
| --- | --- | --- |
| v1.0 | 2026-07-27 | `.env`·PostgreSQL·Migration·Seed·Smoke·공유 경계 통합 |
| v1.1 | 2026-07-28 | Python 3.13.13·pip 26.0.1·constraints·bootstrap·VS Code·안전 재생성·일상 실행 추가 |
| v1.2 | 2026-07-29 | fingerprint 동기화, 353 Backend 테스트, Docker daemon·PostgreSQL 16.14·적용 Migration·Health·Auth Smoke 실검증 반영, 구성요소 역할·명령별 목적·정상 기준·오류 복구·Web 실제 API 확인 순서 상세화 |
