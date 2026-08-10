# TEAM_INTEGRATION DB 패키지 독립 QA 결과

> 검토자: 김은진 — 데이터·QA·DevOps  
> 후보: `20260809_TEAM_INTEGRATION_DB_v0.1`  
> 검증 Commit: `62e0d8b58ef0e6ac771f5ac62d725b2292857a99`  
> 후보 구현 Commit: `94ad7b9`  
> 검증일: 2026-08-10 KST  
> 판정: `PACKAGE_QA_APPROVE / REMOTE_NOT_PROVISIONED`

## 1. 판정 요약

후보 파일 17개를 현재 Git 추적 파일로 확인했고, Python 3.13.13 Conda
환경에서 패키지 단위 테스트와 Backend 전체 회귀를 실행했다. 기존
`waterbridge`·`watercare`를 변경하지 않고 `waterbridge_team_integration`을
별도 DB로 신규 생성해 전체 Forward Migration, 권한 재조정, 승인 Demo Seed
2회, T-005 감사와 실제 4-Role Matrix를 재현했다.

로컬 패키지와 Runtime QA 범위는 통과했다. 원격 Endpoint·DNS·CA·팀
Credential과 Backend API Smoke 환경은 제공되지 않았으므로
`TEAM_INTEGRATION_APPROVE`로 확대하지 않는다.

원본 인계서의 `LOCAL_WORKTREE_NOT_PUBLISHED` 상태는 현재 기준으로는
해소됐다. 후보 구현 Commit `94ad7b9`는 확인 당시 `origin/main`,
`origin/jiyong`, `origin/eunjin`, `origin/dongyoon`에 포함돼 있었다. 이는
코드 패키지 게시 상태일 뿐 원격 TEAM_INTEGRATION DB 공유 완료를 뜻하지
않는다.

## 2. 검증 환경

| 항목 | 실제 값 |
| --- | --- |
| Python | Conda `watercare-bootstrap`, Python 3.13.13 |
| PostgreSQL | 16.14, `pgvector/pgvector:0.8.6-pg16-bookworm` |
| 환경 | `QA_ISOLATED`, 로컬 Docker PostgreSQL |
| 대상 DB | `waterbridge_team_integration` |
| Schema | `public` |
| 로컬 연결 TLS | `connection_ssl=false` |
| 원격 `verify-full` | `NOT_RUN` |

Role 비밀번호 4개는 프로세스 메모리에서 난수로 생성해 검증 종료 시
환경변수와 함께 폐기했다. 값·DSN·`.env` 내용은 출력하거나 파일로 저장하지
않았다. 이 로컬 DB는 QA 증거용이며 팀 Credential 배포 대상이 아니다.

## 3. 요구사항별 결과

| 검증 항목 | 결과 | 현재 실행 증거 |
| --- | --- | --- |
| 후보 파일 완전성 | `PASS` | 요구 파일 17/17 존재·Git 추적 |
| 패키지 단위 테스트 | `PASS` | 56 passed |
| Provision Plan | `PASS` | `PLAN_READY`, `mutates_database=false` |
| 최초 Apply | `PASS` | DB `CREATED`, 4 Role 모두 `CREATED` |
| Forward Migration | `PASS` | 전체 Migration 적용 완료 |
| Migration 상태 | `PASS` | `migrate --check` exit 0, Drift 없음 |
| Django Check | `PASS` | 문제 0 |
| 권한 재조정 | `PASS` | DB·4 Role `EXISTS`, 이후 명시 회전 `ROTATED` |
| Demo Seed Replay | `PASS` | 2회차 비의도 신규 생성 0 |
| T-005 감사 | `PASS` | `READY`, blockers 0 |
| 실제 4-Role Matrix | `PASS` | 1 passed, skip 0 |
| Backend 전체 회귀 | `PASS` | 882 passed, 14 skipped |
| 원격 TLS·API Smoke | `NOT_RUN` | Endpoint·DNS·CA·Credential 미제공 |

Backend 전체 회귀의 14개 Skip에는 PostgreSQL 전용 Assertion과 기본적으로
비활성화된 TEAM_INTEGRATION Role Test가 포함된다. Role Test는 별도
`TEAM_INTEGRATION_POSTGRES_TEST=1` 실행에서 1/1 통과했다.

