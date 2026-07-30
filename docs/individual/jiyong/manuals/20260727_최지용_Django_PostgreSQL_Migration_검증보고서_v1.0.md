# 최지용 Django·PostgreSQL Migration 검증 보고서 v1.0

> 기준일: 2026-07-27
> 명령 실행 기준: 저장소 루트
> 대상: PostgreSQL 16.14·`config.settings.local`
> 문서 시점: `HISTORICAL SNAPSHOT` — 현재 실행·재현은 [공유 패키지 인계서 v1.3](<./20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md>)을 사용

## 0. 문서 책임·협업·검토

| 항목 | 내용 |
| --- | --- |
| 문서 상태 | `HISTORICAL SNAPSHOT` — 2026-07-27 당시 Model·Migration 적용 증거 |
| 관련 WBS | `T-005`, `T-016` |
| 작성·유지 책임 | 최지용 — Model·Migration 구현 범위와 실행 증거 갱신 |
| 산출물/내용 의사결정자 | 최지용 — ERD·테이블 명세·Migration Wave와 PostgreSQL 구현 기준 |
| 협업 책임 | 김은진 — PostgreSQL·Migration·Seed·통합 테스트 재현, 윤승혁(PM) — 전체 통합과 Workflow 영향 확인, 이동윤 — 후속 Vector·Evidence Schema 영향 확인 |
| 검토 요청 대상 | 김은진의 빈 PostgreSQL·Migration·Seed 재현 검토를 우선하고, 영향 Wave에서는 윤승혁(PM)·이동윤에게 해당 계약 범위만 검토 요청 |
| 검토 상태 | **미요청 또는 증거 미확인** — 이 문서에는 완료된 리뷰의 PR·Issue·Commit 증거가 아직 연결되어 있지 않음 |
| PR 병합 담당 | 윤승혁(PM) — 작성자가 아닌 팀원 1명 이상의 리뷰 후 병합 |
| 인계 대상 | 김은진, 윤승혁(PM), 이동윤 |

검토는 최지용의 DB 명세 작성이나 다음 Wave 착수를 허가하는 선행
승인이 아니다. 실제 PostgreSQL 재현성, 통합 영향과 후속 계약
호환성을 확인하는 절차다.

## 1. 판정

현재 구현된 Django Model과 Migration은 실제 PostgreSQL에서
재현됐다. 확정 도메인 테이블 32개 중 현재 Runtime 구현은 2개이며,
나머지 30개는 Wave 순서로 구현한다.

| 항목 | 2026-07-27 당시 실행 결과 |
| --- | --- |
| PostgreSQL 연결 | `CONNECTED` |
| PostgreSQL 버전 | 16.14 |
| DB 시간대 | UTC |
| Model 변경 누락 | 없음 |
| 미적용 Migration | 없음 |
| 구현된 도메인 Model | 2개 |
| 미구현 도메인 Model | 30개 |
| Demo Seed | 2회 멱등성 통과 |
| Backend 전체 회귀 | 239 passed |

ERD·테이블 명세·API 명세는 최지용의 확정 기준선이다. 이 보고서는
기준선 중 실제 Django·PostgreSQL로 구현된 범위를 실행 증거로
구분한다. 표의 테스트 수와 PostgreSQL 결과는 기록 시점 스냅샷이며
현재 Branch 완료 판정에는 같은 Commit에서 재실행한 결과를 사용한다.

## 2. 기준선

| 자료 | 용도 |
| --- | --- |
| [T-005 저장소 기준](<../../../database/t-005/README.md>) | ERD·계약·검증 진입점 |
| [T-005 결정 등록부](<../../../database/t-005/t005_decision_register_v0.1.json>) | 확정 설계 결정 |
| [T-005 물리 계약](<../../../database/t-005/t005_physical_contract_v1.0.json>) | ERD Snapshot과 구현 기준 연결 |
| [ADR-0008](<../../../adr/0008-t005-data-contract-decisions.md>) | 데이터 계약 결정 기록 |
| [구현 준비도 감사기](<../../../../scripts/database/audit_t005_implementation_readiness.py>) | 32개 테이블의 Model·App·Migration 매핑 |
| [T-005 Schema 검증기](<../../../../scripts/database/validate_t005_schema.py>) | 구조와 PostgreSQL 검증 |

