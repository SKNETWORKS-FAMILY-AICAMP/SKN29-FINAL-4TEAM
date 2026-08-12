# WaterCare Backend

Django와 Django REST Framework 기반 업무 백엔드입니다. T-016 공통
기반과 T-017 OWNER 구현 기준선이 있으며, 문의 3·상담 4·방문 5개
External Action을 Crosswalk `RUNTIME_IMPLEMENTED` 12개로 실행합니다.
API 계약과 PM State 입력은 실제 Route·Service·실행 테스트 증거와
분리해 판정합니다.

이 `backend/**`가 현행 Django Runtime 원본입니다. 저장소 루트의
`WaterCareBackend/**`와 이를 호출하는 구형 BAT 파일은 과거 Android
연동 starter 참고본이며 현재 Migration·API·State 계약의 실행 기준이
아닙니다.

현재 로컬 개발의 실행 기준은 PostgreSQL **database `waterbridge`**와
그 안의 **schema `public`**입니다. database 이름과 schema 이름을
혼동하지 않습니다. 이번 전환과 Active 범위 검증 결과는
[WaterBridge DB 전환·Active 범위 검증서](../docs/individual/jiyong/technical/backend/20260731_waterbridge_database_transition_and_active_scope_validation.md)에
정리돼 있습니다.

DB 변경·복구·인계의 현행 실행 기준은 위 WaterBridge 검증서입니다.
[Django·PostgreSQL 공유 패키지 인계서 v1.3](../docs/individual/jiyong/manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md)은
2026-07-29 `watercare` 환경의 역사 증거로 보존합니다. 이 README는
일상 실행을 위한 빠른 진입점만 제공합니다.

## 현재 구현 범위

- `GET /health`: 외부 상세를 노출하지 않는 liveness
- `/api/v1`: 도메인 API 연결 위치
- `success`, `data`, `error` 공통 응답
- `code`, `message`, `details` 공통 오류
- 유효한 `X-Correlation-ID` 요청 Header 재사용 또는 UUID 발급
- 응답 Header·공통 Wrapper `metadata`·JSON 로그의 추적 ID 연결
- 승인 Origin만 응답하는 환경변수 기반 CORS Allowlist
- 로컬·테스트·배포 설정 분리
- 기존 process environment를 우선하는 `backend/.env` 선택 로딩
- View가 명시한 역할·소유자·배정자를 검사하는 detail 요청용
  fail-closed Permission

T-005 물리 계약은 `waterbridge.public`에 **32개 테이블을 유지**하는
것입니다. 이 가운데 **Active MVP 13개 테이블**만 현재 데이터 생성·
조회 범위로 사용하고, **Target-only 19개 테이블**은 후속 데이터와
기능 계약이 준비될 때까지 테이블만 유지하며 **0행**을 보장합니다.
따라서 `13개만 사용한다`는 말은 19개 테이블을 삭제하거나 별도
schema로 분리한다는 뜻이 아닙니다. 확장 시에도 기존 32개 계약 안에서
Target-only 테이블을 하나씩 활성화하고 Migration·Seed·회귀 검증을
같은 Commit에서 수행합니다.

T-017에는 합성 계정 Demo 로그인, JWT 발급·회전·폐기, `/me`,
`User`·`CustomerProfile`, `0001_initial.py`, 역할·소유권 Permission,
반복 가능한 `seed_demo_accounts`가 구현돼 있습니다. 2026-07-27 당시
PostgreSQL 연결·Migration·Seed 실행 기록은 과거 스냅샷이며 현재
Branch 완료 판정에는 같은 Commit에서 다시 실행한 결과를 사용합니다.
소비 호환성·실행 재현·비작성자 PR 리뷰는 구현 후 품질 게이트이지
최지용의 작성·구현 착수 승인이 아닙니다.

T-022의 대표 `START_INQUIRY`는 `POST /api/v1/inquiries`로 구현돼
있습니다. 고객 본인의 활성 구독 UUID, `Idempotency-Key`, 원문을
검증하고 `DRAFT` 문의·증상 원문·전이 이력·멱등 기록을 한
트랜잭션에서 생성합니다.

