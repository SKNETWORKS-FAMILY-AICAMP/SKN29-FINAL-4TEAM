# Week 5 Mobile Blockers

1. Customer inquiry latest/detail read
   - Status: BLOCKED_BY_BACKEND
   - Current GET inquiry detail route is consultant-role projection, not customer recovery.
   - Needed for authoritative 409 refresh when conflict payload is insufficient.

2. Follow-up / questionnaire
   - Status: BLOCKED_BY_BACKEND
   - Mobile does not invent question IDs, wording, options, or submit route.

3. Guidance / Evidence
   - Status: BLOCKED_BY_BACKEND
   - Mobile does not call AI/LLM/VectorDB directly.

4. Consultation request
   - Status: BLOCKED_BY_BACKEND
   - UI remains unavailable rather than fake-success.

5. Technician visits
   - Status: BLOCKED_BY_BACKEND
   - Actual technician login is kept.
   - Remote visit repository fails closed.
   - Synthetic Visit data appears only after explicit offline preview.

6. Latest-main Backend local smoke
   - Status: BLOCKED_BY_MIGRATION
   - Reason: latest main migrate --check failed; no migration applied
   - No migration was auto-applied.
   - No DB volume was deleted.