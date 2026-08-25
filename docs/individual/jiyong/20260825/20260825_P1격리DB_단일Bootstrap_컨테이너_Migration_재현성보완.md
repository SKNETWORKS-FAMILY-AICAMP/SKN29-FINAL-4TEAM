# P1 격리 DB 단일 Bootstrap 컨테이너·Migration 재현성 보완

작성일: 2026-08-25  
담당: 최지용(Backend·DB)  
대상: 신규 팀원 PC의 P1 회원가입·문의 E2E용 로컬 PostgreSQL

## 1. 결론

최신 `main`의 깨끗한 작업공간과 보호된 승인 고객 입력 파일이 있으면,
아래 Bootstrap 한 번으로 P1 격리 DB의 Docker Image·Container·Volume,
Role, 승인 Migration, 고객 6건, 합성 상담사, Replay 및 HOLD Gate까지
준비할 수 있다.

```powershell
.\scripts\development\bootstrap_p1_team_isolated_local.ps1 -Apply
```

실제 고객 연락처 원문은 Git에 넣지 않는다. 팀원은 승인된 보안 채널로
입력 파일을 받아 다음 위치에 먼저 저장한다.

```text
backend/.runtime/p1-approved-customers.json
```

## 2. 이번 보완 내용

### 2.1 Docker 실행 계약 검증

Bootstrap은 Container가 단순히 `healthy`인지만 보지 않고 다음 값까지
일치해야 완료된다.

| 항목 | 승인값 |
|---|---|
| Image | `pgvector/pgvector:0.8.6-pg16-bookworm` |
| Container | `waterbridge-p1-team-isolated-postgres` |
| Compose Project | `waterbridge-p1-team-isolated` |
| Volume | `waterbridge-p1-team-isolated-postgres-data` |
| Host Bind | `127.0.0.1`만 허용 |
| DB | `waterbridge_p1_team_isolated` |
| Data 분류 | `approved-test-synthetic-only` |

Image·Label·Port·Volume 중 하나라도 다르면 Fail-closed한다. 기존 Volume을
삭제하거나 다른 DB로 자동 대체하지 않는다.

### 2.2 PostgreSQL Port 충돌 자동 회피

새 Runtime에서 기본 Port `55445`가 사용 중이면 `55446`부터 `55545`까지
첫 번째 비어 있는 Loopback Port를 자동 선택한다. 선택값은 보호된
`admin.env`와 최종 상태 JSON에 동일하게 기록된다.

이미 만든 Runtime을 재사용할 때는 새 Port를 고르지 않고 그 Runtime에
기록된 기존 Port를 그대로 사용한다. 사용자가 다른 Port를 강제로 넘기면
DB 혼선을 막기 위해 중단한다.

### 2.3 승인 고객 입력 누락 방지

기본 입력 경로를 고정했다. 따라서 팀원이 매번 `-ApprovedCustomerInput`
인자를 입력할 필요가 없다.

입력 파일의 계약은 다음과 같다.

- JSON 배열이며 정확히 6건
- 각 행의 필드는 `name`, `phone`, `email`만 허용
- 이름·전화번호 중복 금지
- 전화번호는 승인된 합성 형식만 허용
- 입력 파일은 반드시 `backend/.runtime` 아래에 위치
- Bootstrap 시작 시 현재 Windows 사용자만 접근하도록 ACL 제한
- 이메일은 DB에 평문 저장하지 않고 암호화 본문과 검색용 HMAC으로 저장
- 가입 전 상태이므로 `User=0`, `CustomerAccountLink=0` 유지

입력 파일 원문·이메일·전화번호·OTP는 문서, Git, CI Log에 남기지 않는다.

### 2.4 Web 개발 Port 허용

로컬 Web 실행 Port `5173`과 `5174`를 모두 Backend CORS 허용 목록에
포함했다. 이는 Web이 Backend API를 호출할 수 있게 하는 설정이며,
Web 기능 자체를 Bootstrap이 실행한다는 뜻은 아니다.

## 3. 단일 Apply에서 수행하는 순서

