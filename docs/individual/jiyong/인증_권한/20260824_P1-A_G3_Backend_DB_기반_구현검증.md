# P1-A G3 Backend·DB 기반 구현·검증

> 작성일: 2026-08-24
>
> 담당: 최지용 (Backend·DB)
>
> 기준선: `origin/main@e99cf78faa58a40f2cec49281119c437b594e470`
>
> 판정: `G3_BACKEND_DB_AUTHOR_PASS / DATA_CROSSWALK_ACK_PENDING / API_RUNTIME_NOT_IMPLEMENTED / MOBILE_G2_MERGED_RUNTIME_WAIT`

## 1. 목적

G2에서 동결된 합성 계약고객 회원가입·계정연결 계약을 구현하기 전에,
가입 전 고객과 보호 이메일·계정 연결 이력을 PostgreSQL에서 안전하게 표현할
수 있는 Backend·DB 기반을 준비한다.

2026-08-22에 작성됐던 기존 G3 WIP의 Model·Migration·Seed를 폐기하거나
재생성하지 않았다. 최신 `main`에서 다시 검증한 뒤 유효한 핵심 로직만
선별 적용했다. 오래된 Endpoint·오류계약 변경은 가져오지 않았다.

검증 도중 `main`에 Mobile G2 구현이 병합되어 기준 SHA가 `e99cf78f`로
변경됐다. 해당 변경은 `mobile/**`에만 있으므로 Backend 후보와 겹치지
않았고, 새 `main`에서 후보를 다시 적용해 표적 검증했다.

## 2. 구현 범위

### 가입 전 고객

기존 `CustomerProfile.user` 관계를 삭제하지 않고 nullable로 완화했다.

- 기존 가입 고객: 현재 `CustomerProfile.user` 관계 유지
- 가입 전 합성 계약고객: `user_id=NULL`
- 가입 전 고객은 기존 사용자 소유권 조회에 일치하지 않아 공개 고객 API에
  노출되지 않음

### 보호 계약 이메일

`accounts_contract_email_contact`를 추가했다.

- 발송용 인증 암호문과 검색용 HMAC-SHA256을 분리 저장
- Key Version 보존
- 고객당 활성 대표 연락처 1건
- 고객·HMAC 조합당 활성 연락처 1건
- `.invalid` 합성 이메일만 허용
- 실제 키·평문 이메일은 Git·문서·로그에 기록하지 않음

필수 환경변수 이름은 다음과 같다.

```text
CONTRACT_EMAIL_ENCRYPTION_KEY
CONTRACT_EMAIL_HMAC_KEY
CONTRACT_EMAIL_KEY_VERSION
```

### 계정 연결 이력

`accounts_customer_account_link`를 추가했다.

- User와 Customer의 활성 1:1 연결 보존
- 기존 직접 관계는 `LEGACY_BACKFILL`로 이관
- 신규 회원가입은 후속 Runtime에서 `SIGN_UP_EMAIL_OTP`로 생성
- User당 활성 Link 1건
- Customer당 활성 Link 1건
- 해제 상태와 `revoked_at` 정합성 DB Check

현재 G3 Seed는 가입 전 상태만 만들기 때문에 User와 Link를 생성하지 않는다.

## 3. Migration

신규 Migration:

```text
accounts.0006_p1_account_link_foundation
```

적용 순서:

```text
신규 Contact·Link 테이블 생성
→ 기존 CustomerProfile.user 관계 Backfill
→ 누락·User 중복·Customer 중복 검증
→ CustomerProfile.user nullable 완화
```

팀 통합 Migration Allowlist에도 `accounts.0006`을 추가했다.
`visits.0005` HOLD는 그대로 유지한다.

실제 Claim이 생긴 뒤에는 역 Migration으로 Link를 제거하지 않는다.
장애 대응은 기능 비활성화와 Forward-only 보정 Migration을 사용한다.

## 4. 합성 Seed

명령:

```powershell
python manage.py seed_p1_account_link_fixture --dry-run --json
python manage.py seed_p1_account_link_fixture --json
```

입력은 기존 정본 Candidate와 Schema를 사용한다.

```text
data/synthetic/candidates/p1_account_link_candidates.json
data/schemas/synthetic/p1AccountLinkCandidate.schema.json
```

Seed 결과 기준:

```text
CustomerProfile=1
ContractEmailContact=1
CustomerSubscription=1
User=0
CustomerAccountLink=0
plaintext_email_rows=0
```

동일 Seed Replay는 기존 PK·public_id·암호문·updated_at을 변경하지 않는다.
승인 Candidate와 기존 행이 충돌하면 덮어쓰지 않고 전체 Transaction을
실패시킨다.

## 5. 작성자 검증

### 정적·표적 검증

