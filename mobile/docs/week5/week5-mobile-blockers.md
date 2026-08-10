# Week 5 Mobile Blockers

## Closed

- Backend migration gate: **CLOSED**
- Canonical synthetic fixture gate: **CLOSED**
- Customer P0 mobile vertical slice: **CLOSED / REAL_DEVICE_PASS**
- REMOTE Guidance Fixture automatic fallback: **CLOSED / FAIL_CLOSED**
- Offline/FAKE Guidance preview isolation: **CLOSED**

## Contract ready / Runtime pending

1. Guidance / Evidence
   - Status: **CONTRACT_READY / MOBILE_FAIL_CLOSED / BACKEND_ROUTE_PENDING**
   - Contract: `docs/handoff/week6/20260810_양정현_mobile_guidance_followup_contract.md`
   - Backend DB models exist.
   - Customer Runtime route/serializer is not registered.
   - REMOTE does not substitute Fixture Guidance.
   - Mobile does not call AI/LLM/VectorDB directly.

2. Follow-up
   - Status: **CONTRACT_READY / BACKEND_ROUTE_PENDING**
   - FollowupConfirmation DB model exists.
   - Customer GET/respond Runtime route is not registered.

## Remaining Backend Runtime blockers

3. Customer inquiry latest/detail read
   - Status: **BLOCKED_BY_BACKEND**
   - Current detail route is consultant projection.

4. Consultation request
   - Status: **BLOCKED_BY_BACKEND**
   - Customer Runtime route not registered.

5. Technician visits
   - Status: **BLOCKED_BY_BACKEND**
   - Technician auth is real; Visit Runtime is not registered.
