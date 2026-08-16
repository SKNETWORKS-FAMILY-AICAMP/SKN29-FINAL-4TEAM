# 구독·제품·케어 이력 API 구현 가이드

> 관련 업무: 구독·제품 조회와 관리 이력
> 소비자: Customer Mobile·상담사 Web

## 1. 기능 범위

- 고객 본인 구독 목록·상세
- 합성 제품 구독 등록·수정
- 완료된 케어 이력 목록·상세
- 승인된 셀프 케어 결과 저장
- 다음 케어일 계산·재산정과 변경 이력

## 2. 주요 경로

- `backend/apps/subscriptions/**`
- `backend/apps/care/**`
- `backend/apps/catalog/**`
- `contracts/api/paths/products.yaml`
- `contracts/api/paths/care.yaml`
- `backend/tests/api/test_t018_*`
- `backend/tests/api/test_t019_*`

## 3. 권한·데이터 경계

- 고객은 본인 구독·케어 기록만 조회한다.
- 외부 입력은 승인된 합성 제품과 공개 UUID만 허용한다.
- 제품 활성·MVP 지원 여부를 저장 전에 검증한다.
- 내부 가격·원가·고객 식별정보를 Projection에 포함하지 않는다.
- 조회는 Side Effect 없이 수행한다.

## 4. 쓰기·멱등·동시성

동일 고객 Profile과 Subscription을 먼저 잠근 뒤 멱등 레코드를 확인한다.

| 요청 | 기대 결과 |
| --- | --- |
| 동일 Key·동일 Payload | 저장 1회, 동일 Resource Replay |
| 동일 Key·다른 Payload | 409, 패자 Payload 미반영 |
| 서로 다른 Key·중복 활성 제품 | 정확히 1건만 생성 |
| 저장 실패 | 구독·케어·멱등 원장 전체 Rollback |

## 5. 다음 케어일

공식 제품·관리 규칙의 `model`, `care_type`, `interval`, `source`, `version`을
사용한다. 복수 필터 주기를 임의로 한 날짜로 합치지 않는다. 규칙이 확정되지
않으면 계산 결과를 운영 기준으로 승격하지 않는다.

## 6. 검증

```powershell
.\backend\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  .\backend\tests\api\test_t018_subscription_write_runtime.py `
  .\backend\tests\api\test_t019_care_history_runtime.py
```

PostgreSQL 동시성 Case는 실제 DB에서 0 skip으로 확인한다.

## 7. 판정

계약·권한·IDOR·멱등·Rollback·PostgreSQL 동시성과 Projection 비노출이
통과하면 구현 완료다. 관리 주기 정책이 미확정이면 다음 케어일만 별도 HOLD다.
