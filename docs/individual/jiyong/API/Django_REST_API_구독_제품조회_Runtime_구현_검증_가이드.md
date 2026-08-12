# T-018 구독·제품 조회·등록·수정 Runtime 구현·검증 가이드

## 1. 결과

- 기준: `main@8b5bb6292e087fd15558f53c530b06653edc4d29`
- 작성일: 2026-08-12
- 상태: `AUTHOR_VERIFIED / POSTGRESQL_QA_PENDING`
- 공식 WBS: `진행 중` 유지

기존 본인 구독 목록·상세에 합성 고객 제품 등록과 허용 필드 수정을 추가했다.
제품 Catalog는 고객이 생성하지 않으며 MVP 지원 모델 `WPUJAC104DWH`만 선택한다.

## 2. Endpoint

| Method | Path | Runtime |
|---|---|---|
| `GET` | `/api/v1/me/subscriptions` | 본인 ACTIVE 구독 목록 |
| `POST` | `/api/v1/me/subscriptions` | 합성 고객 지원 제품 등록 |
| `GET` | `/api/v1/me/subscriptions/{subscription_id}` | 본인 ACTIVE 구독 상세 |
| `PATCH` | `/api/v1/me/subscriptions/{subscription_id}` | 시작일·관리 유형·최근 관리일 수정 |

POST 입력:

```json
{
  "model_code": "WPUJAC104DWH",
  "started_on": "2026-08-01",
  "management_type_code": "SELF_MANAGED",
  "last_care_on": "2026-08-05"
}
```

PATCH는 `started_on`, `management_type_code`, `last_care_on` 중 하나 이상만
허용한다. 알 수 없는 필드는 422로 거부한다.

## 3. 권한·제품·날짜 경계

- 미인증은 401, CUSTOMER가 아닌 역할과 비합성 고객 Write는 403이다.
- 타 고객, 삭제 고객, 비ACTIVE 구독, 미지원·비활성 제품 상세·수정은 동일 404다.
- POST의 미지원·차단 모델은 `422 PRODUCT_NOT_SUPPORTED`다.
- 동일 고객·제품의 ACTIVE/SUSPENDED 구독 중복은
  `409 SUBSCRIPTION_ALREADY_ACTIVE`다.
- 미래 시작일·관리일과 시작일보다 빠른 관리일은 422다.
- 기존 완료 관리일보다 뒤로 시작일을 늦추는 수정은 422다.

## 4. 멱등성과 저장

- Write는 `Idempotency-Key`를 필수로 사용한다.
- Scope는 `actor + operation_id + key`다.
- 같은 Key·같은 Body는 저장 결과를 Replay하고
  `idempotent_replay=true`를 반환한다.
- 같은 Key·다른 Body/대상은 `409 DUPLICATE-EVENT-01`이다.
- 고객 Profile Row Lock으로 같은 고객의 등록·수정을 직렬화한다.
- `contract_no`, `serial_no`와 공개 `subscription_id`는 서버가 합성 생성한다.
- `last_care_on`은 기존 `CareRecord`에 IMPORT·COMPLETED·FILTER_REPLACEMENT
  기준 이력으로 저장하고 목록·상세의 최근 관리일 계산에 포함한다.
- 신규 Model·Migration 없이 기존 Subscription·Care·Idempotency 테이블을 사용한다.

## 5. 공개 응답과 비노출

공개 필드:

- `subscription_id`, `status_code`, `management_type_code`, `started_on`
- `ended_on`, `last_care_on`, `next_care_on`, `idempotent_replay`(Write)
- Product의 공개 UUID, 모델 코드·이름·세대·제조사

비노출:

- 내부 정수 PK, customer 내부/공개 ID
- 계약번호, Serial, 설치 주소
- 원본 fixture ID, Product features, 고객 개인정보

## 6. 구현·계약 증거

- [Route·View](../../../../backend/apps/subscriptions/api/views.py)
- [Serializer](../../../../backend/apps/subscriptions/api/serializers.py)
- [Service](../../../../backend/apps/subscriptions/services/subscription_service.py)
- [Repository](../../../../backend/apps/subscriptions/repositories/subscription_repository.py)
- [OpenAPI Path](../../../../contracts/api/paths/products.yaml)
- [Create Schema](../../../../contracts/api/components/schemas/product/SubscriptionCreateRequest.yaml)
- [Update Schema](../../../../contracts/api/components/schemas/product/SubscriptionUpdateRequest.yaml)
- [Read Runtime Test](../../../../backend/tests/api/test_t018_subscription_runtime.py)
- [Write Runtime Test](../../../../backend/tests/api/test_t018_subscription_write_runtime.py)
- [Write Contract Test](../../../../backend/tests/api/test_t018_subscription_write_contract.py)

## 7. 작성자 검증

| 검증 | 결과 |
|---|---:|
| T-018 Read·Write Contract/Runtime + OpenAPI Inventory | `33 passed` |
| OpenAPI Validator | PASS, `124 YAML / 513 refs / 36 paths / 40 operations` |
| Example Validator | PASS, `61/61 referenced` |
| Code Registry Validator | PASS, `28 files / 144 codes` |
| 전체 Backend 회귀 | `1076 passed / 19 skipped / 0 failed` |

재현:

```powershell
Set-Location backend
$python = ".\.venv\Scripts\python.exe"
& $python -B -m pytest -q -p no:cacheprovider `
  tests/api/test_t018_subscription_write_contract.py `
  tests/api/test_t018_subscription_write_runtime.py `
  tests/api/test_t018_product_subscription_contract.py `
  tests/api/test_t018_subscription_runtime.py `
  tests/api/test_openapi_runtime_coverage.py
Pop-Location
& $python -B scripts/contracts/validate_openapi.py
& $python -B scripts/contracts/validate_examples.py
& $python -B scripts/contracts/validate_codes.py
```

## 8. 남은 Gate

- 격리 PostgreSQL에서 Create/PATCH 동시 동일 Key·다른 Key를 재현한다.
- 김은진이 동일 후보 SHA에서 401·403·404·409·422와 비노출을 독립 QA한다.
- Web·Mobile은 QA와 main 병합 뒤에만 Write Remote를 소비한다.
- `last_care_on` 외 일반 케어 이력 등록은 T-019 계약을 사용한다.
- 다음 관리 예정일 계산·변경 이력은 T-020에서만 처리한다.
