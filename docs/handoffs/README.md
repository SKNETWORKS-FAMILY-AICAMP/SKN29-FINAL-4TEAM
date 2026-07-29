# WaterCare 팀별 충돌 해결·Pull 작업 인계

> 기준일: 2026-07-29
> 작업 소스 Branch: `jiyong`
> 팀 반영 기준: 최지용 `jiyong` Push → PM 검토·`main` 병합 → PM이 공유한 40자리 `main` Commit SHA
> 개발 최우선: 현재 구현 Runtime 7개의 OpenAPI·Serializer·오류 Registry·정상/오류 예시 정합화
> 실행 원칙: `작업 → 검증 → 작업 → 검증`
> 문서 원칙: 저장소 안의 상대경로만 연결하고 개인 PC 절대경로는 사용하지 않는다.

## 1. 이 문서의 목적

이 문서는 최지용이 `jiyong` Branch에 Push한 Backend 기준선을 PM이
검토해 `main`에 병합한 뒤, 각 팀원이 자기 PC와 자기 Branch에
반영하고 남아 있는 협업 충돌을 자기 관할에서 해결하기 위한 단일
팀 공용 인계 진입점이다.

이 문서 하나만 보고도 다음을 판단할 수 있어야 한다.

- 어느 `main` Commit을 받아야 하는가
- 최초 실행에 무엇이 필요한가
- 현재 구현된 범위와 아직 구현되지 않은 범위는 무엇인가
- 각 팀원이 어느 파일을 수정하고 무엇을 검증해야 하는가
- 다음 팀원에게 무엇을 전달해야 하는가
- 어떤 상태에서 완료라고 보고하면 안 되는가

최지용의 `jiyong` Commit SHA는 PR·추적용 소스 기준이다. 팀원이 실제
작업 기준으로 반영할 값은 PM이 `jiyong` 변경을 검토·병합한 뒤
전달하는 40자리 `main` Commit SHA다. 문서에 고정 SHA를 적어 오래된
값으로 만들지 않고, 각 팀원이 아래 명령으로 전달받은 SHA가
`origin/main`과 자기 Branch의 조상인지 확인한다.

## 2. 현재 기준과 완료 범위

### 2.1 실제 구현·검증된 기준선

| 범위 | 현재 기준 |
| --- | --- |
| 환경 | Python 3.13.13, pip 26.0.1, PostgreSQL 16.14 |
| Backend 전체 회귀 | 최신 `main` 통합·Auth 초 경계 회귀 보정·문서 반영을 포함한 최종 HEAD에서 `353 passed` |
| Migration | drift 없음, PostgreSQL 16.14 연결·적용 Migration 검사 통과 |
| Seed | Accounts → Products → Subscriptions → Care 순서로 PostgreSQL에서 2회 연속 실행 통과 |
| T-005 | 계약 테이블 32개 중 7개 구현, 25개 후속 |
| T-022 | `POST /api/v1/inquiries` 대표 `START_INQUIRY` 구현 |
| T-023 | `POST /api/v1/inquiries/{inquiry_id}/cancel` 대표 `CANCEL_INQUIRY` 구현 |
| 충돌 처리 | 상태 충돌 `STATE-CONFLICT-01`, 키 재사용 `DUPLICATE-EVENT-01` |
| 멱등성 | 동일 Key·동일 Body 재생, 동일 Key·다른 Body 409 |
| 공개 식별자 | 외부 UUID와 업무 표시 코드를 분리 |
| API 계약·Runtime | OpenAPI Operation 9개, 실제 Runtime 7개, 설계 전용 2개 |
| API JSON 예시 | 총 22개: 신규 20개 + 기존 Workflow 409 두 종류 |
| 오류 Registry | Runtime 공통 코드 4개 추가, 최상위 총 10개와 `runtime_http_mapping` 검증 |

관련 기준 문서:

- [Backend 실행 기준](../../backend/README.md)
- [Backend 가상환경 재현 가이드](../individual/jiyong/technical/backend/backend_venv_reproducibility_guide.md)
- [Django·PostgreSQL 공유 패키지 인계서](../individual/jiyong/manuals/20260728_최지용_Django_PostgreSQL_공유패키지_인계서_v1.1.md)
- [T-005 구현 기준](../database/t-005/README.md)
- [T-005 3계층 식별자 ADR](../adr/0010-t005-three-layer-identifier-bridge.md)
- [T-005 상태 이력 멱등성 ADR](../adr/0011-t005-status-history-idempotency-scope.md)
- [OpenAPI 원본](../../contracts/api/openapi.yaml)
- [문의 API 계약](../../contracts/api/paths/inquiries.yaml)
- [Workflow Action 계약](../../contracts/api/paths/workflow.yaml)
- [API Runtime 구현 상태](../api/runtime_implementation_status.md)
- [Backend API 계약 정합화 검증보고서](../individual/jiyong/manuals/20260729_최지용_Backend_API_계약_정합화_검증보고서_v1.0.md)

### 2.2 완료로 보고하면 안 되는 범위

- T-005 전체 32개 테이블 완료
- Account 기존 문자열 PK의 전체 재키잉
- Visit Aggregate·VisitResult FK 전체 구현
- 문의 문진·자가조치·목록·상세 전체 Runtime
- `CANCEL_INQUIRY` 이외의 전체 Workflow Action
- 범용 State Engine·Guard의 Service 연결, Reopen·부모 문의 Runtime
- Data Fixture와 Backend Seed의 자동 변환
- Web·Mobile 실제 API 전체 전환
- AI 실행환경·AI Runtime·Backend AI Client

T-005 감사 결과가 `NOT_READY`이거나
`completion_claim_allowed=false`이면 문서·테스트 일부가 통과해도
T-005 전체 완료라고 쓰지 않는다.

### 2.3 팀 작업을 막는 현재 기준 불일치

| 영역 | 2026-07-29 실측 | 팀원이 따라야 할 판단 |
| --- | --- | --- |
| Git 기준선 | API 정합화·최신 `main` 통합·자동 회귀를 작업 단위 Commit으로 고정 | `jiyong` SHA는 PR·추적 기준이다. PM이 검토해 `main`에 병합하고 전달한 40자리 `main` SHA만 팀별 Branch에 반영 |
| PM 계약 | State Machine `v1.0.0`이 2026-07-29 `TEAM_APPROVED`로 채택됨 | Data는 `data-state-crosswalk.yaml`과 대표 14단계 계약을 기준으로 Fixture·QA를 갱신하고, Backend는 승인된 값을 중복 정의하지 않고 소비 |
| State Machine 생성물 | 최신 `origin/main` 기준 파일과 순수 계산 Engine·Guard 단위 기반을 `jiyong`에 반영했으나 운영 Service에는 미연결 | PM 계약·생성 Script·산출물을 삭제하거나 구형 수동본으로 되돌리지 않음 |
| Web | 환경·공통 API·인증 관련 핵심 파일이 비어 있고 Test Script가 없음 | 상담사 실제 연동 완료가 아니라 공통 Client·인증·계약 Fixture부터 구현 |
| Mobile | 구조 V2·최신 `main`·`jiyong` 모두 `:customer-app`·`:technician-app`·`:core` 3모듈이며 `mobile/app`·`mobile_prev` 없음 | 구조 충돌은 해소됐다. 양정현은 3모듈 의존성·Network 위치·Build 기준을 검증한 뒤 기능 작업 |
| AI | 계약 일부가 비어 있고 `pyproject.toml`·Runtime·Health가 Placeholder | 확정 설치 명령이 없으므로 이동윤이 환경·Schema·Runtime을 먼저 완성 |
| API 구현 상태 | OpenAPI 9·Runtime 7·OpenAPI-only 2, JSON 22개, Registry 공통 코드 정합화 완료 | 미구현 2개를 호출하지 않고 PM `main` SHA에서 소비 검증 |
| 설명 문서 Drift | 사람용 명세와 Runtime 상태표를 기계 계약·실제 Route의 9·7로 갱신 | 이후 수치는 Runtime·OpenAPI 계약 테스트를 통과한 변경에서만 갱신 |

따라서 개별 테스트 통과, `jiyong` Push, “모든 팀원이 Pull해도 되는
최종 공유 SHA”는 서로 다른 뜻이다. 4.0의 공유 게이트를 거쳐 PM이
병합·전달한 `main` Commit만 팀 인계 기준으로 사용한다.

### 2.4 2026-07-29 개발 최우선 게이트

새 Model Wave, 후속 Workflow Action, Data Importer 또는 AI Client를
추가하기 전에 현재 등록된 Runtime을 먼저 정합화한다. 이 작업은
PM·Data·AI의 신규 입력을 기다리지 않고 최지용이 바로 수행할 수 있다.

현재 대상 Runtime은 다음 7개다.

- `GET /health`
- `POST /api/v1/auth/demo-login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/me`
- `POST /api/v1/inquiries`
- `POST /api/v1/inquiries/{inquiry_id}/cancel`

