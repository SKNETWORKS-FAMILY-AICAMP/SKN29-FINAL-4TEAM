# Django T-017C 계정 수명주기·감사 구현 및 검증 가이드

> 작성일: 2026-08-11 KST
> 작성자: 최지용 — Backend·Database
> 범위: 합성 계정의 비활성화·재활성화, Token 세대, 관리자 보호, 감사
> 현재 판정: `작성자 구현·SQLite 회귀 PASS / PostgreSQL 동시성·독립 QA 대기`
> 배포 판정: `HOLD`

## 1. 구현 목적

T-017B의 Django Admin Action은 계정을 비활성화할 수 있었지만 다음 보안
공백이 있었다.

- 비활성화 전 Access Token이 재활성화 뒤 다시 유효해질 수 있었다.
- 한 사용자의 기존 Refresh Token 전체 폐기 경계가 없었다.
- Admin과 Bootstrap 명령이 상태·Group을 직접 변경해 Transaction과 감사를
  우회했다.
- 마지막 Superuser와 마지막 실무 계정관리자를 동시에 보호할 공통 잠금이
  없었다.
- 계정 변경 전후 상태·수행자·사유·Correlation을 보존하는 전용 원장이
  없었다.

이번 Slice는 새 Public 관리 API를 추가하지 않고 기존 JWT, Django Admin,
Bootstrap 명령을 같은 Lifecycle Service로 묶어 위 공백을 닫는다.

## 2. 구현 범위

### 2.1 User와 JWT

- `User.auth_version`: 1 이상의 정수, 기존 행 기본값 1
- Access·Refresh 모두 `auth_version` Claim 포함
- 누락·문자열·Boolean·0·음수·과거·미래 값은 동일한 인증 실패로 차단
- Login·Refresh 발급 직전에 User 행을 `select_for_update()`로 재검증
- Refresh 회전 중에도 원 Token과 현재 User의 세대가 정확히 같아야 함
- OutstandingToken의 저장 문자열도 최종 역할·세대 Claim과 동기화

### 2.2 계정 Lifecycle Service

아래 내부 Service만 계정 상태와 고정 관리자 Group을 변경한다.

- `deactivate()`
- `reactivate()`
- `grant_account_admin()`
- `revoke_account_admin()`

공통 처리 순서는 다음과 같다.

1. 공백이 아닌 변경 사유와 UUID Correlation 검증
2. `AccountLifecycleLock(pk=1)` 잠금
3. Actor·Target User를 PK 순서로 잠금
4. Actor 권한과 합성 Target 재검증
5. 자기 변경·중복 상태·마지막 관리자 Guard
6. 상태 또는 관리자 권한 변경
7. `auth_version + 1`
8. Target의 Outstanding Refresh 전체 blacklist
9. append-only 감사 1건 생성
10. 모두 성공할 때만 Commit

감사 저장이나 Token 폐기 중 하나라도 실패하면 User·Group·Token·감사 변경을
전부 rollback한다.

### 2.3 관리자 보호

실무 계정관리자는 다음 조건을 모두 만족해야 한다.

- 활성·합성·staff `OPERATOR`
- 고정 Group `T017_ACCOUNT_ADMINISTRATORS` 구성원
- `add_user`, `change_user`, `view_user` Permission 보유
- 사용 가능한 Password 보유

마지막 복구 가능 Superuser와 마지막 실무 계정관리자의 비활성화·권한 회수는
`LAST_ADMIN_PROTECTED`로 차단한다. 서로 다른 두 관리자를 동시에 변경해도
Singleton 잠금으로 직렬화하도록 구현했다.

### 2.4 계정 감사

`AccountAuditEvent`에는 다음만 저장한다.

- Target·Actor, 이벤트 유형, 변경 사유, Correlation UUID, 발생 시각
- 역할·활성·staff·superuser·세대
- 정렬된 Group·Permission 이름
- 실제 값이 아닌 변경 필드 이름

Password, Token, Secret, hash 및 프로필 PII 값은 저장하지 않는다. 기존 감사
행의 `save`, `delete`, QuerySet `update/delete/bulk_update/bulk_create`는 모두
차단한다. Actor·Target FK는 `PROTECT`다.

