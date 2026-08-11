# Week 5 Mobile API Runtime Matrix

| Area | Backend Runtime | Mobile state |
| --- | --- | --- |
| Customer demo login / `/me` | READY | INTEGRATED |
| Technician demo login / `/me` | READY | INTEGRATED |
| Subscription list | READY | INTEGRATED |
| Subscription detail | READY | INTEGRATED |
| Inquiry create | READY | INTEGRATED |
| Symptom submit | READY | INTEGRATED |
| Inquiry cancel | READY | INTEGRATED |
| Customer inquiry latest/detail | 미게시 | BLOCKED_BY_BACKEND |
| Follow-up answers | NOT_ROUTED | BLOCKED_BY_BACKEND |
| Guidance / Evidence | NOT_ROUTED | MOBILE_FAIL_CLOSED / BLOCKED_BY_BACKEND |
| Consultation request | NOT_ROUTED | BLOCKED_BY_BACKEND |
| Technician Visit list/detail | NOT_ROUTED | MOBILE_FAIL_CLOSED / BLOCKED_BY_BACKEND |
| Technician Visit start/complete/result | NOT_ROUTED | BLOCKED_BY_BACKEND |

## Remote / Fake boundary

Customer REMOTE:

```text
RemoteSubscriptionRepository 필수
→ 구독 실패는 ApiResult.Failure 유지
→ FakeCustomerCareRepository 자동 fallback 없음

Guidance Runtime 없음
→ GUIDANCE_ROUTE_UNAVAILABLE
→ Fixture 성공으로 대체하지 않음
```

Technician REMOTE:

```text
BlockedTechnicianVisitRepository
→ VISIT_RUNTIME_UNAVAILABLE

Offline Preview
→ FakeTechnicianVisitRepository
→ synthetic Fixture 표시
```

```text
INDEPENDENT_MOBILE_WEEK5 = PASS
FULL_P0_FEATURE_COMPLETE = BLOCKED_BY_BACKEND
```
