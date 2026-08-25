# P1 격리 DB 신규 PC Bootstrap 구현·검증

- 작성일: 2026-08-25
- 담당: 최지용(Backend·DB)
- 실제 Docker 검증 SHA: `ac42cc26aa08b8319336037038263b5d8f320fbb`
- 대상 DB: `waterbridge_p1_team_isolated`
- 판정: `BACKEND_DB_READY / AI_8001_OUT_OF_SCOPE`

## 1. 문제와 원인

기존 `start_p1_team_isolated_backend.ps1`은 이미 존재하는 DB를 점검하고
Backend를 실행하는 소비 스크립트였다. 신규 PC에서 DB가 없을 때 DB·Role·
Migration·Seed를 생성하는 Bootstrap 단계가 없어서 Mobile 담당자의
`database does not exist` 오류를 해결할 수 없었다.

또한 기존 시작 스크립트의 일반 `migrate --check`는 의도적으로 HOLD 중인
`visits.0005`도 미적용 Migration으로 판단한다. 기존 로컬 DB에서 검사가
통과했다면 오히려 `visits.0005`가 이미 적용됐을 가능성이 있었다.

## 2. 구현 범위

### 신규 PC Bootstrap

- 기본 실행은 비변경 Plan
- Apply는 깨끗한 `main` 또는 검증용 `jiyong`이 원격과 정확히 같을 때만 허용
- 전용 Runtime·Compose Project·Container·Volume 사용
- Runtime 폴더와 Volume 중 하나만 존재하면 차단
- 실패한 최초 실행은 Volume을 삭제하지 않고 명시적 Reuse로 재개
- 완료된 Runtime Reuse에서는 Seed·Rollback E2E를 다시 실행하지 않음

### DB·Role·Migration

- 기존 Provisioner 기본 `team-integration` 동작 유지
- 허용 프로필 `p1-team-isolated` 추가
- P1 전용 DB와 Migrator·Runtime·Readonly·AI Readonly Role 분리
- P1 프로필은 loopback PostgreSQL만 허용하고 RDS·원격 Host 차단
- 기존 Migration Allowlist를 P1 프로필과 공유
- 승인 Migration 96건 적용
- `visits.0004` 적용, `visits.0005` 미적용 HOLD
- 누락·예상 밖·남은 승인 Migration 0건 검증

### 최소 Seed와 운영 Audit

- `seed_demo_accounts`를 사용하지 않음
- 합성 상담사 `DEMO-CONSULTANT-001` 한 명만 생성
- 최초 비밀번호는 사용 불가 상태이며 보안 입력 스크립트로 별도 설정
- P1 고객·대표 연락처·활성 JAC104 구독 각 6건만 생성
- Customer User와 AccountLink는 실제 OTP 가입 전 0건 유지
- Baseline Audit와 Operational Audit 분리
- Operational은 P1 고객 계정과 그 고객 소유 문의만 허용
- 비P1 고객·문의, 기사·운영자 계정은 Fail-closed

### 공통 실행환경과 OTP Worker

- Bootstrap이 만든 동일 Runtime 환경을 Backend·Seed·OTP Worker가 공유
- 고정된 로컬 Django Secret으로 이메일·OTP 암호문 복호화 정합성 유지
- DB Role 비밀값은 Admin 단계에만 Process 환경으로 로드 후 복원
- OTP Outbox Worker 전용 실행 스크립트 추가
- 비밀값·이메일·OTP 원문은 상태 JSON과 로그에 기록하지 않음

## 3. 실제 PostgreSQL 검증

### Plan

```text
status=PLAN_READY
mutates_local_environment=false
exact_tracking_ref=true
worktree_clean=true
target_database=waterbridge_p1_team_isolated
visits_0005=P1_HOLD_EXCLUDED
```

### 최초 실행 중 포트 충돌

기본 포트 `55445`가 이 PC에서 이미 사용 중이라 Container 네트워크 생성 전에
중단됐다. 스크립트는 신규 전용 Volume을 삭제하지 않고 보존했다.

이 결과를 반영해 미완료 Runtime은 같은 소스에서 다른 포트를 명시하여
이어갈 수 있도록 보완했다. `55479`로 재개해 정상 완료했다.

### Migration 결과

```text
status=APPLIED_AND_VERIFIED
approved_migration_count=96
applied_approved_count=96
missing=[]
unexpected=[]
remaining_plan_count=0
visits.0004=APPLIED
visits.0005=NOT_APPLIED_P1_HOLD
```

### Seed·Audit 결과

