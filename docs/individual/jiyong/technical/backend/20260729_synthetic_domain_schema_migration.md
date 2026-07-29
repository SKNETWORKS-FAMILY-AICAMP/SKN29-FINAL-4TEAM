# 합성 데이터 도메인 스키마·Migration 개발 인계서

- 작성일: 2026-07-29
- 대상: Backend·Data/QA·PM 협업자
- 단계 종료 당시 상태: 모델·Migration·Django 자동화 검증 완료 / PostgreSQL 적용·운영 적재 검증 미수행
- 기준 브랜치 상태: 로컬 작업 트리의 현재 구현 기준이며, 커밋·PR 승인 상태를 의미하지 않는다.

> 후속 통합 검증(2026-07-29): 이 문서의 미수행·후속 작업 문구는
> Schema/Migration 단계를 닫을 당시의 단계별 증거다. 이후 격리
> PostgreSQL에서 Migration과 합성 full 367건 적재가 완료됐다.
> 현재 통합 판정은 [PostgreSQL 합성 Handoff Runtime 검증·인계서](../../manuals/20260729_postgresql_synthetic_handoff_runtime_verification.md)를
> 우선하고, 현재 설치·Migration·Seed 절차의 단일 원본은
> [Django·PostgreSQL 공유 패키지 인계서 v1.3](../../manuals/20260729_최지용_Django_PostgreSQL_공유패키지_인계서_v1.3.md)이다.
>
> 같은 날 기본 `watercare` PostgreSQL 16.14에는 아래 9개 Migration과
> `workflow.0003` 보정 Migration까지 적용했다. 적용 전후 기존 테이블
> 행 수를 보존했고, 기존 Workflow 이력 11건의 `changed_at`을 원래
> `created_at`으로 보정했다. 이 후속 실측은 최초 Schema 단계의
> `390 passed` 기록을 덮어쓰지 않는다.

## 1. 작업 목적과 완료 범위

합성 고객 시나리오가 `문의 → 상담 → 방문 → 후속 확인 → 케어`로 이어질 때 필요한 영속 모델과 이력·감사 구조를 보강했다. 이번 문서는 실제로 구현되고 Django 검사 및 테스트를 통과한 스키마만 다룬다.

완료 범위는 다음과 같다.

1. 상담(`Consultation`), 방문(`Visit`), 후속 확인(`FollowupConfirmation`) 모델과 초기 Migration
2. 기존 케어(`CareRecord`)의 외부 데이터 수용 필드와 Migration
3. 기존 문의(`Inquiry`)·구독(`Subscription`)의 합성 데이터 연결 필드와 Migration
4. 문의 전용이던 상태 이력을 설문·문의·상담·방문 대상으로 확장
5. 상태 전이와 1:1로 연결되는 감사 이벤트(`AuditEvent`) 모델과 초기 Migration
6. 모델 무결성, Migration drift, 전체 Backend 회귀 테스트 검증

운영 importer, 367건 전체 적재, PostgreSQL 적용·롤백, API 전체
시나리오 실행은 이 Schema 작업 당시의 완료 범위가 아니다. 후속 격리
DB Import 검증과 기본 DB Migration 실측은 위 Runtime 검증서에 별도
누적해 단계별 증거를 구분한다.

## 2. 구현 산출물

