# CR-001 상담사 전화 문의 등록 API

> 기준일: 2026-08-11
> Actor: `CONSULTANT`
> 상태: `CONFIRMED / IMPLEMENTED / AUTHOR_VERIFIED / WEB_REMOTE_PENDING`
> OpenAPI: [`contracts/api/openapi.yaml`](../../contracts/api/openapi.yaml)

## 1. 한 문장 결론

기존 CUSTOMER 문의 생성은 그대로 두고, 상담사가 합성 고객의 활성 구독을
검색한 뒤 전화 문의를 상담 대기열에 등록하는 전용 API 2개를 추가한다.

## 2. Endpoint

| Method | Path | operationId | 목적 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/consultant/customer-subscriptions/search` | `searchConsultantCustomerSubscriptions` | 기존 고객·활성 구독 후보 검색 |
| `POST` | `/api/v1/consultant/phone-inquiries` | `registerConsultantPhoneInquiry` | 전화 문의 등록 |

검색도 POST인 이유는 이름·연락처 검색어가 URL, Browser History, Proxy
Access Log에 노출되는 범위를 줄이기 위해서다. 데이터 변경 API라는 뜻은
아니다.

## 3. 공통 규칙

- JWT 인증된 활성 `CONSULTANT`만 호출한다.
- 개발·테스트·발표에서는 합성 고객·합성 계정만 허용한다.
- 요청·응답은 공통 `ApiResponse` Envelope와 `X-Correlation-ID`를 사용한다.
- 전화번호 원문, Token, DB PK, 실제 개인정보를 응답·오류·로그에 넣지
  않는다.
- Web은 실패 시 Mock으로 자동 전환하지 않는다.

## 4. 고객·구독 검색

### 4.1 요청

```json
{
  "query": "0000",
  "limit": 10
}
```

| 필드 | 필수 | 규칙 |
| --- | :---: | --- |
| `query` | Y | 고객명 trim 후 2자 이상 또는 연락처 정규화 숫자 4자리 이상 |
| `limit` | N | 1~20, 기본 10 |

연락처는 숫자·하이픈·공백·괄호·`+`를 입력할 수 있고 Backend가 숫자
기준으로 검색한다. 알 수 없는 Body 필드는 422다.

### 4.2 검색 범위

아래 조건을 모두 만족하는 구독만 후보가 된다.

1. 고객 프로필이 삭제되지 않음
2. 고객 프로필과 연결 User가 합성 데이터임
3. 연결 User가 활성 상태임
4. 구독 상태가 `ACTIVE`임

결과 없음은 오류가 아니라 `items=[]`, `returned_count=0`인 200이다.

### 4.3 응답 후보

```json
{
  "customer_id": "00000000-0000-4000-8000-000000000001",
  "customer_display_name": "합성 전화 고객 1",
  "phone_masked": "010-****-0001",
  "subscription_id": "00000000-0000-4000-8000-000000000002",
  "subscription_status": "ACTIVE",
  "management_type_code": "VISIT_CARE",
  "product_id": "00000000-0000-4000-8000-000000000003",
  "product_model_code": "WPUJAC104DWH",
  "product_name": "초소형 직수 정수기"
}
```

동일 고객에게 활성 구독이 여러 개면 구독 한 건을 후보 한 행으로 반환한다.
Web은 상담사가 실제 문의 대상 제품을 선택하도록 한다.

## 5. 전화 문의 등록

### 5.1 Header·요청

- `X-Correlation-ID`: 공백 없는 UUID, 필수
- `Idempotency-Key`: 1~128자, 필수

```json
{
  "subscription_id": "00000000-0000-4000-8000-000000000002",
  "raw_text": "전화로 접수한 누수 문의입니다.",
  "representative_symptom_code": "LEAK",
  "priority_code": "HIGH"
}
```

| 필드 | 규칙 |
| --- | --- |
| `subscription_id` | 검색 결과에서 선택한 ACTIVE 구독 공개 UUID |
| `raw_text` | trim 후 1~5000자 |
| `representative_symptom_code` | `NO_WATER`, `LOW_FLOW`, `LEAK`, `ODOR`, `TASTE`, `TEMPERATURE_ABNORMAL`, `NOISE`, `DISPLAY_ERROR`, `OTHER` |
| `priority_code` | `LOW`, `NORMAL`, `HIGH`, `URGENT` |

고객명·전화번호·제품 ID를 등록 요청에 다시 보내지 않는다. Backend가
`subscription_id`로 관계를 재검증하므로 화면 문자열 조작으로 다른 고객을
연결할 수 없다.

### 5.2 저장 결과

```text
channel_code=PHONE
initiated_by=현재 상담사
assigned_user=현재 상담사
assigned_role_code=CONSULTANT
status_code=CONSULTATION_REQUIRED
state_version=1
```

- `support_inquiry`와 `support_inquiry_symptom` 기존 테이블을 사용한다.
- `priority_code`는 기존 `support_inquiry`에 Forward Migration으로 추가한다.
- `REGISTER_PHONE_INQUIRY` 전이 이력과 Correlation·Idempotency 정보를
  저장한다.
- AI·RAG는 자동 호출하지 않는다.

### 5.3 성공 응답

201 `data`는 다음 필드만 반환한다.

- `inquiry_id`
- `inquiry_code`
- `status_code=CONSULTATION_REQUIRED`
- `state_version=1`
- `idempotent_replay`
- Backend가 계산한 `allowed_actions`

같은 상담사·Operation·Idempotency-Key와 같은 요청은 새 문의를 만들지
않고 기존 201 결과를 재생한다. 같은 키로 다른 요청을 보내면 409다.

## 6. 오류 처리

| HTTP | 의미 | Web 처리 |
| ---: | --- | --- |
| 401 | 인증 없음·만료 | 세션 갱신 또는 로그인 |
| 403 | 상담사 역할 아님 | 기능 차단 |
| 404 | 선택 구독이 미존재·비활성·비합성·삭제 | 선택 초기화 후 재검색 |
| 409 | Idempotency-Key 충돌 | 새 키로 사용자의 명시적 재시도 |
| 422 | Header·본문 검증 실패 | 입력 유지, 필드 오류 표시 |
| 500 | 서버 오류 | Mock 전환 금지, 재시도와 Correlation 기록 |

## 7. 기존 기능 보호선

- CUSTOMER `POST /api/v1/inquiries` Path·DTO·권한은 변경하지 않는다.
- Web 소스는 Backend 작업에서 수정하지 않는다.
- 신규 고객 생성, 수동 문의 제목, 상담 메모, 콜백 예약, 개인정보 동의
  확인은 이번 범위가 아니다.
- AI Schema·Prompt·RAG 판정 정책을 변경하지 않는다.
- 전화 접수 문의는 기존 `START_CONSULTATION`부터 상담 Workflow를
  이어간다.

## 8. 구현·검증 위치

- Runtime: `backend/apps/inquiries/api`, `repositories`, `services`
- Migration: `backend/apps/inquiries/migrations/0013_inquiry_priority_code.py`
- 계약: `contracts/api/paths/consultant-phone-inquiries.yaml`
- State: `contracts/state-machine/inquiry-events.yaml`,
  `transition-rules.yaml`, `transition-guards.yaml`, `role-permissions.yaml`
- 표적 테스트:
  `backend/tests/api/test_consultant_phone_inquiry_contract.py`,
  `backend/tests/api/test_consultant_phone_inquiry_runtime.py`

작성자 검증 수치와 PostgreSQL 결과는 구현·검증 보고서에서 별도로
고정한다. Web Remote Adapter와 공동 Smoke PASS는 Backend 작성자 검증을
대신하지 않으며 별도 인계·회신으로 종료한다.
