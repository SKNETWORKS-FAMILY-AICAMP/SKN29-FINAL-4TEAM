# 최지용 Django·PostgreSQL 공유 패키지 인계서 v1.1

> 기준일: 2026-07-28
> 문서 상태: `SUPERSEDED` — 현재 실행 기준은 [v1.2](<./20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.2.md>)
> 명령 실행 기준: 저장소 루트
> 목적: 팀원이 Git Pull 직후 동일한 Backend 환경을 재현하도록 지원

## 0. 문서 책임·협업·검토

| 항목 | 내용 |
| --- | --- |
| 문서 상태 | `SUPERSEDED` — 2026-07-28 실행 기록으로 보존하며 현재 기준은 v1.2 |
| 관련 WBS | `T-005`, `T-016`, `T-017` |
| 작성·유지 책임 | 최지용 — 문서와 Backend·DB·Auth 실행 기준 갱신 |
| 산출물/내용 의사결정자 | 최지용 — ERD·테이블·API 명세와 Django·PostgreSQL 구현 기준 |
| 협업 책임 | 윤승혁(PM) — 전체 통합, 김은진 — QA·PostgreSQL·Migration·Seed·인프라 재현, 한예나 — Web 소비, 양정현 — Mobile 소비, 이동윤 — Backend↔AI 연동 소비 |
| 검토 요청 대상 | 김은진의 새 환경 재현 검토와 윤승혁(PM)의 통합 검토를 우선하며, PR에는 작성자가 아닌 팀원 1명 이상의 리뷰가 필요 |
| 검토 상태 | **미요청 또는 증거 미확인** — 이 문서에는 완료된 리뷰의 PR·Issue·Commit 증거가 아직 연결되어 있지 않음 |
| PR 병합 담당 | 윤승혁(PM) — 작성자 본인이 병합 완료를 단정하지 않음 |
| 인계 대상 | 윤승혁(PM), 김은진, 한예나, 양정현, 이동윤 |

여기서 검토는 최지용의 문서 작성이나 구현 착수를 허가하는 선행 승인이
아니다. 공유된 실행 패키지의 통합 가능성, 새 환경 재현성 및 각 소비
영역과의 호환성을 확인하는 절차다.

## 1. 현재 결론

ERD·테이블 명세·API 명세는 최지용이 작성·개정하는 확정 기준선이다.
팀원 확인을 구현 시작 조건으로 두지 않고, 확정 명세를 Django
Runtime과 PostgreSQL에 순차 반영한다.

다음 표는 환경 재현은 2026-07-28 현재 검증, PostgreSQL Runtime은
2026-07-27 마지막 실행 기록을 구분한 공유 최소선이다.

| 항목 | 현재 결과 |
| --- | --- |
| Backend Python | 3.13.13, 실제 `.venv` 재생성 통과 |
| pip·의존성 | pip 26.0.1, constraints 31개 일치, 추가 패키지 0개 |
| 환경 검증 | `pip check`, Django check, Migration drift, Git 제외 통과 |
| PostgreSQL | 16.14 구성 완료, 2026-07-27 실제 연결 통과·현재 Docker 미실행으로 재검증 대기 |
| Django Model | 확정 도메인 테이블 32개 중 2개 구현 |
| Django Migration | `accounts` 최초 Migration 적용 |
| Runtime Route | Health 1개 + Auth 4개 |
| JWT | Access 60분, Refresh 최초 발급부터 최대 7일이며 rotation으로 절대 만료 연장 없음 |
| Demo Seed | 1차 4명 생성, 2차 4명 갱신, 중복 0 |
| Health·Auth Smoke | 실제 HTTP 2회 통과 |
| Backend 전체 회귀 | 2026-07-28 새 `.venv`에서 `239 passed` |