현재 구현에 적용하는 주요 기준은 다음과 같다.

- 일반 실행 ID: `<ENTITY>-<UUID4_HEX_32>`, 최대 48자
- 합성 Seed ID: `<DEMO|SYN>-<ENTITY>-<SEQUENCE>`
- 사용 안내 canonical 필드: `usage_guidance_status`
- 사용 안내 코드: `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`,
  `PENDING_CONSULTATION`
- legacy `USE_ALLOWED`: 저장하지 않고 반입 시 `NORMAL`로 변환
- 방문 일정: `preferred_date`, `confirmed_date`, `schedule_status`,
  `synthetic_technician_id`
- Enum: 계약 YAML과 Django `TextChoices` 정합성 유지
- Seed: 검증된 ID와 `update_or_create`로 반복 실행 안전성 확보

## 3. 적용된 Migration

빈 PostgreSQL에 다음 Migration을 처음부터 적용했다.

| App | 적용 범위 |
| --- | --- |
| `contenttypes` | Django ContentType |
| `auth` | Django Permission·Group |
| `accounts` | User·CustomerProfile |
| `token_blacklist` | Refresh Token rotation·폐기 원장 |

현재 최지용 도메인 구현분은 다음 두 테이블이다.

```text
accounts_user
customers_customer_profile
```

Django와 라이브러리 내부 테이블은 32개 도메인 테이블 구현 수에
포함하지 않는다.

## 4. 재현 명령

저장소 루트에서 실행한다.

```powershell
Set-Location .\backend

.\.venv\Scripts\python.exe ..\scripts\database\check_postgresql_connection.py
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate --plan
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py migrate --check
.\.venv\Scripts\python.exe ..\scripts\database\validate_t005_schema.py --verify-postgresql
.\.venv\Scripts\python.exe ..\scripts\database\audit_t005_implementation_readiness.py
```

## 5. 검증 결과

| 검사 | 결과 |
| --- | --- |
| `makemigrations --check --dry-run` | `No changes detected` |
| Migration Plan | 생성 통과 |
| 빈 PostgreSQL Migration | 통과 |
| `migrate --check` | 미적용 Migration 없음 |
| DB Vendor | PostgreSQL |
| 현재 Model↔Migration 정합성 | 통과 |
| T-005 구조 | 32개 테이블·526개 컬럼 구조 유효 |
| 현재 구현 매핑 | 2개 구현·30개 미구현 |

`django_model_migration_parity_verified=true`는 현재 등록된 Model과
Migration 사이의 차이가 없다는 뜻이다. 확정 32개 테이블 전체가
구현됐다는 뜻으로 사용하지 않는다.

## 6. Seed 검증

[Demo Seed Command](<../../../../backend/apps/accounts/management/commands/seed_demo_accounts.py>)를
같은 PostgreSQL에서 두 번 실행했다.

| 실행 | 결과 |
| --- | --- |
| 1차 | 생성 4·갱신 0 |
| 2차 | 생성 0·갱신 4 |
| Demo 사용자 | 4 |
| 합성 고객 프로필 | 1 |
| 사용자 코드 중복 | 0 |
| 실제 전화번호·주소·이메일 | 0 |
| 사용 가능한 비밀번호 | 0 |

Seed 명령과 전체 로컬 재현 순서는
[공유 패키지 인계서 v1.3](<./20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md>)을
따른다.

## 7. Wave 구현 순서

32개 테이블을 한 번에 구현하지 않고 관계 순서로 진행한다.