| 영역 | DB 테이블 | 구현 내용 | 핵심 무결성·추적 조건 | 근거 |
|---|---|---|---|---|
| 상담 | `support_consultation` | 문의별 상담 순번, 담당 상담사, 상태·결과, 요약, 시작·종료 시각, 데이터 분류를 저장 | 문의+순번 유일성, 상담사 역할 확인, 상태·결과·시각의 생명주기 조건, 양수 `state_version`, 비어 있지 않은 idempotency key | [Consultation 모델](../../../../../backend/apps/consultations/models/consultation.py), [모델 테스트](../../../../../backend/tests/unit/consultations/test_models.py) |
| 방문 | `field_service_visit` | 문의별 방문, 담당 기사, 요청·예정·시작·완료 시각, 방문 결과와 데이터 분류를 저장 | 기사 역할 확인, 상태별 시각·결과 필드 조건, 시간 순서 조건, 양수 `state_version`, 비어 있지 않은 idempotency key | [Visit 모델](../../../../../backend/apps/visits/models/visit.py), [모델 테스트](../../../../../backend/tests/unit/visits/test_models.py) |
| 후속 확인 | `support_followup_confirmation` | 문의에 대한 해결 확인, 연결 상담·방문, 안내 식별자, 응답 채널·결과·다음 동작을 저장 | 연결 상담·방문이 같은 문의에 속하는지 확인, 상태별 응답·확정 시각 조건, 양수 `state_version` | [FollowupConfirmation 모델](../../../../../backend/apps/inquiries/models/followup_confirmation.py), [모델 테스트](../../../../../backend/tests/unit/inquiries/test_followup_confirmation.py) |
| 케어 | `subscriptions_care_record` | 기존 케어 레코드에 문의·방문·방문결과 식별자, 상태·일정·수행일·결과·완료/취소 정보, 수행자, 원천 코드·요약을 추가 | 연결 엔티티와 날짜·완료/취소 상태의 조합을 제약하고 조회용 인덱스를 추가 | [CareRecord 모델](../../../../../backend/apps/care/models/care_history.py), [모델 테스트](../../../../../backend/tests/unit/care/test_models.py) |
| 문의 | `support_inquiry` | 시나리오 코드, 배정 사용자·역할, 채널·위험도·사용 안내 상태, 근거 ID 목록, fallback 여부, 원천 idempotency/correlation ID, 설문 세션 ID를 추가 | 시나리오 코드 유일성, 배정 사용자와 역할의 동시 존재·역할 일치, 허용 코드값과 양수 버전 제약 | [Inquiry 모델](../../../../../backend/apps/inquiries/models/inquiry.py), [모델 테스트](../../../../../backend/tests/unit/inquiries/test_t022_models.py) |
| 구독 | `subscriptions_customer_subscription` | 설치일, 원천 고객제품 UUID, 설치 주소를 추가 | 원천 고객제품 UUID는 값이 있을 때 유일하며 기존 고객·제품·일련번호 관계를 유지 | [Subscription 모델](../../../../../backend/apps/subscriptions/models/subscription.py), [모델 테스트](../../../../../backend/tests/unit/subscriptions/test_models.py) |
| 상태 이력 | `workflow_transition_history` | 대상 유형을 `QUESTIONNAIRE`, `INQUIRY`, `CONSULTATION`, `VISIT`로 확장하고 시스템 행위자, 이력 코드, 이벤트·상태·버전·상관관계 정보를 저장 | 한 행에 대상 하나만 허용, 사용자/시스템 행위자 조합 제약, 대상별 `state_version` 유일성, 최초/후속 상태 규칙, 대상별 idempotency 조회 인덱스 | [TransitionHistory 모델](../../../../../backend/apps/workflow/models/transition_history.py), [Workflow 테스트](../../../../../backend/tests/unit/workflow/test_t023_readiness.py) |
| 감사 이벤트 | `audit_event` | 상태 전이 한 건에 대한 문의/방문 감사 레코드, 이벤트·행위자 역할·버전·idempotency/correlation ID·발생 시각·분류를 저장 | 상태 전이와 1:1, 문의/방문 대상 유형과 FK 일치, 양수 버전, 행위자·발생시각 정합성 | [AuditEvent 모델](../../../../../backend/apps/audit/models/audit_event.py), [모델 테스트](../../../../../backend/tests/unit/audit/test_models.py) |

`CareRecord`의 필드 보강은 외부 데이터를 받을 수 있는 스키마 준비까지를 뜻한다. 이 문서에서는 실제 fixture가 해당 테이블에 적재됐다고 주장하지 않는다.

## 3. 설계상 연쇄 오류 방지 장치