## 4. Seed 멱등성 결과

| Command | 재실행 결과 |
| --- | --- |
| `seed_common_codes` | group created=0, code created=0 |
| `seed_demo_accounts` | created=0, updated=4 |
| `seed_demo_products` | 기존 `DEMO-PMD-001` update |
| `seed_demo_subscriptions` | 기존 `DEMO-SUB-001` update |
| `seed_demo_care_records` | created=0, updated=3 |

`seed_common_codes`가 보고한 확정되지 않은 위험도·AI 단계 Mapping 차단은
기존 Fail-closed 정책이며, 미매핑 값을 자동 추론하거나 적재하지 않았다.

## 5. 관찰된 안전 동작

검증 도중 기존 Role에 새 임시 비밀번호를 주입하면서
`--rotate-passwords`를 생략한 재실행은 redacted `OperationalError`로
중단됐다. 기존 비밀번호를 암묵적으로 바꾸지 않는 동작이었으며,
`--rotate-passwords`를 명시한 뒤 4개 Role이 모두 `ROTATED`되고 같은 검증이
통과했다. 이 결과는 코드 결함으로 분류하지 않았다.

기존 DB Rename·덮어쓰기, Volume 삭제, Rollback·파괴 Test, Dump 반입과
실제 개인정보 사용은 수행하지 않았다.

## 6. 실행한 명령 범주

```powershell
# Python 3.13 Conda 환경에서 실행
python -m pytest <TEAM_INTEGRATION package test 5개> -q -p no:cacheprovider
python scripts/database/provision_team_integration.py
python scripts/database/provision_team_integration.py --apply --confirm-database waterbridge_team_integration
python backend/manage.py migrate --plan --settings=config.settings.local
python backend/manage.py migrate --noinput --settings=config.settings.local
python backend/manage.py migrate --check --settings=config.settings.local
python backend/manage.py makemigrations --check --dry-run --settings=config.settings.local
python backend/manage.py check --settings=config.settings.local
python backend/manage.py <승인 Demo Seed 5개> --settings=config.settings.local
python scripts/database/check_postgresql_connection.py
python scripts/database/audit_t005_implementation_readiness.py --settings config.settings.local --require-ready
python -m pytest backend/tests/integration/database/test_team_integration_roles_postgresql.py -q -p no:cacheprovider
python -m pytest -q -p no:cacheprovider
```

## 7. QA 회신

```text
reviewer=김은진
review_scope=TEAM_INTEGRATION_DB_PACKAGE_AND_RUNTIME_QA
candidate_label=20260809_TEAM_INTEGRATION_DB_v0.1
candidate_received=true
required_files_complete=true
environment=QA_ISOLATED
actual_database=waterbridge_team_integration
actual_schema=public
postgresql_version=16.14
package_tests=PASS
provision_plan=PASS
migration_forward=PASS
migration_drift=NONE
seed_replay=PASS
role_matrix=PASS
backend_regression=882 passed/14 skipped/0 failed
tls_verify_full=NOT_RUN
connection_ssl=false
decision=PACKAGE_QA_APPROVE
remaining_issue=REMOTE_ENDPOINT_DNS_CA_CREDENTIAL_API_SMOKE_NOT_PROVIDED
reviewed_at=2026-08-10 10:23:10 KST
```

## 8. 다음 Gate

- DevOps: 운영 DB와 분리된 원격 Endpoint, 인증서 DNS, 신뢰 CA와 Role별
  Secret 발급 메타데이터 준비
- 최지용: 원격 Migrator Forward Migration과 권한 재조정 실행 창구 확정
- 김은진: 원격 `verify-full`, `connection_ssl=true`, Migration·Seed·Role
  Matrix와 Backend API Smoke 독립 재검증
- 윤승혁: 현재 상태를 `PACKAGE_QA_APPROVE`로만 반영하고 원격 Gate 통과 전
  `TEAM_INTEGRATION_APPROVE` 또는 팀 DB 완료로 표시하지 않기
