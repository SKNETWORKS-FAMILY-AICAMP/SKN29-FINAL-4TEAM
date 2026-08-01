# T-018 구독·제품 조회 API 계약 제안서

> 기준일: 2026-08-01
>
> 주담당: 최지용
>
> 검토: 김은진(Data·QA), 윤승혁(PM)
>
> 상태: `SAFE_CONTRACT_TEST_PROPOSAL_ONLY`
>
> 구현 여부: **미구현 — 계약·테스트 제안만 작성했으며 Runtime·Migration은 변경하지 않았다.**

## 1. 목적과 안전 범위

T-018의 첫 작업을 `GET /api/v1/me/subscriptions` 단일 읽기 Slice로 제한한다.
현재 Model·Migration·Seed 기반은 있지만 API 계층과 기계 계약은 비어 있다.
따라서 이 문서를 승인받기 전에는 OpenAPI 한 파일만 추가하거나 Runtime을
추측 구현하지 않는다.

| 구분 | 이번 제안 |
| --- | --- |
| 포함 | 본인 구독 목록, 제품 요약, 상태 필터, Pagination, 권한·오류 테스트 |
| 제외 | POST·PATCH·제품 선택, State 이벤트, `Idempotency-Key`, AI·RAG |
| DB 변경 | 없음 |
| Target-only 활성화 | 없음 |
| 완료 판정 | 계약·Runtime·PostgreSQL·소비 검증 전까지 T-018 미완료 |

## 2. 확인된 현재 상태

| 항목 | 현재 증거 | 판정 |
| --- | --- | --- |
| 구독 Model | [CustomerSubscription](../../../../../backend/apps/subscriptions/models/subscription.py) | Public UUID·고객·제품·관리 유형·상태·시작일·다음 케어일 존재 |
| 제품 Model | [ProductModel](../../../../../backend/apps/products/models/product_model_registry.py) | Public UUID·모델 코드·이름·지원·활성 상태 존재 |
| API Stub | [subscriptions URL](../../../../../backend/apps/subscriptions/api/urls.py), [View](../../../../../backend/apps/subscriptions/api/views.py), [Serializer](../../../../../backend/apps/subscriptions/api/serializers.py) | Docstring만 있고 Runtime 없음 |
| 통합 Route | [API URL](../../../../../backend/config/api_urls.py) | accounts·inquiries만 연결, subscriptions 미연결 |
| 사람용 기준 | [API 명세](../../../../api/watercare_api_specification.md) | `API-SUB-001` 설계 기준 존재 |
| 기계 계약 | [products path](../../../../../contracts/api/paths/products.yaml), [SubscriptionSummary](../../../../../contracts/api/components/schemas/product/SubscriptionSummary.yaml) | 경로·Schema가 비어 있음 |
| Runtime Coverage | [OpenAPI Runtime 검사](../../../../../backend/tests/api/test_openapi_runtime_coverage.py) | 현재 9 Operation을 고정하므로 단독 경로 추가 시 실패 |

## 3. 제안 계약 `T018-R1`

### 3.1 요청

```http
GET /api/v1/me/subscriptions?page=1&size=20&status_code=ACTIVE
Authorization: Bearer <access-token>
```

| 입력 | 형식 | 기본값·제약 |
| --- | --- | --- |
| `page` | integer | 기본 1, 최소 1 |
| `size` | integer | 기본 20, 최소 1, 최대 100 |
| `status_code` | optional enum | `ACTIVE`, `SUSPENDED`, `CANCELLED`, `EXPIRED` |

Body와 `Idempotency-Key`는 사용하지 않는다. 정렬은
`-started_on, public_id`로 고정해 페이지 결과를 결정적으로 만든다.

