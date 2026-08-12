# Week 5 Mobile API Runtime Matrix

기준일: 2026-08-12 KST
Backend 기준: `origin/main@e146d2349d82c964ca57baa4c77b501f8e84c1ab`

| Area | Backend Runtime | Mobile state |
| --- | --- | --- |
| Customer demo login / `/me` | READY | INTEGRATED |
| Technician demo login / `/me` | READY | INTEGRATED |
| Subscription list | READY | INTEGRATED |
| Subscription detail | READY | INTEGRATED |
| Inquiry create | READY | INTEGRATED |
| Symptom submit | READY | INTEGRATED |
| Inquiry cancel | READY | INTEGRATED |
| Customer inquiry Snapshot | READY | INTEGRATED |
| Customer unanswered Questions | READY | INTEGRATED |
| Customer follow-up Answers | READY | INTEGRATED |
| Official Mobile follow-up Fixture | READY | CONSUMABLE |
| Backend actual-socket 3API smoke | AUTHOR_VERIFIED | PASS |
| Mobile device 3API remote smoke | RUNTIME URL/seed 필요 | NOT_RUN |
| Guidance / Evidence | CUSTOMER_ROUTE_NOT_PUBLISHED | MOBILE_FAIL_CLOSED / BLOCKED_BY_BACKEND |
| Customer consultation request | CUSTOMER_ROUTE_NOT_PUBLISHED | BLOCKED_BY_BACKEND |
| Consultant consultation workflow | READY / CONSULTANT_ONLY | NOT_CUSTOMER_MOBILE_API |
| Consultant Visit review/create/schedule/confirm | READY / CONSULTANT_ONLY | NOT_TECHNICIAN_API |
| Technician Visit list/detail | NOT_ROUTED | MOBILE_FAIL_CLOSED / BLOCKED_BY_BACKEND |
| Technician Visit start/complete/result | NOT_ROUTED | BLOCKED_BY_BACKEND |

## Customer Inquiry 3 API

```text
GET  /api/v1/me/inquiries/{inquiry_id}
GET  /api/v1/me/inquiries/{inquiry_id}/questions
POST /api/v1/inquiries/{inquiry_id}/answers
```

Mobile Adapter:

```text
Snapshot DTO / Domain / Mapper
- status_code
- state_version
- subscription_id
- product.model_code
- allowed_actions
- updated_at RFC3339 원문 보존

Questions DTO / Domain / Mapper
- FREE_TEXT
- SINGLE_CHOICE
- required
- public options only

Answers Request / Response
- state_version
- exactly one of answer_text / answer_payload.selected_option
- Idempotency-Key
- success → Snapshot + Questions 재조회
```

오류 처리:

```text
404 → 타 고객/미존재를 구분하지 않는 동일 화면
409 STATE-CONFLICT-01
    → 작성 입력 유지
    → Snapshot + Questions 재조회
    → 최신 allowed_actions가 SUBMIT_ANSWERS를 허용할 때만 명시적 재시도
409 DUPLICATE-EVENT-01
    → 동일 Key 자동 재시도 금지
422 → 입력 유지 + 사용자 수정
5xx / NETWORK_ERROR → Fake 성공으로 대체하지 않음
```

## Official fixture

Backend `main`에는 다음 공식 명령이 존재한다.

```text
python manage.py seed_demo_accounts
python manage.py seed_demo_mobile_followup --json
```

고정 제품 코드:

```text
WPUJAC104DWH
```

Fixture Public UUID는 Mobile 제품 코드에 상수로 넣지 않는다. 실제 앱은 로그인 후
`/api/v1/me/subscriptions`, Snapshot, Questions 응답을 소비한다.

## Remote / Fake boundary

```text
REMOTE_FAILURE != FAKE_SUCCESS
OFFLINE_PREVIEW != REMOTE_COMPLETE
BACKEND_STATE_VERSION = SOURCE_OF_TRUTH
BACKEND_ALLOWED_ACTIONS = SOURCE_OF_TRUTH
```

Customer `REMOTE`에서는 실제 Subscription / Inquiry Runtime을 사용한다.
`FAKE` 또는 Offline Preview에서만 합성 Guidance를 사용한다.

## Current blockers

```text
CUSTOMER_GUIDANCE_EVIDENCE = BLOCKED_BY_BACKEND
CUSTOMER_REQUEST_CONSULTATION = BLOCKED_BY_BACKEND
TECHNICIAN_VISIT_LIST_DETAIL = BLOCKED_BY_BACKEND
TECHNICIAN_VISIT_START_COMPLETE_RESULT = BLOCKED_BY_BACKEND
FULL_CUSTOMER_AI_CONSULTATION_VISIT_TECHNICIAN_E2E = BLOCKED_PREREQUISITES
```

현재 게시된 Consultation / Visit write Runtime은 `CONSULTANT` 역할 전용이므로
Customer 또는 Technician Mobile API로 오사용하지 않는다.