환경과 전체 회귀 결과는 현재 작업의 새 `.venv`에서 재실행했다.
PostgreSQL 연결·Migration·Seed·HTTP Smoke는 Docker가 실행 중이던
2026-07-27 기록이므로 현재 Branch의 DB 결과로 재사용하지 않고 아래
명령을 같은 Commit에서 다시 실행한다. 어느 결과도 32개 도메인
테이블과 전체 API Runtime 구현 완료를 뜻하지 않는다.

## 2. 공유 파일

| 파일 | 용도 |
| --- | --- |
| [저장소 README](<../../../../README.md>) | 프로젝트 진입점 |
| [Backend README](<../../../../backend/README.md>) | 설치·DB·Migration·Seed·실행·테스트 |
| [Python 버전](<../../../../backend/.python-version>) | Backend Python 3.13.13 기준 |
| [의존성 constraints](<../../../../backend/requirements/constraints-py313.txt>) | Python 3.13 직접·간접 의존성 잠금 |
| [환경 생성 스크립트](<../../../../scripts/development/bootstrap.py>) | `.venv` 생성·동기화·안전 재생성 |
| [환경 검증 스크립트](<../../../../scripts/development/check_environment.py>) | 경량·전체·PostgreSQL 읽기 전용 검사 |
| [VS Code 설정](<../../../../.vscode/settings.json>) | 상대경로 Backend Interpreter·자동 활성화 |
| [VS Code Task](<../../../../.vscode/tasks.json>) | 폴더 열기 검사·최초 생성·전체 검증 |
| [환경변수 예시](<../../../../backend/.env.example>) | 공개 가능한 로컬 기본값과 비밀값 교체 표식 |
| [PostgreSQL Compose](<../../../../docker-compose.yml>) | PostgreSQL 16.14 로컬 실행 |
| [PostgreSQL 연결 검사기](<../../../../scripts/database/check_postgresql_connection.py>) | 비밀값을 출력하지 않는 읽기 전용 연결 검사 |
| [Health·Auth Smoke](<../../../../scripts/smoke/check_backend_auth.py>) | Token을 출력하지 않는 실제 HTTP 검사 |
| [Accounts 최초 Migration](<../../../../backend/apps/accounts/migrations/0001_initial.py>) | 현재 User·CustomerProfile Schema |
| [Demo Seed Command](<../../../../backend/apps/accounts/management/commands/seed_demo_accounts.py>) | 합성 계정 Upsert |
| [OpenAPI](<../../../../contracts/api/openapi.yaml>) | API 기계 계약 |
| [Auth API Path](<../../../../contracts/api/paths/auth.yaml>) | 구현된 인증 API 계약 |

세부 검증 근거는 다음 문서에서 확인한다.

- [Django·PostgreSQL Migration 검증](<./20260727_최지용_Django_PostgreSQL_Migration_검증보고서_v1.0.md>)
- [Auth API 계약·Runtime 정합화](<./20260727_최지용_Auth_API_계약_Runtime_정합화_보고서_v1.0.md>)
- [Backend `.venv` 재현성과 VS Code 환경 설계](<../technical/backend/backend_venv_reproducibility_guide.md>)
- [T-005 데이터 설계 기준선](<../../../database/t-005/README.md>)

## 3. 로컬 Runtime 기준

| 구분 | 기준값 |
| --- | --- |
| Django 설정 | `config.settings.local` |
| Django 시간대 | `Asia/Seoul` |
| DB 저장 시간 | UTC |
| API DateTime | UTC offset가 있는 ISO 8601 |
| Access Token | 60분·3,600초 |
| Refresh Token | 최초 발급은 604,800초, rotation 응답은 최초 `exp`까지 남은 초 |
| Web 개발 Origin | `localhost:5173`, `127.0.0.1:5173` |
| Django 개발 Host | `localhost`, `127.0.0.1`, `[::1]` |
| AI 서비스 개발 주소 | `http://127.0.0.1:8001` |
| PostgreSQL Host | `127.0.0.1:5432` |
| PostgreSQL DB | `watercare` |
| PostgreSQL User | `watercare_app` |
| 구조화 로그 | `backend/.runtime/logs/backend.jsonl` |
| Demo 로그인 | 합성 계정 4종 Allowlist |

