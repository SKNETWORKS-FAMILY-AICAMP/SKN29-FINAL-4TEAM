# PostgreSQL 합성 데이터 적재 및 통합 검증 가이드

- 최초 구현·검증일: 2026-07-29
- 현행화일: 2026-08-02
- 담당 영역: Backend·Database
- 협업 대상: Data/QA, PM, Backend API 소비자
- 현재 판정: 빈 격리 PostgreSQL의 합성 데이터 367건 작성자 검증 완료
- 내부 상태 코드: `DB_FULL_VERIFIED`
- 제외 범위: 실제 고객·운영 데이터, 기본 개발 DB에 대한 합성 데이터 Import

이 문서는 합성 데이터용 도메인 Model·Migration, Fixture 무결성,
정식 적재기와 PostgreSQL 실행 검증을 하나의 재현 기준으로 제공한다.
단계별 수치는 해당 시점의 증거로 취급하고, 현재 판정은 이 문서의 최종
실측과 재현 조건을 함께 충족할 때만 사용한다.

현재 설치·Migration·Seed의 저장소 진입점은
[Backend README](../../../../backend/README.md)이고, T-005 전체 구현
판정은
[T-005 워터브리지 PostgreSQL 통합 검증 보고서](PostgreSQL_통합검증_보고서_20260731.md)를
우선한다.

## 1. 적용 범위와 판정

정식 Django 관리 명령으로 `db-smoke` 37건과 `db-full` 367건을 각각
`dry-run → 1차 실제 적재 → 동일 입력 재실행` 순서로 검증했다.

| 범위 | 결과 | 판정 의미 |
|---|---|---|
| 합성 Fixture 12종 | Source 367건 | 승인 합성 데이터 입력 범위 |
| Smoke | 37 Source, 31 Direct, 6 Projected | 최소 관계 Closure 검증 |
| Full | 367 Source, 355 Direct, 12 Projected | 전체 합성 Handoff 검증 |
| Dry-run | 도메인·배치·원장 저장 0건 | 동일 검증 경로 실행 후 Rollback |
| Replay | 생성 0건, 수정 0건 | 반복 안전성 확인 |
| Aggregate | 문의 22건·방문 4건, 불일치 0건 | 최종 상태·버전과 최신 이력 정합 |
| Audit | 125쌍, 불일치 0건 | 감사 이벤트와 전이 이력 1:1 정합 |

`DB_FULL_VERIFIED`는 새 빈 격리 PostgreSQL의 합성 Handoff 367건에만
적용한다. 운영 적재 완료, 실제 개인정보 데이터 검증, Web·Mobile 전체
업무 E2E 완료를 의미하지 않는다.

과거 문서의 `10/32`, `12/32`, `NOT_READY` 표기는 각 Wave 당시의 역사
기록이다. 현재 T-005 Model·App Registry·Migration 기술 판정은
`32/32`이며, 공식 WBS 완료 여부는 PM 리뷰·계약 Gate와 분리한다.

## 2. 도메인 Model과 Migration

### 2.1 구현 테이블과 무결성

| 영역 | DB 테이블 | 주요 데이터 | 핵심 무결성·추적 조건 |
|---|---|---|---|
| 상담 | `support_consultation` | 문의별 순번·상담사·상태·결과·요약·시각 | 문의+순번 유일, 역할·상태·시각 검증, 양수 버전·멱등 키 |
| 방문 | `field_service_visit` | 담당 기사·요청·예정·완료 시각·결과 | 기사 역할, 상태별 필수값, 시간 순서, 양수 버전·멱등 키 |
| 후속 확인 | `support_followup_confirmation` | 문의·상담·방문·안내·응답·다음 동작 | 연결 상담·방문의 문의 일치, 상태별 응답·확정 시각 |
| 케어 | `subscriptions_care_record` | 문의·방문·결과·일정·수행자·원천 | 연결 엔티티와 완료·취소·날짜 조합 제약 |
| 문의 | `support_inquiry` | 시나리오·배정·채널·위험도·안내·근거·추적 ID | 시나리오 유일, 배정 역할 일치, 코드·버전 제약 |
| 구독 | `subscriptions_customer_subscription` | 설치일·원천 고객제품 UUID·주소 | 원천 UUID 조건부 유일, 고객·제품 관계 유지 |
| 상태 이력 | `workflow_transition_history` | 대상·행위자·상태·이벤트·버전·상관관계 | 한 행 한 대상, 대상별 버전 유일, 시스템 행위자 조합 |
| 감사 이벤트 | `audit_event` | 전이별 대상·이벤트·행위자·버전·추적값 | 전이와 1:1, 대상 유형·FK 일치, 발생 시각 정합 |
| 적재 원장 | `operations_synthetic_import_batch`, `operations_synthetic_import_item` | 실행·원본 행·대상·Hash·처리 결과 | Source 합계와 Action 합계 일치, 행별 provenance |

