# WaterBridge 데이터베이스·저장소 설계

> 현행 기준일: 2026-07-31
> 기본 PostgreSQL 데이터베이스: `waterbridge`
> PostgreSQL Schema: `public`
> 상세 전환·복구·검증 근거:
> [WaterBridge DB 전환 및 Active 범위 검증](../individual/jiyong/technical/backend/20260731_waterbridge_database_transition_and_active_scope_validation.md)

## 저장소 책임

| 영역 | 책임 |
|---|---|
| PostgreSQL `waterbridge/public` | 고객·구독·문의·상담·방문·상태이력·감사 관계 |
| PostgreSQL pgvector | 승인된 공식 문서 청크의 embedding과 검색 |
| 외부 원본 저장소 | 공식 PDF·FAQ 원본, Git 비추적 |
| Git `data/**` | 합성 fixture, Schema, expected data, manifest·QA |

Docker Compose 프로젝트명과 Volume 이름은 데이터베이스 이름과 다른
식별자다. 기존 데이터를 보존하기 위해 Compose 프로젝트
`watercare-local`과 Volume `watercare-postgres-data`는 변경하지 않는다.

## 물리 계약과 Active 데이터 범위

| 구분 | 현재 범위 | 의미 |
|---|---:|---|
| T-005 물리 계약 | 32개 테이블 | Model·Migration과 PostgreSQL에 모두 유지 |
| Active 데이터 범위 | 13개 테이블 | 2026-07-31 기준 1행 이상 존재 |
| Target-only 범위 | 19개 테이블 | 물리 계약은 유지하며 현재 0행 |

Active 13은 별도 Schema나 축소 Migration이 아니다. 나머지 19개를
삭제하거나 비활성화하지 않고, 데이터·기능이 준비될 때 기존 32개
계약 안에서 순차 사용한다. Django·JWT·운영 원장 등 계약 외 기술
테이블은 위 32개 집계에 포함하지 않는다.

## 식별자·적재 원칙

- fixture 정수 `id`는 로컬 관계용이며 Backend PK로 직접 주입하지 않는다.
- `public_id`와 업무키로 Backend row를 조회한 뒤 실제 DB FK를 사용한다.
- 업무 코드는 Public API ID나 DB FK로 사용하지 않는다.
- 미확정 Care mapping은 직접 load 대상에서 제외한다.
- “원본 24개 중 활성 22개”는 Data fixture 소스의 계약 정합 load
  후보 범위이며, PostgreSQL 계약 테이블 32/13/19 집계와 다른 기준이다.
- 기본 `waterbridge`에는 합성 Handoff Importer를 `--dry-run`까지
  포함해 실행하지 않는다. 새 빈 격리 DB에서만 최초 적재와 Replay를
  검증한다.

## 2026-07-31 현재 검증 상태

- PostgreSQL 16.14·pgvector 0.8.6, `current_database()=waterbridge`,
  `current_schema()=public`을 읽기 전용으로 확인했다.
- 전체 Migration 적용, `makemigrations --check --dry-run`, T-005
  계약 테이블 32/32와 Active 13/Target-only 19의 행 수 경계를
  확인했다.
- 기본 DB에서 Demo Seed 5종을 2회 실행했고 2회차 신규 생성은 0이다.
- 새 빈 격리 PostgreSQL에서 367 Source의 Dry-run·최초 적재·Replay를
  검증했다. Replay는 355 unchanged·12 projected이며 검증 후 격리
  DB를 삭제했다.
- Backend 회귀는 표적 API 21, SQLite 740 passed·11 skipped,
  PostgreSQL 751 passed다.
- Data는 67 tests, QA 오류·경고 0, 대표 E2E 17/17을 통과했다.
- Health·Demo Login·UUID JWT·`/me`·Refresh Rotation·Logout과
  401 Replay 차단 HTTP Smoke를 통과했다.
- T-005 구현 준비도는 기술적으로 `READY`이나, 비작성자·외부 리뷰와
  PM 계약 완료 승인이 남아 있어 공식 완료로 선언하지 않는다.

## 이력 보존과 금지사항

2026-07-29~30 보고서의 `watercare` DB명, 검증용 DB 이름, 백업
파일명과 실행 수치는 당시 실제 증거이므로 바꾸지 않는다. 현행 실행
기준만 `waterbridge/public`을 사용한다.

- `docker compose down -v`와 Volume 삭제를 실행하지 않는다.
- `.env`, 비밀번호, Token, DB Dump를 Git에 추가하지 않는다.
- Migration 대신 수동 SQL로 테이블 계약을 맞추지 않는다.
- Target-only 19개 테이블을 삭제하거나 별도 축소 Schema로 분리하지 않는다.

RAG 승인은 JAC104D D세대 REV.00 37~39쪽 7개 증상에 한정하며,
누수 검색 5위와 지침서 3.3 v2 평가 포맷은 후속 개선 대상이다.