```text
Django Check=PASS
makemigrations --check --dry-run=NO_CHANGES
pip check=PASS
G3 Model·Migration·Seed·Allowlist 표적=33 passed
Contract Test=46 passed
P1-A Candidate Test=7 passed
Backend 전체 회귀=1475 passed, 41 skipped
git diff --check=PASS
```

41개 Skip은 PostgreSQL Row Lock·실제 Socket처럼 별도 실행환경을 요구하는
기존 조건부 검사다. 신규 G3 PostgreSQL 검증은 아래 격리 환경에서 별도로
실행했다.

Windows 제한 실행환경에서는 Pytest 임시 폴더 ACL 때문에 전체 결과 집계가
중단됐으나, 동일 명령을 제한환경 밖의 전용 임시 경로에서 재실행해
`1475 passed / 41 skipped`를 확인했다. 문제 구간 136건 분리 실행도
`136 passed / 23 skipped`였으므로 제품 코드 실패로 분류하지 않는다.

### 격리 PostgreSQL

기존 팀 DB·보존 Volume과 연결되지 않는 tmpfs 컨테이너에서 검증했다.

```text
Allowlist Before=PLAN_READY
Allowlist After=ALREADY_APPLIED
approved_migrations=93
remaining_plan=0
unexpected_migrations=0
accounts.0006=APPLIED
visits.0005=NOT_APPLIED
Seed Dry-run=DRY_RUN_READY
Seed First Apply=APPLIED
Seed Replay created_rows=0
Replay Snapshot SHA-256 Match=true
PostgreSQL Check Constraints=4/4
PostgreSQL Conditional Unique Indexes=4/4
```

검증용 컨테이너는 결과 확인 후 종료·자동삭제했다. 영속 Volume은 생성하지
않았으며 기존 Docker Container·DB·Volume은 수정하지 않았다.

### Data Source Hash Gate

읽기 전용 Source Hash 검사인
`python scripts/data/refresh_source_hashes.py --check`는
`CustomerProfile.user` nullable 변경에 따라 Data Crosswalk의 등록
Source Hash가 오래됐음을 정확히 보고했다.

```text
source=backend/apps/accounts/models/customer_profile.py
current_sha256=2AAC87DFF333A317EFF843299B04417E066F5433FEAD041E4D597F54A78C7A5C
registered_sha256=F3406AF7D09268C85ECD9042D04CF5A5261F7993D2B4BEC95415C1326CAB578C
source_hash_gate=STALE_CHANGED_1
```

`data/**`는 김은진 주관할이므로 Crosswalk와 생성 보고서를 임의 수정하지
않았고 Source Hash를 수동 갱신하지 않았다. 현재 Pre-commit Hook는 staged
`data/**`가 없으면 Data QA를 생략하므로 기술적으로 Commit을 차단하지는
않는다. 그러나 팀 소유권·Crosswalk 정합성 기준상 Data Owner ACK 전에는
G3 Runtime 코드를 원격에 공개하지 않는다.

Backend Commit·Push는 김은진이 위 Source 변경을 검토하고 Hash-only 정합화
범위를 ACK한 뒤 진행한다. Fixture 값·Scenario·기대 결과는 변경 대상이 아니다.

## 6. 의도적으로 하지 않은 작업

- OTP Challenge·발송·검증 Runtime
- Signup·ID/PW Login·아이디 찾기·비밀번호 재설정 API Runtime
- claim/reset ticket 발급·소비
- 기존 Owner Resolver의 `CustomerAccountLink` 전환
- Mobile·Web·AI 코드 수정
- 실제 고객·실제 이메일 적재
- 기존 Migration 수정
- `visits.0005` 적용

G2 OpenAPI는 `CONFIRMED`지만 위 API Runtime은 아직 `NOT_IMPLEMENTED`다.

## 7. 다음 단계

1. 김은진에게 `CustomerProfile` 변경과 새 Source Hash를 전달해 Data
   Crosswalk 정합화 범위를 확인받는다.
2. Data Source Hash Gate PASS 후 본 G3 Backend·DB 기반을 `main`에 병합한다.
3. 양정현의 Mobile G2 구현은 `main@e99cf78f`에 병합됐으며 실제 HTTP
   연동은 Backend Runtime 이후 진행한다.
4. 다음 Backend Slice에서 OTP·Signup·Login·Recovery Runtime을 구현한다.
5. Runtime 완료 후 Mobile과 실제 HTTP Smoke를 진행한다.
6. PostgreSQL 독립 QA에서 Migration·Backfill·Seed Replay·비밀값 비노출을
   재검증한다.

현재는 Mobile 결과를 기다리면서 Backend·DB 기반까지 독립적으로 준비된
상태이며, 전체 회원가입 E2E 완료로 판정하지 않는다.