주요 구현 근거:

- [Consultation Model](../../../../backend/apps/consultations/models/consultation.py)
- [Visit Model](../../../../backend/apps/visits/models/visit.py)
- [FollowupConfirmation Model](../../../../backend/apps/inquiries/models/followup_confirmation.py)
- [CareRecord Model](../../../../backend/apps/care/models/care_history.py)
- [Inquiry Model](../../../../backend/apps/inquiries/models/inquiry.py)
- [Subscription Model](../../../../backend/apps/subscriptions/models/subscription.py)
- [TransitionHistory Model](../../../../backend/apps/workflow/models/transition_history.py)
- [AuditEvent Model](../../../../backend/apps/audit/models/audit_event.py)
- [Import Ledger Model](../../../../backend/apps/operations/models/synthetic_import_ledger.py)

### 2.2 연쇄 오류 방지 장치

| 위험 | 적용 장치 | 적재기·서비스 책임 |
|---|---|---|
| 다른 문의의 상담·방문 연결 | `FollowupConfirmation.clean()`의 문의 일치 검사 | 저장 전 `full_clean()` 또는 같은 서비스 검증 수행 |
| 잘못된 역할 배정 | 상담사·기사·문의 담당자의 역할 검증 | `bulk_create()` 등 검증 우회 금지 |
| 이력 한 건에 복수 대상 연결 | 정확히 하나의 대상만 허용하는 `CheckConstraint` | 원천 상태와 승인 상태 계약 매핑 |
| 같은 버전 전이 중복 | 대상별 조건부 유일 제약·멱등 키 인덱스 | 트랜잭션·재시도 정책 보장 |
| 이력과 감사 불일치 | `OneToOneField(PROTECT)`와 대상 일치 검사 | 한 트랜잭션에서 함께 생성·Rollback |
| 완료·취소 필드 모순 | 상태별 필수·금지 필드 및 시각 순서 제약 | 오류 행은 건너뛰지 않고 전체 중단 |
| 원천 추적 단절 | 공개 UUID·업무 키·상관 ID·행 Hash·원장 보존 | Crosswalk·Fixture 버전과 Hash 검증 |

### 2.3 Migration 체인

실제 적용 순서는 파일 목록의 수동 순서가 아니라 Django Migration
Graph의 `dependencies`가 결정한다.

| 앱 | Migration | 역할 |
|---|---|---|
| inquiries | [0003_add_synthetic_handoff_fields](../../../../backend/apps/inquiries/migrations/0003_add_synthetic_handoff_fields.py) | 문의 합성 데이터·배정·추적 필드 |
| visits | [0001_initial](../../../../backend/apps/visits/migrations/0001_initial.py) | 방문 테이블·제약·인덱스 |
| consultations | [0001_initial](../../../../backend/apps/consultations/migrations/0001_initial.py) | 상담 테이블·제약·인덱스 |
| workflow | [0002_expand_transition_targets](../../../../backend/apps/workflow/migrations/0002_expand_transition_targets.py) | 전이 대상 확장 |
| audit | [0001_initial](../../../../backend/apps/audit/migrations/0001_initial.py) | 감사 이벤트 |
| care | [0002_add_imported_care_fields](../../../../backend/apps/care/migrations/0002_add_imported_care_fields.py) | 케어 외부 데이터 필드 |
| inquiries | [0004_followup_confirmation](../../../../backend/apps/inquiries/migrations/0004_followup_confirmation.py) | 후속 확인 |
| subscriptions | [0002_add_synthetic_projection_fields](../../../../backend/apps/subscriptions/migrations/0002_add_synthetic_projection_fields.py) | 고객제품 투영·설치 필드 |
| operations | [0001_initial](../../../../backend/apps/operations/migrations/0001_initial.py) | 적재 배치·항목 원장 |
| workflow | [0003_backfill_legacy_changed_at](../../../../backend/apps/workflow/migrations/0003_backfill_legacy_changed_at.py) | 기존 이력 11건의 `changed_at` 보정 |

