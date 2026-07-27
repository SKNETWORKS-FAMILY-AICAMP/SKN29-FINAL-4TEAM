# WaterCare Backend

Django와 Django REST Framework 기반 업무 백엔드입니다. T-016 공통
기반과 T-017 OWNER 구현 기준선이 있으며, T-022 API 기준선과 T-023
PM State 계약 입력을 실제 Runtime 준비도와 분리해 검증합니다.

이 `backend/**`가 현행 Django Runtime 원본입니다. 저장소 루트의
`WaterCareBackend/**`와 이를 호출하는 구형 BAT 파일은 과거 Android
연동 starter 참고본이며 현재 Migration·API·State 계약의 실행 기준이
아닙니다.

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

T-017에는 합성 계정 Demo 로그인, JWT 발급·회전·폐기, `/me`,
`User`·`CustomerProfile`, `0001_initial.py`, 역할·소유권 Permission,
반복 가능한 `seed_demo_accounts`가 구현돼 있습니다. 2026-07-27 당시
PostgreSQL 연결·Migration·Seed 실행 기록은 과거 스냅샷이며 현재
Branch 완료 판정에는 같은 Commit에서 다시 실행한 결과를 사용합니다.
소비 호환성·실행 재현·비작성자 PR 리뷰는 구현 후 품질 게이트이지
최지용의 작성·구현 착수 승인이 아닙니다.

T-022 문의 Runtime은 아직 Placeholder지만
`contracts/api/paths/inquiries.yaml`에는 3개 operation이 있습니다.
T-023은 PM State 계약의 상태 13·이벤트 30·전이 34·Guard 39·역할
5·외부 행동 23을 Loader·Validator가 교차검증합니다. 공식 검증과
Workflow 집중 테스트는 현재 변경에서 통과했지만 Engine·Model·
Migration·Repository·Service·Route·Runtime API는 미구현입니다.
상태 계약 원본은 윤승혁(PM) 주관, `backend/apps/workflow/**` 구현은
최지용 주관입니다.

사람용 Public API 명세는 `OWNER_CONFIRMED DESIGN BASELINE`이며 41개
작성·설계 기준선이 확정됐습니다. 기계 계약의 세부 성숙도는
`contracts/api/**`의 `x-contract-status`, 실제 구현은 Route·
Serializer·테스트 증거로 각각 판정합니다.

## 개발 환경

`requirements/base.txt`와 `requirements/local.txt`는 2026-07-27
재현 검증에 사용한 직접 의존성 버전을 고정합니다. 팀이 버전을
변경하면 요구 파일·검증 기록을 함께 갱신합니다.

아래 Windows PowerShell 명령은 저장소 루트에서 시작한다.

```powershell
Set-Location .\backend

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements\local.txt
```

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

## 검증

```powershell
Set-Location .\backend

$env:DJANGO_SETTINGS_MODULE = 'config.settings.test'
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pytest -q
```

실제 로컬 PostgreSQL 실행은 `backend/.env.example`의 키를
`backend/.env`에 안전하게 채운 뒤 수행합니다.

```powershell
Set-Location ..
docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres

Set-Location .\backend
.\.venv\Scripts\python.exe ..\scripts\database\check_postgresql_connection.py
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo_accounts
.\.venv\Scripts\python.exe manage.py seed_demo_accounts
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

PostgreSQL은 로컬 PC의 `127.0.0.1`에만 공개되며, DB 파일은
`watercare-postgres-data` Docker Volume에 보존됩니다. 단순 중지는
`docker compose stop postgres`를 사용합니다. `down -v`는 Volume의
DB 데이터를 삭제하므로 초기화가 명시적으로 필요한 경우에만
사용합니다.

Compose는 공식 `postgres:16.14-bookworm` 이미지를 사용하고
`backend/.env` 전체를 컨테이너에 전달하지 않습니다. DB 이름·사용자·
비밀번호 3개만 PostgreSQL에 주입합니다. pgvector는 VectorField를
소유하는 Django Migration과 함께 추가·검증하며 이 초기 연결
기준선에서는 선행 생성하지 않습니다.

다른 터미널에서 liveness 확인:

```powershell
$response = Invoke-WebRequest 'http://127.0.0.1:8000/health'
$response.StatusCode
$response.Headers['X-Correlation-ID']
```

Health와 인증 전체 흐름은 Token을 출력하지 않는 Smoke 스크립트로
재현할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe ..\scripts\smoke\check_backend_auth.py
```

스크립트는 Health, CORS, Demo 로그인, `/me`, Refresh rotation,
Logout과 폐기 Token 재사용 차단을 검사합니다. 출력에는 HTTP 상태,
만료 초, 검증 여부만 포함하고 실제 Token은 포함하지 않습니다.

`/health`는 Liveness 200·빈 본문과 `X-Correlation-ID`만 제공합니다.
DB 연결은 별도 PostgreSQL 검사와 Migration으로 확인합니다. 공통 DRF
응답은 `success`, `data`, `error`, `metadata.correlation_id`를
사용합니다.

T-022·T-023의 현재 차단점은 다음 명령으로 확인합니다. 기본 실행은
증거를 출력하고, `--require-ready`는 미충족 시 exit code 2를
반환합니다.

```powershell
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
