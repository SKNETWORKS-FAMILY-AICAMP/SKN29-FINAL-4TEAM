# Backend·Mobile API 안전 연동 가이드

> 작성·유지 책임: Backend·Database·API 계약 담당
> 검토·소비 역할: Mobile 담당, Web 담당
> 기준일: 2026-08-02
> 문서 상태: 안전 인계 기준 — Runtime·미게시 구현 후보·설계·미구현 범위 분리 (`SAFE_HANDOFF`)
> 변경 범위: Mobile 파일은 변경하지 않고 Backend 후보와 소비 경계만 전달
> 제외 범위: 지도, 위치 추적, ETA, 경로, GPS·Polling

이 문서는 Mobile 소비 역할이 Runtime·OpenAPI-only·Mock·Blocked 경계를
확인하는 연동 가이드다. 개인 작업 이력 대신 팀 기준선과 실행 증거를
완료 판단의 기준으로 사용한다.

---

## 1. 연동 결론

`subscription_id` P0 Blocker는 실제로 존재한다.
현재 `/api/v1/me`는 구독 ID를 반환하지 않고,
`GET /api/v1/me/subscriptions`도 Runtime Route가 아니다.

다음 방식으로 작업을 분리한다.

1. **환경 한정 Backend Smoke**는 검증된 합성 고객과 실행 환경에서 조회한
   `subscription_id`를 사용한다.
2. 해당 UUID는 앱 소스에 하드코딩하거나 공용 Fixture로 확정하지 않는다.
3. **정식 해결**은 본인 ACTIVE 구독 목록 API
   `GET /api/v1/me/subscriptions`를 계약·구현한 뒤 조회 결과의 Public UUID를
   문의 생성에 전달하는 방식으로 한다.
4. `/me.customer_profile.subscription_id` 단일 필드 추가는 고객이 여러
   ACTIVE 구독을 가질 수 있는 현행 Model과 맞지 않으므로 채택하지 않는다.
5. 추가 문진, Guidance, 상담, 문의 상세·Timeline, 기사 방문은 현재
   Runtime이 아니므로 계약 확정 전까지 Mock 전용으로 표시하거나 실제 호출을 차단한다.

### 1.1 요구 항목별 Backend 기준

| 요구 항목 | Backend 기준 | 현재 상태 | Mobile 처리 |
|---|---|---|---|
| P0 `subscription_id` | 로컬 Smoke용 환경 한정 값 제공, 정식으로 구독 목록 API 추진 | 로컬만 즉시 가능 | 소스 하드코딩 금지 |
| `allowed_actions` | 성공은 행동 객체, 409 Snapshot은 코드 문자열 | 용도별 확정 계약 | 성공 DTO와 409 오류 DTO를 분리 Parsing |
| 추가 답변 version | Inquiry `state_version` 사용 | 계약 근거 있음, API 미구현 | 실제 호출 Blocked |
| Guidance DTO | `inquiry_state_version`과 정수 `guidance_version` 분리 | Enum·API 미동결 | opaque string Mock |
| 상담 요청 | `reason` 선택, 활성 상담 UPSERT, 두 version 분리 | 정책 제안, API 미구현 | 실제 호출 Blocked |
| 문의 상세·Timeline | 요청 항목 모두 포함하는 컨테이너 응답 채택 | 조회 계약·API 미구현 | Mock 전용 — 조회 계약과 Runtime Route 없음 |
| 방문 상세 version | Inquiry·Visit version 둘 다 반환 | 엔진의 이중 version 검증 미구현 | 결과 등록 Blocked |
| 방문 결과 분기 | 정상 완료·재방문을 행동별 Endpoint로 분리하는 안 채택 | HTTP 계약·API 미구현 | 실제 호출 Blocked |

---

## 2. 현재 프로젝트를 깨뜨리지 않는 작업 경계

### 2.1 Mobile 3모듈 유지

```text
mobile/
├─ customer-app/
├─ technician-app/
└─ core/
```

- `customer-app`과 `technician-app`을 서로 참조시키지 않는다.
- 두 App이 공통으로 사용하는 순수 Kotlin Model·Enum·Mapper만 `core`에 둔다.
- URL, Token, Android `BuildConfig`, Activity, Compose와 위치 권한 코드는
  `core`에 넣지 않는다.
- namespace, applicationId, package와 기존 Navigation을 변경하지 않는다.
- 과거 문서의 `mobile/app/**` 단일 App 경로를 다시 만들지 않는다.

