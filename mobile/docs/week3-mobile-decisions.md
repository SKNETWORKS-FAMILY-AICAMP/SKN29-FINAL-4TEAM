# Week 3 Mobile Decisions

- Final local verification: 2026-07-31 15:56:02 +09:00
- Local branch: jeonghyun
- GitHub connection/push: intentionally not performed

## Approved structure

- customer-app, 	echnician-app, and core three-module structure is retained.
- Customer and technician apps share common models, networking, repositories, and design components through core.
- The older single-app-module wording is treated as superseded by the current approved three-module structure.

## UI and UX

- Customer app: sky-blue primary visual language.
- Technician app: orange operational accent.
- Supplied customer and technician mascot assets are restored in the app and launcher icons.
- Material 3 rounded cards, large actions, plain-language labels, loading, error, and unavailable states are used.
- Risk states are communicated with labels and messages in addition to color.

## Data and API

- The mobile app uses the existing Backend contract and Demo login first.
- Missing production endpoints remain explicit Mock or unavailable states.
- The mobile app does not invent production endpoints or modify Backend source.
- Physical-device local development uses 127.0.0.1:8000 with db reverse tcp:8000 tcp:8000.

## Safety

- Unknown codes do not become confirmed failures.
- Danger, consultation-required, and no-evidence states hide resolved/close actions.
- Evidence UI excludes internal chunk_id, source paths, retrieval text, and internal storage URLs.