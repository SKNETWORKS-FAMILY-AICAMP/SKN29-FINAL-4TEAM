# Week 3 Mobile Decisions

- Updated: 2026-08-03 20:32:24 +09:00
- Branch: $branch
- Baseline commit before this change: $headBefore
- Repository root: $root
- Android project root: $mobile

## Structure

- The approved project structure consists of customer-app, 	echnician-app, and core.
- Shared networking, models, repositories, and common UI resources are owned by core.
- The customer and technician applications retain independent entry points and navigation.

## UI and state

- Kotlin, Jetpack Compose, Material 3, Navigation Compose, ViewModel, Coroutines, and StateFlow are used.
- Customer UI uses the customer visual system; technician UI uses the operational technician visual system.
- Loading, success, empty, error, and retry states must remain explicit.
- Risk is communicated using text and status labels, not color alone.

## Backend connection

- Backend base URL for a physical USB-connected Android device is http://127.0.0.1:8000/.
- Local physical-device integration uses db reverse tcp:8000 tcp:8000.
- Existing backend contracts and demo authentication are used.
- Backend, database, migration, Docker, and API contract sources are outside this mobile commit.

## Safety

- Unknown error codes are not treated as confirmed diagnoses.
- Danger, consultation-required, and no-evidence states must not expose a resolved or close action.
- Customer UI excludes internal RAG paths, retrieval text, internal identifiers, and token values.