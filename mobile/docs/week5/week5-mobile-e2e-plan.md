# Week 5 Mobile E2E Plan

Scenario: W5-MOBILE-P0-001

1. DEMO-CUSTOMER-001 actual login
2. GET actual active WPUJAC104DWH subscription
3. GET subscription detail
4. Create Inquiry with "출수량이 줄었어요"
5. Submit symptom using returned state_version
6. If Backend exposes follow-up, answer only contract-provided questions
7. If Backend exposes Guidance, show only customer-safe DTO/Evidence
8. If Backend exposes consultation, request through actual API
9. If Backend creates/assigns Visit, DEMO-TECHNICIAN-001 reads same Visit
10. Perform only server-provided allowed actions

Rules:
- No direct DB writes by Mobile.
- No automatic Fake fallback.
- No secret/token evidence.
- Public IDs/state_version/allowed_actions are the only workflow evidence.