OpenAPI에는 있지만 Runtime이 없는 다음 2개는 `NOT_IMPLEMENTED`로
분리하며, 구현된 것처럼 JSON 예시나 완료 상태를 만들지 않는다.

- `PATCH /api/v1/inquiries/{id}/questionnaire`
- `POST /api/v1/inquiries/{id}/action-results`

순차 작업 결과:

| 순서 | 작업 | 현재 결과 |
|---:|---|---|
| 1 | OpenAPI 9개를 Runtime 7개·OpenAPI-only 2개로 매핑 | 완료·계약 검증 통과 |
| 2 | Runtime 공통 오류 4개와 HTTP 선택 규칙 정합화 | 완료·400~599 Mapping 검증 통과 |
| 3 | 구현 Endpoint 정상·오류·Replay 예시 | 총 22개·상대 참조·비밀값 검증 통과 |
| 4 | 계약·권한·전체 Backend 회귀 | 94건·31건·353건 통과 |
| 5 | 지원·미구현 경계와 소비자 인계 | 문서 반영 완료·PM 리뷰 대기 |

다음 중 하나라도 발생하면 신규 기능으로 넘어가지 않는다.

- OpenAPI와 Route의 Path·Method·`operationId` 대응이 다름
- Schema와 Serializer의 필드·필수값·Enum이 다름
- Runtime 오류 코드가 Registry에 없거나 HTTP 상태가 다름
- 구현됐다고 선언한 응답의 검증 가능한 예시가 없음
- 계약 또는 Runtime 테스트 실패

현재 로컬 자동 검증에서는 위 중단 조건이 발생하지 않았다. 팀 공용
완료 상태는 `jiyong` Push와 PM `main` 병합 뒤에만 선언한다.

T-005 다음 Wave는 김은진의 Data Mapping·Fixture 입력 뒤에,
T-023 후속 Action·Service 연결은 윤승혁의 State·Terminal·Reopen
계약 입력 뒤에 한 단위씩 진행한다.

## 3. 변경하지 않는 확정 계약

팀원은 다음 기준을 임의로 다시 정의하지 않고 소비한다.

| 항목 | 확정 기준 |
| --- | --- |
| 외부 리소스 ID | UUID `public_id` 또는 API의 `inquiry_id` |
| 업무 표시값 | `inquiry_code`, `model_code`, `contract_no`, `care_code` |
| 금지사항 | `DEMO-*`, `SYN-*` 업무 코드를 URL 리소스 ID로 사용하지 않음 |
| 상담사 Role | Backend·API 표준은 `CONSULTANT` |
| 멱등 Key | HTTP `Idempotency-Key` Header |
| 상태 Action 요청 | 현재 `state_version`을 Request Body로 전송 |
| 성공 응답 행동 | `allowed_actions`는 code·label·operation 정보가 있는 객체 배열 |
| 상태 충돌 409 | `error.details.allowed_actions`는 현재 허용 Action code 배열 |
| Key 재사용 409 | `DUPLICATE-EVENT-01`의 `error.details`는 빈 객체이며 Snapshot이 아님 |
| 상태 계산 | Web·Mobile·AI가 선행 계산하지 않고 Backend 결과를 사용 |
| AI 권한 | AI는 분석 JSON만 반환하고 업무 DB 상태를 직접 변경하지 않음 |
| AI 호출 정책 | 전체 30초, Backend 자동 재시도 0회, AI 내부 최대 1회 |

세부 원본:

- [Role 코드](../../contracts/codes/user-roles.yaml)
- [409 복구 정보 Schema](../../contracts/api/components/schemas/workflow/WorkflowConflictDetails.yaml)
- [State Machine 안내](../../contracts/state-machine/README.md)
- [상태](../../contracts/state-machine/inquiry-states.yaml)
- [이벤트](../../contracts/state-machine/inquiry-events.yaml)
- [전이](../../contracts/state-machine/transition-rules.yaml)
- [Guard](../../contracts/state-machine/transition-guards.yaml)
- [허용 행동](../../contracts/state-machine/allowed-actions.yaml)
- [동시성 정책](../../contracts/state-machine/concurrency-policy.yaml)
- [완료 정책](../../contracts/state-machine/completion-policy.yaml)

## 4. 팀 Branch·PM 병합·Pull 전 준비

| 담당자 | 역할 | 원격 Branch |
| --- | --- | --- |
| 최지용 | Backend·Database | `jiyong` |
| 김은진 | Data·QA·DevOps | `eunjin` |
| 한예나 | Web | `yena` |
| 양정현 | Mobile | `jeonghyun` |
| 이동윤 | AI·RAG | `dongyoon` |
| 윤승혁(PM) | PM·기술 통합 | `seunghyuk` |

### 4.0 Git 공유 게이트 — 개발 우선순위와 분리

이 절은 정합화된 결과를 팀에 배포하기 위한 절차다. 2.4의 Runtime
계약 정합보다 먼저 수행해야 하는 개발 우선순위가 아니다.

팀원은 최지용의 `jiyong` Push만 보고 Pull하지 않는다. 최지용이
작업·검증·Push를 끝내고 PM이 검토·`main` 병합을 완료한 뒤, PM이
40자리 `main` Commit SHA를 전달해야 Pull 작업을 시작한다.

1. 최지용은 `jiyong`의 변경 범위와 최신 `origin/main`과의 차이를
   파일 단위로 확인한다.
2. `origin/main`의 State Machine Render Script와 자동 생성
   MMD·SVG를 보존한다.
3. 구조 V2와 최신 `origin/main`의 Mobile 3모듈
   `:customer-app`·`:technician-app`·`:core`를 보존하고 Backend
   공유 과정에서 삭제하거나 단일 `:app`으로 되돌리지 않는다.
4. `mobile/app` 또는 `mobile_prev`가 다시 나타나면 기능 작업을
   진행하지 않고 구조 V2와 전달 SHA를 대조해 중복 유입 원인을 먼저
   기록한다.
5. Backend 구현·계약·Migration·테스트·인계 문서를 모두 Commit한다.
6. 같은 Commit에서 PostgreSQL·Seed 2회·전체 Backend 회귀를
   통과한다.
7. `git diff --check`를 통과시키고 원격 `origin/jiyong`과 로컬
   `jiyong` SHA를 일치시킨다.
8. PM은 `jiyong` PR을 검토하고 충돌·보존 범위를 확인한 뒤
   `main`에 병합한다.
9. PM은 병합된 40자리 `main` SHA와 완료·미구현 범위를 팀에
   전달한다.

최지용은 아래 명령으로 공유 가능 여부를 확인한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

git fetch --prune origin

if ((git branch --show-current) -ne 'jiyong') {
    throw '최지용의 jiyong Branch에서 공유 게이트를 실행하세요.'
}

git status --short
git rev-list --left-right --count origin/main...HEAD
git diff --name-status origin/main...HEAD
Get-Content .\mobile\settings.gradle.kts
git ls-tree -d --name-only origin/main -- mobile mobile_prev

if (git status --porcelain) {
    throw '미커밋 변경이 있어 아직 공유할 수 없습니다.'
}

$localSha = git rev-parse HEAD
$remoteSha = git rev-parse origin/jiyong
if ($localSha -ne $remoteSha) {
    throw '로컬 jiyong과 origin/jiyong SHA가 일치하지 않습니다.'
}
```

단순히 “`jiyong` Push 완료”라는 메시지만 받고 시작하지 않는다.
반드시 PM이 병합해 전달한 40자리 `main` Commit SHA와 이 문서의
경로를 함께 받는다.

### 4.1 공통 준비물

- Git
- VS Code 또는 본인 개발 IDE
- Docker Desktop
- Backend 작업 시 Python 3.13.13
- 별도 전달받은 `backend/.env`
- Web 작업 시 Vite가 지원하는 Node.js
- Mobile 작업 시 JDK 17과 Android SDK
- AI 작업 시 이동윤이 확정할 Python·의존성 기준

다음 항목은 Git으로 공유하지 않는다.

- `backend/.env`
- `backend/.venv`
- AI·Mobile 개인 환경 파일
- Access/Refresh Token
- 실제 Password·API Key
- PostgreSQL Docker Volume

### 4.2 자기 작업 보존

저장소 터미널을 연 뒤 실행한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

$dirty = git status --porcelain
if ($dirty) {
    git status --short
    throw '기존 작업이 있습니다. 먼저 본인 Branch에 커밋하거나 안전하게 보관한 뒤 다시 실행하세요.'
}

git branch --show-current
git status --short
```

기존 작업을 없애기 위해 `git reset --hard`나 다른 사람 파일 삭제를
사용하지 않는다.

### 4.3 자기 Branch에 PM 병합 `main` Commit 반영

아래 두 값만 자기 정보로 변경한다.

