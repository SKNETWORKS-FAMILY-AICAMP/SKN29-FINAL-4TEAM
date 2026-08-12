# Water Bridge API Swagger HTML 실행 결과 분석

## 1. 분석 대상

- 원본 파일: `C:\Users\Playdata\Downloads\Water Bridge API.html`
- 분석 일자: 2026-08-11
- 분석 기준: Swagger의 예상 `Responses` 표가 아니라 각 항목에 저장된 실제 `Server response`
- 민감정보 처리: Token 원문은 수집하거나 문서에 기록하지 않음

## 2. 최종 요약

| 판정 | API 수 | 내용 |
|---|---:|---|
| 성공 | 1 | `GET /health`가 실제 `200` 반환 |
| 실패 | 21 | 인증 API 3개 `422`, 보호 API 18개 `401` |
| 미실행 | 2 | 방문 확정·방문 일정 API에 실제 Server response 없음 |
| 합계 | 24 | HTML에 포함된 전체 API 항목 |

```text
SUCCESS=1
FAILED=21
NOT_EXECUTED=2
```

이번 HTML에서 정상 완료가 확인된 것은 Health뿐입니다. 다만 보호 API의 `401`은 백엔드 장애가 아니라 인증되지 않은 요청을 정상 차단한 결과입니다. 실제 업무 응답의 성공 여부는 아직 검증되지 않았습니다.

## 3. 공통 실패 원인

### 3.1 Demo Login 요청값 누락

가장 먼저 성공해야 하는 Demo Login이 빈 요청으로 실행됐습니다.

```text
POST /api/v1/auth/demo-login
actual_status=422
error_code=VALIDATION_ERROR
missing_field=demo_user_code
```

따라서 `access_token`이 발급되지 않았습니다.

올바른 요청 예시는 다음과 같습니다.

```json
{
  "demo_user_code": "DEMO-CONSULTANT-001"
}
```

### 3.2 Swagger Authorize 미적용

저장된 모든 보호 API 요청에서 아래 헤더가 확인되지 않았습니다.

```text
Authorization: Bearer <access_token>
```

그 결과 보호 API 18개가 업무 로직이나 리소스 검증에 도달하기 전에 모두 `401 AUTH_REQUIRED`로 종료됐습니다.

### 3.3 POST·PATCH 요청 본문과 업무 Header 미입력

여러 POST·PATCH 요청이 빈 본문으로 실행됐습니다. 인증 문제를 해결한 뒤에도 각 API가 요구하는 다음 값이 필요합니다.

- Request body
- `state_version`
- `Idempotency-Key`
- 문의·방문 상태에 맞는 역할과 허용 행동

현재 HTML에서는 인증 단계에서 먼저 차단됐으므로, 위 입력값의 유효성은 검증되지 않았습니다.

### 3.4 Swagger 하단 `Responses 200`의 의미

각 항목 하단의 `Responses 200`은 OpenAPI 명세에 기록된 예상 응답입니다. 실제 실행 성공을 의미하지 않습니다. 성공 여부는 반드시 `Server response`의 실제 코드와 본문으로 판단해야 합니다.

## 4. API별 판정