| 위험 | 적용한 방지 장치 | 남은 책임 |
|---|---|---|
| 문의와 다른 상담·방문을 후속 확인에 연결 | `FollowupConfirmation.clean()`에서 연결 엔티티의 문의 일치 여부 검사 | importer/API도 저장 전 `full_clean()` 또는 동일한 서비스 검증을 수행해야 한다. |
| 잘못된 역할의 담당자 배정 | 상담사·기사·문의 배정자의 역할을 모델 검증에서 확인 | 대량 적재 시 검증을 우회하는 `bulk_create()` 사용 여부를 별도 통제해야 한다. |
| 한 상태 이력에 여러 대상이 동시에 연결 | 대상 유형별 정확히 하나의 식별자/FK만 허용하는 DB `CheckConstraint` | 원천 상태 코드와 PM 승인 상태머신의 매핑은 importer 단계에서 검증해야 한다. |
| 같은 전이 버전 중복 기록 | 대상별 조건부 유일 제약과 idempotency key 인덱스 적용 | 트랜잭션 경계와 재시도 정책은 서비스/importer에서 보장해야 한다. |
| 상태 이력과 감사 이벤트 불일치 | `AuditEvent.transition`을 `OneToOneField(PROTECT)`로 연결하고 대상 유형/FK 일치를 검사 | 모든 전이에 감사 이벤트를 반드시 생성하는 것은 서비스 트랜잭션에서 보장해야 한다. |
| 완료·취소·결과 필드의 모순 | 상담·방문·후속 확인·케어 모델에 상태별 필수/금지 필드와 시각 순서 제약 적용 | 외부 데이터 오류를 어떤 코드로 반려·격리할지는 Data/QA 정책이 필요하다. |
| 원천 데이터와 내부 레코드의 추적 단절 | 시나리오 코드, 원천 UUID, idempotency key, correlation ID, 공개 UUID를 유지 | 실제 Crosswalk 생성·재생성 및 367건 적재 검증은 후속 작업이다. |

## 4. Migration 체인

| 순서 | 앱 | Migration | 역할 |
|---:|---|---|---|
| 1 | inquiries | [0003_add_synthetic_handoff_fields](../../../../../backend/apps/inquiries/migrations/0003_add_synthetic_handoff_fields.py) | 문의 합성 데이터·배정·추적 필드 추가 |
| 2 | visits | [0001_initial](../../../../../backend/apps/visits/migrations/0001_initial.py) | 방문 테이블·제약·인덱스 생성 |
| 3 | consultations | [0001_initial](../../../../../backend/apps/consultations/migrations/0001_initial.py) | 상담 테이블·제약·인덱스 생성 |
| 4 | workflow | [0002_expand_transition_targets](../../../../../backend/apps/workflow/migrations/0002_expand_transition_targets.py) | 기존 이력 코드 생성 후 상태 이력 대상을 확장 |
| 5 | audit | [0001_initial](../../../../../backend/apps/audit/migrations/0001_initial.py) | 상태 이력 연계 감사 이벤트 테이블 생성 |
| 6 | care | [0002_add_imported_care_fields](../../../../../backend/apps/care/migrations/0002_add_imported_care_fields.py) | 케어 외부 데이터 수용 필드·제약 추가 |
| 7 | inquiries | [0004_followup_confirmation](../../../../../backend/apps/inquiries/migrations/0004_followup_confirmation.py) | 후속 확인 테이블 생성 |
| 8 | subscriptions | [0002_add_synthetic_projection_fields](../../../../../backend/apps/subscriptions/migrations/0002_add_synthetic_projection_fields.py) | 구독 원천 연결·설치 필드 추가 |
| 9 | operations | [0001_initial](../../../../../backend/apps/operations/migrations/0001_initial.py) | 합성 Import 배치·항목 원장과 제약·인덱스 생성 |
| 10 | workflow | [0003_backfill_legacy_changed_at](../../../../../backend/apps/workflow/migrations/0003_backfill_legacy_changed_at.py) | `workflow.0002`가 만든 기존 이력 11건의 `changed_at`을 원래 `created_at`으로 보정 |

실제 적용 순서는 각 Migration 파일의 `dependencies`가 결정한다. 표의 순번을 수동 실행 순서로 사용하지 말고, Django Migration graph를 그대로 사용해야 한다.

## 5. 검증 결과

검증은 `backend` 디렉터리에서 수행했다.

| 단계 | 실행 명령 | 결과 | 판정 범위 |
|---|---|---|---|
| Django 시스템 검사 | `.\.venv\Scripts\python.exe manage.py check --settings=config.settings.test` | `System check identified no issues (0 silenced).` | 앱 등록·모델 로딩·설정의 정적 검사 |
| 대상 앱 Migration drift | `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=config.settings.test consultations visits inquiries subscriptions care workflow audit` | 7개 앱 모두 `No changes detected` | 현재 모델과 작성된 Migration 파일의 일치 |
| Schema 단계 Backend 전체 회귀 | `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` | `390 passed in 50.08s` | 당시 테스트 설정 기반 전체 자동화 회귀의 역사 기록 |