### 3.2 정상 응답 제안

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "00000000-0000-0000-0000-000000000000",
        "product": {
          "id": "00000000-0000-0000-0000-000000000000",
          "model_code": "WATERBRIDGE-MVP-01",
          "model_name": "WaterBridge MVP 정수기",
          "generation_code": null,
          "is_supported": true,
          "is_active": true
        },
        "management_type_code": "VISIT_CARE",
        "status_code": "ACTIVE",
        "started_on": "2026-07-01",
        "next_care_on": null
      }
    ],
    "page": 1,
    "size": 20,
    "total": 1
  },
  "error": null
}
```

외부 `id`는 각 Model의 `public_id`다. 내부 BigInt PK, `customer_id`,
`contract_no`, `serial_no`, `installation_address`, 원본 `features` JSON은
목록 응답에서 제외한다.

기본 MVP 조회는 `product_model.is_supported_mvp=true`와
`product_model.is_active=true`를 적용하는 안으로 검토한다. 과거 사람용
DTO의 고객·계약·일련번호·주소 필드는 이 최소 Summary에 자동 승계하지 않는다.

## 4. 권한과 오류

Repository에서 다음 범위를 함께 적용한다.

```text
customer__user=request.user
customer__deleted_at__isnull=True
```

| 상황 | HTTP | 코드·응답 |
| --- | ---: | --- |
| 정상 또는 빈 목록 | 200 | 빈 목록은 `items: []`, `total: 0` |
| 미인증 | 401 | `AUTH_REQUIRED` |
| CUSTOMER 이외 역할 | 403 | `FORBIDDEN` |
| 잘못된 page·size·status | 422 | `VALIDATION_ERROR` |
| 예상하지 못한 오류 | 500 | `INTERNAL_ERROR` |

Collection 조회이므로 다른 고객의 행은 404로 드러내지 않고 결과에서 완전히
제외한다. GET은 상태·이력·멱등 레코드를 생성하지 않는다.

## 5. 최근 관리일 경계

T-018 완료 조건에는 최근 관리일이 포함되지만, 현재 기계 계약에는 어떤
CareRecord를 최신으로 볼지 확정된 집계 규칙이 없다. 다음 규칙을 김은진과
검토한 뒤 nullable Projection을 추가한다.

- 완료 상태 CareRecord만 사용할지
- `performed_on` 최대값을 사용할지
- 동일 날짜 동률을 어떤 공개 식별자로 결정할지
- soft delete·취소·미완료 기록을 어떻게 제외할지

이 규칙이 승인되지 않은 R1은 부분 Slice이며 T-018 완료로 표시하지 않는다.

## 6. 승인 뒤 동시 변경할 파일 묶음

OpenAPI 또는 Runtime 파일 하나만 단독 수정하지 않는다.

| 단계 | 함께 변경할 범위 | 즉시 검증 |
| ---: | --- | --- |
| 1 | `contracts/api/paths/products.yaml`, Product·Subscription Schema, `openapi.yaml` 참조 | OpenAPI parse·operation·example 검사 |
| 2 | Operation inventory 기대값 `9→10`, 계약 단계 분류 `Runtime 7 / OpenAPI-only 3` | `test_openapi_runtime_coverage.py` |
| 3 | Repository·Service·Permission·Serializer·View·URL과 `config/api_urls.py` | Unit·API 집중 테스트 |
| 4 | Runtime 구현 뒤 분류 `Runtime 8 / OpenAPI-only 2` | 계약·Route 교차검사 |
| 5 | Django check·Migration drift·SQLite 전체 | 전체 Backend 회귀 |
| 6 | 빈 PostgreSQL·기본 PostgreSQL·권한·데이터 노출 | 동일 PR 변경 묶음의 PostgreSQL 회귀 |

## 7. 최소 테스트 Matrix

| 계층 | 필수 Case |
| --- | --- |
| Repository | 본인 범위, 타인 제외, soft-deleted profile 제외, `select_related`, 결정적 정렬, 상태 필터 |
| Service | page·size 경계, total, 빈 목록, Public UUID 매핑, nullable 날짜 |
| API | 200 본인만, 빈 목록 200, 401, 403, 422, 타인·내부 PK·PII 비노출, GET side effect 0 |
| OpenAPI | Path·Method·operationId·security·query·wrapper·enum·Schema |
| PostgreSQL | 동일 정렬, 권한 범위, Query 수, Migration drift 0 |

권장 테스트 경로:

```text
backend/tests/unit/subscriptions/test_subscription_repository.py
backend/tests/unit/subscriptions/test_subscription_service.py
backend/tests/api/test_t018_subscription_list.py
backend/tests/api/test_openapi_product_contract.py
backend/tests/api/test_openapi_runtime_coverage.py
```

## 8. 도미노 오류 방지

| 위험 | 차단 방법 |
| --- | --- |
| OpenAPI Path만 추가해 9 Operation 고정 테스트 실패 | Schema·inventory·예시·분류를 같은 계약 작업에서 갱신 |
| 최근 관리일을 즉시 구현해 T-019 규칙과 중복 | 집계 규칙 승인 전 R1에서 제외하고 부분 완료 유지 |
| 고객·계약·일련번호·주소 노출 | 최소 Summary Allowlist와 Public UUID만 사용 |
| `features` JSON에 API가 결합 | 공식 Product 필드로만 Projection |
| POST·PATCH까지 확장해 State·멱등 충돌 | GET 한 개를 계약→검증→Runtime→검증 순으로 완료 |

## 9. 검토 요청

| 검토자 | 확인할 내용 | 반환 |
| --- | --- | --- |
| 김은진 | 본인 범위·MVP 제품 필터·최근 관리일 집계·QA Matrix | 승인·변경 요청과 재현 Case |
| 윤승혁 | 공개 필드·역할·오류·T-018 부분 완료 경계 | 승인·보류·변경 요청 |
| 최지용 | 승인 결과를 계약 Diff로 반영하고 작은 Slice 구현 | 명령·Exit code·동일 PR 변경 묶음 회귀 |

승인 전 현재 완료 범위는 이 제안서와 링크·내용 검증까지다.