### 2.2 기존 `ServiceCallApi` 보존

현재 고객·기사 `ServiceCallApi`는 `/api/service-calls/**`와 지도·위치 시연을
  위한 `HttpURLConnection` 기반 코드다. WaterBridge `/api/v1` 공통 Wrapper,
JWT, `Idempotency-Key`, `state_version`, 409 Snapshot 처리가 없다.

따라서 다음을 지킨다.

- 기존 `ServiceCallApi` 이름과 내부 Path를 `/api/v1`로 바꾸지 않는다.
- 기존 지도·호출·Tracking 화면은 호환성 보존 대상으로 유지한다.
- WaterBridge 실제 업무 API Client·DTO·Repository를 별도 경계로 추가한다.
- 고객 문의 API는 `customer-app`, 기사 방문 API는 `technician-app`에 둔다.
- 정말 공통인 순수 DTO·Enum·Mapper만 `core`로 올린다.
- 현재 `BuildConfig.BACKEND_BASE_URL` 주입 방식은 유지한다.

권장 경계 예시이며, 클래스명은 Mobile 담당자가 현행 패키지에 맞게 정한다.

```text
customer-app/.../data/watercare/      # Auth·구독·문의·Guidance·상담 Client
customer-app/.../repository/          # 고객 화면 Repository
technician-app/.../data/watercare/    # 방문 목록·상세·결과 Client
technician-app/.../repository/        # 기사 화면 Repository
core/.../model/                       # 순수 상태·DTO 변환 결과
```

---

## 3. 현재 Runtime 경계

### 3.1 공유 기준선에서 사용할 수 있는 API

| Method | Path | Mobile 용도 |
|---|---|---|
| `POST` | `/api/v1/auth/demo-login` | 합성 사용자 로그인 |
| `POST` | `/api/v1/auth/refresh` | Access Token 갱신 |
| `POST` | `/api/v1/auth/logout` | Refresh Token 폐기 |
| `GET` | `/api/v1/me` | 사용자·역할 확인, 구독 ID는 없음 |
| `POST` | `/api/v1/inquiries` | 문의 생성 |
| `POST` | `/api/v1/inquiries/{id}/cancel` | DRAFT 문의 취소 |

### 3.2 미게시 구현 후보

아래 Slice는 구현·검증 증거가 있으나 팀 기준선에는 아직 반영되지 않았다.

```http
POST /api/v1/inquiries/{inquiry_id}/submit
```

- 동작: 저장된 증상 제출 확정
- 상태: `DRAFT → QUESTIONNAIRE_IN_PROGRESS`
- Request: `state_version`
- Header: `Authorization`, `Idempotency-Key`
- 로컬 Route·OpenAPI·Serializer·Service·테스트 존재
- 현재 집중 검증 통과
- **팀 기준선 반영과 독립 검토 전에는 Mobile 공유 Runtime 완료로 간주하지 않음**

### 3.3 현재 `api-not-found`인 요청 범위

```text
GET  /api/v1/me/subscriptions
GET  /api/v1/inquiries/{id}/questions
POST /api/v1/inquiries/{id}/answers
GET  /api/v1/inquiries/{id}/guidance
POST /api/v1/inquiries/{id}/consultation-requests
GET  /api/v1/inquiries/{id}
GET  /api/v1/technician/visits
GET  /api/v1/technician/visits/{id}
POST /api/v1/technician/visits/{id}/results
```

Model·Migration이 존재하더라도 이 경로의 실제 API 구현 증거가 아니다.

---

## 4. P0 `subscription_id` 연동 기준

### 4.1 요구사항 판정

Mobile 요구사항을 코드·Route에 대조한 결과 다음 제약이 확인된다.

- 통합 URL에 `subscriptions` 앱이 포함돼 있지 않다.
- `/me.customer_profile`에는 구독 Public UUID가 없다.
- Mobile이 본인 ACTIVE 구독을 조회하는 Runtime API가 없다.
- 따라서 문의 생성은 사용할 UUID가 없으면 실제 Smoke가 막힌다.

### 4.2 Smoke 식별자 취득 원칙

Smoke를 수행할 때는 아래와 같이 현재 실행 DB에서 조회한 Public UUID를
로컬 설정에 주입한다. 문서의 값은 형식을 설명하는 자리표시자다.