```powershell
$myBranch = '<본인-Branch>'
$mainSha = '<PM이-공유한-main-Commit-SHA>'

Set-Location (git rev-parse --show-toplevel)

if ($mainSha -notmatch '^[0-9a-fA-F]{40}$') {
    throw 'PM에게 전달받은 40자리 main Commit SHA를 입력하세요.'
}

git fetch --prune origin

git merge-base --is-ancestor $mainSha origin/main
if ($LASTEXITCODE -ne 0) {
    throw '전달받은 SHA가 origin/main에 없습니다. Merge하지 말고 PM에게 확인하세요.'
}

git switch $myBranch
git pull --ff-only origin $myBranch
git merge --no-ff $mainSha

if ($LASTEXITCODE -ne 0) {
    git status --short
    git diff --name-only --diff-filter=U
    throw 'Merge 충돌입니다. 임의 삭제하지 말고 충돌 파일과 담당자를 확인하세요.'
}

git merge-base --is-ancestor $mainSha HEAD
if ($LASTEXITCODE -ne 0) {
    throw '전달받은 main Commit이 현재 Branch에 포함되지 않았습니다.'
}

git status --short
```

로컬 Branch가 아직 없을 때만 다음 명령으로 만든다.

```powershell
git fetch --prune origin
git switch --track -c <본인-Branch> origin/<본인-Branch>
```

Merge 충돌을 해결하지 않고 원래 상태로 되돌릴 때는 충돌 파일을
수정하기 전에 다음 명령을 사용한다.

```powershell
git merge --abort
```

### 4.4 병합 직후 공통 보안 검사

```powershell
git status --short
git ls-files backend/.env backend/.venv
```

두 번째 명령은 아무 파일도 출력하지 않아야 한다.

## 5. Backend 공통 실행 기준선

Backend API를 소비하거나 Data·통합 QA를 수행하는 팀원은 최초 한 번
다음 순서로 환경을 재현한다.

### 5.1 Python·가상환경

```powershell
Set-Location (git rev-parse --show-toplevel)

python --version
python .\scripts\development\bootstrap.py --service backend
python .\scripts\development\check_environment.py --service backend
```

`python --version`은 정확히 `Python 3.13.13`이어야 한다.

### 5.2 PostgreSQL

```powershell
Set-Location (git rev-parse --show-toplevel)

if (-not (Test-Path .\backend\.env)) {
    throw 'backend/.env가 없습니다. 별도 전달받은 파일을 먼저 배치하세요.'
}

docker version
docker compose --env-file .\backend\.env config --quiet
docker compose --env-file .\backend\.env up -d postgres
docker compose --env-file .\backend\.env ps postgres

python .\scripts\development\check_environment.py `
  --service backend `
  --postgresql
```

### 5.3 Migration·Seed

```powershell
Set-Location .\backend
$python = '.\.venv\Scripts\python.exe'

& $python manage.py migrate --check
if ($LASTEXITCODE -ne 0) {
    & $python manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Migration 적용 실패' }
}

& $python manage.py seed_demo_accounts
if ($LASTEXITCODE -ne 0) { throw 'Accounts Seed 실패' }

& $python manage.py seed_demo_products
if ($LASTEXITCODE -ne 0) { throw 'Products Seed 실패' }

& $python manage.py seed_demo_subscriptions
if ($LASTEXITCODE -ne 0) { throw 'Subscriptions Seed 실패' }

& $python manage.py seed_demo_care_records
if ($LASTEXITCODE -ne 0) { throw 'Care Seed 실패' }

Set-Location ..
```

### 5.4 서버 실행·종료

서버 전용 터미널:

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\backend
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

- Django 종료: 서버 터미널에서 `Ctrl+C`
- PostgreSQL 데이터 보존 중지:

```powershell
Set-Location (git rev-parse --show-toplevel)
docker compose --env-file .\backend\.env stop postgres
```

`docker compose down -v`는 DB Volume을 삭제하므로 명시적인 전체
초기화 작업이 아니면 사용하지 않는다.

## 6. 충돌 해결 담당표

| 번호 | 충돌 | 현재 상태 | 주담당 | 부담당·소비자 |
| ---: | --- | --- | --- | --- |
| 1 | Action Endpoint 부족 | START·CANCEL 대표 흐름만 구현 | 최지용 | 윤승혁(PM), 한예나, 양정현 |
| 2 | 상태·버전·409 Snapshot | 대표 흐름만 구현 | 최지용 | 한예나, 양정현, 김은진 |
| 3 | Inquiry·Visit Aggregate 분리 | Inquiry 구현, Visit 후속 | 최지용 | 윤승혁(PM), 김은진 |
| 4 | Data 12단계·PM 전이 차이 | PM `v1.0.0` Crosswalk·대표 14단계에서 계약 충돌 해결, Data Fixture·Backend 소비 검증 후속 | 윤승혁(PM), 김은진 | 최지용 |
| 5 | Terminal·Reopen 정책 | 순수 엔진 단위 기반 구현, 운영 Service·Reopen Runtime 후속 | 윤승혁(PM), 최지용 | 김은진 |
| 6 | Data UUID·업무 코드·Seed 연결 | Backend 분리 완료, Mapping 후속 | 김은진, 최지용 | 한예나, 양정현 |
| 7 | `COUNSELOR`·`CONSULTANT` | Backend 표준 완료, Data 후속 | 김은진 | 최지용 |
| 8 | AI Schema·Timeout·Retry | 정책만 확정, Runtime 후속 | 이동윤, 최지용 | 김은진 |
| 9 | Mobile 단일 App·3모듈 구조 충돌 | **해결** — V2·`main`·`jiyong` 모두 3모듈, `mobile/app`·`mobile_prev` 없음 | 양정현 | 윤승혁(PM), 최지용 |
| 10 | Web 상담사 UI·고객 전용 START/CANCEL | 상담사 Runtime API 미구현 | 한예나, 최지용 | 윤승혁(PM) |

## 7. 권장 협업 실행 순서

| 구분 | 순서 | 담당 | 작업 | 다음 담당자에게 주는 결과 |
| --- | ---: | --- | --- | --- |
| 독립 선행 | A | 최지용 | 현재 Runtime 7개의 OpenAPI·Serializer·오류·예시·테스트 정합화 | 소비 가능한 현재 Backend 계약 |
| 독립 선행 | B | 양정현 | V2 3모듈 의존성·Network 위치·Build 기준 확인 | `:customer-app`·`:technician-app`·`:core` 실행·검증 기준 |
| 완료 입력 | 1 | 윤승혁(PM) | 14단계·Terminal·Guard를 State `v1.0.0 TEAM_APPROVED`로 채택 | 채택된 State 계약·Crosswalk·Transition·Guard ID |
| 팀 의존성 | 2 | 김은진 | PM 계약 기준 Data ID·Role·상태 Mapping·Fixture·QA 갱신 | Mapping 파일·Fixture SHA·QA 결과 |
| 팀 의존성 | 3 | 최지용 | 확정 Mapping을 Backend Import·Visit·Guard에 한 수직 흐름씩 반영 | 안정된 Backend 계약·Runtime |
| 팀 의존성 | 4 | 한예나·양정현 | Web·Mobile 소비 코드와 오류 복구 갱신 | 소비자 계약·Build·Smoke 결과 |
| 팀 의존성 | 5 | 이동윤 → 최지용 | AI Schema·Runtime 확정 후 Backend AI Client 연결 | Backend↔AI 통합 결과 |
| 최종 검증 | 6 | 김은진 | 동일 Commit 계약·DB·E2E·안전 통합 QA | 최종 QA 결과 |
| 공유 게이트 | G | 최지용 → 윤승혁(PM) | 최지용 `jiyong` Push → PM 검토·`main` 병합·40자리 SHA 공유 | 팀원이 반영할 공식 `main` SHA |

개발 의존성은 `PM 승인 입력 완료 → Data → Backend → 소비자 → AI → QA`
순서다.
독립 선행 A·B는 필요한 외부 입력을 기다리지 않고 진행할 수 있다.
공유 게이트 G는 개발 기능 순위가 아니라 검증된 결과를 배포하는
절차다. 팀원은 자기 선행 입력이 오지 않았으면 임의 Mock을 확정
계약처럼 고정하지 않고 `BLOCKED`와 필요한 입력을 기록한다.

## 8. 최지용 인계·후속 작업

### 8.1 주관 파일

- [Backend](../../backend/)
- [REST API 계약](../../contracts/api/)
- [공통 코드](../../contracts/codes/)
- [오류 코드](../../contracts/error-codes/)
- [DB 검증 스크립트](../../scripts/database/)
- [Backend AI 연동](../../backend/integrations/ai/)

`contracts/state-machine/**`, `data/**`, `web/**`, `mobile/**`,
`ai/**`는 해당 주담당자의 입력을 소비하며 대신 수정하지 않는다.

### 8.2 현재 전달할 내용