| Wave | 대상 | 검증 |
| ---: | --- | --- |
| 1 | common code, user, customer profile | Model·Migration·코드·Seed |
| 2 | product model, subscription, care record | FK·UNIQUE·CHECK |
| 3 | inquiry, symptom, QA, assessment, guidance | 문의 누적·위험·안내 |
| 4 | consultation, handoff, visit, follow-up, status history | 상태 이력·배정·방문 관계 |
| 5 | knowledge, document, chunk, embedding, evidence, AI run | 문서·청크·근거·AI 추적 |

각 Wave는 다음 검증을 통과한 뒤 다음 단계로 이동한다.

1. `makemigrations --check --dry-run`
2. 빈 PostgreSQL Migration
3. PK·FK·UNIQUE·CHECK·Index 검사
4. Seed·Fixture 참조 검사
5. API Serializer·OpenAPI 예시 정합성

현재 다음 작업은 Wave 1이다. Wave 1 검증 후 Wave 2를 진행하고,
Wave 2 검증 후 T-022 문의 최소 수직 흐름을 구현한다.

## 8. 완료 경계

현재 완료:

- PostgreSQL 16.14 실제 연결
- 현재 User·CustomerProfile Model과 Migration 정합성
- 빈 DB Migration 재현
- Demo Seed 2회 멱등성
- 현재 구현분 Auth·Health Smoke

후속 구현:

- 나머지 도메인 Model·Migration 30개
- 각 Wave의 제약·Index·Seed
- T-022 이후 업무 API Runtime
- 지식·임베딩 Wave의 pgvector Migration

## 9. 변경 이력

| 버전 | 날짜 | 내용 |
| --- | --- | --- |
| v1.0 | 2026-07-27 | T-005 결정·2/32 매핑·실제 PostgreSQL Migration·Seed 증거를 최신 기준으로 통합 |

## 10. 인계 사항

| 대상 | 전달 항목 | 다음 행동 | 완료 확인 | 현재 상태 |
| --- | --- | --- | --- | --- |
| 김은진 | 현재 2/32 구현 경계, Migration 적용 순서, Seed 2회 결과, Schema·회귀 검증 명령 | 빈 PostgreSQL에서 Migration과 Seed를 재현하고 제약·민감정보·회귀 결과를 확인 | 재현 명령과 결과가 PR 또는 Issue에 남고 예상 밖 중복·drift가 없음 | 작성자 검증 완료, 제3자 재현 증거 미확인 |
| 윤승혁(PM) | Wave 순서와 Workflow·상태 이력에 영향을 주는 후속 테이블 경계 | Workflow 관련 Wave 착수 시 State Machine 계약과 DB 관계의 충돌 여부를 확인 | 영향 항목 또는 충돌 없음이 PR 리뷰에 기록됨 | 현재 2개 Model에는 별도 검토 증거 없음 |
| 이동윤 | 지식·문서·Chunk·Embedding·Evidence·AI Run을 다루는 Wave 5 경계와 pgvector 적용 원칙 | Wave 5 착수 전에 Vector 차원·Evidence 연결 키·AI Schema 매핑을 확인 | 계약 매핑과 검증 결과가 PR 또는 Issue에 남음 | 후속 인계 예정, 현재 Wave에서는 미실시 |
| 최지용 | 제3자 재현·통합·AI 계약 검토에서 발견된 차이 | 차이를 해당 Model·Migration·계약·검증 보고서에 함께 반영하고 해당 Wave를 다시 검증 | 관련 집중 테스트와 전체 회귀 결과가 갱신됨 | 회신 대기 |

현재 다음 실행 책임은 최지용의 Wave 1 구현과 즉시 검증이다. 김은진,
윤승혁(PM) 또는 이동윤의 검토는 명세 작성 승인 대기가 아니며, 각자의
관할과 맞닿는 재현·통합·계약 차이를 발견해 회신하는 인계 단계다.