T-023의 대표 `CANCEL_INQUIRY`는
`POST /api/v1/inquiries/{inquiry_id}/cancel`로 구현돼 있습니다.
고객 본인·현재 담당 상담사·`inquiries.cancel_inquiry` 권한 운영자가
`DRAFT` 또는 `QUESTIONNAIRE_IN_PROGRESS` 문의를 `CANCELLED`로
전환하며 실제 직전 상태를 이력에 남기고 `state_version`을 증가시킵니다.
같은 키·같은 요청은 저장 결과를 재생하며, 키 재사용 충돌은
`DUPLICATE-EVENT-01`, 상태·버전 충돌은 `STATE-CONFLICT-01`의 HTTP
409로 반환합니다.

PM State 계약의 상태 13·이벤트 30·전이 34·Guard 39·외부 행동 23은
Loader·Validator가 교차검증합니다. `allowed_actions`는 State·Role 후보,
Transition Rule, 저장된 Domain Guard, Crosswalk Runtime 가용성을 모두
통과한 Action만 반환하며 성공과 stale 409에서 같은 Resolver를
사용합니다. 상태 계약 원본은 윤승혁(PM) 주관,
`backend/apps/workflow/**` 구현은 최지용 주관입니다.

사람용 Public API 명세는 `OWNER_CONFIRMED DESIGN BASELINE`이며 41개
작성·설계 기준선이 확정됐습니다. 기계 계약의 세부 성숙도는
`contracts/api/**`의 `x-contract-status`, 실제 구현은 Route·
Serializer·테스트 증거로 각각 판정합니다.

## 개발 환경

`backend/.python-version`은 Python `3.13.13`,
`requirements/base.txt`와 `requirements/local.txt`는 직접 의존성,
`requirements/constraints-py313.txt`는 Python 3.13에서 검증한
직접·간접 의존성 32개를 고정합니다. 팀이 버전을 변경하면 세 파일과
검증 기록을 같은 변경 단위로 갱신합니다.

새 PC에서는 Python 3.13.13을 준비한 뒤 저장소 루트에서 다음 한 줄로
`backend/.venv`를 생성·동기화합니다.

```powershell
python .\scripts\development\bootstrap.py --service backend
```

스크립트는 `.env`, Docker, Migration, Seed를 변경하지 않습니다.
기존 환경이 정상이고 fingerprint가 같으면 패키지 설치를 생략합니다.
손상되었거나 Python 버전이 다른 환경을 명시적으로 다시 만들 때만
가상환경 밖의 Python 3.13.13으로 다음 명령을 실행합니다.

```powershell
python .\scripts\development\bootstrap.py --service backend --recreate
```

VS Code는 저장소 루트를 열었을 때 `backend/.venv`를 기본 Interpreter로
사용하고 새 터미널에서 자동 활성화합니다. 폴더 열기 Task는 읽기 전용
빠른 검사만 실행합니다. `.venv`가 없는 최초 Pull에서는
`Backend: 환경 최초 생성·동기화` Task를 한 번 실행해야 합니다.

실제 비밀값은 Git에 저장하지 않습니다. `backend/.env.example`에는
공개 가능한 로컬 기본값과 `replace-with-*` 대체 표식만 둡니다. 이를
복사해 만든 `backend/.env`의 두 비밀값은 로컬에서만 관리합니다.
`config/env.py`는 비어 있지 않은 값만 읽고, 이미 주입된 process
environment를 덮어쓰지 않습니다. 실제 `.env` 값은 문서·로그·Git에
기록하지 않습니다. `config.settings.test`를 명시한 실행은 개인
`.env`를 읽지 않아 PC별 테스트 편차를 막습니다. `.env` 자체가
`config.settings.test`를 선택한 경우에도 설정 모듈 이름만 반영하고
로그·DB 등 나머지 개인값은 테스트 process에 합치지 않습니다.

로컬·배포 실행은 다음 키가 비어 있으면 값은 노출하지 않고 키 이름만
포함한 오류로 중단합니다.

- `DJANGO_SECRET_KEY`, `DJANGO_TIME_ZONE`
- `DJANGO_CORS_ALLOWED_ORIGINS`, `AI_SERVICE_BASE_URL`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
  `POSTGRES_HOST`, `POSTGRES_PORT`

확정 기준은 `DJANGO_TIME_ZONE=Asia/Seoul`, Access Token 60분,
Refresh Token 168시간(7일)입니다. Django의 `USE_TZ=True`로 DB에는
UTC를 저장하고 API에는 한국 시간대 오프셋을 포함한 ISO 8601 형식을
사용합니다.

