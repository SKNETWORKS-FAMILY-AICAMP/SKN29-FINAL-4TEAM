# Week 3 Mobile Decisions

- Branch: `jeonghyun`
- Base branch: `main`

## Structure

- The approved Android structure consists of `customer-app`, `technician-app`, and `core`.
- Shared networking, API models, repositories, session management, and common resources are owned by `core`.
- The customer and technician applications retain independent entry points, themes, and navigation flows.

## UI and state

- Kotlin, Jetpack Compose, Material 3, Navigation Compose, ViewModel, Coroutines, and StateFlow are used.
- Loading, success, empty, error, retry, and submitting states remain explicit.
- Risk is communicated with text and status labels, not color alone.
- Duplicate submissions are prevented while a request is in progress.

## Backend connection

- Physical-device base URL: `http://127.0.0.1:8000/`
- USB forwarding: `adb reverse tcp:8000 tcp:8000`
- PostgreSQL, Django migrations, demo accounts, demo product, demo subscription, and demo care records were prepared successfully.
- `/health`, customer demo login, and technician demo login returned successful HTTP responses.

## Safety

- Unknown error codes are not treated as confirmed diagnoses.
- Danger, consultation-required, and no-evidence states must not expose a resolved or close action.
- Customer UI excludes internal RAG paths, retrieval text, internal database identifiers, JWT values, and private document locations.

## Verification

- Customer unit tests passed.
- Customer connected Compose UI tests passed on `SM_F721N`.
- Customer and technician Debug APK builds passed.
- Verification passed again after rebasing onto the latest `origin/main`.