[환경변수 예시](<../../../../backend/.env.example>)와 로컬
`backend/.env`의 키 집합은 18개다. 예시 파일에는 공개 가능한 기본값과
`replace-with-*` 표식만 두며, 실제 비밀값은 Git에서 제외된
`backend/.env`에만 둔다.

각 PC에서 반드시 새 값으로 교체할 항목은 다음 두 개다.

```text
DJANGO_SECRET_KEY
POSTGRES_PASSWORD
```

포트를 변경하면 `.env`, Compose, Backend README의 명령을 함께
갱신한다.

## 4. 새 PC 재현 순서

### 4.1 환경변수

저장소 루트에서 실행한다.

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

`backend/.env`의 두 `replace-with-*` 값을 새 난수값으로 교체한다.
실제 값은 채팅·문서·Git Diff·캡처·오류 로그에 남기지 않는다.

### 4.2 Python

현재 PC에 Python 3.13.13을 준비한 뒤 저장소 루트에서 실행한다.

```powershell
python --version
python .\scripts\development\bootstrap.py --service backend
```

정상 기준은 Python 3.13.13, pip 26.0.1, constraints 31개 일치,
constraints 밖 추가 패키지 0개다. `.venv`와 `.runtime`은 Git 공유
대상이 아니다. Conda의 Python을 생성 기반으로 사용할 수 있지만
결과는 표준 `backend/.venv`이며 Conda 환경 자체를 공유하지 않는다.

VS Code는 저장소를 열면 `backend/.venv`를 기본 Interpreter로 선택하고
새 터미널에서 활성화한다. 폴더 열기 Task는 읽기 전용 빠른 검사만
실행한다. 최초 Pull에서 `.venv`가 없다면
`Backend: 환경 최초 생성·동기화` Task를 한 번 실행한다.

일상 확인:

```powershell
python .\scripts\development\check_environment.py --service backend
```

공유 전 전체 확인:

```powershell
python .\scripts\development\check_environment.py --service backend --full
```

환경이 손상되었거나 Python 기준이 달라진 경우에만 `.venv` 밖의
Python 3.13.13으로 안전 재생성을 실행한다.

```powershell
python .\scripts\development\bootstrap.py --service backend --recreate
```

기존 환경은 `.runtime/venv-backups/<timestamp>/.venv`로 이동된다.
새 환경 생성·경량 검증이 실패하면 자동 복원되며, 성공한 경우에도
`--full` 통과 전에는 출력된 백업을 삭제하지 않는다. 세부 복구 기준은
[Backend `.venv` 재현 가이드](<../technical/backend/backend_venv_reproducibility_guide.md>)를
따른다.

### 4.3 PostgreSQL

Docker Desktop을 실행한 뒤 저장소 루트에서 실행한다.

```powershell
docker compose --env-file .\backend\.env config --quiet
docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres
```

현재 구성은 다음 기준을 사용한다.

| 항목 | 기준 |
| --- | --- |
| Image | `postgres:16.14-bookworm` |
| Service | `postgres` |
| Compose Project | `watercare-local` |
| Host Port | `127.0.0.1:5432` |
| Volume | `watercare-postgres-data` |
| Timezone | UTC |
| Healthcheck | `pg_isready` |

Compose는 `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`만
PostgreSQL 초기화에 전달한다. Django Secret·AI 주소·Demo 로그인
코드는 DB Container에 전달하지 않는다.