## 설치 완료 후 일상 실행

`.env`와 `backend/.venv`가 이미 준비된 경우 저장소 루트에서 다음
순서로 PostgreSQL과 Django를 다시 실행합니다. `docker compose up -d`는
컨테이너가 없으면 생성하고, 이미 있으면 같은 구성을 재사용합니다.

```powershell
Set-Location (git rev-parse --show-toplevel)
docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres

Get-Content .\backend\.env |
    Select-String '^(POSTGRES_DB|POSTGRES_HOST|POSTGRES_PORT)='

Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python ..\scripts\database\check_postgresql_connection.py
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL 대상 연결 확인 실패"
}

& $python manage.py migrate --check
if ($LASTEXITCODE -ne 0) {
    throw "미적용 Migration이 있습니다. 자동 적용하지 말고 WaterBridge 검증서의 안전 적용 절차를 따르세요."
}
```

`migrate --check` 실패는 자동 Migration 실행 조건이 아니라 즉시 중단
조건입니다. 적용이 필요하면 WaterBridge 검증서에 따라
① DB 이름·Host·Port 재확인,
② Django·Importer·Job 등 모든 Writer 중단, ③ `migrate --plan` 검토,
④ 데이터 유무에 따른 백업·복원 검증 필요 여부 결정, ⑤ 승인된
`migrate --noinput` 명시 실행, ⑥ `migrate --check`와 전체 Gate 재검증
순서로 진행합니다.

Migration 확인이 통과하면 저장소 루트에서 읽기 전용 PostgreSQL
Gate를 실행합니다. 서버 시작과 포트 선택은 아래 Health·Auth Smoke
절차를 따릅니다.

```powershell
Set-Location (git rev-parse --show-toplevel)
& .\backend\.venv\Scripts\python.exe `
  .\scripts\development\check_environment.py `
  --service backend `
  --postgresql
if ($LASTEXITCODE -ne 0) {
    throw "Backend·PostgreSQL 일상 시작 검사 실패"
}
```

공통코드 Seed는 새 DB와 코드 계약 변경 시 먼저 실행하고, Demo Seed는
새 DB·Demo 데이터 복구 시에만 Accounts → Products → Subscriptions →
Care 순서로 실행합니다. Django 서버는
실행 터미널에서 `Ctrl+C`로 종료하거나 재시작하고, PostgreSQL은
저장소 루트에서 다음 명령으로 데이터를 보존한 채 중지합니다.

```powershell
docker compose --env-file .\backend\.env stop postgres
```

전체 일상 실행·종료·상태 확인·포트 충돌 절차는
[Backend 가상환경 재현 가이드](../docs/individual/jiyong/technical/backend/backend_venv_reproducibility_guide.md)와
위 WaterBridge 검증서를 따릅니다.

## 검증

저장소 루트에서 환경만 빠르게 확인합니다. 시스템 Python 대신
프로젝트의 `backend/.venv`를 사용하므로 그대로 복사해 실행할 수
있습니다.

```powershell
Set-Location (git rev-parse --show-toplevel)
& .\backend\.venv\Scripts\python.exe `
  .\scripts\development\check_environment.py `
  --service backend
```

PostgreSQL을 실행한 뒤에는 실제 `waterbridge.public` 연결과 적용
Migration을 읽기 전용으로 확인합니다.

```powershell
& .\backend\.venv\Scripts\python.exe `
  .\scripts\development\check_environment.py `
  --service backend `
  --postgresql
```

공유 전에는 Migration drift와 전체 Backend 테스트까지 실행합니다.

```powershell
& .\backend\.venv\Scripts\python.exe `
  .\scripts\development\check_environment.py `
  --service backend `
  --full
