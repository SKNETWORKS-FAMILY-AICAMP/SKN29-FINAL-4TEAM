# Week 5 Mobile Blockers

## Closed

- Backend migration gate: **CLOSED**
- Canonical synthetic fixture gate: **CLOSED**
- Customer P0 mobile vertical slice: **CLOSED / REAL_DEVICE_PASS**
- REMOTE Guidance Fixture automatic fallback: **CLOSED / FAIL_CLOSED**
- Offline/FAKE Guidance preview isolation: **CLOSED**
- REMOTE Technician Visit Fixture boundary: **CLOSED / FAIL_CLOSED**
- Offline Technician Visit Fixture isolation: **CLOSED**

## Contract ready / Runtime pending

1. Guidance / Evidence
   - Status: **CONTRACT_READY / MOBILE_FAIL_CLOSED / BACKEND_ROUTE_PENDING**
   - Contract: `docs/handoff/week6/20260810_양정현_mobile_guidance_followup_contract.md`
   - Customer Runtime route/serializer not registered.

2. Follow-up
   - Status: **CONTRACT_READY / BACKEND_ROUTE_PENDING**
   - Customer GET/respond Runtime route not registered.

3. Technician Visit
   - Status: **CONTRACT_READY / MOBILE_FAIL_CLOSED / BACKEND_ROUTE_PENDING**
   - Contract: `docs/handoff/week6/20260810_양정현_mobile_technician_visit_contract.md`
   - Actual Technician auth is READY.
   - REMOTE visit list/detail fail closed with `VISIT_RUNTIME_UNAVAILABLE`.
   - Offline Preview alone uses synthetic Visit Fixture.
   - visits Runtime route not registered.

## Remaining Backend Runtime blockers

4. Customer inquiry latest/detail read
   - Status: **BLOCKED_BY_BACKEND**
   - Current detail route is consultant projection.

5. Consultation request
   - Status: **BLOCKED_BY_BACKEND**
   - Customer Runtime route not registered.
