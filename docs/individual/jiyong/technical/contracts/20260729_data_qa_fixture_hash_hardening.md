# Data QA fixture·계약 해시 강화 개발 문서

- 작업일: 2026-07-29
- 작성 범위: 최지용의 Backend 연동 관점 검증 후보와 김은진 Owner Review 요청
- Data 소유 책임: 김은진(`data/**`, `scripts/data/**`)
- 데이터셋 버전: `0.9.0`
- 금지 범위 준수: `data/synthetic/fixtures/**` 및 `contracts/state-machine/**` 미수정

> 후속 통합 검증(2026-07-29): 이 단계의 Data QA를 통과한 동일 fixture로
> PostgreSQL smoke 37건과 full 367건의 적재·재실행까지 완료했다.
> 최종 실측은 [PostgreSQL 합성 Handoff Runtime 검증·인계서](../../manuals/20260729_postgresql_synthetic_handoff_runtime_verification.md)를 따른다.
>
> 이 문서는 Data 최종 승인서가 아니다. 현재 자동 검증 결과를 바탕으로
> 김은진에게 19개 Data 소유 경로의 의미·생성물·결정성 검토를 요청하는
> Backend 측 개발 기록이다.

## 1. 작업 목적

Backend 운영 적재 전에 정식 synthetic fixture 수가 누락되거나 임의로 늘어나는 문제를 차단하고, 계약 파일의 운영체제별 줄바꿈 차이를 실제 내용 변경과 구분하도록 Data QA를 강화했다.

## 2. 구현 내용

| 우선순위 | 변경 | 구현 위치 | 검증 기준 |
|---|---|---|---|
| P0 | 전체 fixture 레코드 불변식 추가 | [`pipeline.json`](../../../../../data/config/pipeline.json), [`pipeline.schema.json`](../../../../../data/schemas/config/pipeline.schema.json) | `synthetic_fixture_records = 367`이며 스키마 `const`로 고정 |
| P0 | 12개 활성 fixture 합계 검증 | [`validation.py`](../../../../../data/tools/watercare/validation.py) | `users`부터 `audit_events`까지 정확히 12개 컬렉션만 합산 |
| P1 | manifest용 집계 보강 | [`operations.py`](../../../../../data/tools/watercare/operations.py) | `synthetic_products = 1`, `synthetic_fixture_records = 367` 제공 |
| P1 | 파일별 건수와 레지스트리 분포 테스트 | [`test_t005_data_projection.py`](../../../../../data/tools/tests/test_t005_data_projection.py), [`test_service_contract_mapping.py`](../../../../../data/tools/tests/test_service_contract_mapping.py) | fixture 12개 파일별 건수, 합계 367, 계약 레지스트리 24/22/2 |
| P1 | 텍스트 해시 경계조건 테스트 | [`test_service_contract_mapping.py`](../../../../../data/tools/tests/test_service_contract_mapping.py) | LF/CRLF/CR/BOM 동일, 내용 변경 시 상이, 잘못된 UTF-8 거부 |

### 2.1 활성 fixture 기준

| 파일 | 레코드 |
|---|---:|
| `users.json` | 16 |
| `customer_profiles.json` | 12 |
| `products.json` | 1 |
| `customer_products.json` | 12 |
| `subscriptions.json` | 12 |
| `inquiries.json` | 22 |
| `consultations.json` | 12 |
| `visits.json` | 4 |
| `care_histories.json` | 25 |
| `followup_confirmations.json` | 1 |
| `inquiry_status_histories.json` | 125 |
| `audit_events.json` | 125 |
| **합계** | **367** |

## 3. 작업 사이 검증 결과

| 단계 | 실행 결과 | 판정 |
|---|---|---|
| 신규 불변식·해시 집중 테스트 | 7개 테스트, 7 PASS | PASS |
| Python 구문 검증 | `compileall` 오류 0 | PASS |
| fixture 원본 SHA-256 전후 비교 | 12개 중 12개 동일 | PASS |
| 읽기 전용 live Data QA | 47 files, 739 records, 신규 `synthetic_fixture_records = 367` 확인 | 신규 기능 PASS |
| 전체 Data 단위 테스트 | 57개 중 54 PASS, 3 FAIL | 조건부 PASS |

전체 테스트의 3개 실패는 이 작업에서 최종 갱신을 금지한 Backend Crosswalk 해시의 일시적 불일치가 원인이다. 실제 불일치는 `subscription_model`, `care_model` 2건이며, 이를 소비하는 CLI 호환성 테스트 2개가 연쇄 실패했다. fixture 수·레지스트리·해시 정책 신규 테스트에는 실패가 없다.

## 4. 최종 통합 인계

1. Backend 모델과 importer 구현이 모두 고정된 뒤 [`backend_import_crosswalk.json`](../../../../../data/config/handoff/backend_import_crosswalk.json)의 semantic hash를 한 번만 최종 갱신한다.
2. 전체 Data 테스트를 다시 실행해 57개 전부 통과하는지 확인한다.
3. `qa --verify-rebuild`로 manifest와 QA 보고서를 최종 재생성하고, `synthetic_products`와 `synthetic_fixture_records`가 생성물에 반영되는지 확인한다.
4. 저장된 PASS 보고서와 live QA의 동일성을 검사하는 staleness 테스트는 1~3 완료 후 추가한다. 현재 추가하면 의도적으로 미갱신한 Crosswalk 때문에 결정적으로 실패하므로 이번 중간 단계에서는 제외했다.

## 5. 후속 통합 완료 증거

위 3장의 실패 3건과 4장의 후속 항목은 단계별 검증을 위해 보존한
중간 기록이며, 최종 통합에서 모두 해소했다.

| 후속 작업 | 최종 결과 |
|---|---|
| Backend Crosswalk | Backend source semantic hash 17/17, entity mapping 12개, blocked mapping 0개 |
| PostgreSQL 기계 증적 | DB명, 최초·재실행 batch code, fixture-set SHA-256, 명령, base commit, Runtime 문서 hash 기록 |
| Care 결과 계약 | [`care-results.yaml`](../../../../../contracts/codes/care-results.yaml)의 3개 코드가 Data Schema·fixture·Backend `CareRecord.Result`와 정확히 일치 |
| 저장 QA staleness 차단 | 저장된 `pipeline_validation`과 live QA의 status·summary·counts·errors 비교 테스트 추가 |
| 최종 Data 회귀 | 61/61 PASS |
| 최종 Backend 회귀 | 397/397 PASS |
| 최종 QA·manifest | 2회 연속 오류·경고 0, 대표 E2E 17/17, Manifest 154 entries PASS |
| 금지 범위 | `data/synthetic/fixtures/**`, `contracts/state-machine/**` 변경 0건 |

## 6. 현재 Owner Review Gate

현재 후보의 기계 검증은 완료했지만, 다음 경로의 최종 내용 책임은
김은진에게 있다.

- `data/**` 변경 18개
- `scripts/data/refresh_source_hashes.py` 1개

김은진은 Source Hash 검사, Data 61건, QA 2회와 Manifest Hash 안정성을
재현하고 `APPROVED` 또는 `CHANGES_REQUESTED`를 반환한다. 변경이 있으면
`eunjin` Branch의 40자리 Commit SHA를 함께 전달한다.

최지용은 반환본을 받은 뒤 Backend 397건과 PostgreSQL 적용 상태를 다시
검증한다. 이 왕복이 끝나기 전에는 PM에게 현재 후보의 `main` 병합을
요청하지 않는다.