| 항목 | 결과 |
|---|---:|
| P1 승인 고객 | 6 |
| 활성 대표 연락처 | 6 |
| 활성 WPUJAC104DWH 구독 | 6 |
| 합성 상담사 | 1 |
| 가입 전 Customer User | 0 |
| 기사·운영자 User | 0 |
| 문의 | 0 |
| Blocker | 0 |

승인 고객 Seed를 다시 실행했을 때 고객·연락처·구독 추가 생성은 모두 0건이었다.

### AI 없는 인증·문의 생성

실제 PostgreSQL에서 DRF API Client로 다음을 실행하고 전체 Rollback했다.

```text
OTP signup=true
ID/PW login=true
inquiry_created=true
inquiry_status=DRAFT
inquiry_state_version=1
consultant_login=true
rollback_preserved=true
ai_called=false
```

따라서 AI 8001이 없어도 회원가입·로그인·구독 소유권 확인·신규 문의 DRAFT
생성까지는 실행 가능하다. 문진·Guidance·상담 요청은 이번 완료 범위가 아니다.

### 재사용·소비 스크립트

완료된 Runtime을 다시 실행해 다음을 확인했다.

```text
reuse=true
auth_login_inquiry_contract=NOT_RERUN_ON_REUSE
inquiry_creation_without_ai=PRESERVED
```

추가로 Backend `-CheckOnly`와 OTP Worker `-Once`를 실행했다.

```text
p1_isolated_database=READY
customers=6
inquiries=0
visits_0005=NOT_APPLIED_P1_HOLD
worker_failed=0
worker_processed=0
secret_values_printed=false
```

검증 후 PostgreSQL Container만 중지했고 전용 Volume은 보존했다.

## 4. 자동 테스트

다음 표적·인접 회귀를 함께 실행했다.

```text
65 passed
```

포함 범위:

- Provisioner 기존 팀 프로필과 신규 P1 프로필
- Migration Allowlist와 `visits.0005` 차단
- Bootstrap·Runtime Loader·Backend·OTP Worker 계약
- 상담사 최소 Seed Dry-run·Apply·Replay·충돌 차단
- Baseline·Operational Audit
- 기존 P1 정리·Rollback E2E·상담사 로그인 회귀

추가 확인:

- Python `py_compile`: PASS
- PowerShell Parser 5개: PASS
- `git diff --check`: PASS
- Data 폴더 변경: 없음

## 5. 산출물

| 경로 | 역할 |
|---|---|
| `scripts/development/bootstrap_p1_team_isolated_local.ps1` | 신규 PC Plan·Apply·Reuse |
| `scripts/development/import_p1_team_isolated_env.ps1` | 동일 Runtime 환경 로드 |
| `scripts/development/start_p1_team_isolated_backend.ps1` | 운영 Audit 후 Backend 실행 |
| `scripts/development/start_p1_auth_email_worker.ps1` | OTP Outbox 처리 |
| `scripts/development/set_p1_consultant_password.ps1` | 상담사 보안 비밀번호 입력 |
| `scripts/database/provision_team_integration.py` | 명명된 P1 DB·Role 프로필 |
| `scripts/database/migrate_team_integration_allowlist.py` | P1 승인 Migration Gate |
| `seed_p1_team_consultant.py` | 합성 상담사 한 명만 Seed |
| `audit_p1_team_runtime_scope.py` | Baseline·Operational 읽기 전용 Audit |

팀 공용 사용법은 Daily Process의 다음 파일로 별도 전달한다.

```text
20260825_팀공용_P1격리Backend_DB_보안입력_실행가이드_v0.1.md
```

## 6. 인계와 남은 작업

### Mobile

Bootstrap과 Backend·OTP Worker를 실행한 뒤 실제 화면에서 다음을 확인한다.

1. OTP 회원가입
2. 생성한 username과 password로 로그인
3. 활성 JAC104 구독 확인
4. 신규 문의 생성
5. `DRAFT`, `state_version=1` 회신

### Web

합성 상담사 ID/PW 로그인은 가능하다. 다만 Mobile 신규 문의가 DRAFT인 동안
미배정 상담 목록 표시를 기대하지 않는다. AI 후 `CONSULTATION_REQUIRED`가 된
동일 문의로 목록·Claim을 검증한다.

### QA

Main 병합 후 신규 PC에서 Plan→Apply→Reuse를 독립 재실행하고 DB 수량,
Migration HOLD, 비밀값 비노출, DRAFT 문의 생성을 확인한다.

## 7. 최종 경계

이번 결과로 완료된 것은 신규 PC용 P1 Backend·DB 환경과 AI 없는 신규 문의
생성까지다. AI Runtime 8001, 실제 문진·Guidance·상담 요청, Web 미배정 목록
표시는 후속 수직 E2E이며 현재 PASS로 선언하지 않는다.