```properties
DEMO_USER_CODE=DEMO-CUSTOMER-001
DEMO_SUBSCRIPTION_ID=<현재 DB에서 조회한 CustomerSubscription.public_id>
```

연결 데이터:

```text
contract_no=DEMO-SUB-001
status_code=ACTIVE
product_model_code=DEMO-PMD-001
```

중요:

- 조회한 UUID는 **해당 Backend 실행 DB 전용**이다.
- 구독 Model은 최초 생성 시 UUID4를 발급한다.
- `seed_demo_subscriptions`는 `contract_no=DEMO-SUB-001`로
  `update_or_create`하지만 Public UUID를 상수로 지정하지 않는다.
- 같은 DB에서 Seed를 다시 실행하면 UUID는 보존되지만 DB를 새로 만들면
  달라질 수 있다.
- 앱 Kotlin 소스, 공용 JSON, README와 Git 추적 파일에 넣지 않는다.

Mobile에서 임시 주입이 필요하면 Git에서 제외된
`mobile/local.properties`를 사용한다. 현재 Gradle에는
`DEMO_SUBSCRIPTION_ID`용 BuildConfig field가 없으므로 해당 주입 코드까지
완료된 것으로 보지 않는다.

### 4.3 Backend 재조회 명령

Backend 담당자가 Mobile이 연결할 실제 개발 DB를 확인한 뒤 실행한다.

```powershell
Set-Location .\SKN29-FINAL-4TEAM
$env:PYTHONDONTWRITEBYTECODE = "1"
$script = @'
from apps.subscriptions.models import CustomerSubscription

subscription = CustomerSubscription.objects.get(
    contract_no="DEMO-SUB-001",
    status_code="ACTIVE",
)
print(subscription.public_id)
'@
.\backend\.venv\Scripts\python.exe .\backend\manage.py shell -c $script
```

출력값은 문서·Git이 아니라 해당 개발환경의 로컬 설정으로만 전달한다.

### 4.4 정식 해결안

정식 계약 방향:

```http
GET /api/v1/me/subscriptions?page=1&size=20&status_code=ACTIVE
Authorization: Bearer <access_token>
```

