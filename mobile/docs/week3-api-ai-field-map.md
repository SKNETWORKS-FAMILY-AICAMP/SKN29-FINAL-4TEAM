# Week 3 API and AI Field Map

- Final local verification: 2026-07-31 15:56:02 +09:00

## CUST-01

| UI | Source/model |
| --- | --- |
| Customer display name | authenticated Demo user |
| Product and management type | customer home repository or approved Mock |
| Questionnaire status | customer home UiState |
| Active inquiry | public inquiryId plus display inquiryCode |
| Actions | approved routes and supported repository functions |

## CUST-02

| UI input | Request/state |
| --- | --- |
| Inquiry type | entryMode |
| Multiple symptom topics | selectedSymptoms |
| Customer original text | awText |
| Occurrence conditions | occurrenceCondition |
| Display text/error code | displayText |
| Duplicate submission protection | isSubmitting and idempotency handling |
| State conflict | latest state, stateVersion, llowedActions; user input remains |

## CUST-04

| UI section | Response/display |
| --- | --- |
| Risk | iskLevel |
| Usage state | usageStatus |
| Usage message | usageMessage |
| Restricted functions | estrictedFunctions |
| Safe actions | safeActions |
| Escalation conditions | escalationConditions |
| Prohibited actions | prohibitedActions |
| Next action | 
extAction |
| Consultation | equiresConsultation |
| Evidence | document, version, page, structured summary, verification status, classification, approved URL |
| Buttons | llowedActions with danger/no-evidence safety filtering |

## Fields hidden from customer UI

- internal integer PK
- chunk_id
- source_path
- retrieval score and retrieval text
- full source document text
- internal RAG/storage URL
- access and refresh tokens