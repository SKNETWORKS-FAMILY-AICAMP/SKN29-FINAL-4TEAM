# Week 3 Mobile Final Local Checklist

- Verified: 2026-07-31 15:56:02 +09:00
- Local branch: jeonghyun
- Remote connection/push: intentionally excluded

## 3.1 Android environment and common structure

- [x] Three-module structure: customer-app / technician-app / core
- [x] Material 3 sky-blue and orange design system
- [x] Customer and technician mascot assets
- [x] Customer and technician launcher icons
- [x] Debug builds generated
- [x] Backend URL remains outside screen code

## 3.2 Customer minimum flow

- [x] CUST-01 customer home
- [x] CUST-02 multiple symptom intake
- [x] CUST-04 safety guidance
- [x] Navigation and UI-test contracts
- [x] General, caution, danger, no-evidence, AI-failure, network-failure scenarios

## 3.3 State management and serialization

- [x] ViewModel and UiState-based customer screens
- [x] StateFlow collection
- [x] Duplicate submission protection
- [x] Failure and conflict state display
- [x] Unknown values use safe handling

## 3.4 Backend and Mock integration

- [x] Local Backend health validation or explicitly skipped
- [x] Customer Demo login validation or explicitly skipped
- [x] Technician Demo login validation or explicitly skipped
- [x] Repository/Mock separation retained
- [x] Backend and contract source not modified

## 3.5 AI, risk and evidence

- [x] Risk and usage status
- [x] Safe actions and prohibited actions
- [x] Consultation fallback
- [x] Danger resolved action hidden
- [x] Public Evidence fields only

## 3.6 Test and documentation

- [x] Core and customer tests
- [x] Connected Compose UI tests
- [x] Customer and technician APK builds
- [x] Week 3 decisions document
- [x] API/AI field map
- [x] Test result
- [x] Open issues
- [ ] Git commit and push — intentionally left to the user
- [ ] PR/reviewer confirmation — performed after user push