### 4.4 연결·Migration

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe ..\scripts\database\check_postgresql_connection.py
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --plan
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py migrate --check
Set-Location ..
```

연결 검사는 비밀번호·DSN을 출력하지 않으며 다음 항목을 확인한다.

```text
status=CONNECTED
vendor=PostgreSQL
select_one=1
server_version_num=160014
database_timezone=UTC
default_transaction_read_only=on
```

### 4.5 Demo Seed

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py seed_demo_accounts
.\.venv\Scripts\python.exe manage.py seed_demo_accounts
Set-Location ..
```

정상 결과는 다음과 같다.

```text
Demo accounts ready (created=4, updated=0)
Demo accounts ready (created=0, updated=4)
```

Seed 대상은 합성 계정만 사용한다.

| 역할 | 사용자 코드 |
| --- | --- |
| 고객 | `DEMO-CUSTOMER-001` |
| 상담사 | `DEMO-CONSULTANT-001` |
| 방문기사 | `DEMO-TECHNICIAN-001` |
| 운영자 | `DEMO-OPERATOR-001` |

고객 계정에는 `DEMO-CUS-001` 프로필 1개가 연결된다. 전화번호·주소·
이메일은 공란이고, 계정 비밀번호는 사용할 수 없는 값이다.

### 4.6 Server·Smoke·회귀

첫 번째 PowerShell에서 저장소 루트를 기준으로 실행한다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

두 번째 PowerShell에서 실행한다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe ..\scripts\smoke\check_backend_auth.py
.\.venv\Scripts\python.exe -m pytest -q
```

Smoke는 다음 Route를 실제 HTTP로 확인한다.

| Method | Path |
| --- | --- |
| `GET` | `/health` |
| `POST` | `/api/v1/auth/demo-login` |
| `GET` | `/api/v1/me` |
| `POST` | `/api/v1/auth/refresh` |
| `POST` | `/api/v1/auth/logout` |

검증 범위에는 Correlation ID 발급·재사용, CORS 허용·차단, Token
수명, `/me` 안전 Projection, Refresh rotation, 기존·폐기 Refresh
재사용 401, 미인증 요청과 Allowlist 밖 Demo 코드 차단이 포함된다.
스크립트는 실제 Token을 출력하지 않는다.

## 5. 일상 실행·종료·재시작

### 5.1 설치 완료 후 매일 다시 켜기

다음 절차는 `backend/.env`와 `backend/.venv`가 이미 준비된 PC의
일상 실행 기준이다. `.env` 복사, bootstrap과 Seed를 매번 반복하지
않는다. 저장소 루트에서 실행한다.

```powershell
docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres

python .\scripts\development\check_environment.py `
  --service backend `
  --postgresql

Set-Location .\backend
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

`migrate --check`가 미적용 Migration을 보고하면 서버를 시작하기 전에
다음 명령을 실행한다.

```powershell
.\.venv\Scripts\python.exe manage.py migrate --noinput
```

`seed_demo_accounts`는 다음 경우에만 실행한다.

- PostgreSQL Volume을 새로 만들었을 때
- Seed Command 또는 합성 계정 기준이 변경됐을 때
- Demo 계정을 명시적으로 복구해야 할 때

requirements fingerprint가 같고 환경 검사가 통과하면 bootstrap도
다시 실행하지 않는다.

### 5.2 Django 종료·재시작

Django 개발 서버는 foreground Process다. 정상 종료는 서버를 실행한
PowerShell에서 `Ctrl+C`를 사용한다. 재시작은 종료 후 같은 명령을
다시 실행한다.

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

8000번 포트를 사용할 수 없다는 오류가 발생하면 먼저 Listener와 PID를
확인한다.

```powershell
$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen
$listener
Get-Process -Id $listener.OwningProcess
```

기존 Django Process가 맞는지 확인하기 전에는 임의로 종료하지 않는다.

### 5.3 실행 상태와 오류 확인

PostgreSQL Container와 Django Liveness는 각각 다음 명령으로 확인한다.

```powershell
docker compose --env-file .\backend\.env ps postgres

$response = Invoke-WebRequest 'http://127.0.0.1:8000/health'
$response.StatusCode
$response.Headers['X-Correlation-ID']
```