| 번호 | Method | API | 판정 | 실제 결과 | 실패·미실행 원인 |
|---:|---|---|---|---|---|
| 1 | POST | `/api/v1/auth/demo-login` | 실패 | `422 VALIDATION_ERROR` | 필수 `demo_user_code` 누락 |
| 2 | POST | `/api/v1/auth/logout` | 실패 | `422 VALIDATION_ERROR` | 필수 `refresh_token` 누락 |
| 3 | POST | `/api/v1/auth/refresh` | 실패 | `422 VALIDATION_ERROR` | 필수 `refresh_token` 누락 |
| 4 | GET | `/api/v1/inquiries` | 실패 | `401 AUTH_REQUIRED` | `Authorization: Bearer ...` 없음 |
| 5 | POST | `/api/v1/inquiries` | 실패 | `401 AUTH_REQUIRED` | 인증 Header 없음. 인증 후 생성 Request body도 필요 |
| 6 | GET | `/api/v1/inquiries/{inquiry_id}` | 실패 | `401 AUTH_REQUIRED` | `inquiry_id` 요청은 도착했지만 인증 Header 없음 |
| 7 | POST | `/api/v1/inquiries/{inquiry_id}/answers` | 실패 | `401 AUTH_REQUIRED` | 고객 인증 Header 없음. 인증 후 답변 body와 `Idempotency-Key` 필요 |
| 8 | POST | `/api/v1/inquiries/{inquiry_id}/cancel` | 실패 | `401 AUTH_REQUIRED` | 고객 인증 Header 없음. 인증 후 취소 body와 `Idempotency-Key` 필요 |
| 9 | POST | `/api/v1/inquiries/{inquiry_id}/complete-consultation` | 실패 | `401 AUTH_REQUIRED` | 상담사 인증 Header 없음. 인증 후 상태에 맞는 body 필요 |
| 10 | PATCH | `/api/v1/inquiries/{inquiry_id}/consultation-summary` | 실패 | `401 AUTH_REQUIRED` | 상담사 인증 Header 없음. 인증 후 상담 요약 body 필요 |
| 11 | POST | `/api/v1/inquiries/{inquiry_id}/consultation-summary/confirm` | 실패 | `401 AUTH_REQUIRED` | 상담사 인증 Header 없음. 인증 후 `state_version`과 `Idempotency-Key` 필요 |
| 12 | POST | `/api/v1/inquiries/{inquiry_id}/start-consultation` | 실패 | `401 AUTH_REQUIRED` | 상담사 인증 Header 없음. 인증 후 `state_version`과 `Idempotency-Key` 필요 |
| 13 | POST | `/api/v1/inquiries/{inquiry_id}/submit` | 실패 | `401 AUTH_REQUIRED` | 고객 인증 Header 없음. 인증 후 증상 제출 body와 `Idempotency-Key` 필요 |
| 14 | POST | `/api/v1/inquiries/{inquiry_id}/visit-not-needed` | 실패 | `401 AUTH_REQUIRED` | 인증 Header 없음. 인증 후 상태·허용 행동·body 검증 필요 |
| 15 | POST | `/api/v1/inquiries/{inquiry_id}/visit-review` | 실패 | `401 AUTH_REQUIRED` | 인증 Header 없음. 인증 후 상태·허용 행동·body 검증 필요 |
| 16 | POST | `/api/v1/inquiries/{inquiry_id}/visits` | 실패 | `401 AUTH_REQUIRED` | 인증 Header 없음. 인증 후 방문 생성 body와 `Idempotency-Key` 필요 |
| 17 | GET | `/api/v1/me` | 실패 | `401 AUTH_REQUIRED` | 로그인 Token이 없으므로 현재 사용자 조회 불가 |
| 18 | GET | `/api/v1/me/inquiries/{inquiry_id}` | 실패 | `401 AUTH_REQUIRED` | 고객 인증 Header 없음 |
| 19 | GET | `/api/v1/me/inquiries/{inquiry_id}/questions` | 실패 | `401 AUTH_REQUIRED` | 고객 인증 Header 없음 |
| 20 | GET | `/api/v1/me/subscriptions` | 실패 | `401 AUTH_REQUIRED` | 고객 인증 Header 없음 |
| 21 | GET | `/api/v1/me/subscriptions/{subscription_id}` | 실패 | `401 AUTH_REQUIRED` | 고객 인증 Header 없음 |
| 22 | POST | `/api/v1/visits/{visit_id}/confirm` | 미실행 | Server response 없음 | HTML에 실행 결과가 저장되지 않음. 현재 격리 DB에도 Visit Seed 없음 |
| 23 | PATCH | `/api/v1/visits/{visit_id}/schedule` | 미실행 | Server response 없음 | HTML에 실행 결과가 저장되지 않음. 현재 격리 DB에도 Visit Seed 없음 |
| 24 | GET | `/health` | 성공 | `200`, 빈 본문 | 정상 liveness 응답 |

## 5. 확인된 정상 동작

실패 결과에서도 다음 백엔드 기반 기능은 정상임을 확인할 수 있습니다.

- 백엔드 서버가 요청을 수신함
- Health Endpoint가 실제 `200`을 반환함
- 인증 없는 보호 API 요청을 `401`로 차단함
- 필수 입력값이 없는 인증 요청을 `422`로 차단함
- 오류 응답에 공개 오류 코드와 `correlation_id`가 포함됨

이는 인증·검증 장치의 동작 확인이며, 각 업무 API의 성공 응답 검증과는 별개입니다.

## 6. 재검증 순서

### 6.1 상담사 API

1. `POST /api/v1/auth/demo-login`에 아래 body 입력

   ```json
   {"demo_user_code": "DEMO-CONSULTANT-001"}
   ```

2. 실제 `Server response=200` 확인
3. 응답의 `data.access_token` 값만 복사
4. Swagger 상단 `Authorize`에서 Token 입력
5. 버튼이 `Authorized` 또는 `Logout` 상태인지 확인
6. 먼저 `GET /api/v1/me` 실행
7. `Server response=200`, `success=true` 확인
8. 상담사 문의 목록·상세를 순서대로 실행

상담사 상세조회 고정 문의 ID:

```text
4f829120-ecbb-5b30-9365-bf02f9044c3b
```

### 6.2 고객 API

고객 API는 상담사 Token이 아니라 `DEMO-CUSTOMER-001` 고객 Token으로 다시 Authorize해야 합니다.

```json
{"demo_user_code": "DEMO-CUSTOMER-001"}
```

고객 구독 상세조회용 ID:

```text
0983e0cc-d80d-4ff6-9439-e3edd7ef3db3
```

문의 답변·취소 API는 고객 본인 소유 문의와 해당 상태에 맞는 Request body가 있어야 성공합니다. 현재 상담사 조회용 고정 문의 ID를 고객 표준 Demo Token으로 실행하는 것은 성공 시나리오가 아닙니다.

### 6.3 방문 API

현재 격리 DB에는 Visit 레코드가 없습니다. 방문 생성 흐름을 먼저 완료하거나 별도 Visit Seed를 만든 뒤 응답의 `visit_id`로 일정·확정 API를 검증해야 합니다.

## 7. 최종 판정

```text
BACKEND_SERVER_REACHABLE=PASS
HEALTH_CHECK=PASS
AUTH_GUARD=PASS
VALIDATION_GUARD=PASS
AUTHENTICATED_BUSINESS_API_SUCCESS=NOT_VERIFIED
VISIT_API=NOT_EXECUTED
```

따라서 이번 HTML 결과는 백엔드 장애 증거가 아닙니다. 최초 로그인 요청값 누락과 Swagger Authorize 미적용으로 인해 성공 경로가 시작되지 못한 실행 결과입니다.
