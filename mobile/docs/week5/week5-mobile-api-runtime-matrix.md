# Week 5 Mobile API Runtime Matrix

| Area | Runtime | Mobile state |
| --- | --- | --- |
| Synthetic customer login (SYN-CUSTOMER-001) | READY | INTEGRATED + REAL_DEVICE_PASS |
| Demo technician login / me | READY | INTEGRATED + REAL_DEVICE_PASS |
| Subscription list | READY | INTEGRATED + REAL_DEVICE_PASS |
| Subscription detail | READY | INTEGRATED + REAL_DEVICE_PASS |
| Inquiry create | READY | INTEGRATED + REAL_DEVICE_PASS |
| Symptom submit | READY | INTEGRATED + REAL_DEVICE_PASS |
| Customer inquiry latest/detail | Consultant-only route | BLOCKED_BY_BACKEND |
| Follow-up | NOT_ROUTED | BLOCKED_BY_BACKEND |
| Guidance / Evidence | NOT_ROUTED | BLOCKED_BY_BACKEND |
| Consultation request | NOT_ROUTED | BLOCKED_BY_BACKEND |
| Technician Visit | NOT_ROUTED | BLOCKED_BY_BACKEND |

Latest main included: 2198e9e90fe894fb848d551ef638fb3ae0a2b433
Canonical fixture: db-full 367-row import PASS.
Local migration gate: PASS.