Compose에서 필수 `POSTGRES_*` 변수가 없다는 오류가 발생하면
`--env-file .\backend\.env` 누락 여부와 `.env` 키 이름을 확인한다.
Docker API 또는 named pipe 권한 오류가 발생하면 Docker Desktop 실행
상태와 현재 Docker Context를 확인한 뒤 같은 명령을 재실행한다.
비밀번호와 전체 DSN은 오류 보고에 포함하지 않는다.

### 5.4 PostgreSQL 중지·재시작

데이터를 보존하면서 중지한다.

```powershell
docker compose --env-file .\backend\.env stop postgres
```

다시 시작한다.

```powershell
docker compose --env-file .\backend\.env start postgres
```

`docker compose down`은 명명된 Volume을 보존하지만, `down -v`는
데이터를 제거한다. 초기화가 명확히 결정되지 않았다면 `-v`를 사용하지
않는다.

기존 Volume을 유지한 채 `.env`의 DB 비밀번호만 변경해도 DB 내부
사용자 비밀번호는 자동으로 바뀌지 않는다. 비밀번호 회전은 DB 내부
변경과 `.env` 갱신을 같은 작업으로 수행한다.

### 5.5 공유하지 않는 항목

- `backend/.env`
- `backend/.venv`
- `backend/.runtime`
- Django Secret Key
- PostgreSQL Password
- Access·Refresh Token
- 실제 고객정보
- 개인 DB Dump
- 로컬 PostgreSQL Volume

### 5.6 pgvector 경계

pgvector는 임베딩 Model과 1024차원 VectorField를 구현하는 Wave에서
Django Migration으로 추가한다. 별도 Init SQL로 미리 생성하지 않고,
빈 DB Migration과 `SELECT extversion`을 같은 단계에서 검증한다.

## 6. 현재 구현 범위와 Known Issues

| 우선 | 항목 | 현재 사실 | 다음 처리 |
| ---: | --- | --- | --- |
| 완료 | Backend 환경 | Python·pip·constraints·bootstrap·VS Code·전체 239 테스트 검증 | 김은진의 독립 재현과 윤승혁의 Workspace 통합 확인 |
| P0 | 도메인 테이블 | 32개 중 2개 구현 | T-005 Wave별 Model·Migration 구현 |
| P0 | API Runtime | Health 1개·Auth 4개 | Model Wave 후 업무 API 수직 구현 |
| P0 | T-022 문의 | 명세 존재, Runtime·Model·Migration 없음 | Wave 2 검증 후 구현 |
| P0 | T-023 Workflow | Loader·Validator 존재 | PM의 상태·이벤트·Guard 입력 후 Engine 구현 |
| P0 | pgvector | 아직 미적용 | 지식·임베딩 Wave Migration에서 적용 |
| P1 | Health | 현재 Liveness 중심 | Dependency Readiness를 별도 정의 |
| P1 | AI 연동 | 개발 주소 계약만 존재 | AI Runtime 이후 연동 Smoke |
| P1 | 배포 | 로컬 개발 기준선 | Production Secret·Host·TLS 검증 |

T-023의 상태·이벤트·Guard·`allowed_actions`는 PM 관할의 실제 외부
입력이다. 이는 최지용이 확정한 ERD·테이블·API 명세와는 별개의
의존 관계다.

## 7. 다음 작업 순서

한 번에 여러 기능을 구현하지 않고 다음 순서를 지킨다.

1. 현재 Docker PostgreSQL 연결·Migration·Seed·Auth Smoke 재검증
2. PostgreSQL 재검증 결과 기록
3. T-005 Wave 1 작업
4. Wave 1 Model·Migration·제약·Seed 검증
5. T-005 Wave 2 작업
6. Wave 2 Model·Migration·FK·UNIQUE·CHECK 검증
7. T-022 문의 최소 수직 흐름 구현
8. T-022 Runtime·권한·PostgreSQL 검증