### 2.5 기존 우회 경로 정리

- Django Admin 비활성화·재활성화 Action → Lifecycle Service 호출
- Admin 생성·프로필 수정 → 사유 필수, 안전한 감사 생성
- Bootstrap `--grant/--revoke` → Actor·사유 필수, Lifecycle Service 호출
- 고정 Group·Permission 직접 M2M 변경 → Signal에서 차단
- Demo Seed 재실행 → 기존 Password·staff·Group·`auth_version` 보존

## 3. Migration과 T-005 경계

Migration `accounts.0005_account_lifecycle_and_audit`는 다음을 수행한다.

- `auth_version` 추가와 양수 CheckConstraint
- `AccountLifecycleLock`과 Sentinel 행 생성
- `AccountAuditEvent`·Index·Constraint 생성
- Cutover 시 기존 Outstanding Refresh 전부 blacklist

Reverse 함수는 폐기된 Refresh를 되살리지 않는다. 감사 행이 생긴 실제 환경에서
Migration을 되돌리면 감사 테이블이 삭제되므로 Schema Reverse는 폐기 가능한 QA
DB에서만 검증한다. 실제 배포 rollback은 새 Schema를 유지하고 구버전 발급을
중단하는 별도 Runbook이 필요하다.

T-005의 32개 업무 테이블 수는 바꾸지 않았다. 신규 감사·잠금 테이블은
`APPROVED_RUNTIME_SUPPORT_TABLES`에만 등록했다.

## 4. 작성자 검증 결과

2026-08-11에 아래를 확인했다.

| 검증 | 결과 |
| --- | --- |
| Django system check | PASS, issue 0 |
| Model·Migration parity | PASS, 변경 누락 0 |
| T-017C·Migration·Seed 표적 | PASS |
| Accounts 전체 + T-005 Readiness | `115 passed, 1 skipped` |
| PostgreSQL 연결 확인 | PostgreSQL 16.14 연결, DB timezone UTC |
| PostgreSQL 쓰기 가능 여부 | `default_transaction_read_only=on` |
| PostgreSQL 동시성 Case | 코드 작성 완료, 현재 연결에서는 NOT_RUN |
| T-017C 구현 직후 Backend 전체 | `961 passed, 17 skipped`, 실패 0 |
| T-024 포함 최신 통합 후보 Backend 전체 | `966 passed, 17 skipped`, 실패 0 |

SQLite에서 SKIP된 1건은 서로 다른 두 실무 관리자의 동시 권한 회수
PostgreSQL 행 잠금 Case다. SQLite 결과를 동시성 PASS로 확대하지 않는다.

## 5. 검증 명령

작업 위치는 `backend`다.

```powershell
.\.venv\Scripts\python.exe manage.py check --settings=config.settings.test
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.settings.test
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/unit/accounts
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/unit/database/test_t005_implementation_readiness.py
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/integration/accounts/test_t017c_lifecycle_postgresql.py
```

PostgreSQL Case는 폐기 가능한 별도 Test DB와 쓰기 가능한 QA Role에서만 실행한다.
공식·공유 DB에 `--create-db`, Migration Apply 또는 Seed를 실행하지 않는다.

## 6. 완료와 미완료 구분

현재 완료된 것:

- 코드·Migration·SQLite 표적·Accounts·Backend 전체 회귀
- 기존 Token 세대 차단과 전체 Refresh 폐기
- 관리자 보호·감사·rollback 경계
- Admin·Bootstrap·Demo Seed 알려진 우회 경로 정리
- PostgreSQL 동시성 Test Case 작성

아직 완료로 표시하면 안 되는 것:

- 쓰기 가능한 PostgreSQL QA DB의 동시성 실제 PASS
- Migration Forward·Reverse·Reapply의 PostgreSQL 재현
- 김은진의 독립 재현
- PM의 WBS 완료 판정
- T-047A 계정관리 보안 전체 완료

따라서 현재 상태는 `OWNER_IMPLEMENTATION_READY`이며, PostgreSQL·독립 QA 전에는
소비자 배포와 T-017C 공식 완료를 허용하지 않는다.