1. 최신 `main` 또는 `jiyong`과 HEAD가 정확히 같은지 확인
2. 추적·미추적 파일을 포함한 작업공간 Clean 여부 확인
3. Docker CLI·Compose 확인
4. 보호 Runtime Secret 및 Role 비밀번호 생성
5. 비어 있는 Loopback PostgreSQL Port 선택
6. 고정 pgvector Image Pull 및 PostgreSQL Container 기동
7. Image·Container·Label·Port·Volume 계약 검증
8. 전용 DB와 Migrator·Runtime·Readonly·AI Readonly Role 생성
9. P1 Migration Allowlist만 적용
10. `visits.0005` 미적용 HOLD 확인
11. 공통 코드와 합성 상담사 1명 Seed
12. 승인 고객·연락처·JAC104 구독 6건 Dry-run·Apply·Replay
13. Django Check와 P1 Scope Audit
14. 회원가입·로그인·AI 없는 DRAFT 문의 생성 후 Rollback 검증
15. Migration 잔여 0건과 최종 상태 JSON 저장

## 4. 신규 PC 실행 절차

### 4.1 사전조건

- Docker Desktop 실행
- Python 3.13.13 Backend 가상환경과 고정 의존성 준비
- 최신 `main` Checkout 및 Clean Worktree
- 승인 고객 입력 파일을 보호 채널로 수신

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git status --short
```

`git status --short` 출력이 없어야 한다.

### 4.2 입력 파일 배치 확인

```powershell
Test-Path .\backend\.runtime\p1-approved-customers.json
```

`True`가 아니면 Apply하지 않는다. 파일을 Git에 추가하지 않는다.

### 4.3 Plan 확인

```powershell
.\scripts\development\bootstrap_p1_team_isolated_local.ps1
```

Plan은 DB를 변경하지 않는다. Image, Container, Volume, HOLD, 입력 파일
존재 여부를 먼저 확인할 수 있다.

### 4.4 단일 Bootstrap 실행

```powershell
.\scripts\development\bootstrap_p1_team_isolated_local.ps1 -Apply
```

정상 완료 시 상태는 `P1_TEAM_ISOLATED_RUNTIME_READY`이다.

## 5. 완료 확인값

최종 상태 파일:

```text
.runtime/p1-team-isolated/evidence/p1-team-bootstrap-status.json
```

필수 확인값:

```text
status=P1_TEAM_ISOLATED_RUNTIME_READY
postgres_health=PASS
migration_gate=READY
visits_0005=NOT_APPLIED_P1_HOLD
approved_customers=6
active_primary_contacts=6
active_subscriptions=6
consultant_users=1
auth_login_inquiry_contract=PASS_ROLLBACK_PRESERVED
approved_customer_input_acl=CURRENT_USER_ONLY
secret_values_printed=false
```

상태 파일에는 실제 Port, Image ID, Container·Volume·Compose Project도
기록되므로 팀원 간 환경을 값으로 비교할 수 있다.

## 6. 기존 Runtime 재확인

이미 같은 Source로 완성된 Runtime은 Seed나 Migration을 반복하지 않는다.

```powershell
.\scripts\development\bootstrap_p1_team_isolated_local.ps1 `
  -Apply -ReuseLocalRuntime
```

기존 고객·문의·가입 결과는 보존하며 Django Check, 운영 Scope Audit,
Migration HOLD와 Docker 계약만 다시 확인한다.

## 7. Bootstrap에 포함하지 않는 항목

다음 항목은 Secret 또는 장치별 설정이므로 별도 실행한다.

- Gmail SMTP 계정·App Password와 실제 OTP 발송
- Backend 장기 실행 Process
- OTP Outbox Worker
- AI Runtime·OpenAI Key
- Web 설치·Vite 실행
- Android Build·APK 설치·USB 승인·ADB Reverse

이 경계를 지키는 이유는 DB Bootstrap에 개인 Secret과 장치 설정을
섞지 않고, DB 재현 실패와 외부 서비스 실패를 분리하기 위해서다.

## 8. 검증 결과

- 현재 Container: `healthy`
- 현재 Image: `pgvector/pgvector:0.8.6-pg16-bookworm`
- 현재 Bind: `127.0.0.1:55479`
- 현재 Volume: 승인 전용 Volume 일치
- Bootstrap 계약 테스트: 8 passed
- P1 계정·Scope·Rollback·Migration·Provision 표적 회귀: 69 passed
- PowerShell Parser: 오류 0건
- `visits.0005`: P1 HOLD 유지

현재 실행 중인 DB를 삭제하거나 다시 Seed하지 않고 읽기 전용 계약 검증을
수행했다. 신규 PC의 Fresh Apply는 각 팀원의 깨끗한 최신 `main`에서
실행하며, 기존 Volume을 자동 삭제하지 않는다.
