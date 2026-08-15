# 5주차 모바일 API 런타임 대응표

기준일: 2026-08-12 KST
백엔드 기준: `origin/main@41ef3d4f7a6699821c6d65398438071a06d23c92`

| 영역 | 백엔드 런타임 | 모바일 상태 |
| --- | --- | --- |
| 고객 데모 로그인 / `/me` | READY | INTEGRATED |
| 방문기사 데모 로그인 / `/me` | READY | INTEGRATED |
| 구독 목록 | READY | INTEGRATED |
| 구독 상세 | READY | INTEGRATED |
| 문의 생성 | READY | INTEGRATED |
| 증상 제출 | READY | INTEGRATED |
| 문의 취소 | READY | INTEGRATED |
| 고객 문의 Snapshot | READY | INTEGRATED |
| 고객 미답변 Questions | READY | INTEGRATED |
| 고객 Follow-up Answers | READY | INTEGRATED |
| 공식 모바일 Follow-up Fixture | READY | CONSUMED_BY_DEVICE_SMOKE |
| 백엔드 실제 Socket 3API Smoke | AUTHOR_VERIFIED | PASS |
| 모바일 실단말 3API 원격 Smoke | READY / REAL_DEVICE | PASS (SM-F721N, skipped=0) |
| 안내 / 근거 | CUSTOMER_ROUTE_NOT_PUBLISHED | MOBILE_FAIL_CLOSED / BLOCKED_BY_BACKEND |
| 고객 상담 요청 | CUSTOMER_ROUTE_NOT_PUBLISHED | BLOCKED_BY_BACKEND |
| 상담사 상담 업무 흐름 | READY / CONSULTANT_ONLY | NOT_CUSTOMER_MOBILE_API |
| 상담사 Visit 검토/생성/일정/확정 | READY / CONSULTANT_ONLY | NOT_TECHNICIAN_API |
| 방문기사 Visit 목록/상세 | NOT_ROUTED | MOBILE_FAIL_CLOSED / BLOCKED_BY_BACKEND |
| 방문기사 Visit 시작/완료/결과 | NOT_ROUTED | BLOCKED_BY_BACKEND |

## 고객 문의 3개 API

```text
GET  /api/v1/me/inquiries/{inquiry_id}
GET  /api/v1/me/inquiries/{inquiry_id}/questions
POST /api/v1/inquiries/{inquiry_id}/answers
```

모바일 어댑터:

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

## 공식 Fixture

백엔드 `main`에는 다음 공식 명령이 존재한다.

```text
python manage.py seed_demo_accounts
python manage.py seed_demo_mobile_followup --json
```

고정 제품 코드:

```text
WPUJAC104DWH
```

Fixture Public UUID는 모바일 제품 코드에 상수로 넣지 않는다. 실제 앱은 로그인 후
`/api/v1/me/subscriptions`, Snapshot, Questions 응답을 소비한다.

## 원격 / Fake 경계

```text
REMOTE_FAILURE != FAKE_SUCCESS
OFFLINE_PREVIEW != REMOTE_COMPLETE
BACKEND_STATE_VERSION = SOURCE_OF_TRUTH
BACKEND_ALLOWED_ACTIONS = SOURCE_OF_TRUTH
```

고객 `REMOTE`에서는 실제 Subscription / Inquiry Runtime을 사용한다.
`FAKE` 또는 오프라인 미리보기에서만 합성 Guidance를 사용한다.

## 현재 차단 항목

```text
CUSTOMER_GUIDANCE_EVIDENCE = BLOCKED_BY_BACKEND
CUSTOMER_REQUEST_CONSULTATION = BLOCKED_BY_BACKEND
TECHNICIAN_VISIT_LIST_DETAIL = BLOCKED_BY_BACKEND
TECHNICIAN_VISIT_START_COMPLETE_RESULT = BLOCKED_BY_BACKEND
FULL_CUSTOMER_AI_CONSULTATION_VISIT_TECHNICIAN_E2E = BLOCKED_PREREQUISITES
```

현재 게시된 Consultation / Visit 쓰기 Runtime은 `CONSULTANT` 역할 전용이므로
고객 또는 방문기사 모바일 API로 오사용하지 않는다.