- 현재 계약은 OpenAPI 9개, 실제 Runtime 7개, OpenAPI-only 2개다.
- 실제 JSON 예시는 Auth 7·Errors 7·Inquiries 3·Workflow 5로
  총 22개이며 모든 파일이 OpenAPI 상대 참조로 연결됐다.
- Runtime 공통 오류 `INVALID_REQUEST`, `RESOURCE_NOT_FOUND`,
  `VALIDATION_ERROR`, `INTERNAL_ERROR`를 최상위 Registry와 Category에
  가산했고 Handler의 4xx·5xx 선택 규칙을 `runtime_http_mapping`으로
  고정했다.
- 사람용 API 설명 문서와 Runtime 상태표는 OpenAPI 9·Runtime 7·
  OpenAPI-only 2로 갱신됐다.
- 계약 94건, 권한·소유권 31건, 전체 Backend 353건이 현재
  작업트리에서 통과했다.
- Public UUID와 업무 코드는 분리돼 있다.
- JWT `sub`는 Public UUID를 우선하며 기존 문자열 PK는 호환
  fallback이다.
- 문의 생성은 CUSTOMER 본인의 ACTIVE 구독 UUID만 허용한다.
- 문의 생성은 `DRAFT`, `state_version=1`로 시작한다.
- 문의 취소는 CUSTOMER 본인의 DRAFT 문의만 허용한다.
- 취소 성공은 `CANCELLED`, `state_version=2`다.
- 생성·취소 모두 `Idempotency-Key`가 필수다.
- T-022는 `START_INQUIRY`, T-023은 `CANCEL_INQUIRY` 대표 Runtime만
  존재한다.
- 범용 State Machine·Guard의 Placeholder는 순수 계산·단위 기반으로
  대체했지만 START·CANCEL 운영 Service에는 아직 연결하지 않았다.
- 요청 replay 판정은
  `workflow_idempotency_record(actor, operation_id, idempotency_key)`가
  담당한다. 상태 이력 Key는 비고유 추적값이며, 요청 원장·Aggregate
  갱신·이력 저장은 같은 PostgreSQL Transaction 안에서 처리해야 한다.
- T-005 Wave 3도 Inquiry·Symptom만 구현됐으며
  QA·Assessment·Guidance와 Wave 4·5의 상담·방문·지식·Evidence·
  AI Run 저장 Model은 후속이다.

### 8.3 완료한 독립 작업과 입력 대기 작업

다음 독립 작업은 `작업 → 집중 검증 → 증거 기록` 순서로 완료했다.

1. OpenAPI 9개를 Runtime 7개와 OpenAPI-only 2개로 분리했다.
2. Runtime 공통 오류 4개와 Handler 선택 규칙을 가산 정합화했다.
3. 구현된 Auth 4개·START·CANCEL만 JSON 22개로 연결했다.
4. 계약 94건·권한 31건·전체 Backend 353건을 통과했다.
5. 상세 증거와 팀별 다음 행동은
   [검증보고서](../individual/jiyong/manuals/20260729_최지용_Backend_API_계약_정합화_검증보고서_v1.0.md)에
   기록했다.

아래 작업은 선행 입력을 받은 뒤에만 진행한다.

1. 김은진의 Data Mapping·Fixture가 확정되면 T-005 다음 Wave와
   Backend Importer를 한 Wave씩 구현한다.
2. Visit Aggregate와 `VisitResult` FK는 해당 Data Mapping·Wave
   입력 뒤에 구현한다.
3. 채택된 State `v1.0.0`·Terminal·Reopen 계약을 입력으로 Action별
   Guard Adapter를 한 Action씩 Service Runtime에 연결한다.
4. 재문의 부모 문의는 PM 계약에 포함된 경우 계약·Model·Migration·
   API·테스트를 한 변경 단위로 구현한다.
5. 소비자가 필요한 구독·문의 조회 API는 2.4의 정합 게이트와
   소비자 입력 뒤 계약부터 수직 구현한다.
6. 이동윤의 AI Schema·Runtime Commit 이후에만 Backend AI Client를
   구현한다.

### 8.4 검증 명령

```powershell
Set-Location (git rev-parse --show-toplevel)

.\backend\.venv\Scripts\python.exe -m pytest `
  backend/tests/unit/accounts/test_auth_contracts.py `
  backend/tests/unit/accounts/test_auth_api.py `
  backend/tests/api/test_health.py `
  backend/tests/api/test_openapi_common_contract.py `
  backend/tests/api/test_openapi_inquiry_contract.py `
  backend/tests/api/test_cancel_inquiry_contract.py `
  backend/tests/api/test_workflow_conflict_contract.py `
  -q

.\backend\.venv\Scripts\python.exe -m pytest `
  backend/tests/api/test_t022_create_inquiry.py `
  backend/tests/api/test_t023_cancel_inquiry.py `
  backend/tests/api/test_workflow_conflict_contract.py `
  -q

.\backend\.venv\Scripts\python.exe `
  .\scripts\database\validate_t005_schema.py

.\backend\.venv\Scripts\python.exe `
  .\scripts\database\audit_t005_implementation_readiness.py

python .\scripts\development\check_environment.py `
  --service backend `
  --full `
  --postgresql
```

### 8.5 완료·인계 기준

- 현재 Runtime 7개의 OpenAPI·Route·Serializer 대응 차이 0건
- Runtime·Registry 오류 코드와 HTTP 상태 차이 0건
- 구현된 Endpoint의 정상·오류 예시 누락 0건
- 관련 계약·Runtime 테스트 실패 0건
- 최지용의 실제 `jiyong` 소스 SHA와 PM이 병합·전달한 실제 `main`
  SHA를 함께 기록
- OpenAPI·Route·Serializer·Service·Migration·테스트가 같은 Commit
- PostgreSQL·Seed 2회·전체 회귀 결과 전달
- 구현하지 않은 T-005·T-022·T-023 범위를 명시
- AI Schema·Runtime 입력 전에는 `BLOCKED`를 기록하고, 입력 후
  Backend AI Client를 연결했다면 해당 Commit과 검증 결과를 전달

## 9. 윤승혁(PM) 계약 유지·변경 인계

### 9.1 주관 파일

- [State Machine 계약](../../contracts/state-machine/)
- [전체 연결 예시](../../contracts/examples/)
- [방문 해결 예시](../../contracts/state-machine/examples/visit-resolution.yaml)
- [State Machine 검증 스크립트](../../scripts/contracts/validate_state_machine.py)
- [계약 Changelog](../../contracts/CHANGELOG.md)
- [계약 Version](../../contracts/VERSION)

Backend API·ERD 작성을 다시 승인하는 절차가 아니다. PM은 자기
관할인 State 계약의 채택 상태·원본성과 Data 시나리오가 소비할 전이
순서를 책임진다. 최지용이 확정한 Backend API·ERD를 다시 승인
대기시키지 않는다.

### 9.2 `v1.0.0` 채택으로 해결된 계약 충돌과 남은 Runtime 경계

- 충돌 3: Inquiry 13상태와 Visit 7상태를 별도 Aggregate로 유지한다.
- 충돌 4: Data의 12단계 흐름에 빠진
  `VISIT_REVIEW_REQUIRED`·`UPDATE_VISIT_SCHEDULE`을 포함해 아래
  14단계 대표 흐름을 기계 판독 가능한 예시로 확정한다.

```text
START_INQUIRY
SUBMIT_SYMPTOM
SUBMIT_ANSWERS
SAFE_GUIDANCE_READY
REQUEST_CONSULTATION
START_CONSULTATION
VISIT_REVIEW_REQUIRED
VISIT_NEEDED
UPDATE_VISIT_SCHEDULE
CONFIRM_VISIT
START_VISIT
VISIT_COMPLETED
SUBMIT_RESOLUTION_FEEDBACK
FINALIZE_INQUIRY
```

- 충돌 5: `RESOLVED`·`CANCELLED`는 변경할 수 없는 Terminal로 두고
  같은 Inquiry를 다시 열지 않는다. `REOPENED`는
  `COMPLETION_PENDING + CUSTOMER_REPORTED_UNRESOLVED`에서만 허용한다.
- State Machine 내부 의미 오류
  `STATE_VERSION_CONFLICT`·`IDEMPOTENCY_KEY_REUSE_CONFLICT`와 공개 API
  오류 `STATE-CONFLICT-01`·`DUPLICATE-EVENT-01`의 Mapping을 명시한다.
- 성공 `allowed_actions` 객체 배열, 상태 충돌의 Action code 배열,
  멱등 Key 재사용 충돌의 빈 `details`를 서로 섞지 않는다.
- 현재 계약 YAML·대표 예시는 `v1.0.0 TEAM_APPROVED`이며 Version과
  Changelog도 기록됐다. 계약 채택과 Backend의 전체 Action Runtime
  구현 완료는 별도 상태로 보고한다.

### 9.3 후속 계약 변경 시 유지 절차

1. 최신 `main` 반영 과정에서
   `scripts/contracts/render_state_machine.py`와 자동 생성
   `inquiry-state-machine.mmd`·`.svg`를 보존한다.
2. `inquiry-states.yaml`, `transition-rules.yaml`,
   `completion-policy.yaml` 사이의 모순을 확인한다.
3. PM 소유의 기계 판독 Crosswalk
   `contracts/state-machine/data-state-crosswalk.yaml`을 상태·전이
   변경과 같은 Commit에서 함께 갱신한다.
4. Data 구상태를 다음처럼 분리해서 Mapping한다.

| Data 구값 | PM 계약 Mapping |
| --- | --- |
| `AI_GUIDANCE_READY` | Inquiry `AI_GUIDANCE` |
| `CONSULTATION_PENDING` | Inquiry `CONSULTATION_REQUIRED` |
| 상태 `PRODUCT_VALIDATION_FAILED` | Event `PRODUCT_VALIDATION_FAILED` 후 Inquiry `CONSULTATION_REQUIRED` |
| `VISIT_PENDING` | Inquiry `VISIT_SCHEDULED` + Visit `CONFIRMED` |
| `VISIT_IN_PROGRESS` | Inquiry `VISIT_SCHEDULED` + Visit `IN_PROGRESS` |

5. 이벤트 맥락 없이 Inquiry와 Visit 상태를 하나의 상태값으로
   치환하지 않는다.
6. 14단계 대표 예시, Terminal/Reopen, 오류 Mapping,
   `allowed_actions` 형태를 함께 갱신한다.
7. 채택 상태·Version·Changelog의 일관성을 유지·갱신하고 생성
   Diagram을 다시 만든다.
8. 계약 변경이 없으면 변경 없음과 기준 Commit SHA를 전달한다.
9. 계약 변경이 있으면 김은진·최지용에게 변경 이벤트·전이·Guard ID와
   Migration 영향 여부를 먼저 전달한다.

### 9.4 검증 명령

```powershell
Set-Location (git rev-parse --show-toplevel)
$python = '.\backend\.venv\Scripts\python.exe'

