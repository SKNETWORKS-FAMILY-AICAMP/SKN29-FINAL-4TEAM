# Django REST API 구독·제품조회 Runtime 구현·검증 가이드

> 기준일: 2026-08-08
> WBS 범위: T-018 R1 조회 Slice
> 구현 상태: 목록·상세 Runtime과 작성자 검증 완료
> 전체 T-018 상태: 등록·수정 기능은 미구현

## 1. 구현 범위

구현한 Endpoint는 두 개다.

| Method | Path | 기능 |
| --- | --- | --- |
| GET | `/api/v1/me/subscriptions` | 본인 ACTIVE 구독 목록 |
| GET | `/api/v1/me/subscriptions/{subscription_id}` | 본인 ACTIVE 구독 상세 |

다음 기능은 이번 Slice에 포함하지 않는다.

- 제품·구독 등록
- 관리 유형 수정
- 기본 제품 선택
- 문의 가능 여부와 `allowed_actions`
- T-019 케어 이력 API

따라서 “T-018 R1 조회 완료”는 맞지만 “T-018 전체 완료”로 확대하지 않는다.

## 2. 조회 경계

두 Endpoint는 같은 Repository 필터를 사용한다.

```text
customer.user = request.user
customer.deleted_at IS NULL
subscription.status_code = ACTIVE
product_model.model_code = WPUJAC104DWH
product_model.is_active = true
```

타 고객·삭제 고객·비활성 구독·미지원 모델·비활성 제품은 존재 여부를
노출하지 않고 상세 조회에서 모두 404로 처리한다.

접근 결과:

- 미인증: 401
- CUSTOMER가 아닌 역할: 403
- 잘못된 UUID·미존재·비소유·필터 제외: 404
- 알 수 없는 Query·Pagination 오류: 422

## 3. 응답 허용 필드

목록 Item:

- `subscription_id`
- `status_code`
- `management_type_code`
- `started_on`
- `last_care_on`
- `next_care_on`
- `product`

상세는 위 필드에 `ended_on`만 추가한다.

Product:

- `product_model_id`
- `model_code`
- `model_name`
- `generation_code`
- `manufacturer`

다음 값은 반환하지 않는다.

- 내부 정수 PK·customer_id
- contract_no·serial_no·설치 주소
- source_customer_product_public_id
- product.features·활성/지원 내부 Flag
- 고객 이름·전화·주소

## 4. `last_care_on` 계산

대상은 `CareRecord.status_code=COMPLETED`만이다.

1. `performed_on`이 있으면 우선 사용
2. 없으면 `completed_at`을 Asia/Seoul 날짜로 변환
3. 구독별 최대 날짜 반환
4. 완료 이력이 없으면 `null`

Repository에서 완료 이력을 Prefetch하므로 목록 크기에 따라 N+1 Query가
발생하지 않는다. 목록은 Count·Subscription+Product·Care Prefetch의
3 Query로 검증했다.

## 5. 정렬·Pagination·Query

- 정렬: `started_on DESC`, `public_id ASC`
- 기본값: `page=1`, `size=20`
- page 최소값: 1
- size 범위: 1~100
- 목록 허용 Query: `page`, `size`
- 상세 허용 Query: 없음

`status_code=ACTIVE`처럼 서버가 고정한 필터를 Query로 다시 보내도 알 수
없는 Query로 보고 422를 반환한다.

## 6. 구현 파일

| 계층 | 파일 |
| --- | --- |
| Route | `backend/apps/subscriptions/api/urls.py` |
| View | `backend/apps/subscriptions/api/views.py` |
| Serializer | `backend/apps/subscriptions/api/serializers.py` |
| Permission | `backend/apps/subscriptions/permissions.py` |
| Service | `backend/apps/subscriptions/services/subscription_service.py` |
| Repository | `backend/apps/subscriptions/repositories/subscription_repository.py` |
| API Mount | `backend/config/api_urls.py` |
| 계약 상태 | `contracts/api/paths/products.yaml` |
| Runtime Test | `backend/tests/api/test_t018_subscription_runtime.py` |

T-018 조회 구현은 Model이나 Migration을 변경하지 않는다. 계약의
`migration_change_allowed=false`, `database_change_allowed=false`를 유지했다.

## 7. 실행 방법

```powershell
cd backend
python manage.py check --settings=config.settings.local
python manage.py makemigrations --check --dry-run --settings=config.settings.local
python -m pytest -q `
  tests/api/test_t018_product_subscription_contract.py `
  tests/api/test_t018_subscription_runtime.py
```

PostgreSQL 검증 시 비밀값을 출력하지 않고 검증 DB 이름만 Process 환경으로
지정한다.

```powershell
$env:POSTGRES_DB='검증용_DB명'
python -m pytest -q --ds=config.settings.local `
  tests/api/test_t018_subscription_runtime.py
```

## 8. Test Matrix

| 영역 | 검증 |
| --- | --- |
| 목록 | 소유권·ACTIVE·제품 코드·제품 활성·삭제 Profile 필터 |
| 정렬 | started_on 동률에서 public_id 오름차순 |
| Pagination | 기본값·경계·2페이지·total |
| 상세 | 정상 Projection과 동일 404 경계 |
| 날짜 | performed_on 우선·Seoul fallback·MAX·null |
| 권한 | 401·비CUSTOMER 403·비활성 사용자 403 |
| 입력 | unknown Query·page·size 오류 422 |
| 보안 | 계약·일련번호·주소·features·개인정보 미노출 |
| 회귀 | OpenAPI Runtime 인벤토리 10 구현/13 미구현 |

## 9. 2026-08-08 결과

| 실행 | 결과 |
| --- | --- |
| T-018 계약+Runtime | `12 passed` |
| OpenAPI 인벤토리 포함 표적 회귀 | `15 passed` |
| PostgreSQL T-017B Admin+T-018 Runtime | `16 passed` |
| 관련 도메인 묶음 회귀 | `145 passed, 2 skipped` |
| 해당 Slice 검증 시점 전체 Backend 회귀 | `817 passed, 13 skipped` |

독립 QA는 두 Route의 실제 응답, 동일 404 경계, 422 Query 정책과 민감 필드
제외를 확인한다. 등록·수정 기능을 이 결과에 포함하면 안 된다.