기본 개발 DB에는 위 Migration과 보정 Migration을 적용하면서 기존 테이블
행 수를 보존했다. `workflow.0003` 적용 후 대상 11건은
`changed_at = created_at`이고 잘못된 미래 시각은 0건이었다.

## 3. 정식 합성 데이터 적재기

### 3.1 구현 구성요소

| 계층 | 구현 | 역할 |
|---|---|---|
| 원장 | [synthetic_import_ledger.py](../../../../backend/apps/operations/models/synthetic_import_ledger.py) | 배치·Source 행별 결과와 provenance |
| Repository | [operations_repository.py](../../../../backend/apps/operations/repositories/operations_repository.py) | 공개 UUID·업무 키 해석, 충돌 검출, 검증·저장 |
| Service | [operations_service.py](../../../../backend/apps/operations/services/operations_service.py) | Fixture 로딩, Closure, 순차 적재, 사후 검증, 트랜잭션 |
| CLI | [import_synthetic_handoff.py](../../../../backend/apps/operations/management/commands/import_synthetic_handoff.py) | `smoke`, `full`, `--dry-run` 실행 |
| 테스트 | [test_synthetic_handoff_import.py](../../../../backend/tests/integration/operations/test_synthetic_handoff_import.py) | Rollback, 멱등성, 전수 적재, 충돌 검증 |

### 3.2 처리 순서와 트랜잭션

```text
users
→ customer_profiles
→ products
→ customer_products(PROJECTED)
→ subscriptions
→ inquiries + representative symptoms
→ consultations
→ visits
→ followup_confirmations
→ care_histories
→ inquiry_status_histories
→ audit_events
→ 사후 검증
→ batch/item ledger
→ commit 또는 dry-run rollback
```

모든 단계는 `transaction.atomic()` 안에서 실행한다. Model 검증, FK,
식별자, Source Closure, Aggregate 상태, 감사 이력 중 하나라도 실패하면
도메인 행과 원장 모두 Rollback한다. `--dry-run`도 같은 쓰기·검증 경로를
끝까지 실행한 뒤 의도적으로 Rollback한다.

PostgreSQL Sequence는 일반 행과 같은 방식으로 Rollback되지 않을 수
있다. 따라서 dry-run은 폐기 가능한 새 빈 격리 DB에서만 수행한다.

`customer_products`는 별도 Backend 테이블로 만들지 않고
`CustomerSubscription`에 투영한다. 원장에는 `PROJECTED`로 기록해
367개 입력 중 누락으로 오인하지 않게 한다.

### 3.3 식별자·갱신·시간 정책

| 항목 | 정책 | 방지하는 문제 |
|---|---|---|
| 조회 | 공개 UUID 우선, 업무 키 결과와 교차 확인 | 다른 UUID의 silent merge |
| 불변값 | 소유·연결·업무 키가 다르면 전체 중단 | Aggregate 재연결 |
| 갱신 | 값이 다른 필드만 `update_fields`로 저장 | 불필요한 쓰기·시각 변경 |
| 검증 | 신규·변경 객체에 `full_clean()` | 역할·상태 조합 우회 |
| 원본 정수 ID | 실행 중 관계 Map에만 사용 | Fixture PK와 DB PK 결합 |
| 원본 시각 | 존재하는 Source 시각만 보존 | 추정 시각의 감사 근거화 |
| 비밀번호 | 합성 사용자는 unusable password | Fixture 기반 공용 비밀번호 노출 |

문의 대표 증상은 문의 공개 UUID 기반 UUID v5로 결정적으로 생성한다.
구조화 Payload에는 공개 UUID만 넣고 Fixture 정수 FK는 넣지 않는다.

### 3.4 원장과 provenance