`390 passed`는 [테스트 설정](../../../../../backend/config/settings/test.py)의
메모리 SQLite DB에서 실행한 당시 기록이다. 따라서 그 수치 자체는
PostgreSQL DDL 적용, PostgreSQL 전용 동작, importer 또는 367건 적재
성공을 증명하지 않는다.

후속 현재 통합 Gate에서는 같은 SQLite 테스트가 `397 passed`였고,
`--postgresql` 단계가 기본 `watercare`의 PostgreSQL 16.14 연결과 적용
Migration 누락 없음을 읽기 전용으로 확인했다. 이는 “PostgreSQL에서
397개 테스트 통과”가 아니라 SQLite 테스트와 PostgreSQL 읽기 전용
검사를 한 Gate에서 각각 통과했다는 뜻이다. 기본 DB에는 위 9개와
`workflow.0003`이 적용됐고, 기존 행 수 보존과 Workflow 11건 보정을
확인했다.

## 6. 의도적으로 변경하지 않은 기준 자산

- PM 소유 기준인 [`contracts/state-machine/**`](../../../../../contracts/state-machine/)는 이번 스키마 작업에서 변경하지 않았다.
- Data/QA 소유 원천인 [`data/synthetic/fixtures/**`](../../../../../data/synthetic/fixtures/)도 변경하지 않았다.
- 위 진술은 두 경로에 한정한다. 다른 contract 영역 전체가 변경되지 않았다는 뜻은 아니다.

모델은 현재 승인된 상태 코드와의 연결을 준비하지만, 상태머신 기준 자체를 Backend 모델이 새로 정의하거나 승인하지 않는다.

## 7. 인계 및 후속 작업

| 담당 | 후속 작업 | 완료 기준 |
|---|---|---|
| Backend | 서비스 트랜잭션에서 상태 이력과 감사 이벤트를 함께 생성하고 실패 시 함께 롤백 | 서비스/API 테스트에서 전이 1건당 이력·감사 이벤트 정합성 확인 |
| Data/QA | 정식 importer와 Crosswalk를 모델 제약에 맞춰 유지하고 오류 행 격리 정책 적용 | 승인 fixture 전체 건수·참조·코드·해시 검증과 격리 DB 적재 보고서 유지 |
| DB/Backend | 기본 DB Migration·Demo Seed와 합성 Import 격리 DB를 분리 | 기본 DB 기존 행 보존·Seed 2회 중복 0, 빈 격리 DB smoke/full 재현 |
| PM | 상태·이벤트·역할 코드가 승인된 상태머신 계약과 같은지 최종 확인 | 계약 버전·승인 해시를 포함한 검토 기록 |
| QA | 문의→상담→방문→후속 확인→케어의 성공·취소·재개 시나리오 검증 | API/서비스 E2E 결과와 데이터 추적 ID 연결 확인 |

### 인계 시 주의사항

1. Schema 단계의 `390 passed`만으로 `DB_VERIFIED`나
   `IMPORT_VERIFIED`를 붙이지 않는다. 격리 합성 DB의
   `DB_FULL_VERIFIED`는 Runtime 검증서의 범위 안에서만 사용한다.
2. `makemigrations`를 다시 생성하기 전에 현재 Migration graph와 작업 트리의 미커밋 파일을 먼저 확인한다.
3. 모델의 `clean()` 검증은 DB `CheckConstraint`와 역할이 다르므로 importer가 검증을 우회하지 않게 한다.
4. 상태 코드 변경이 필요하면 Backend 모델을 먼저 임의 수정하지 말고 [상태머신 계약](../../../../../contracts/state-machine/) 승인 절차부터 진행한다.
5. 기본 `watercare`에는 canonical fixture와 공개 UUID가 다른 기존
   레코드가 있으므로 합성 Importer와 그 `--dry-run`을 실행하지 않는다.
   Importer는 새 빈 격리 PostgreSQL에서만 실행한다.
