# Week 3 API and AI Field Map

## CUST-01 Customer home

| UI field | Mobile/API source |
| --- | --- |
| Customer identity | authenticated demo user |
| Product/model summary | approved customer home repository response |
| Subscription/management type | subscription or product summary |
| Active inquiry code | display-only inquiry code |
| Active inquiry identifier | public inquiry UUID |
| Available actions | approved route plus backend workflow state |

## CUST-02 Symptom intake

| UI input | Request/model field |
| --- | --- |
| Entry type | `entryMode` |
| Multiple symptoms | symptom selections/topic codes |
| Customer original text | `rawText` |
| Occurrence condition | `occurrenceCondition` |
| Display or error text | `displayText` |
| Duplicate submission prevention | submitting state and request guard |
| Conflict recovery | current state, state version, and allowed actions |

## CUST-04 Guidance

| UI section | Response/display field |
| --- | --- |
| Risk | `riskLevel` |
| Usage state | `usageStatus` |
| Usage explanation | `usageMessage` |
| Restricted functions | `restrictedFunctions` |
| Safe actions | `safeActions` |
| Escalation conditions | `escalationConditions` |
| Prohibited actions | `prohibitedActions` |
| Next action | `nextAction` |
| Consultation requirement | `requiresConsultation` |
| Official evidence | approved public evidence metadata |
| Workflow buttons | `allowedActions` plus danger/no-evidence safety filtering |

## Non-public fields

- Internal integer primary keys
- JWT access/refresh tokens
- `chunk_id`
- source storage paths
- retrieval scores and raw retrieval text
- internal document URLs