응답의 `items[].id`는 `CustomerSubscription.public_id`이고, 문의 생성
Request의 `subscription_id`로 사용한다.

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "10000000-0000-4000-8000-000000000001",
        "product": {
          "id": "00000000-0000-4000-8000-000000000000",
          "model_code": "DEMO-PMD-001",
          "model_name": "WaterBridge Demo Product",
          "is_supported": true,
          "is_active": true
        },
        "management_type_code": "VISIT_CARE",
        "status_code": "ACTIVE",
        "started_on": "2026-01-15",
        "next_care_on": "2026-08-04"
      }
    ],
    "page": 1,
    "size": 20,
    "total": 1
  },
  "error": null,
  "metadata": {
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

현재 상태는 계약·테스트 제안만 존재하고 Runtime은 미구현이다
(`SAFE_CONTRACT_TEST_PROPOSAL_ONLY`).
계약·Route·Repository·권한·테스트를 같은 변경 단위로 구현한 뒤 Mobile에
정식 제공한다.

---

## 5. 문의 생성·취소 실제 연동 전달

### 5.1 공통 Header

```http
Authorization: Bearer <access_token>
X-Correlation-ID: <UUID>
Idempotency-Key: <1~128자 고유값>
Content-Type: application/json; charset=utf-8
```

- `X-Correlation-ID`가 없으면 Backend가 생성한다.
- 응답 `metadata.correlation_id`를 오류·Smoke 증거에 보존한다.
- 같은 작업의 Network 재전송은 같은 Key·같은 Payload를 사용한다.
- 사용자의 새로운 작업 또는 다른 Payload에는 새 Key를 사용한다.

### 5.2 문의 생성

```http
POST /api/v1/inquiries
```

```json
{
  "subscription_id": "10000000-0000-4000-8000-000000000001",
  "channel_code": "MOBILE",
  "raw_text": "정수기 물줄기가 평소보다 약해졌어요.",
  "representative_symptom_code": "LOW_FLOW"
}
```

필수:

```text
subscription_id
channel_code = WEB | MOBILE | PHONE | OPERATOR
raw_text
```

선택:

```text
representative_symptom_code
questionnaire_session_id
```

응답 핵심:

```json
{
  "inquiry_id": "30000000-0000-4000-8000-000000000001",
  "inquiry_code": "INQ-30000000000040008000000000000001",
  "status_code": "DRAFT",
  "state_version": 1,
  "idempotent_replay": false,
  "allowed_actions": []
}
```

- `inquiry_id`는 공개 UUID, `inquiry_code`는 업무 표시번호다.
- 내부 정수 PK를 Route·저장 DTO에 사용하지 않는다.
- 문의 생성 시 `state_version`은 보내지 않고 서버가 `1`로 초기화한다.
- 타인 소유·비활성 구독은 존재를 숨기기 위해 404다.

### 5.3 문의 취소

```http
POST /api/v1/inquiries/{inquiry_id}/cancel
```

```json
{
  "state_version": 1,
  "reason_code": "CUSTOMER_REQUEST",
  "reason_detail": "고객이 문의 작성을 취소했습니다."
}
```

취소 사유 Enum:

```text
CUSTOMER_REQUEST
DUPLICATE_INQUIRY
ISSUE_RESOLVED
OTHER
```

취소는 현재 DRAFT 문의에서 실제 Smoke한다. 이미 증상 제출로 상태가
변경됐다면 stale version·허용 상태 충돌로 409가 발생할 수 있다.

---

## 6. 후속 계약 항목별 상세 기준

### 6.1 `allowed_actions` 형식

성공 응답의 `allowed_actions`는 아래 행동 객체 배열이다.

```json
{
  "code": "REQUEST_CONSULTATION",
  "label": "상담 요청",
  "operation_id": "requestConsultation",
  "style": "SECONDARY",
  "requires_confirmation": false,
  "confirmation_message": null
}
```

현재 상태:

- 팀 승인 State 계약은 위 객체 필드를 정의한다 (`TEAM_APPROVED`).
- 문의 생성 성공 Runtime도 객체 배열이다.
- 409 Snapshot의 `allowed_actions`는 코드 문자열 배열이다.
- 공용 OpenAPI `AllowedAction` Schema는 아직 비어 있다.
- Resolver는 현재 상태+역할을 계산하지만 모든 동적 Guard까지 평가하지 않는다.

두 Shape는 불일치가 아니라 용도가 다른 확정 계약이다. 성공 응답은 버튼
표시에 필요한 전체 행동 메타데이터를 제공하고, 409는 최신 상태에서 가능한
행동 코드만 제공한다. Mobile은 두 응답 DTO를 하나로 억지 통합하지 않는다.

Mobile 소비 규칙:

- 성공 DTO에서는 객체 배열을 읽고 409 오류 상세에서는 문자열 배열을 읽는다.
- 문자열 코드만 받은 경우 label·operation·확인 문구를 임의 생성하지 않는다.
- 409에서는 입력을 보존하고 상태·version을 갱신한다.
- 완전한 행동 객체를 다시 받기 전 mutation 버튼을 보수적으로 비활성화한다.

### 6.2 추가 답변 `state_version`

채택 방향:

```text
POST /inquiries/{id}/answers 요청은 Inquiry의 state_version을 사용한다.
```

근거:

- State Guard는 `request.state_version == inquiry.state_version`을 검사한다.
- 현행 `InquiryQuestionnaireRequest`도 Inquiry 기대 version으로 정의한다.
- 추가 답변은 Inquiry 상태를 `QUESTIONNAIRE_IN_PROGRESS`로 유지하면서
  재평가를 촉발할 수 있다.

`QuestionnaireSession.state_version`은 별도 CARE_PRECHECK 세션 원장용이다.
향후 두 원장을 동시에 변경하면 필드를 명시적으로 분리한다.

```text
inquiry_state_version
questionnaire_state_version
```

현재 추가 답변 Route·Serializer·Service가 없으므로 Mobile 실제 호출은
Blocked다.

### 6.3 Guidance DTO

채택 방향:

```text
data.inquiry_state_version  # 문의 동시성
data.guidance.guidance_version  # Guidance 버전, integer
data.allowed_actions[]  # 현재 Inquiry 기준 객체 배열
```

Guidance 자체에는 `state_version`을 추가하지 않는다.

확정 Enum:

```text
risk_level = general | caution | danger
usage_guidance_status =
  NORMAL | PARTIAL_STOP | TOTAL_STOP | PENDING_CONSULTATION
```

미확정 코드:

```text
review_status_code
evidence_sufficiency_code
action_type_code
```

세 코드는 Backend 코드표 승인 전 Mobile에서 확정 Enum으로 고정하지 않고
opaque string 또는 Mock 전용 값으로 처리한다. 알 수 없는 값을 일반·정상
상태로 바꾸지 말고 안전 오류·상담 Fallback으로 보낸다.

Guidance 조회 Runtime은 없다.

### 6.4 상담 요청

채택 방향:

- `state_version`: Inquiry 기대 version 필수
- `reason`: 선택 nullable, 제공 시 trim 후 저장
- 같은 Key+같은 Payload: 저장된 응답 Idempotent Replay
- 같은 Key+다른 Payload: `409 DUPLICATE-EVENT-01`
- 다른 Key지만 활성 상담 존재: 새 상담을 만들지 않고 기존 상담 UPSERT·확인 기록
- stale version: `409 STATE-CONFLICT-01`
- 응답: `inquiry_state_version`과 `consultation.state_version`을 분리

활성 상담을 DB에서 하나로 보장하는 제약, `reason` 저장 위치와 API Service가
아직 없으므로 위 내용은 구현 전 계약 방향이다.

### 6.5 문의 상세·Timeline

최종 Response 컨테이너에는 원문 요청 항목을 모두 포함한다.

```text
문의 기본 정보
status_code
state_version
guidances[]
consultations[]
visits[]
timeline[]
allowed_actions[]
```

Timeline 최소 공개 필드:

```text
target_type
target_id
event
previous_state
next_state
state_version
changed_by
changed_at
reason
correlation_id
```

- 내부 정수 PK와 `idempotency_key`를 상세 응답에 노출하지 않는다.
- Timeline은 `changed_at` 오름차순으로 정렬한다.
- Mobile은 Timeline event를 자체 전이 명령으로 사용하지 않는다.
- 저장 Model은 있으나 조회 Repository·Serializer·Route는 없다.

### 6.6 방문 상세 version

방문 상세에는 다음 두 값을 명시적으로 모두 제공한다.

```text
inquiry_state_version
visit_state_version
```

방문 결과 쓰기는 두 version을 같은 transaction에서 검사해야 한다.
현재 Workflow Snapshot·Guard가 Visit version을 함께 검사하지 않으므로
Backend 보완 전 결과 등록은 Blocked다.

### 6.7 방문 결과 등록 분기

State 계약에는 다음 두 행동이 별도로 존재한다.

```text
VISIT_COMPLETED / completeVisit
  Visit -> COMPLETED
  Inquiry -> COMPLETION_PENDING

REVISIT_NEEDED / requestRevisit
  Visit -> FOLLOW_UP_REQUIRED
  Inquiry -> REVISIT_REQUIRED
```

따라서 행동·권한·Guard를 명확히 하기 위해 정상 완료와 재방문 요청을
행동별 Endpoint로 분리하는 안을 채택한다.

HTTP Path 예시는 최종 OpenAPI 작업에서 확정한다.

```text
POST /api/v1/technician/visits/{visit_id}/complete
POST /api/v1/technician/visits/{visit_id}/request-revisit
```

두 Endpoint 모두 저장은 하나의 `VisitResult` 원장을 사용할 수 있다.
현재 Path·Request Schema·Service는 미구현이므로 Mobile은 호출하지 않는다.

---

## 7. Mobile 상태·Enum 전달사항

현재 Mobile `InquiryState`에는 서버 계약에 없는 `ERROR_CONFIRMED`가 있고,
다음 서버 상태가 누락돼 있다.

```text
AI_GUIDANCE
CONSULTATION_REQUIRED
CONSULTATION_IN_PROGRESS
VISIT_SCHEDULING
REVISIT_REQUIRED
REOPENED
```

서버 Inquiry 상태:

```text
DRAFT
QUESTIONNAIRE_IN_PROGRESS
AI_GUIDANCE
CONSULTATION_REQUIRED
CONSULTATION_IN_PROGRESS
VISIT_REVIEW_PENDING
VISIT_SCHEDULING
VISIT_SCHEDULED
COMPLETION_PENDING
REVISIT_REQUIRED
REOPENED
RESOLVED
CANCELLED
```

작업 지침:

- 기존 Mobile `InquiryStateMachine`은 호환성 보존 대상으로 유지하며 삭제·대규모 재작성하지 않는다.
- 실제 API 화면의 상태와 버튼 판단에는 사용하지 않는다.
- 서버 `status_code`, `state_version`, `allowed_actions`를 최종 기준으로 한다.
- 미지원 Enum은 Mobile 내부 `UNKNOWN(rawCode)` 또는 안전 오류로 처리한다.
- `UNKNOWN`을 서버 Request로 전송하지 않는다.
- Mobile이 다음 상태·event code를 계산해 전송하지 않는다.

Visit 업무 상태와 위치·이동 표시 상태도 분리한다.

```text
서버 Visit 상태:
ASSIGNING | SCHEDULING | CONFIRMED | IN_PROGRESS |
COMPLETED | FOLLOW_UP_REQUIRED | CANCELLED

위치·이동 표시 상태 예:
EN_ROUTE | NEARBY | ARRIVED
```

후자는 이번 API 계약 변경 범위가 아니다.

---

## 8. Mobile 작업 순서

### 8.1 즉시 착수 가능

- [ ] 3모듈·패키지·Navigation과 기존 ServiceCall/Tracking 코드 보존
- [ ] WaterBridge 업무 API용 별도 Client·Repository 경계 생성
- [ ] `ApiResponse<T>`, `ApiError`, `Metadata` DTO 작성
- [ ] `metadata.correlation_id` 보존과 안전한 로그 처리
- [ ] Bearer Token Header와 401 Refresh 1회 처리
- [ ] `Idempotency-Key` 생성·동일 요청 재전송 정책 적용
- [ ] `state_version` 저장과 409 입력 보존 처리
- [ ] 성공용 객체형 `allowed_actions` DTO와 409용 code-only 오류 DTO 분리
- [ ] 서버 Enum 안전 Parsing과 `UNKNOWN` 처리
- [ ] Runtime·미게시 구현 후보·Mock/Blocked Repository 구분
- [ ] 로컬 설정으로 주입한 합성 구독 UUID로 문의 생성 Smoke
- [ ] DRAFT 문의 취소 Smoke

### 8.2 기준선 공유 후 착수

- [ ] `POST /inquiries/{id}/submit`의 팀 기준선 반영과 독립 검토 완료 후 실제 연결
- [ ] 응답 `QUESTIONNAIRE_IN_PROGRESS`, version 증가, Replay, 409 검증

### 8.3 Backend Runtime 제공 후 착수

- [ ] 본인 ACTIVE 구독 목록 실제 조회
- [ ] 추가 질문 조회·답변 제출
- [ ] Guidance·Evidence 조회
- [ ] 상담 요청
- [ ] 문의 상세·Timeline
- [ ] 기사 방문 목록·상세
- [ ] 정상 방문 완료·재방문 요청

### 8.4 완료 처리 금지

- [ ] 존재하지 않는 Path를 임시 Runtime으로 호출
- [ ] 설계 DTO를 확정 DTO로 선반영
- [ ] 로컬 State Machine으로 서버 다음 상태 계산
- [ ] stale version 409를 자동 무한 재시도
- [ ] `allowed_actions`에 없는 버튼 표시
- [ ] 실제 Token·개인정보·운영 URL·환경별 UUID를 Git 추적 파일에 저장
- [ ] 고객 App과 기사 App 상호 의존
- [ ] 지도·GPS·Tracking 코드를 업무 API에 혼합하거나 삭제
- [ ] Mobile 담당자가 `contracts/**` 또는 `backend/**`를 직접 수정

---

## 9. 공통 오류 처리

| HTTP | Code | Mobile 처리 |
|---:|---|---|
| 400 | `INVALID_REQUEST` | 요청 구성 점검 |
| 401 | `AUTH_REQUIRED` | Refresh 1회 후 실패 시 로그인 |
| 403 | `FORBIDDEN` | 역할·권한 오류 |
| 404 | `RESOURCE_NOT_FOUND` | 대상 존재를 추정하지 않고 목록 복귀 |
| 409 | `STATE-CONFLICT-01` | 입력 보존, 최신 상태·version·행동 반영 |
| 409 | `DUPLICATE-EVENT-01` | 같은 Key의 다른 Payload 중단 |
| 422 | `VALIDATION_ERROR` | 필드 오류 표시 |
| 500 | `INTERNAL_ERROR` | correlation ID와 안전 오류 안내 |
| 503 | `AI-FAILED-01` | 재시도 또는 상담 Fallback |
| 503 | `SEARCH-FAILED-01` | 행동 임의 생성 금지, 상담 Fallback |
| 504 | `AI-TIMEOUT-01` | 입력 보존, 재시도·상담 Fallback |

409 처리 순서:

1. 사용자가 입력한 내용을 유지한다.
2. 응답의 `current_status`와 `current_state_version`을 반영한다.
3. 완전한 객체형 행동이 아니면 mutation 버튼을 비활성화한다.
4. 지원되는 상세 조회가 있을 때만 최신 상세를 다시 조회한다.
5. 새 사용자 동작에는 새 `Idempotency-Key`를 사용한다.

---

## 10. 검증 결과와 Mobile 검토 반환

### 10.1 Backend 현재 검증

2026-08-01 기준 기능 후보에서 실행:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\manage.py check --settings=config.settings.test
.\backend\.venv\Scripts\python.exe -m pytest `
  backend/tests/api/test_t022_submit_symptom.py `
  backend/tests/unit/inquiries/test_t022_submit_symptom_serializer.py `
  backend/tests/api/test_openapi_inquiry_contract.py `
  backend/tests/api/test_openapi_runtime_coverage.py `
  backend/tests/api/test_runtime_examples_contract.py `
  backend/tests/unit/inquiries/test_t022_readiness.py `
  -q -p no:cacheprovider
```

결과:

```text
Django System Check: no issues
77 passed, 2 skipped
PostgreSQL concurrency: 2 passed
```

두 Skip은 PostgreSQL row-lock 전용 검증이다. 위 결과는 미게시 구현 후보를
포함한 집중 검증이며, 미구현 후속 API의 완료 증거가 아니다.

### 10.2 Mobile 권장 검증

```powershell
Set-Location .\mobile
.\setup-local-properties.bat
.\bootstrap-wrapper.bat

java -version
.\gradlew.bat projects
.\gradlew.bat test
.\gradlew.bat lintDebug
.\gradlew.bat :customer-app:assembleDebug
.\gradlew.bat :technician-app:assembleDebug
```

`verify-build.bat`은 `core:build`와 두 App Assemble 확인용이며 Unit·Lint
증거를 대신하지 않는다.

### 10.3 Mobile 검토 반환 형식

```text
[Mobile API 연동 검토 결과]
consumer_role=MOBILE
runtime_baseline=TEAM_BASELINE | LOCAL_CANDIDATE
verification_status=PASS | FAIL | BLOCKED
jdk_gradle_sdk=<버전>
unit_lint_build=<명령 / Exit code / 결과>
emulator=<기종 / Android 버전>
runtime_connected_endpoints=<목록>
local_candidate_endpoints=<목록>
mock_blocked_endpoints=<목록>
runtime_api_smoke=<역할 / Method / Path / HTTP / correlation_id>
subscription_source=LOCAL_CONFIG | SUBSCRIPTION_API
dto_contract_diff=<목록>
state_enum_diff=<목록>
allowed_actions_shape=OBJECT | CODE_ONLY | MIXED
backend_change_request=<없음 또는 경로·필드·현재값·기대값·재현 절차>
remaining_blocker=<없음 또는 상세>
```

---

## 11. 기준 파일

- `backend/config/api_urls.py`
- `backend/apps/accounts/services/account_service.py`
- `backend/apps/inquiries/api/urls.py`
- `backend/apps/inquiries/api/serializers/**`
- `backend/apps/inquiries/services/**`
- `backend/apps/subscriptions/models/subscription.py`
- `backend/apps/subscriptions/management/commands/seed_demo_subscriptions.py`
- `contracts/api/openapi.yaml`
- `contracts/api/components/schemas/workflow/WorkflowConflictDetails.yaml`
- `contracts/state-machine/allowed-actions.yaml`
- `contracts/state-machine/inquiry-states.yaml`
- `contracts/state-machine/inquiry-events.yaml`
- `contracts/state-machine/transition-rules.yaml`
- `docs/api/waterbridge_api_specification.md`
- `docs/individual/jiyong/API/Django_REST_API_구독_제품조회_계약_제안서.md`
- `mobile/customer-app/build.gradle.kts`
- `mobile/customer-app/src/main/java/com/skn29/watercare/data/dispatch/ServiceCallApi.kt`
- `mobile/technician-app/src/main/java/com/skn29/watercare/technician/data/dispatch/ServiceCallApi.kt`
- `mobile/core/src/main/kotlin/com/skn29/watercare/model/Models.kt`
- `mobile/core/src/main/kotlin/com/skn29/watercare/domain/InquiryStateMachine.kt`
