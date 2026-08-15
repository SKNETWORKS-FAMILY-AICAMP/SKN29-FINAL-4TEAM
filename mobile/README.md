# WaterCare Android — 5주차 모바일 원격 연동 기준선

5주차 모바일 원칙은 **실제 백엔드 런타임이 열린 경로는 원격 연동으로 사용하고, 열리지 않은 경로는 가짜 성공으로 숨기지 않는 것**이다.

## 고객 원격 연동

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
- `GET /api/v1/me/inquiries/{inquiry_id}`
- `GET /api/v1/me/inquiries/{inquiry_id}/questions`
- `POST /api/v1/inquiries/{inquiry_id}/answers`

고객 기본 흐름은 실제 구독 목록/상세 → 실제 `subscription_id` 선택 → 문의 생성 → 증상 제출 → 문의 Snapshot/Questions 조회 → Follow-up Answers 제출을 사용한다.

`RemoteIntakeCustomerCareRepository`는 `SubscriptionRepository`를 필수 의존성으로 사용한다. 원격 구독 조회 실패를 `FakeCustomerCareRepository` 성공으로 자동 대체하지 않는다.

## 백엔드 미지원으로 차단된 고객 기능

- 고객용 Guidance / Evidence 런타임
- 상담 요청 런타임

Guidance 런타임이 없는 원격 모드는 `GUIDANCE_ROUTE_UNAVAILABLE`로 fail-closed한다. AI FastAPI, LLM, Vector DB를 모바일이 직접 호출하지 않는다.

## 방문기사 앱

- 실제 데모 인증과 `/me`: 원격 연동
- 배정 Visit 목록/상세: `BLOCKED_BY_BACKEND`
- Visit 시작/완료/조치 결과: `BLOCKED_BY_BACKEND`

원격 모드에서는 `BlockedTechnicianVisitRepository`를 사용한다. `FakeTechnicianVisitRepository`는 사용자가 명시적으로 선택한 오프라인 미리보기에서만 사용한다.

## Fake / Fixture 사용 원칙

- 원격 API 실패 → Fake 성공 자동 대체 금지
- 오프라인 미리보기 → 합성 Fixture 허용
- 실제 고객 개인정보 사용 금지
- 백엔드에 없는 Endpoint, State, Action 생성 금지
- `WAITING_COMPLETION`을 모바일에서 `COMPLETED`로 변환 금지
- 알 수 없는 Visit 상태는 fail-closed

## 로컬 백엔드 / 기기 연결

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

## 빌드 / 테스트

```powershell
cd mobile
.\verify-build.bat
.\gradlew.bat :customer-app:connectedDebugAndroidTest
.\gradlew.bat :technician-app:connectedDebugAndroidTest
.\gradlew.bat :customer-app:assembleDebugAndroidTest :technician-app:assembleDebugAndroidTest
```

## 5주차 문서

- `docs/week5/week5-mobile-api-runtime-matrix.md`
- `docs/week5/week5-mobile-regression.md`
- `docs/week5/week5-mobile-independent-closeout.md`
- `docs/handoff/week6/mobile-week6-handoff.md`

## 현재 판정

```text
INDEPENDENT_MOBILE_WEEK5 = PASS
FULL_P0_FEATURE_COMPLETE = BLOCKED_BY_BACKEND
```

전체 고객 → AI → 상담 → 방문 → 방문기사 E2E는 필요한 백엔드 런타임이 제공된 뒤 실행한다.
