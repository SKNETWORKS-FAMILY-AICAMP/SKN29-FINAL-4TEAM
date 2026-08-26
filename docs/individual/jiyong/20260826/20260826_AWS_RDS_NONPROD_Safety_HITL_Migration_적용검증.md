# AWS RDS NONPROD Safety·HITL Migration 적용 검증

## 1. 판정

- 적용 기준 main SHA: `4ab9ce614ff1cb4695bce16e6b2224051f81e3d7`
- 환경: AWS RDS NONPROD `waterbridge_team_integration`
- 결과: 승인 Migration 적용 및 사후 검증 완료
- 승인 Migration: `98 / 98 APPLIED`
- 남은 승인 Plan: `0`
- 예상 밖 Migration: `0`
- `visits.0005`: `NOT_APPLIED_P1_HOLD`
- Seed·Evidence Import·Crosswalk·데이터 삭제: 실행하지 않음

이 문서의 완료 범위는 RDS Schema Migration Gate다. Backend 배포,
Safety·HITL 실제 API E2E, 독립 QA, 소비자 연결과 WBS 완료를 뜻하지 않는다.

## 2. 승인 경계

윤승혁(PM)의 A/A/A/A 결정에 따라 다음 경계를 적용했다.

1. 최신 main 병합본만 사용한다.
2. 최종 Allowlist에 포함된 승인 Migration만 적용한다.
3. `visits.0005`는 P1 HOLD로 제외한다.
4. 이번 단계에서는 Migration만 적용하고 데이터 작업은 하지 않는다.

작업은 별도 Clean Worktree에서 수행했으며 사용자 작업 중인 파일은 수정하지 않았다.

## 3. 접속·보안 확인

- 공용 PEM 공개키 지문과 승인 문서의 지문 일치: PASS
- EC2 Host Key와 기존 `known_hosts` 승인 지문 일치: PASS
- SSH 터널: PASS
- PostgreSQL: `16.14`
- pgvector: `0.8.2` 설치 및 지원 버전 판정 PASS
- TLS 연결: PASS
- 연결 대상 DB·Migrator Role 일치: PASS

Endpoint·IP·DSN·Password·PEM·Token 원문은 기록하지 않았다.

## 4. 적용 전 Gate

Allowlist Plan 결과는 다음과 같았다.

| 항목 | 적용 전 결과 |
|---|---|
| 상태 | `PLAN_READY` |
| 적용 Migration 수 | 96 |
| 남은 승인 Plan | 2 |
| 남은 항목 | `inquiries.0014`, `inquiries.0015` |
| `visits.0005` | 미적용·Plan 제외 |
| 새 Constraint 위반 행 | 0 |
| `support_human_review` | 미존재 |

적용 전 업무 데이터는 덤프하지 않았다. 복구·감사 용도로 Schema와
`django_migrations` 원장만 Git 제외 Runtime 경로에 논리 백업했다.

| 백업 | SHA-256 |
|---|---|
| 적용 전 Schema | `3F37ECBCF8B2B66510212C7046C5E570796763DED02EE1B48F94682A50EAB3D6` |
| 적용 전 Migration 원장 | `759CFD028E4F3AE34ABC8B879C987D5C37BBF436AF8832CBDF1DBD9A4D209B9E` |

RDS 자동 Backup Retention과 최근 복구 가능 시점은 EC2 IAM에
`rds:DescribeDBInstances` 권한이 없어 이번 실행에서 확인하지 못했다.
이는 운영 후속 확인 항목이며 자동백업을 확인했다고 확대 판정하지 않는다.

## 5. 적용 결과

공식 `migrate_team_integration_allowlist.py`를 사용해 다음 두 건만 적용했다.

1. `inquiries.0014_allow_approved_partial_stop_danger`
2. `inquiries.0015_humanreview`

적용 결과는 `APPLIED_AND_VERIFIED`였다.

| 항목 | 적용 후 결과 |
|---|---|
| 승인 Migration | `98 / 98 APPLIED` |
| 남은 승인 Plan | 0 |
| 예상 밖 Migration | 0 |
| `visits.0005` | `NOT_APPLIED_P1_HOLD` |
| `support_human_review` | 생성됨 |
| 초기 행 수 | 0 |
| Constraint | 17개, 전부 Validated |
| Index | 9개 |
| Danger `PARTIAL_STOP` 승인 규칙 | 반영됨 |

적용 후 Schema와 Migration 원장도 다시 백업했다.

| 백업 | SHA-256 |
|---|---|
| 적용 후 Schema | `BFBB93B9561F4B0F3ACB60AE6E3818CFB92A17385EBDAE2BCC8C7E0506CBF228` |
| 적용 후 Migration 원장 | `2EF0DC45C32025984A8D6DD4C8BD8713C726BE84962D71DD54572B79DEC36E26` |

## 6. 권한 검증

Admin Provisioning 재실행은 보호환경의 Admin 접속 인증 문제로 실패했다.
비밀번호 회전이나 우회 권한 변경은 하지 않았다.

다만 기존 Migrator Default Privilege가 신규 Table에 정상 상속됐으며,
실제 Catalog 기준 권한은 다음과 같이 요구사항을 충족한다.

| Role | 검증 결과 |
|---|---|
| Migrator | Table Owner, Schema CREATE 허용 |
| Runtime | SELECT·INSERT·UPDATE·DELETE 허용, TRUNCATE 금지 |
| Readonly | SELECT 허용, INSERT·UPDATE·DELETE·Schema CREATE 금지 |
| AI Readonly | 원본 Table SELECT 금지, 공식 View SELECT 허용, DML·Schema CREATE 금지 |

따라서 현재 Migration의 권한 Gate에는 Blocker가 없다. 향후 Role 생성·비밀번호
회전·권한 복구가 필요할 때를 위해 Admin 보호환경 인증은 별도로 정비해야 한다.

## 7. Readiness

과거 7건 Baseline Profile로 실행하면 현재 RDS가 이미 3모델 53건이어서
건수 불일치로 BLOCKED된다. 이는 이번 Migration 실패가 아니다.

현재 실측 데이터에 맞는 Three-model Profile 결과는 다음과 같다.

- 상태: `READY`, Exit 0
- Crosswalk·Embedding Identity·Readonly View: 53건
- 모델 분포: JAC104 15, IAC425 19, IAC606 19
- Lineage 완전성: 53 / 53
- AI Readonly 정책: PASS
- Blocker: 없음

기존 8월 18일의 “RDS Evidence 7건” 문서는 당시 기준선 기록이며,
현재 RDS 상태를 뜻하지 않는다.

## 8. 후속 작업

1. 김은진(QA)이 동일 main SHA에서 Migration·Schema·Role 결과를 독립 확인한다.
2. 윤승혁(PM) 또는 인프라 담당자가 자동 Backup Retention과 복구 가능 시점을 확인한다.
3. Admin 보호환경 인증을 점검하되 비밀번호 임의 회전은 하지 않는다.
4. Backend 최신 main 배포 후 Safety·HITL API 실제 E2E를 별도 수행한다.
5. `visits.0005`는 별도 승인 전까지 계속 HOLD한다.