& $python .\scripts\contracts\validate_state_machine.py

if (-not (Test-Path .\scripts\contracts\render_state_machine.py)) {
    throw '최신 main의 State Machine Render Script가 없습니다. 계약 작업을 중단하세요.'
}

& $python .\scripts\contracts\render_state_machine.py `
  --compact `
  --state-labels both `
  --check

& $python -m pytest `
  backend/tests/unit/workflow `
  -q

git diff --check
```

계약을 변경했다면 `--check` 전에 생성물을 갱신한다.

```powershell
& $python .\scripts\contracts\render_state_machine.py `
  --compact `
  --state-labels both `
  --image-output contracts/state-machine/diagrams/inquiry-state-machine.svg
```

### 9.5 완료·인계 기준

- 상태·이벤트·전이·Guard·허용 행동 검증 통과
- 14단계 대표 예시와 Inquiry 13상태·Visit 7상태 Crosswalk 존재
- Terminal 상태에서 금지된 전이 0건
- 의미 오류와 공개 API 오류 코드 Mapping 존재
- 성공·상태 충돌·멱등 Key 충돌의 `allowed_actions/details` 형태 구분
- Version·Changelog·채택 상태 기록
- MMD·SVG가 Render Script 결과와 일치
- 김은진이 그대로 Fixture로 옮길 수 있는 대표 이벤트 순서
- 최지용이 Guard로 구현할 Transition·Guard ID 목록

## 10. 김은진 Data·QA 인계 작업

### 10.1 주관 파일

- [Data 안내](../../data/README.md)
- [합성 원본 시나리오](../../data/config/synthetic/scenarios.json)
- [대표 E2E 원본](../../data/config/e2e/representative_case.json)
- [소비자 Handoff 원본](../../data/config/handoff/consumer_profiles.json)
- [Pipeline 설정](../../data/config/pipeline.json)
- [설정 Schema](../../data/schemas/config/)
- [합성 Schema](../../data/schemas/synthetic/)
- [필드 사전](../../data/catalog/field_dictionary.yaml)
- [Dataset Vocabulary](../../data/config/workflow/dataset_vocabulary.json)
- [Dataset 목록](../../data/catalog/datasets.yaml)
- [Data Changelog](../../data/catalog/CHANGELOG.md)
- [생성 Fixture](../../data/synthetic/fixtures/)
- [생성 시나리오](../../data/synthetic/scenarios/)
- [Consumer Handoff Manifest](../../data/processed/metadata/consumer_handoff_manifest.json)
- [E2E 검증 로직](../../data/tools/watercare/e2e_validation.py)
- [Data 단위 테스트](../../data/tools/tests/)
- [Data 도구](../../data/tools/)
- [최상위 테스트](../../tests/)

### 10.2 해결할 충돌

| Data 현행 | Backend·계약 기준 | 해야 할 일 |
| --- | --- | --- |
| `COUNSELOR` | `CONSULTANT` | Fixture·이력·Schema·Vocabulary를 단일화 |
| Fixture UUID | Backend Public UUID | 원본 보존 또는 명시적 1:1 Mapping |
| `DEMO-*` 업무 코드 | API 리소스 UUID | PK/FK로 사용하지 않도록 분리 |
| `customer_id` | User와 CustomerProfile 분리 | User→CustomerProfile Mapping |
| `customer_products` | 현행 Subscription 평탄화 | Product·설치·시리얼 Mapping |
| `subscription_number` | `contract_no` | 필드 변환 |
| `plan_code` | `management_type_code` | 코드 변환 |
| `REGULAR_INSPECTION` 등 | Backend Care 코드 | Care Type·Result Crosswalk |
| Data 12단계 | PM 계약 전이 | 대표 Fixture·이력 재작성 |
| RESOLVED 직접 Reopen | Terminal 정책 | PM 계약에 맞는 신규 문의 또는 허용 전이로 수정 |

Data UUID v5는 이미 PK/FK이므로 `SYN-*` 코드로 바꾸지 않는다.
Backend와는 다음 공개 식별자 Mapping을 사용한다.

| Data | Backend |
| --- | --- |
| 각 `*_id` UUID | 각 Model의 `public_id` |
| `inquiry_number` | `inquiry_code` |
| `subscription_number` | `contract_no` |
| `product_code` | `model_code` |
| User UUID | `User.public_id`; 고객 Role이면 `CustomerProfile` FK로 해석 |
| `customer_product_id` | `Subscription`의 고객·제품·시리얼 필드로 평탄화 |

원본 Data UUID와 저장된 Backend `public_id`를 양방향 추적할
Mapping·Manifest는 반드시 남긴다.

### 10.3 작업 순서

1. 변경 전 단위 테스트로 기준선을 고정한다.
2. 윤승혁(PM)의 최종 전이·Crosswalk Commit을 기준으로 삼는다.
3. 생성 Fixture를 직접 고치지 않고 `data/config/**` 원본,
   `data/schemas/**`, 검증 Test부터 수정한다.
4. `COUNSELOR`를 `scenarios.json`뿐 아니라 User·Inquiry·History·Audit
   등 모든 Synthetic Schema와 Expected에서 `CONSULTANT`로 맞춘다.
5. Vocabulary에 Inquiry 상태와 Visit 상태 목록을 분리한다.
6. 대표 흐름을 PM의 14단계로 갱신하고 History·Audit의 상태 Version
   수치는 실제 재생성 결과로 산출한다. `117`처럼 예상값을 먼저
   하드코딩하지 않는다.
7. Synthetic Build 후 `db-smoke`·`db-full`·`qa` Handoff를 차례로
   다시 만든다.
8. Backend Model·제약·Seed Mapping을 교차검증한다.
9. `service_contracts_used=false`,
   `READY_FOR_FIELD_MAPPING`,
   `QA_READY_SERVICE_MAPPING_PENDING`은 실제 Mapping·Seed 검증 전까지
   유지한다.
10. Schema 의미가 바뀌므로 Data Version·Changelog·Dataset 목록과
    Manifest를 함께 갱신한다. 새 Version 번호는 김은진의 정책으로
    결정한다.

### 10.4 Data 검증 명령

```powershell
Set-Location (git rev-parse --show-toplevel)

python -B -m unittest discover -s data/tools/tests -v
python -B data/tools/pipeline.py build synthetic
python -B data/tools/pipeline.py handoff db-smoke
python -B data/tools/pipeline.py handoff db-full
python -B data/tools/pipeline.py handoff qa
python -B data/tools/pipeline.py qa --verify-rebuild
python -B -m unittest discover -s data/tools/tests -v
python -B data/tools/pipeline.py inventory
python -B data/tools/pipeline.py finalize
git diff --check
```

Backend Mapping 교차검증:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest `
  backend/tests/unit/accounts `
  backend/tests/unit/products `
  backend/tests/unit/subscriptions `
  backend/tests/unit/care `
  backend/tests/unit/inquiries `
  backend/tests/api/test_t022_create_inquiry.py `
  backend/tests/api/test_t023_cancel_inquiry.py `
  -q
```

### 10.5 완료·인계 기준

- `COUNSELOR` 잔존 0건 또는 명시적인 입력 alias만 존재
- Fixture PK/FK에 표시용 `DEMO-*` 코드 사용 0건
- User→CustomerProfile→Subscription→Product→Care 추적 가능
- Inquiry 상태와 Visit 상태 혼합 0건
- PM의 14단계 순서와 상태 Version 연속성이 대표 E2E와 일치
- UUID/FK 중복·누락 0건
- QA 오류·경고 0건과 Rebuild Drift 0건
- Handoff Manifest Hash 불일치 0건
- Data Version·Schema·Dataset 목록·Changelog가 함께 갱신
- 최지용에게 Mapping 파일·Fixture Commit SHA 전달

Backend Seed 2회와 DB E2E 승인은 최지용의 최종 통합 게이트다. 이를
김은진 단독 완료 조건으로 보고하지 않는다.

## 11. 한예나 Web 인계 작업

### 11.1 주관 파일

- [Web 패키지 설정](../../web/package.json)
- [공통 API Client](../../web/src/common/api/)
- [환경 설정](../../web/src/app/config/env.ts)
- [로그인 화면](../../web/src/pages/auth/LoginPage.tsx)
- [Workflow Entity](../../web/src/entities/workflow/)
- [Workflow Action 기능](../../web/src/features/workflow-action/)
- [상담사 화면](../../web/src/pages/consultant/)
- [Web 테스트](../../web/tests/)

### 11.2 해결할 충돌

1. `DEMO-INQ-*`를 URL 리소스 ID로 사용하지 않는다.
2. UUID `inquiry_id`와 표시용 `inquiry_code`를 별도 Type으로 둔다.
3. 로그인 응답의 Access Token을 Authorization Header에 사용한다.
4. 사용자 쓰기 1회가 시작될 때 UUID 형식 `Idempotency-Key` 하나를
   발급하고 In-flight 요청·Draft와 함께 보존한다.
5. 같은 논리 요청의 네트워크 재시도에만 같은 Key를 사용하고,
   성공하거나 사용자가 새 행동을 시작하면 새 Key를 발급한다.
   공통 Interceptor가 모든 요청마다 Key를 새로 만들면 안 된다.
6. 상태 Action에는 화면이 보유한 `state_version`을 보낸다.
7. 성공 응답의 `allowed_actions`는
   `code`·`label`·`operation_id`·`style`·확인 문구가 있는 객체
   배열로 처리한다.
8. `STATE-CONFLICT-01`은
   `current_status`·`current_state_version`·Action code 문자열
   배열로 화면을 복구한다.
9. `DUPLICATE-EVENT-01`의 `details: {}`는 최신 Snapshot으로 간주하지
   않고 “같은 Key에 다른 Body를 사용한 오류”로 처리한다.
10. 409 후 사용자 입력을 삭제하지 않고 Backend보다 먼저 로컬
    상태를 전환하지 않는다.

### 11.3 선행 차단점

현재 Web은 `CONSULTANT` 화면이지만 구현된 문의 START·CANCEL은
`CUSTOMER` 본인 전용이다. `DEMO-CONSULTANT-001`로 두 Endpoint를
호출하면 403이 정상이며, 이를 상담사 Action 완료로 바꾸면 안 된다.
고객 계약 Harness가 필요할 때만 `DEMO-CUSTOMER-001`을 사용하고
상담사 화면 기능과 명확히 구분한다.

또한 Web의 `.env.example`, 환경 Loader, 공통 HTTP Client,
Response·Error·Request Context, Auth·Role Guard가 현재 비어 있고
`package.json`에 Test Script도 없다. 다음을 구현하기 전에는 실제
Web 연동 완료로 보고하지 않는다.

- `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1`처럼 비밀값이 아닌
  공개 환경변수의 검증
- Demo Login·Refresh·Logout·`/me` 네 Auth Route
- 401 동시 요청의 Refresh Single-flight와 원요청 최대 1회 재시도
- Refresh 실패·Logout 시 Token·사용자 상태 제거 기준
- `DEMO-CONSULTANT-001` 로그인과 상담사 Role Guard
- Vitest 등 팀이 채택한 Test Runner와 `npm test` 계열 Script

활성 구독 UUID 조회 API와 상담사 문의 목록·상세·Action Runtime도
전체 구현되지 않았다. 다음 중 하나가 제공되기 전에는 해당 화면을
실제 연동 완료로 보고하지 않는다.

- 최지용이 제공한 조회 API
- 김은진이 확정한 소비자용 Mapping
- 테스트에서만 사용하는 명시적인 계약 Fixture

임의의 로컬 DB UUID나 `DEMO-SUB-001`을 운영 API ID로 하드코딩하지
않는다.

### 11.4 작업 순서

1. API Base URL 환경변수·시작 시 검증
2. 공통 Response·Error·Correlation·Authorization 처리
3. Demo Login·Refresh·Logout·`/me`와 Role Guard
4. Refresh Single-flight·원요청 1회 재시도·Token 제거
5. Inquiry UUID·업무 코드 Type 분리
6. 성공 Action 객체·상태 충돌·Key 재사용 충돌 DTO 분리
7. `CONSULTANT` 목록·상세·Action의 계약 Fixture·Component 테스트
8. 고객 계약 Harness에서만 START·CANCEL·멱등성·`state_version` 검증
9. 정상·401·403·404·두 종류 409 테스트
10. Backend가 제공한 상담사 API 범위만 실제 API로 전환하고 나머지는
    `BLOCKED`로 표시

### 11.5 준비·검증 명령

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\web

node --version
npm ci
npm run lint
npm run build
```

현재 `package.json`에는 Test Script가 없으므로 테스트 환경을 추가한
뒤에는 팀이 확정한 Script도 함께 실행한다. Test Script가 없는데
테스트까지 완료했다고 보고하지 않는다.

개발 서버:

```powershell
npm run dev -- --host 127.0.0.1
```

종료는 개발 서버 터미널에서 `Ctrl+C`다.

### 11.6 완료·인계 기준

- UUID와 업무 코드가 Type·Route에서 분리
- `DEMO-CONSULTANT-001` 로그인·Role Guard 통과
- Authorization·Correlation은 공통 계층에서 처리
- Idempotency Key는 논리 쓰기 작업 계층에서 생성·재시도 보존
- 401 Refresh 성공·실패와 원요청 1회 재시도 검증
- 성공 Action 객체와 409 Action code 배열을 구분
- 정상·401·403·404·두 종류 409 Fixture
- 사용자 입력 보존
- lint·build·추가한 테스트 통과
- 상담사 실제 API와 Mock, 고객 계약 Harness 범위를 README에 구분

## 12. 양정현 Mobile 인계 작업

### 12.1 주관 파일

- [Mobile 안내](../../mobile/README.md)
- [Mobile Module 설정](../../mobile/settings.gradle.kts)
- 구형 `mobile/docs/BACKEND_API_CONTRACT.md`는 현재 Checkout에 없으므로
  존재하는 계약처럼 참조하지 않는다.
- [Mobile 전체](../../mobile/)

### 12.2 확정된 3모듈 구조 확인

프로젝트 구조 V2와 최신 `origin/main`·`jiyong`은 다음 구조로
일치한다.

- `:customer-app`: 고객용 Android Application
- `:technician-app`: 방문기사용 Android Application
- `:core`: 두 앱의 공통 순수 Kotlin Module
- `mobile/app`, `mobile_prev`: 존재하지 않음

양정현은 구조 선택을 다시 시작하지 않고, 전달받은 SHA에서 이 기준이
유지되는지 확인한 뒤 Network·DTO·화면 연동을 진행한다.

최지용이 공유한 SHA를 반영한 뒤 다음을 확인한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Get-Content .\mobile\settings.gradle.kts
git ls-tree -d --name-only HEAD -- mobile mobile_prev
```

`settings.gradle.kts`에 세 Module이 모두 있고 `mobile/app`과
`mobile_prev`가 없으면 구조 게이트를 통과한다. 다음으로 Package
Namespace·Network 구현 위치·검증 명령을 기록한다. `core`에 없는
Retrofit·OkHttp·Serialization 의존성과 Network Package 위치는
양정현 관할에서 설계·검증한다.

### 12.3 해결할 충돌

1. UUID `inquiryId`와 표시용 `inquiryCode`를 분리한다.
2. `DEMO-INQ-*`를 API 리소스 ID로 사용하지 않는다.
3. 공통 Network 계층은 Authorization·Correlation을 처리한다.
   `Idempotency-Key`는 사용자 쓰기 작업 시작 시 Repository·Operation
   호출자가 생성해 명시적으로 전달한다.
4. In-flight·Draft와 Key를 함께 보존하고 같은 논리 재시도에만 같은
   Key를 사용한다. 성공·새 행동부터 새 Key를 만든다.
5. 성공 `allowed_actions` 객체 배열,
   `STATE-CONFLICT-01`의 Action code 배열,
   `DUPLICATE-EVENT-01`의 빈 `details`를 별도 DTO로 둔다.
6. `stateVersion`과 상태 충돌 Snapshot을 DTO에 포함한다.
7. Mobile 자체 State Machine이 Backend보다 먼저 상태를 바꾸지 않는다.
8. Backend `allowed_actions`만 사용자 Action으로 노출한다.
9. Timeout·409 후 입력 Draft를 보존한다.
10. 구형 문서의 `/symptom`·`/images`·`/analyze`·`/events`를 현행
    OpenAPI Endpoint처럼 구현하지 않는다. 문서를 폐기 표시하거나
    역사 참고용으로 격리한다.

### 12.4 작업 순서

1. 구조 V2·전달 SHA·3모듈 설정 일치 확인
2. JDK·SDK와 Module별 의존성 확인
3. `core` 또는 문서화한 공통 Network 위치에 응답·오류 DTO 구현
4. 인증·Correlation과 Operation 단위 Idempotency 처리
5. Inquiry ID·Code Type 분리
6. 성공 Action·두 종류 409 Mapper
7. 고객·기사 화면의 로컬 선행 전이 제거
8. 고객은 `DEMO-CUSTOMER-001`, 기사는
   `DEMO-TECHNICIAN-001`로 역할별 계약 검증
9. 선택 구조의 Unit·Build·Lint
10. Emulator API Smoke와 Token·비밀값 Log 비노출 확인

### 12.5 준비·검증 명령

다음 명령은 확정된 3모듈 구조에서 실행한다.

```powershell
Set-Location (git rev-parse --show-toplevel)
Set-Location .\mobile

java -version
.\gradlew.bat :core:test
.\gradlew.bat :customer-app:testDebugUnitTest
.\gradlew.bat :technician-app:testDebugUnitTest
.\gradlew.bat :customer-app:assembleDebug
.\gradlew.bat :technician-app:assembleDebug
.\gradlew.bat :customer-app:lintDebug
.\gradlew.bat :technician-app:lintDebug
```

기준은 JDK 17이다. Gradle·Android Plugin·SDK 호환성은 문서 추정이
아니라 위 실제 명령 통과로 판정한다.

### 12.6 완료·인계 기준

- UUID와 표시 코드 분리
- V2 3모듈·Package·Network 위치가 지침과 일치하고
  `mobile/app`·`mobile_prev`가 없음
- 인증·Correlation Header와 Operation 단위 Idempotency 처리
- 서버 상태·Action만 소비
- 정상·401·403·404·두 종류 409·Timeout 테스트
- 같은 Key·같은 Body 재생과 같은 Key·다른 Body 409 검증
- Stale Version 409 뒤 Draft 보존
- 고객·기사 앱 Build·Lint 통과
- Emulator에서 대표 API Smoke 통과
- Token·비밀값 Log 0건
- 활성 구독 조회가 없으면 실제 전체 연동 완료로 표시하지 않음

## 13. 이동윤 AI·RAG 인계 작업

### 13.1 주관 파일

- [AI 계약](../../contracts/ai/)
- [AI 요청 Schema](../../contracts/ai/requests/)
- [AI 응답 Schema](../../contracts/ai/responses/)
- [AI 예시](../../contracts/ai/examples/)
- [AI Pydantic Schema](../../ai/app/schemas/)
- [AI HTTP Interface](../../ai/app/interfaces/http/)
- [AI 실행 진입점](../../ai/app/main.py)
- [AI Retry 정책](../../ai/configs/retry_policy.yaml)
- [AI 프로젝트 설정](../../ai/pyproject.toml)
- [AI 테스트](../../ai/tests/)
- [AI 오류 Category](../../contracts/error-codes/categories/ai.yaml)
- [공통 오류 Registry](../../contracts/error-codes/error-codes.yaml)

### 13.2 해결할 충돌

1. `SymptomAnalysisRequest`의 `inquiry_id` 일반 문자열과
   `DEMO-INQ-*` 예시를 UUID 계약으로 바꾼다. `DEMO-INQ-*`는
   `inquiry_code`일 뿐 공개 리소스 ID가 아니다.
2. 응답 JSON Schema의 최상위 `inquiry_id`·`correlation_id`와
   Pydantic의 중첩 `trace_context` 중 하나를 Canonical로 정한다.
3. Pydantic 필수 `model_metadata`와 JSON Schema의 누락을 맞추고,
   비어 있는 `ModelMetadata`·`ProcessingTrace` 속성을 정의한다.
4. 비어 있는 Consultation·Technician 요청·응답 Schema를 실제
   필드·Enum·필수값으로 완성한다.
5. README만 있는 예시 폴더에 정상·위험·근거 없음·제품 검증 실패·
   Timeout·Fallback JSON을 만들고 Schema를 통과시킨다.
6. 공통 Registry의 `AI-FAILED-01`과 비어 있는 AI Error Category를
   정합화한다.
7. OpenAPI Questionnaire Operation
   `accumulateInquiryQuestionnaire`와 PM Action `submitSymptom`을
   최지용 API 기준에서 하나로 맞추기 위한 변경안을 전달한다.
8. 실행 가능한 FastAPI App과 Health·분석 Endpoint, Python 버전,
   의존성, 환경변수, 설치·종료 명령을 고정한다.
9. AI는 위험도와 System Event 후보만 반환하고 Backend DB나
   `Inquiry.status_code`를 직접 수정하지 않는다.
10. AI 내부 재시도는 최대 1회이고 전체 30초 예산 안에 종료한다.

Backend 정책은 전체 Timeout 30초, Backend 자동 재시도 0회다. AI가
이 시간을 전부 소비하지 않도록 단계별 Timeout 합과 Fallback을
테스트한다. 설정 파일 값만 존재하고 Runtime이 읽지 않으면 구현
완료가 아니다.

AI 호출 시점은 `START_INQUIRY` 직후가 아니다.
`SUBMIT_SYMPTOM`으로 `DRAFT → QUESTIONNAIRE_IN_PROGRESS` 전이가
성공한 뒤 호출한다. AI 결과 후보는 다음 System Event로만 전달한다.

- `SAFE_GUIDANCE_READY`
- `DANGER_DETECTED`
- `NO_EVIDENCE`
- `PRODUCT_VALIDATION_FAILED`

### 13.3 작업 순서

1. `contracts/ai/**`의 ID·Trace·Metadata·오류를 정합화한다.
2. JSON Schema와 Pydantic의 양방향 직렬화를 맞춘다.
3. 실제 JSON Example을 추가하고 Schema 검증 Test를 만든다.
4. `ai/pyproject.toml`의 Python·Dependency와 `.env.example`의
   공개 변수명을 확정한다.
5. FastAPI App·Health·분석 Endpoint를 구현한다.
6. 전체 30초 안에서 내부 최대 1회 Retry·Fallback을 구현한다.
7. 비밀값·원문 전체·Prompt·개인 PC 경로가 Log에 남지 않게 한다.
8. 김은진의 계약·Timeout·안전 QA를 받는다.
9. 최지용에게 AI Commit SHA, Schema Version, 설치·실행·종료 명령,
   검증된 JSON Example을 전달한다.

### 13.4 환경·검증 명령

현재 `ai/pyproject.toml`이 설명 주석뿐이고 App 진입점도
Placeholder다. 따라서 아래는 **현재 실행 명령이 아니라 이동윤이
호환성을 검증하고 README에 확정한 뒤 사용할 명령 형식**이다.

```powershell
Set-Location (git rev-parse --show-toplevel)

python -m venv .\ai\.venv
.\ai\.venv\Scripts\python.exe -m pip install --upgrade pip
.\ai\.venv\Scripts\python.exe -m pip install -e .\ai
.\ai\.venv\Scripts\python.exe -m pytest .\ai\tests -q
```

실제 `app`을 구현한 뒤에는 별도 서버 터미널에서 다음 형식의 명령과
Health 응답을 검증해 README에 고정한다.

```powershell
Set-Location (git rev-parse --show-toplevel)

.\ai\.venv\Scripts\python.exe -m uvicorn `
  ai.app.main:app `
  --host 127.0.0.1 `
  --port 8001
```

다른 터미널:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

AI 서버 종료는 서버 터미널에서 `Ctrl+C`다. 실제 `app`이 없거나 위
명령을 검증하지 않았다면 팀 표준으로 공유하지 않는다.

### 13.5 완료·인계 기준

- JSON Schema와 Pydantic 상호 검증
- 필드·중첩·Enum·필수값 일치와 UUID 추적 ID
- 실제 정상·위험·근거 없음·검증 실패·오류·Fallback 예시 Schema 통과
- 재현 가능한 설치·실행·Health 명령
- AI 내부 Retry 최대 1회와 전체 30초 예산 테스트
- `.env.example`·Python·Dependency·README 완성
- AI의 DB 직접 수정 코드 0건
- 비밀값·원문 전체·Prompt·내부 경로 Log 노출 0건
- 최지용에게 정확한 AI Commit SHA·Schema·예시 전달

## 14. Backend AI Client 후속 연결

이동윤의 AI Commit이 전달된 뒤 최지용이 다음 경로를 구현한다.

- [AI HTTP Client](../../backend/integrations/ai/client.py)
- [Request Mapper](../../backend/integrations/ai/request_mapper.py)
- [Response Mapper](../../backend/integrations/ai/response_mapper.py)
- [Schema Validator](../../backend/integrations/ai/schema_validator.py)
- [Retry 정책](../../backend/integrations/ai/retry_policy.py)
- [AI 연동 예외](../../backend/integrations/ai/exceptions.py)

구현 기준:

- AI 계약 검증 후 요청
- `SUBMIT_SYMPTOM` 전이 Commit 이후에만 AI 작업을 예약
- 요청 시작 시 `inquiry_id`·`state_version`·`ai_request_id` 보존
- 외부 AI 호출을 DB Transaction 안에서 실행하지 않고 Commit 이후
  실행 또는 Outbox 정책 사용
- 전체 Wall-clock Deadline 30초와 개별 Connect·Read Timeout을 구분
- Backend 자동 재시도 0회
- `X-Correlation-ID`·Inquiry UUID 유지
- AI 오류를 Backend 공통 오류로 변환
- 응답 적용 전 Inquiry를 다시 잠그고 `state_version` 비교
- Stale 응답은 기록만 하고 상태에 적용하지 않음
- 동일 `ai_request_id`는 최초 성공 한 번만 적용
- AI 응답은 System Event 후보로 검증하며 상태를 직접 변경하지 않음
- 정상·위험·근거 없음·Timeout·Schema 오류·Stale·Duplicate Mock 테스트
- PostgreSQL과 Backend 전체 회귀 통과

`httpx.Timeout(30)` 하나만 설정해 전체 30초가 보장됐다고 보고하지
않는다. Queue·직렬화·Retry·응답 검증을 포함한 전체 경과시간으로
Deadline을 검증한다.

## 15. 팀원 작업 후 자기 Branch 검증·공유

### 15.1 변경 범위 확인

```powershell
Set-Location (git rev-parse --show-toplevel)

git status --short
git diff --check
git diff --name-only
```

자기 주관 범위를 벗어난 파일이 있으면 커밋 전에 원인을 확인한다.

### 15.2 Commit 원칙

- PM `main` 병합으로 들어온 최지용 파일을 다시 별도 수정본처럼
  Stage하지 않는다.
- 자기 주관 파일만 명시적으로 Stage한다.
- 생성물·Cache·가상환경·비밀값을 Stage하지 않는다.
- 하나의 작업과 검증을 하나의 Commit 단위로 묶는다.

예시 Commit:

```text
Data ID·Role·상태 Mapping 및 QA 갱신 | 2026-07-29
Web Workflow API·409 복구 연동 | 2026-07-29
Mobile Workflow API·상태 복구 연동 | 2026-07-29
AI Schema·Runtime·Timeout 정책 정합화 | 2026-07-29
PM State 대표 전이·Terminal 정책 정합화 | 2026-07-29
```

### 15.3 자기 Branch Push

`<본인-Branch>`를 자기 Branch로 바꾼다.

```powershell
git status --short
git log -1 --oneline
git push origin <본인-Branch>
```

`main`에 직접 Push하지 않는다.

## 16. 최종 동일 Commit 통합 게이트

통합 담당자가 지정한 하나의 Commit에서 다음을 실행한다. 팀원별
서로 다른 SHA의 결과를 합쳐 전체 통과라고 보고하지 않는다.

### 16.1 Backend

```powershell
Set-Location (git rev-parse --show-toplevel)

docker compose --env-file .\backend\.env up -d postgres

python .\scripts\development\check_environment.py `
  --service backend `
  --full `
  --postgresql
```

### 16.2 PM 계약

```powershell
$python = '.\backend\.venv\Scripts\python.exe'
& $python .\scripts\contracts\validate_state_machine.py
& $python .\scripts\contracts\render_state_machine.py `
  --compact `
  --state-labels both `
  --check
```

### 16.3 Data

```powershell
python -B data/tools/pipeline.py build synthetic
python -B data/tools/pipeline.py handoff db-smoke
python -B data/tools/pipeline.py handoff db-full
python -B data/tools/pipeline.py handoff qa
python -B data/tools/pipeline.py qa --verify-rebuild
python -B -m unittest discover -s data/tools/tests -v
python -B data/tools/pipeline.py inventory
python -B data/tools/pipeline.py finalize
```

### 16.4 Web

```powershell
Set-Location .\web
npm ci
npm run lint
npm run test -- --run
npm run build
Set-Location ..
```

Web 담당자가 Test Script를 추가하지 않았다면 이 단계는 실패가
정상이며 최종 상태는 `BLOCKED`다.

### 16.5 Mobile

아래 Script는 V2 3모듈을 확인한 뒤 해당 명령만 실행한다.

```powershell
Set-Location .\mobile
$settings = Get-Content .\settings.gradle.kts -Raw

if (
    $settings.Contains('include(":customer-app")') -and
    $settings.Contains('include(":technician-app")') -and
    $settings.Contains('include(":core")')
) {
    .\gradlew.bat :core:test
    .\gradlew.bat :customer-app:testDebugUnitTest
    .\gradlew.bat :technician-app:testDebugUnitTest
    .\gradlew.bat :customer-app:assembleDebug
    .\gradlew.bat :technician-app:assembleDebug
    .\gradlew.bat :customer-app:lintDebug
    .\gradlew.bat :technician-app:lintDebug
}
else {
    throw '프로젝트 구조 V2의 Mobile 3모듈과 일치하지 않습니다.'
}

Set-Location ..
```

Module 구조가 통과해도 Network 위치·API 계약 소비·Build 결과가
인계 기록에 없으면 Mobile 통합 승인으로 쓰지 않는다.

### 16.6 AI

```powershell
.\ai\.venv\Scripts\python.exe -m pytest ai/tests -q
```

AI 환경·테스트가 아직 확정되지 않았으면 `BLOCKED`로 보고하며,
실행하지 않고 통과로 기록하지 않는다.

## 17. 팀원이 돌려줄 인계 결과

각 팀원은 다음 양식을 작성해 다음 담당자에게 전달한다.

```text
[담당자]
[Branch]
[최종 Commit SHA]
[반영한 PM main SHA]
[참고한 jiyong 소스 SHA]
[수정 파일]
[해결한 충돌 번호]
[실행 명령]
[통과 결과]
[실패·미실행 결과]
[다음 담당자에게 주는 입력]
[남은 Blocker]
```

최소 전달물:

- 윤승혁(PM): `jiyong` 병합 `main` SHA·최종 전이·Terminal 계약 SHA
- 김은진: Data Mapping·Fixture·QA SHA
- 한예나: Web 계약 소비·Build·오류 복구 SHA
- 양정현: Mobile 계약 소비·Build·오류 복구 SHA
- 이동윤: AI Schema·Runtime·실행 명령 SHA
- 최지용: Backend Runtime·PostgreSQL·전체 회귀 SHA

## 18. 최종 완료 조건

- 같은 Commit에서 환경·계약·Migration·Seed·전체 테스트 통과
- 최신 `main`의 State Machine 생성 Script·MMD·SVG 보존
- Mobile이 V2의 3모듈과 일치하고 `mobile/app`·`mobile_prev`가 없음
- Public UUID와 업무 코드가 모든 소비자에서 분리
- `COUNSELOR`·`CONSULTANT` 정책이 Data와 Backend에서 일치
- PM 계약의 채택 상태·Version·Changelog가 기록되고 14단계 대표
  전이와 Data 시나리오가 일치
- Web·Mobile이 Backend 상태와 행동만 소비
- 상태 충돌 409만 최신 Snapshot으로 반영하고 사용자 입력 보존
- Key 재사용 409를 Snapshot으로 오인하지 않음
- AI Schema와 Backend AI Client가 상호 검증
- Stale·Duplicate AI 응답을 차단하고 AI가 DB 상태를 직접 변경하지 않음
- 현재 구현 Runtime의 OpenAPI·Serializer·오류 Registry·예시 정합
  차이 0건
- 미구현 범위와 Blocker가 숨겨지지 않음
- `main` 직접 Push 없이 각자 Branch와 Commit SHA로 인계

새 인계 문서를 중복 생성하지 않고 이 문서와 연결된 최신 기준
문서를 계속 갱신한다.