Wave 1은 공통 코드와 현재 User·CustomerProfile 기준선을 함께
검증한다. Wave 2는 Product Model·Subscription·Care Record를
구현한다.

## 8. 공유 경계

기능별 변경은 다음 경계로 나눈다.

1. T-016 로컬 Runtime·공통 Backend
2. T-005 DB 기준선과 구현 증거
3. T-017 Auth·권한 Runtime
4. T-022 문의 Runtime
5. T-023 Workflow Runtime

변경 파일 개수는 시점마다 달라지므로 문서에 고정하지 않는다. 공유
전에는 `git diff -- <path>`로 범위를 확인하고, `.env`, Token, 실제
개인정보가 Diff·문서·로그에 없는지 검사한다.

## 9. 변경 이력

| 버전 | 날짜 | 내용 |
| --- | --- | --- |
| v1.0 | 2026-07-27 | 환경변수·PostgreSQL·Migration·Seed·Smoke·공유 경계를 하나의 팀 Runbook으로 통합 |
| v1.1 | 2026-07-28 | Python 3.13.13·pip 26.0.1·constraints·bootstrap·VS Code·안전 재생성·일상 실행·종료·재시작 및 새 `.venv` 239 테스트 결과 반영 |

## 10. 인계 사항

| 대상 | 전달 항목 | 다음 행동 | 완료 확인 | 현재 상태 |
| --- | --- | --- | --- | --- |
| 윤승혁(PM) | `.vscode/**`, 현재 Runtime 범위, Known Issues, WBS별 공유 경계와 전체 실행 순서 | 공통 Workspace가 Web·AI 설정과 충돌하지 않는지 확인하고 비작성자 리뷰 후 PR 병합 | 통합 검토 의견 또는 승인 기록과 병합 Commit이 남음 | 문서·설정 준비 완료, 검토·병합 증거 미확인 |
| 김은진 | `scripts/development/**`, Python·constraints, `.env.example`, PostgreSQL Compose, Migration·Seed·Smoke·전체 회귀 명령 | 새 Git Pull 환경에서 bootstrap·전체 환경 검사와 PostgreSQL 시작부터 Smoke까지 재현하고 실패 시 명령·오류·환경 차이만 기록 | Python·패키지·전체 239 테스트와 연결·Migration·Seed 2회·Smoke 결과가 PR 또는 Issue에 남음 | 작성자 새 `.venv` 검증 완료, 제3자 재현 증거 미확인 |
| 한예나 | Backend 주소, Auth 4개 Route, CORS·오류·Token 사용 기준과 합성 계정 코드 | Web에서 로그인·현재 사용자·재발급·로그아웃과 오류 처리를 연동 확인 | Web 연동 결과와 불일치 항목이 PR 또는 Issue에 남음 | 인계 자료 준비 완료, 소비 확인 미확인 |
| 양정현 | Backend 주소, Auth 4개 Route, Authorization Header·오류·Token 수명과 합성 계정 코드 | Mobile에서 인증 흐름과 401·403 처리 호환성을 확인 | Mobile 연동 결과와 불일치 항목이 PR 또는 Issue에 남음 | 인계 자료 준비 완료, 소비 확인 미확인 |
| 이동윤 | Backend↔AI 개발 주소, 인증·Correlation 경계와 현재 AI 연동 미구현 범위 | AI Runtime 준비 후 Adapter·오류·추적 계약의 호환성을 확인 | 연동 Smoke 결과 또는 차이 목록이 PR 또는 Issue에 남음 | 경계 문서화 완료, AI Runtime 연동 확인 미실시 |

실제 Secret, PostgreSQL Password와 Access·Refresh Token은 인계
대상이 아니다. 인계 완료는 문서를 읽었다는 확인이 아니라 위 대상별
재현 또는 호환성 증거가 남았을 때 판정한다.
