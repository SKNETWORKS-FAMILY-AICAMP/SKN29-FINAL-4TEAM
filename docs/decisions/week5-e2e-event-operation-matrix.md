# 5주차 E2E Event–Operation Matrix

> 기준: State Machine `1.0.0`, 현재 OpenAPI `0.7.0`  
> 신규 8개 HTTP 경계는 PM 승인안이며 API 주관 담당자 적용 대기다.  
> 정상 시나리오: `SYN-JAC104-002` / `DEMO-INQ-002`

| # | Event | Actor | Operation·HTTP | Transition | 핵심 Guard | 계약 상태 |
|---:|---|---|---|---|---|---|
| 1 | `START_INQUIRY` | CUSTOMER | `startInquiry` · `POST /inquiries` | `TR-INQ-001` | 제품 소유권·멱등키 | Runtime 구현 |
| 2 | `SUBMIT_SYMPTOM` | CUSTOMER | `submitSymptom` · `POST /inquiries/{id}/submit` | `TR-INQ-002` | 소유권·Version·증상 Payload | Runtime 구현 |
| 3 | `SUBMIT_ANSWERS` | CUSTOMER | `submitFollowUpAnswers` · `POST /inquiries/{id}/answers` | `TR-INQ-003` | 열린 질문·중복 금지·Version | PM 승인·적용 대기 |
| 4 | `SAFE_GUIDANCE_READY` | SYSTEM | 외부 Operation 없음 | `TR-INQ-008` | 안전 검증·공식 근거·위험 충돌 없음 | 내부 Event |
| 5 | `REQUEST_CONSULTATION` | CUSTOMER | `requestConsultation` · `POST /inquiries/{id}/request-consultation` | `TR-INQ-012` | 소유권·Version·멱등키 | PM 승인·적용 대기 |
| 6 | `START_CONSULTATION` | CONSULTANT | `startConsultation` · `POST /inquiries/{id}/start-consultation` | `TR-INQ-014` | 담당 상담사·Version | OpenAPI 확정 |
| 7 | `VISIT_REVIEW_REQUIRED` | CONSULTANT | `requestVisitReview` · `POST /inquiries/{id}/visit-review` | `TR-INQ-018` | 담당 상담사·검토 Payload | OpenAPI 확정 |
| 8 | `VISIT_NEEDED` | CONSULTANT | `createVisitRequest` · `POST /inquiries/{id}/visits` | `TR-INQ-019` | 방문 인계 완전성 | OpenAPI 확정 |
| 9 | `UPDATE_VISIT_SCHEDULE` | CONSULTANT | `updateVisitSchedule` · `PATCH /visits/{visit_id}/schedule` | `TR-INQ-020/021` | 담당 상담사·일정 Payload | OpenAPI 확정 |
| 10 | `CONFIRM_VISIT` | CONSULTANT | `confirmVisit` · `POST /visits/{visit_id}/confirm` | `TR-INQ-022` | 기사 배정·확정일 | OpenAPI 확정 |
| 11 | `START_VISIT` | TECHNICIAN | `startVisit` · `POST /visits/{visit_id}/start` | `TR-INQ-025` | 담당 기사·Inquiry/Visit Version | PM 승인·적용 대기 |
| 12 | `VISIT_COMPLETED` | TECHNICIAN | `completeVisit` · `POST /visits/{visit_id}/complete` | `TR-INQ-026` | 담당 기사·방문 결과 완전성 | PM 승인·적용 대기 |
| 13 | `SUBMIT_RESOLUTION_FEEDBACK` | CUSTOMER | `submitResolutionFeedback` · `POST /inquiries/{id}/resolution-feedback` | `TR-INQ-029` | 소유권·`resolved=true` | PM 승인·적용 대기 |
| 14 | `FINALIZE_INQUIRY` | 마지막 처리 담당자 | `finalizeInquiry` · `POST /inquiries/{id}/finalize` | `TR-INQ-033` | 최신 해결 피드백·최종 Payload | PM 승인·적용 대기 |

## 비정상 보조 시나리오

| # | Event | Actor | Operation·HTTP | Transition | 핵심 Guard |
|---:|---|---|---|---|---|
| 1 | `CUSTOMER_REPORTED_UNRESOLVED` | CUSTOMER | `reportUnresolved` · `POST /inquiries/{id}/report-unresolved` | `TR-INQ-030` | 소유권·`resolved=false` |
| 2 | `RESUME_CONSULTATION` | CONSULTANT | `resumeConsultation` · `POST /inquiries/{id}/resume-consultation` | `TR-INQ-032` | 상담사·Version·멱등키 |

`SAFE_GUIDANCE_READY`는 AI가 직접 State를 변경하는 API가 아니다. AI 결과를 검증·저장한 Backend가 System Event 적용 여부를 최종 결정한다.

비정상 보조 시나리오의 `reportUnresolved`, `resumeConsultation` HTTP 경계도 동일하게 API 주관 담당자 적용 대기다.
