# Week 3 mobile completion checklist

## Source implementation

- [x] Three-module package structure and executable activities
- [x] CUST-01, CUST-02 and CUST-04 navigation
- [x] CUST-02 validation, input snapshot, duplicate-submit blocking and failure retention
- [x] ViewModel and StateFlow screen state
- [x] Kotlinx Serialization request and response models
- [x] Retrofit, OkHttp, correlation ID, bearer auth and one-time token refresh
- [x] Repository replacement point and explicitly named Fake implementation
- [x] Normal, caution, danger, no-evidence, AI-failure and network-failure scenarios
- [x] Danger/no-evidence resolve and close action suppression
- [x] Evidence UI without internal RAG fields
- [x] 400/401/403/404/409/5xx safe mapping, including 409 latest-state UiState
- [x] `+09:00` display formatting without duplicate timezone addition
- [x] Unit and Compose test sources
- [x] README, decisions, field map, test result and open-issue documents
- [x] Consolidated Backend Demo seed command
- [x] One-command Backend startup and final verification scripts

## Workstation execution evidence

Run `START_WEEK3_BACKEND.cmd` in one window and `FINALIZE_WEEK3.cmd` in another. A successful run creates `mobile/docs/week3-local-verification.txt` and both Debug APKs. Then run `INSTALL_WEEK3_APPS.cmd` for a physical device.

This separation prevents fabricated success claims: source completion is recorded here, while machine-specific Android SDK, Gradle, Docker and device results are recorded by the generated local verification log.
