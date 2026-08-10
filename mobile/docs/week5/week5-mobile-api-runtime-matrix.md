# Week 5 Mobile API Runtime Matrix

| Area | Backend Runtime | Mobile state |
| --- | --- | --- |
| Synthetic customer login (`SYN-CUSTOMER-001`) | READY | INTEGRATED / REAL_DEVICE_PASS |
| Demo technician login / `/me` | READY | INTEGRATED / REAL_DEVICE_PASS |
| Subscription list | READY | INTEGRATED / REAL_DEVICE_PASS |
| Subscription detail | READY | INTEGRATED / REAL_DEVICE_PASS |
| Inquiry create | READY | INTEGRATED / REAL_DEVICE_PASS |
| Symptom submit | READY | INTEGRATED / REAL_DEVICE_PASS |
| Customer inquiry latest/detail | Customer Runtime 미게시 | BLOCKED_BY_BACKEND |
| Follow-up | NOT_ROUTED | CONTRACT_READY / BACKEND_ROUTE_PENDING |
| Guidance / Evidence | NOT_ROUTED | CONTRACT_READY / MOBILE_FAIL_CLOSED / BACKEND_ROUTE_PENDING |
| Consultation request | NOT_ROUTED | BLOCKED_BY_BACKEND |
| Technician Visit list/detail/result | NOT_ROUTED | CONTRACT_READY / MOBILE_FAIL_CLOSED / BACKEND_ROUTE_PENDING |

## Runtime boundary

Customer Guidance:

```text
REMOTE
→ Fixture fallback 금지
→ GUIDANCE_ROUTE_UNAVAILABLE

FAKE / Offline Preview
→ synthetic Fixture 허용
→ 실제 Backend/AI 결과가 아님을 표시
```

Technician Visit:

```text
REMOTE
→ BlockedTechnicianVisitRepository
→ VISIT_RUNTIME_UNAVAILABLE

Offline Preview
→ FakeTechnicianVisitRepository
→ synthetic Fixture 표시
```

## Verified baseline

- Latest main included: `2198e9e90fe894fb848d551ef638fb3ae0a2b433`
- Week5 closeout base: `205aae40111c7a19164bc875a2ca14bdd8d09333`
- Canonical fixture: `db-full` 367-row import PASS
- Local migration gate: PASS
- Customer P0 Galaxy instrumentation: PASS
- Customer Guidance REMOTE fail-closed Galaxy regression: PASS
- Technician Auth Galaxy instrumentation: PASS
