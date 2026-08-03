# WaterCare Android — Week 4 mobile baseline

Kotlin, Jetpack Compose, Material 3, Navigation Compose, ViewModel, StateFlow, Kotlinx Serialization, Retrofit and OkHttp are used across three modules.

## Modules

- `core`: shared auth/health networking, token refresh, common response/error handling, pure workflow models/mappers, fake customer-care fixture, theme and shared base UI.
- `customer-app`: customer-only WaterCare inquiry Client·Repository·session boundary, CUST-01 home → CUST-02 actual inquiry create/cancel → CUST-04 Mock/Blocked safety guidance.
- `technician-app`: actual technician Demo authentication and explicit placeholders for APIs not routed yet.

The fake implementation is deliberately named `FakeCustomerCareRepository`. It is the replacement point for questionnaire and guidance APIs and never contains real personal information.

## Implemented customer flow

1. Actual `GET /health` status check.
2. Actual `POST /api/v1/auth/demo-login` with `DEMO-CUSTOMER-001`.
3. CUST-01 product card for synthetic `WPUJAC104DWH` / `WPU-JAC104D`, management type, questionnaire state and active inquiry.
4. CUST-02 multiple symptom selection, raw text, occurrence condition and display/error text are converted to the confirmed `POST /api/v1/inquiries` DTO.
5. Inquiry creation stores `inquiry_id`, `inquiry_code`, raw `status_code`, `state_version`, object-shaped `allowed_actions` and `metadata.correlation_id`.
6. Same-payload retries reuse the same `Idempotency-Key`; editing request input creates a new key.
7. Actual `POST /api/v1/inquiries/{id}/cancel` is available only when Backend returns `CANCEL_INQUIRY`.
8. 401·403·404·409·422 are mapped to safe UI errors; 409 preserves the draft and applies the latest status/version/action snapshot.
9. `+09:00` API timestamps are formatted without duplicate timezone conversion.
10. CUST-04 remains an explicit Mock/Blocked safety preview: current action → risk/usage restriction → safe actions → escalation → evidence → symptom summary → prohibited actions.
11. Normal, caution, danger, no-evidence, AI-failure and network-failure deterministic scenarios.
12. Danger/no-evidence/consultation-required states suppress resolved and close actions.
13. Evidence UI includes only document name, version, page, structured summary, verification status, classification and Backend-provided official URL. It has no `chunk_id`, source path, retrieval text or full source text fields.

## Backend preparation

From the repository root, use the verified manual sequence below.
The old Week 3 helper scripts are no longer used.

Manual sequence:

```cmd
cd /d C:\skn29\WaterCare

docker compose --env-file backend\.env -f docker-compose.yml -f docker-compose.local.yml up -d postgres
cd backend
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py seed_week3_demo
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

## Device network configuration

Copy `local.properties.example` to `local.properties` and keep it untracked.

Physical Android device:

```properties
BACKEND_BASE_URL=http://127.0.0.1:8000/
DEMO_SUBSCRIPTION_ID=<DEMO-CUSTOMER-001 활성 구독 Public UUID>
```

`DEMO_SUBSCRIPTION_ID` is local-only because the subscription lookup Runtime endpoint is not available yet. Do not commit `local.properties`.

```cmd
"C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000
"C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe" reverse --list
```

Android emulator:

```properties
BACKEND_BASE_URL=http://10.0.2.2:8000/
DEMO_SUBSCRIPTION_ID=<DEMO-CUSTOMER-001 활성 구독 Public UUID>
```

## Build and tests

```cmd
cd /d C:\skn29\WaterCare\mobile

gradlew.bat clean
gradlew.bat :core:test
gradlew.bat :customer-app:testDebugUnitTest
gradlew.bat :customer-app:assembleDebug
gradlew.bat :technician-app:assembleDebug
```

Connected-device Compose tests:

```cmd
gradlew.bat :customer-app:connectedDebugAndroidTest
```

APK paths:

- `customer-app\build\outputs\apk\debug\customer-app-debug.apk`
- `technician-app\build\outputs\apk\debug\technician-app-debug.apk`

## Actual and fake boundary

Actual Backend routes used by mobile:

- `GET /health`
- `POST /api/v1/auth/demo-login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/me`
- `POST /api/v1/inquiries`
- `POST /api/v1/inquiries/{inquiry_id}/cancel`

Subscription lookup, questionnaire, guidance, consultation, inquiry detail/timeline and visit routes are not currently included in the shared Django Runtime. CUST-03·04·05·06 and technician work screens remain explicit Mock/Blocked functions. The local candidate `POST /api/v1/inquiries/{id}/submit` is not connected until a committed shared SHA is provided. See `docs/runtime-api-update-20260801.md`.