```

이 검사는 Python·pip·32개 constraints·추가 패키지·환경 fingerprint,
`pip check`, Django check, Migration drift, 전체 pytest,
`.venv` Git 추적 여부를 확인합니다. `--postgresql`은 Docker
PostgreSQL이 실행 중일 때 읽기 전용 연결과 적용 Migration을 추가로
확인합니다.

> **HISTORICAL — 2026-07-29 `watercare` 실측**
>
> 다음 표는 DB 이름 전환 전 로컬 작업 트리의 과거 증거입니다.
> 현재 `waterbridge.public` 기준이나 병합된 팀 `main`의 영구 증거로
> 재사용하지 말고, 위 명령과 최신 검증서로 다시 확인합니다.

| 항목 | 실측 결과 | 범위 |
| --- | --- | --- |
| PostgreSQL | `16.14` | Compose와 실제 연결 버전 |
| Migration | 기존 미적용 9개와 `workflow.0003` 적용 | 현재 로컬 `watercare` |
| Legacy 보정 | `changed_at` 11행을 `created_at`으로 보정 | `workflow.0003` |
| 전체 Gate | `397 passed`와 PostgreSQL Gate 통과 | pytest는 SQLite, PostgreSQL은 읽기 전용 연결·적용 Migration 확인 |
| Health·Auth Smoke | Port `8001`, `status=PASSED` | 기존 Process가 8000을 점유해 현재 코드에 8001 사용 |

[Backend 가상환경 재현 가이드](../docs/individual/jiyong/technical/backend/backend_venv_reproducibility_guide.md)와
[Django·PostgreSQL 공유 패키지 인계서 v1.3](../docs/individual/jiyong/manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md)에
환경 설계 근거와 2026-07-29 역사 절차를 정리했습니다. 현재 복구
순서와 검증 결과는 위 WaterBridge 검증서를 우선합니다.

실제 로컬 PostgreSQL 실행은 `backend/.env.example`의 키를
`backend/.env`에 안전하게 채운 뒤 수행합니다. 기본 `waterbridge` DB에는
공통코드 Seed를 먼저 실행한 뒤 Demo Seed 네 종류를 순서대로
실행합니다. 팀 인계용 멱등성 증거와 실행 전제는 v1.3 및
[공통코드 Registry 구현 가이드](../docs/individual/jiyong/technical/backend/t005_common_code_registry_implementation.md)를
참고하되, 현재 DB 이름과 검증 결과는 WaterBridge 검증서를 따릅니다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py seed_common_codes
.\.venv\Scripts\python.exe manage.py seed_demo_accounts
.\.venv\Scripts\python.exe manage.py seed_demo_products
.\.venv\Scripts\python.exe manage.py seed_demo_subscriptions
.\.venv\Scripts\python.exe manage.py seed_demo_care_records
```

Canonical `import_synthetic_handoff`는 기본 `waterbridge`에서 실행하지
않습니다. 새로 만든 격리 DB의 이름과 연결 대상을 확인한 경우에만
WaterBridge 검증서의 격리 DB 전용 절차로 실행합니다.

PostgreSQL은 로컬 PC의 `127.0.0.1`에만 공개되며, DB 파일은
`watercare-postgres-data` Docker Volume에 보존됩니다. 단순 중지는
`docker compose --env-file .\backend\.env stop postgres`를 사용합니다.
`down -v`는 Volume의 DB 데이터를 삭제하므로 초기화가 명시적으로
필요한 경우에만 사용합니다.

Compose는 `pgvector/pgvector:0.8.6-pg16-bookworm` 이미지를 사용하고
`backend/.env` 전체를 컨테이너에 전달하지 않습니다. DB 이름·사용자·
비밀번호 3개만 PostgreSQL에 주입합니다. 이미지의 PostgreSQL 16과
pgvector 0.8.6은 실제 연결 검사와 Django Migration에서 함께
검증합니다.

### 서버와 Health·Auth Smoke

저장소 루트에서 8000 점유 Process를 먼저 확인한 뒤 서버를 시작합니다.
점유 Process를 임의 종료하지 않으며, 8000이 사용 중이고 8001이
비어 있을 때만 8001로 대체합니다.

```powershell
Set-Location (git rev-parse --show-toplevel)
$port = 8000
$listener = @(Get-NetTCPConnection `
    -LocalPort $port `
    -State Listen `
    -ErrorAction SilentlyContinue)