| 원장 값 | 의미 |
|---|---|
| `dataset_version` | `data/config/pipeline.json`의 데이터셋 버전 |
| `mapping_version` | Backend Import Crosswalk 버전 |
| `fixture_set_sha256` | 12개 Fixture 배열의 정규 JSON 세트 Hash |
| `source_dataset` | 원본 Fixture 종류 |
| `source_public_id` | 원본 공개 UUID |
| `source_business_key` | 원본 업무 키 |
| `source_sha256` | 원본 행의 정규 JSON SHA-256 |
| `action` | `CREATED`, `UPDATED`, `UNCHANGED`, `PROJECTED` |
| `target_model` | 적재·투영 대상 Model |
| `target_public_id` | 대상 공개 UUID |
| `target_business_key` | 대상 업무 키 |

Dry-run에서는 원장도 Rollback되므로 성공 JSON의 Batch 식별자는 `null`이다.

## 4. PostgreSQL 실측

### 4.1 검증 환경과 실행 증거

| 항목 | 값 |
|---|---|
| DBMS | PostgreSQL 16.14 |
| 데이터셋 버전 | `0.9.0` |
| Backend 매핑 버전 | `2.0.0` |
| Smoke 격리 DB | `watercare_synthetic_smoke_verify_20260729_mainv2` |
| Full 격리 DB | `watercare_synthetic_full_verify_20260729_mainv2` |
| Fixture Source | 12종, 367건 |

| 프로필 | 실행 | Batch code | 완료 시각(UTC) |
|---|---|---|---|
| `db-smoke` | 최초 | `SYN-IMPORT-6ADD1A8220654C28B40EC6A8A0908EFC` | `2026-07-29T10:58:01.967425+00:00` |
| `db-smoke` | Replay | `SYN-IMPORT-7617F68A827A4CF1B4C875E618967D77` | `2026-07-29T10:58:15.486953+00:00` |
| `db-full` | 최초 | `SYN-IMPORT-22B7EA784F88432399625A6E6E4C4C1C` | `2026-07-29T11:00:02.490369+00:00` |
| `db-full` | Replay | `SYN-IMPORT-1C0E022644654F2BBFF84B2DF5F3BAD3` | `2026-07-29T11:00:24.370239+00:00` |

### 4.2 프로필별 결과

| 프로필 | Source | Dry-run 저장<br>도메인/배치/원장 | 1차<br>생성/수정/무변경/투영 | Replay<br>생성/수정/무변경/투영 |
|---|---:|---:|---:|---:|
| `db-smoke` | 37 | `0 / 0 / 0` | `31 / 0 / 0 / 6` | `0 / 0 / 31 / 6` |
| `db-full` | 367 | `0 / 0 / 0` | `355 / 0 / 0 / 12` | `0 / 0 / 355 / 12` |

### 4.3 Full 실제 행 수

| PostgreSQL 테이블 | 행 | 설명 |
|---|---:|---|
| `accounts_user` | 16 | 합성 사용자 |
| `customers_customer_profile` | 12 | 합성 고객 프로필 |
| `catalog_product_model` | 1 | MVP 제품 |
| `subscriptions_customer_subscription` | 12 | 구독과 고객제품 투영 |
| `support_inquiry` | 22 | 문의 Aggregate |
| `support_inquiry_symptom` | 22 | 문의에서 파생된 대표 증상 |
| `support_consultation` | 12 | 상담 |
| `field_service_visit` | 4 | 방문 |
| `support_followup_confirmation` | 1 | 후속 확인 |
| `subscriptions_care_record` | 25 | Import Source 케어 |
| `workflow_transition_history` | 125 | 문의·방문 상태 이력 |
| `audit_event` | 125 | 상태 이력 1:1 감사 |
| **도메인 합계** | **377** | Source 367건과 파생 증상 포함 |
| `operations_synthetic_import_batch` | 2 | 1차·Replay Batch |
| `operations_synthetic_import_item` | 734 | Source 367 × 2회 |

### 4.4 상태·감사 정합성

| 검증 | 검사 건수 | 불일치 |
|---|---:|---:|
| Inquiry 최종 상태·버전 ↔ 최신 TransitionHistory | 22 | 0 |
| Visit 최종 상태·버전 ↔ 최신 TransitionHistory | 4 | 0 |
| AuditEvent ↔ 연결 TransitionHistory | 125 | 0 |
| **Aggregate 검증 합계** | **26** | **0** |

비교 필드는 이벤트, 행위자, `state_version`, `idempotency_key`,
`correlation_id`, 발생 시각이다. 하나라도 다르면 Batch 원장을 기록하기
전에 전체 트랜잭션을 Rollback한다.

