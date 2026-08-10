# Week 5 Mobile Regression

## Build / Unit / APK

- `verify-build.bat`: **PASS**
- Core tests: **PASS**
- Customer unit tests: **PASS**
- Technician unit tests: **PASS**
- Customer Debug APK: **PASS**
- Technician Debug APK: **PASS**
- Customer androidTest APK: **PASS**
- Device install: **PASS**

## Real Backend / Galaxy

Device:

```text
Samsung SM-F721N
Android 16
```

Customer:

- Synthetic customer login: **PASS**
- `/me` CUSTOMER: **PASS**
- ACTIVE `WPUJAC104DWH` subscription found: **PASS**
- Subscription detail: **PASS**
- Inquiry create: **PASS**
- Symptom submit: **PASS**
- P0 Backend REST smoke: **PASS**
- Customer Galaxy Remote instrumentation: **PASS**
- REMOTE Guidance unavailable fail-closed: **PASS**
- Customer instrumentation final run: `OK (2 tests)`

Technician:

- Demo technician login: **PASS**
- `/me` TECHNICIAN: **PASS**
- Technician Galaxy auth instrumentation: **PASS**
- Visit REMOTE list/detail Unit fail-closed: **PASS**
- Visit Runtime actual list/detail/result: **NOT_RUN / BACKEND_ROUTE_PENDING**

## Contract / error gates

- Guidance Fixture silently mixed into REMOTE: **NO**
- Technician Visit Fixture silently mixed into REMOTE: **NO**
- Hard-coded personal Backend address committed: **NO**
- Tokens/secrets committed: **NO**

The following full actual-Runtime regressions are **not claimed as PASS** because the
required downstream Runtime is not yet published or a dedicated final proof was not
captured in Week5 closeout:

- 401 refresh end-to-end regression
- Customer inquiry read/recovery 404 regression
- Guidance/Follow-up 409 state-version regression
- Technician Visit 409 dual-version regression
- downstream idempotency replay regression

## Final status

```text
Customer P0 actual flow: PASS
Guidance Mobile safety boundary: PASS
Technician Visit Mobile safety boundary: PASS
Full Customer → AI → Consultation → Visit E2E: BLOCKED_BY_BACKEND
```
