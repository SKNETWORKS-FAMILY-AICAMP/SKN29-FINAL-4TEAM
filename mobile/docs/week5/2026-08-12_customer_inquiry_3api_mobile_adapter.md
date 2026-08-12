# 2026-08-12 Customer Inquiry 3 API Mobile Adapter

## 목적

Backend Runtime12에서 공개된 CUSTOMER 전용 문의 조회·추가문진 API를
고객 Android 앱의 실제 Remote 기본 경로에 연결한다.

```text
GET  /api/v1/me/inquiries/{inquiry_id}
GET  /api/v1/me/inquiries/{inquiry_id}/questions
POST /api/v1/inquiries/{inquiry_id}/answers
```

## 구현 범위

- Retrofit Endpoint 3개
- Snapshot DTO / Domain / Mapper
- Snapshot의 최신 `allowed_actions` 소비
- Questions DTO / Domain / Mapper
- `FREE_TEXT`, `SINGLE_CHOICE` 실제 Compose 입력
- Answers Request / Response DTO
- `RemoteCustomerInquiryRepository`
- Follow-up Idempotency Key Store
- Answers 성공 후 Snapshot + Questions 재조회
- 404 동일 오류 처리
- `STATE-CONFLICT-01` 입력 보존·최신 Snapshot 재조회·명시적 재시도
- `DUPLICATE-EVENT-01` 동일 Key 자동 재시도 금지
- 422 입력 유지
- Remote 실패 시 Fake 자동 성공 없음
- `CUSTOMER_CARE_MODE=FAKE`와 Offline Preview에서 Remote 추가문진 호출 금지

## 최신 Backend 계약 반영

Snapshot 공개 필드:

```text
inquiry_id
status_code
state_version
subscription_id
product.model_code
allowed_actions
updated_at
```

Questions 공개 필드:

```text
inquiry_id
state_version
questions[].question_id
questions[].question_type
questions[].prompt
questions[].required
questions[].options[].value
questions[].options[].label
```

Answers 입력:

```text
state_version
answers[]
  question_id
  answer_text
  OR
  answer_payload.selected_option
```

Mobile은 Backend가 제공하지 않은 질문 문구·선택지·상태·Action을 생성하지 않는다.

## 공식 Fixture / Backend actual socket

Backend `main`에는 공식 Mobile follow-up Fixture와 실제 HTTP Socket Smoke가 게시돼 있다.

```text
backend/apps/inquiries/management/commands/seed_demo_mobile_followup.py
backend/tests/integration/test_mobile_followup_live_http_smoke.py
```

Backend 보고 기준 actual-socket smoke는 다음을 검증한다.

```text
Demo Login
Subscription 200
Snapshot 200
Questions 2건 200
FREE_TEXT Answer 200
Same-Key Replay 200
Invalid Choice 422
Stale state_version 409
SINGLE_CHOICE Answer 200
Questions []
Final Snapshot
Other Owner 404
Missing 404
Unknown Query 422
```

외부 AI HTTP 결과는 이 Backend smoke에서 Mock 격리되어 있으므로
실제 Guidance/Evidence 완료로 확대하지 않는다.

## 차단 유지

현재 Backend 공개 Route 감사 결과 다음은 Mobile에서 구현하지 않는다.

- CUSTOMER Guidance / Evidence 공개 Route
- CUSTOMER 상담 요청 Route
- TECHNICIAN 방문 목록 / 상세 Route
- TECHNICIAN 방문 시작 / 완료 / 결과 등록 Route

현재 Consultation과 Visit workflow write Route는 `CONSULTANT` 전용이다.

## 완료 판정

Mobile Unit / Connected / Build / APK 설치가 통과한 Commit에서:

```text
MOBILE_CUSTOMER_INQUIRY_3API_ADAPTER=PASS
BACKEND_OFFICIAL_FIXTURE=AVAILABLE
BACKEND_AUTHOR_ACTUAL_SOCKET=PASS
MOBILE_DEVICE_REMOTE_SMOKE=NOT_RUN_UNTIL_ACCESSIBLE_SEEDED_RUNTIME
FAKE_FALLBACK=DISABLED
```