## 5. 재현 절차

모든 명령은 저장소 루트에서 시작한다. 실제 비밀번호는 명령이나 문서에
넣지 않고 [환경변수 예시](../../../../backend/.env.example)를 따른다.

### 5.1 안전 확인

```powershell
Set-Location .\backend
$previousDatabase = $env:POSTGRES_DB
$env:POSTGRES_DB = 'waterbridge_synthetic_isolated_<yyyymmdd>'

if ($env:POSTGRES_DB -in @('waterbridge', 'watercare')) {
    throw '합성 데이터 적재기는 기본 개발 DB에서 실행할 수 없습니다.'
}
```

### 5.2 Migration·Smoke·Full

```powershell
try {
    $env:DJANGO_SETTINGS_MODULE = 'config.settings.local'

    .\.venv\Scripts\python.exe manage.py check
    .\.venv\Scripts\python.exe manage.py migrate --noinput
    .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run

    .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
      --profile smoke --dry-run
    .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
      --profile smoke
    .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
      --profile smoke

    .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
      --profile full --dry-run
    .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
      --profile full
    .\.venv\Scripts\python.exe manage.py import_synthetic_handoff `
      --profile full
}
finally {
    $env:POSTGRES_DB = $previousDatabase
}
```

완료 기준:

1. `smoke --dry-run` Source 37, 저장 0건
2. Smoke 1차 `31 CREATED + 6 PROJECTED`
3. Smoke Replay `0 CREATED + 0 UPDATED`
4. `full --dry-run` Source 367, 저장 0건
5. Full 1차 `355 CREATED + 12 PROJECTED`
6. Full Replay `0 CREATED + 0 UPDATED`
7. `projection_checks=12`, `aggregate_checks=26`,
   `audit_history_checks=125`

`CommandError`가 발생하면 일부 성공으로 간주하지 않는다. 원본 식별자,
관계, 코드 계약을 확인한 뒤 새 빈 격리 DB에서 dry-run부터 재시작한다.

## 6. 기본 개발 DB와 격리 DB 경계

기본 개발 DB의 `SYN-CUSTOMER-001` 관련 기존 레코드와 Canonical Fixture는
공개 UUID가 다를 수 있다. 이 DB에서 적재기나 `--dry-run`을 실행하면
`public UUID mismatch`로 실패하는 것이 예상 결과다.

이 충돌은 silent merge 차단이 작동한 것이므로 기존 UUID를 바꾸거나
검사를 우회하지 않는다. 기본 DB에서는 Migration·Demo Seed만 검증하고,
합성 데이터 Import는 새 빈 격리 DB에서만 검증한다.

### 금지사항

1. 기본 `waterbridge`·`watercare`에서 적재기와 dry-run을 실행하지 않는다.
2. `docker compose down -v`, `dropdb`, Volume 삭제를 재현 절차에 넣지 않는다.
3. Fixture 정수 ID를 Backend PK로 직접 주입하지 않는다.
4. 식별자 충돌을 자동 병합하거나 오류 행만 건너뛰지 않는다.
5. 실제 고객 정보·운영 Dump·비밀번호·JWT를 합성 DB에 넣지 않는다.
6. Sequence가 dry-run 이전 값으로 돌아간다고 가정하지 않는다.
7. Data/QA 소유 Fixture·Crosswalk를 Backend에서 임의 수정하지 않는다.
8. PM 소유 상태 계약을 Hash나 Model에 맞추기 위해 임의 수정하지 않는다.

## 7. 검증 이력의 해석

| 단계 | 역사 결과 | 현재 해석 |
|---|---|---|
| Schema 단계 | SQLite Backend `390 passed` | Model·Migration 구현 당시 회귀 기록 |
| Importer 단계 | SQLite Smoke·Full·Replay | 트랜잭션·멱등성 선행 검증 |
| 통합 후보 단계 | SQLite Backend `397 passed` | 당시 전체 Backend 회귀 기록 |
| PostgreSQL 단계 | 16.14, 37·367건, Replay 생성·수정 0 | `DB_FULL_VERIFIED`의 직접 근거 |
| T-005 과거 Wave | 10/32 또는 12/32 `NOT_READY` | 당시 진행률이며 현재 판정에 사용하지 않음 |
| T-005 현재 | Model·App Registry·Migration 32/32 | 최신 T-005 보고서를 우선 |

테스트 개수는 해당 Commit·작업 트리의 역사 수치다. 현재 변경의 통과를
주장하려면 동일 명령을 다시 실행해 실행 시각·Commit·환경과 함께 기록한다.

## 8. 팀 인계

| 담당 | 확인할 내용 | 반환 증거 |
|---|---|---|
| Backend·DB | Migration, 적재기, 충돌 분석, 원장·도메인 수 | 격리 DB명, 명령, Exit code, Replay 생성·수정 0 |
| Data·QA | Fixture 12종, Crosswalk, Schema, Hash, 결정성 | Data 책임자 검토, QA 결과, Manifest Hash |
| PM·Workflow | 문의·방문 상태와 125개 전이·감사 | 승인 계약 버전과 불일치 0 |
| 소비자 QA | 적재 데이터의 API 조회·권한·오류 경계 | 역할별 API Smoke와 E2E 결과 |

관련 문서:

- [합성 데이터 픽스처·해시·교차표 검증 원본](../archive/20260802_문서통합_원본/technical/contracts/합성_데이터_픽스처_해시_교차표_검증_보고서.md)
- [합성 고객 데모 로그인 가이드](../인증_권한/Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md)
- [T-005 데이터 설계 기준선](../../../database/t-005/README.md)
- [테이블 사전](../../../database/waterbridge_table_dictionary.md)

## 9. Fixture·Hash·Crosswalk 입력 무결성

Importer 실행 전에 입력 Fixture와 Backend Crosswalk의 의미가 변하지
않았는지 먼저 확인한다.

| 검증 항목 | 기준 |
| --- | --- |
| 활성 Fixture 파일 | 승인된 12개 컬렉션만 합산 |
| Source 레코드 | 총 367건 |
| 텍스트 해시 | LF·CRLF·CR·BOM 정규화 뒤 동일 내용은 동일 Hash |
| 잘못된 입력 | 잘못된 UTF-8과 내용 변경은 실패 또는 다른 Hash |
| Backend Crosswalk | Source semantic hash와 entity mapping을 함께 검증 |
| 금지 범위 | 검증 과정에서 `data/synthetic/fixtures/**`, `contracts/state-machine/**`를 임의 수정하지 않음 |

2026-07-29 중간 검증에서는 신규 불변식·해시 집중 7건이 통과했고,
이후 Crosswalk와 저장 QA가 정렬되면서 최종 Data 회귀·Manifest 검증으로
연결됐다. 현재 계획표가 사용하는 최신 Data QA 기록은 `67 tests`, 대표
E2E `17/17`, 오류·경고 0이다. 57·61건과 Backend 397건 수치는 당시 단계의
역사 스냅샷으로 유지하며 현재 전체 회귀로 재표기하지 않는다.

입력 무결성 확인 순서는 다음과 같다.

1. Fixture 12개 파일과 367건 합계를 확인한다.
2. Source Hash 정규화와 Crosswalk semantic hash를 검증한다.
3. `dry-run`으로 DB 저장 0건과 동일 검증 경로를 확인한다.
4. 격리 PostgreSQL에서 최초 적재와 Replay를 실행한다.
5. Batch·원장·상태·관계 건수와 `correlation_id`를 확인한다.
6. Data QA와 Backend 회귀를 실행하고 후보 SHA·환경·Exit code를 기록한다.

Data Owner의 내용 승인과 비작성자 재현은 작성자 기계 검증과 별도다.

## 10. 유지보수 원칙

- Model·Migration·Fixture·Hash·Crosswalk·Importer 변경은 같은 변경 묶음에서
  검증한다.
- 건수나 테스트 수는 실행일·환경·명령·Exit code가 함께 기록된 경우에만
  현재 증거로 사용한다.
- 기본 개발 DB와 격리 검증 DB를 구분하고, 재현을 위해 공용 DB를
  초기화하지 않는다.
- 실제 고객 데이터, 운영 Dump, 비밀값과 개인 PC 절대경로를 예시나 로그에
  포함하지 않는다.
- Data Owner 승인, 비작성자 재현과 PM 기준선 반영 전에는 작성자 검증을
  팀 공식 완료로 확대하지 않는다.
