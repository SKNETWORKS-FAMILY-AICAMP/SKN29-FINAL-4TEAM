# WaterCare Android — 5주차 Mobile Remote 기준선

5주차 Mobile 원칙은 **실제 Backend Runtime이 열린 경로는 Remote로 사용하고, 열리지 않은 경로는 Fake 성공으로 숨기지 않는 것**이다.

## Customer Remote

- `GET /health`
- `POST /api/v1/auth/demo-login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/me`
- `GET /api/v1/me/subscriptions`
- `GET /api/v1/me/subscriptions/{subscription_id}`
- `POST /api/v1/inquiries`
- `POST /api/v1/inquiries/{inquiry_id}/submit`
- `POST /api/v1/inquiries/{inquiry_id}/cancel`

고객 기본 흐름은 실제 구독 목록/상세 → 실제 `subscription_id` 선택 → 문의 생성 → 증상 제출을 사용한다.

`RemoteIntakeCustomerCareRepository`는 `SubscriptionRepository`를 필수 의존성으로 사용한다. Remote 구독 실패를 `FakeCustomerCareRepository` 성공으로 자동 대체하지 않는다.

## Customer Blocked by Backend

- Inquiry 최신 조회 / 상태 복구 Runtime
- Follow-up answers Runtime
- Guidance / Evidence 고객 Runtime
- Request Consultation Runtime

Guidance Runtime이 없는 Remote 모드는 `GUIDANCE_ROUTE_UNAVAILABLE`로 fail-closed한다. AI FastAPI, LLM, Vector DB를 Mobile이 직접 호출하지 않는다.

## Technician

- 실제 Demo 인증과 `/me`: Remote
- 배정 Visit 목록/상세: `BLOCKED_BY_BACKEND`
- Visit 시작/완료/조치 결과: `BLOCKED_BY_BACKEND`

Remote에서는 `BlockedTechnicianVisitRepository`를 사용한다. `FakeTechnicianVisitRepository`는 사용자가 명시적으로 선택한 Offline Preview에서만 사용한다.

## Fake / Fixture 원칙

- Remote API 실패 → Fake 성공 자동 대체 금지
- Offline Preview → 합성 Fixture 허용
- 실제 고객 개인정보 사용 금지
- Backend에 없는 Endpoint, State, Action 생성 금지
- `WAITING_COMPLETION`을 Mobile에서 `COMPLETED`로 변환 금지
- 알 수 없는 Visit 상태는 fail-closed

## 로컬 Backend / 기기 연결

실제 Android 기기:

```properties
BACKEND_BASE_URL=http://127.0.0.1:8000/
CUSTOMER_CARE_MODE=REMOTE
```

```powershell
adb reverse tcp:8000 tcp:8000
```

에뮬레이터는 필요 시 `http://10.0.2.2:8000/`을 `local.properties`에서 사용한다.

`mobile/local.properties`는 Git 추적 대상이 아니다. Token, API Key, Keystore, 실제 비밀값을 저장소에 커밋하지 않는다.

## Build / Test

```powershell
cd mobile
.\verify-build.bat
.\gradlew.bat :customer-app:connectedDebugAndroidTest
.\gradlew.bat :technician-app:connectedDebugAndroidTest
.\gradlew.bat :customer-app:assembleDebugAndroidTest :technician-app:assembleDebugAndroidTest
```

## Week5 문서

- `docs/week5/week5-mobile-api-runtime-matrix.md`
- `docs/week5/week5-mobile-regression.md`
- `docs/week5/week5-mobile-independent-closeout.md`
- `docs/handoff/week6/mobile-week6-handoff.md`

## 현재 판정

```text
INDEPENDENT_MOBILE_WEEK5 = PASS
FULL_P0_FEATURE_COMPLETE = BLOCKED_BY_BACKEND
```

Full Customer → AI → Consultation → Visit → Technician E2E는 필요한 Backend Runtime이 제공된 뒤 실행한다.
