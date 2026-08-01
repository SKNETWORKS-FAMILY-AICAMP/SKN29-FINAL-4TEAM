# T-005 Wave 1A·1B 체크포인트 및 Seed 연쇄 충돌 수정

> 기준일: 2026-07-30  
> 담당: 최지용  
> 기준 Branch: `jiyong`  
> 기준 시작 SHA: `765047c2342bc30363a5c543a1f9ea324730d079`  
> Wave 당시 상태: `LOCAL_VERIFIED` — 후속 Accounts Gate와 잔여 테이블 Wave 진행 중

> 역사 스냅샷: 이 문서는 Wave 1A·1B 체크포인트 시점의 기록이다.
> 현재 상태는
> [T-005 32개 테이블 최종 검증 보고서](t005_final_32_table_postgresql_seed_importer_validation_report.md)의
> `READY 32/32`, SQLite 740·PostgreSQL 751 결과를 우선한다.

## 1. 작업 목적

[Wave 1A 구현 문서](t005_wave_1a_support_questionnaire_session_implementation.md)와
[Wave 1B 구현 문서](t005_wave_1b_questionnaire_inquiry_composite_fk.md)의
현재 작업본을 다음 Wave 전에 검증 가능한 체크포인트로 고정한다.

또한 한 PostgreSQL 데이터베이스에서 Demo Seed와
367건 canonical synthetic handoff를 순서대로 실행했을 때 발생한
업무 식별자 충돌을 제거한다.

## 2. 체크포인트 결과

| 검사 | 결과 |
| --- | --- |
| Django system check | PASS, 0 issues |
| Migration drift | PASS, `No changes detected` |
| Wave 1A·1B 집중 회귀 | 100 passed |
| Backend 전체 회귀 | 428 passed, 1 skipped |
| Data 전체 회귀 | 67 passed |
| T-005 구조 Validator | `structure_valid=true` |
| T-005 Runtime Auditor | 13/32 구현, 잔여 19, `NOT_READY` |
| 빈 PostgreSQL 전체 Migration | PASS |
| PostgreSQL 전용 Questionnaire 복합 FK | 1 passed |
| Demo Seed 2회 | PASS |
| 367건 Importer dry-run | 355 created 예정, 12 projected |
| 367건 실제 Import 1회 | 355 created, 12 projected |
| 367건 실제 Import 2회 | 0 created, 0 updated, 355 unchanged, 12 projected |

PostgreSQL 검증은 기존 `watercare` 데이터베이스를 변경하지 않고
격리 데이터베이스 `watercare_t005_wave1ab_verify_20260730_02`에서
수행했다.

## 3. 발견한 연쇄 충돌과 수정

| 우선순위 | 증상 | 원인 | 수정 |
| ---: | --- | --- | --- |
| P0 | Importer가 CustomerProfile public UUID mismatch로 중단 | Demo Seed와 canonical fixture가 모두 `SYN-CUSTOMER-001`을 사용했지만 서로 다른 `public_id`를 사용 | Demo 전용 고객 번호를 `DEMO-CUSTOMER-001`로 분리 |
| P0 | 첫 충돌 수정 후 활성 serial UNIQUE 위반 | Demo Subscription과 canonical fixture가 모두 `SYN-JAC104D-0001`을 사용 | Demo serial을 `DEMO-JAC104D-0001`로 분리 |
| P0 | Seed 단위 테스트만으로 통합 충돌을 검출하지 못함 | Seed와 Importer가 서로 다른 테스트 DB 흐름에서만 검증됨 | Demo Seed 2회 후 full Importer 2회를 실행하는 통합 회귀 테스트 추가 |

수정 파일:

- [Demo Accounts Seed](../../../../../backend/apps/accounts/management/commands/seed_demo_accounts.py)
- [Demo Subscription Seed](../../../../../backend/apps/subscriptions/management/commands/seed_demo_subscriptions.py)
- [Accounts Seed 테스트](../../../../../backend/tests/unit/accounts/test_demo_seed.py)
- [Subscription Seed 테스트](../../../../../backend/tests/unit/subscriptions/test_demo_seed.py)
- [Seed·Importer 통합 회귀](../../../../../backend/tests/integration/operations/test_synthetic_handoff_import.py)

## 4. 재현 순서

저장소 루트에서 실제 환경값을 로드하되 비밀번호를 로그나 문서에
출력하지 않는다.

```powershell
Set-Location (git rev-parse --show-toplevel)
$python = ".\backend\.venv\Scripts\python.exe"

& $python .\backend\manage.py migrate --noinput `
  --settings=config.settings.local

foreach ($pass in 1..2) {
  & $python .\backend\manage.py seed_common_codes `
    --settings=config.settings.local
  & $python .\backend\manage.py seed_demo_accounts `
    --settings=config.settings.local
  & $python .\backend\manage.py seed_demo_products `
    --settings=config.settings.local
  & $python .\backend\manage.py seed_demo_subscriptions `
    --settings=config.settings.local
  & $python .\backend\manage.py seed_demo_care_records `
    --settings=config.settings.local
}

& $python .\backend\manage.py import_synthetic_handoff `
  --profile full --dry-run --settings=config.settings.local
& $python .\backend\manage.py import_synthetic_handoff `
  --profile full --settings=config.settings.local
& $python .\backend\manage.py import_synthetic_handoff `
  --profile full --settings=config.settings.local
```

## 5. 인계 사항

- `DEMO-*`는 독립 실행용 Seed 업무 코드다.
- `SYN-*`는 Data 담당자의 canonical synthetic handoff 업무 코드다.
- 두 데이터셋이 같은 DB에 공존할 수 있도록 고객 번호와 serial을
  공유하지 않는다.
- T-005 완료 선언은 아직 금지한다. Accounts 정수 PK, UUID-only JWT,
  잔여 19개 계약 테이블, pgvector, 빈 PostgreSQL 최종 검증이 남아 있다.
- 다음 작업은 [T-005 기준 패키지](../../../../database/t-005/README.md)의
  Physical Contract v1.2에 따라 Accounts Gate를 적용한 뒤 잔여
  테이블을 FK 순서로 구현하는 것이다.
