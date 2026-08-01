# WaterCare Android — Week 3 complete mobile baseline

Kotlin, Jetpack Compose, Material 3, Navigation Compose, ViewModel, StateFlow, Kotlinx Serialization, Retrofit and OkHttp are used across three modules.

## Modules

- `core`: actual Backend auth/health/inquiry networking, token refresh, common models, error mapping, fake customer-care fixture, theme and shared base UI.
- `customer-app`: CUST-01 customer home → CUST-02 symptom intake → CUST-04 AI safety guidance.
- `technician-app`: actual technician Demo authentication and explicit placeholders for APIs not routed yet.

The fake implementation is deliberately named `FakeCustomerCareRepository`. It is the replacement point for questionnaire and guidance APIs and never contains real personal information.

## Implemented Week 3 customer flow

1. Actual `GET /health` status check.
2. Actual `POST /api/v1/auth/demo-login` with `DEMO-CUSTOMER-001`.
3. CUST-01 product card for synthetic `WPUJAC104DWH` / `WPU-JAC104D`, management type, questionnaire state and active inquiry.
4. CUST-02 multiple symptom selection, raw text, occurrence condition, display/error text, entry mode, validation, duplicate-submit blocking and input retention after failure.
5. 409 conflict snapshots preserve the CUST-02 draft and display latest status, `state_version` and `allowed_actions`.
6. `+09:00` API timestamps are formatted without duplicate timezone conversion.
7. CUST-04 ordered safety display: current action → risk/usage restriction → safe actions → escalation → evidence → symptom summary → prohibited actions.
8. Normal, caution, danger, no-evidence, AI-failure and network-failure deterministic scenarios.
9. Danger/no-evidence/consultation-required states suppress resolved and close actions.
10. Evidence UI includes only document name, version, page, structured summary, verification status, classification and Backend-provided official URL. It has no `chunk_id`, source path, retrieval text or full source text fields.

## Backend preparation

From the repository root:

```cmd
START_WEEK3_BACKEND.cmd
```

The command checks Docker, starts PostgreSQL, applies migrations, runs `seed_week3_demo`, and starts Django at `127.0.0.1:8000`. The `.env` file is never included in source archives.

Manual equivalent:

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
```

```cmd
"C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000
"C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe" reverse --list
```

Android emulator:

```properties
BACKEND_BASE_URL=http://10.0.2.2:8000/
```

## Build and tests

```cmd
cd /d C:\skn29\WaterCare\mobile

gradlew.bat clean
gradlew.bat :core:testDebugUnitTest
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

Questionnaire, guidance, product/subscription lookup, consultation and visit routes are not currently included in `backend/config/api_urls.py`. They remain Fake or explicit “API 준비 중” functions rather than invented production endpoints.
