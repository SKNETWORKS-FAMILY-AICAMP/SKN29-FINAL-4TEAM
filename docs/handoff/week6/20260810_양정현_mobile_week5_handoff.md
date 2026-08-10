# 2026-08-10 양정현 Mobile Week5 → Week6 Handoff

## Fixed baseline
- Customer actual subscription list/detail/select Remote
- P0 Demo UUID manual dependency removed
- Inquiry create/submit and idempotency/conflict handling retained
- Technician auth actual Backend
- Technician visit Remote fails closed until Visit Runtime
- Explicit offline Fixture preserved for presentation only
- Customer + Technician Android UI test gates
- Debug APK hashes recorded

## Remaining Backend dependencies
- Customer-authorized inquiry read/recovery
- Follow-up/questionnaire Runtime
- Guidance/Evidence Runtime
- Consultation request Runtime
- Technician Visit list/detail/action/result Runtime

## Release rule
Do not declare Mobile Feature Complete while a required P0 Runtime above remains absent.