if ($listener) {
    $listener | Select-Object LocalAddress, LocalPort, OwningProcess
    Get-Process -Id ($listener.OwningProcess | Select-Object -Unique)
    $port = 8001
    if (Get-NetTCPConnection `
        -LocalPort $port `
        -State Listen `
        -ErrorAction SilentlyContinue) {
        throw "Port 8000과 8001이 모두 사용 중입니다."
    }
}

Set-Location .\backend
& .\.venv\Scripts\python.exe `
  manage.py runserver "127.0.0.1:$port" --noreload
```

새 PowerShell에서는 저장소 루트에서 실제 서버 Port와 같은 Base URL로
liveness와 Auth Smoke를 실행합니다. 기본값은 8000이며 위 대체 경로를
사용했다면 8001로 바꿉니다.

```powershell
Set-Location (git rev-parse --show-toplevel)
$baseUrl = 'http://127.0.0.1:8000' # 대체 실행 시 8001

$response = Invoke-WebRequest "$baseUrl/health"
$response.StatusCode
$response.Headers['X-Correlation-ID']

& .\backend\.venv\Scripts\python.exe `
  .\scripts\smoke\check_backend_auth.py `
  --base-url $baseUrl
```

스크립트는 Health, CORS, Demo 로그인, `/me`, Refresh rotation,
Logout과 폐기 Token 재사용 차단을 검사합니다. 출력에는 HTTP 상태,
만료 초, 검증 여부만 포함하고 실제 Token은 포함하지 않습니다. 다만
읽기 전용 검사가 아니며 로그인·Refresh·Logout 과정에서 DB의 Token
행을 생성·회전·폐기하므로 의도한 로컬 Demo DB에서만 실행하고
공유·운영 DB에서는 실행하지 않습니다.

`/health`는 Liveness 200·빈 본문과 `X-Correlation-ID`만 제공합니다.
DB 연결은 별도 PostgreSQL 검사와 Migration으로 확인합니다. 공통 DRF
응답은 `success`, `data`, `error`, `metadata.correlation_id`를
사용합니다.

T-022·T-023의 현재 차단점은 다음 명령으로 확인합니다. 기본 실행은
증거를 출력하고, `--require-ready`는 미충족 시 exit code 2를
반환합니다. 아래 명령도 `backend`에서 실행합니다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend
.\.venv\Scripts\python.exe .\apps\inquiries\readiness.py
.\.venv\Scripts\python.exe .\apps\workflow\readiness.py
.\.venv\Scripts\python.exe .\apps\inquiries\readiness.py --run-runtime-tests --verify-postgresql --require-ready
.\.venv\Scripts\python.exe .\apps\workflow\readiness.py --run-runtime-tests --verify-postgresql --require-ready
```

환경변수 이름만 존재하는 것은 PostgreSQL 검증으로 인정하지 않습니다.
`--verify-postgresql`은 `config.settings.local`을 강제한 뒤 읽기 전용
연결 검사, `makemigrations --check --dry-run`, `migrate --check`를
각각 실행합니다. Runtime 테스트가 생긴 뒤에는
`--run-runtime-tests`를 함께 사용합니다.

T-005·T-017·T-022·T-023의 `--completion-evidence` JSON은 작성자 외
리뷰와 Seed 등 인계 기록에만 사용합니다. PostgreSQL과
Model/Migration 성공 문자열을 JSON에 적어도 기술 게이트를 통과하지
않으며 반드시 `--verify-postgresql`을 함께 실행해야 합니다.
JSON의 `team_review`는 기존 검사기 호환 키이며 명세 선행 승인이 아니라
소비 호환성·실행 재현·비작성자 PR 리뷰를 기록합니다.

```powershell
.\.venv\Scripts\python.exe .\apps\accounts\readiness.py --completion-evidence ..\docs\handoffs\<완료-증거파일>.json --verify-postgresql --require-ready
.\.venv\Scripts\python.exe .\apps\inquiries\readiness.py --completion-evidence ..\docs\handoffs\<완료-증거파일>.json --run-runtime-tests --verify-postgresql --require-ready
.\.venv\Scripts\python.exe .\apps\workflow\readiness.py --completion-evidence ..\docs\handoffs\<완료-증거파일>.json --run-runtime-tests --verify-postgresql --require-ready
```

T-005는 저장소 루트에서
`scripts/database/validate_t005_schema.py --completion-evidence
<상대경로> --verify-postgresql --require-wbs-complete` 형식으로
사용합니다. 증거에는 비밀번호·DSN·Token을 넣지 않습니다.

## 구조 원칙

- API → Service → Repository → Model 의존 방향을 유지합니다.
- 업무 상태는 `apps/workflow/`에서 관리합니다.
- AI 서비스는 `integrations/ai/`를 통해 호출합니다.
- 화면용 공식 근거는 `apps/evidence/`에서 `EvidenceCardDTO`로 조립합니다.
- Django Migration은 각 App의 `migrations/`에서 관리합니다.
