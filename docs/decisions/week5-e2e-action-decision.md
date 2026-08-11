# 5주차 대표 E2E Action 결정

> 결정일: 2026-08-10 KST  
> 현행화 기준: `main@92b0674cd1a3376a2c058715cd5ef32222125755`
> 상태: **PM_DECISION_APPLIED · CONTRACT_QA_VERIFIED**
> 범위: PM 결정과 계약 적용 완료를 기록하며 각 Action의 Runtime 완료는 Crosswalk와 WBS에서 별도로 판정한다.

## 1. 결정

대표 정상 E2E 14단계의 계약 미정 항목 6개를 P0 Action으로 승인한다. 고객 미해결 후 재상담 2개는 정상 14단계에는 포함하지 않지만, `T-055` 비정상 보조 시나리오용 계약으로 함께 승인한다.

| Event | Operation | 결정 | 정상 14단계 | Runtime 기준 |
|---|---|---|---|---|
| `SUBMIT_ANSWERS` | `submitFollowUpAnswers` | P0 승인 | 포함 | `T-026`·`T-035` 소비 일정과 연결 |
| `REQUEST_CONSULTATION` | `requestConsultation` | P0 승인 | 포함 | `T-036`과 연결 |
| `START_VISIT` | `startVisit` | P0 승인 | 포함 | `T-042`·`T-043`과 연결 |
| `VISIT_COMPLETED` | `completeVisit` | P0 승인 | 포함 | `T-043`·`T-044`와 연결 |
| `SUBMIT_RESOLUTION_FEEDBACK` | `submitResolutionFeedback` | P0 승인 | 포함 | `T-055`와 연결 |
| `FINALIZE_INQUIRY` | `finalizeInquiry` | P0 승인 | 포함 | `T-055`와 연결 |
| `CUSTOMER_REPORTED_UNRESOLVED` | `reportUnresolved` | P0 보조 흐름 승인 | 제외 | `T-055` 비정상 시나리오 |
| `RESUME_CONSULTATION` | `resumeConsultation` | P0 보조 흐름 승인 | 제외 | `T-055` 비정상 시나리오 |

현행 WBS의 구현 날짜는 변경하지 않는다. 아래 HTTP 경계는 `contracts/api/**` 주관 담당자의 적용과 독립 Contract QA를 거쳐 OpenAPI `0.8.0`에 반영됐다.

## 2. 승인된 HTTP 경계

| Operation | Method·Path | Actor·권한 |
|---|---|---|
| `submitFollowUpAnswers` | `POST /inquiries/{id}/answers` | 본인 문의의 `CUSTOMER` |
| `requestConsultation` | `POST /inquiries/{id}/request-consultation` | 본인 문의의 `CUSTOMER` |
| `startVisit` | `POST /visits/{visit_id}/start` | 배정된 `TECHNICIAN` |
| `completeVisit` | `POST /visits/{visit_id}/complete` | 배정된 `TECHNICIAN` |
| `submitResolutionFeedback` | `POST /inquiries/{id}/resolution-feedback` | 본인 문의의 `CUSTOMER` |
| `finalizeInquiry` | `POST /inquiries/{id}/finalize` | 마지막 처리 담당 `CONSULTANT` 또는 `TECHNICIAN` |
| `reportUnresolved` | `POST /inquiries/{id}/report-unresolved` | 본인 문의의 `CUSTOMER` |
| `resumeConsultation` | `POST /inquiries/{id}/resume-consultation` | 상담 대기열을 처리하는 `CONSULTANT` |

모든 외부 쓰기는 `Idempotency-Key`, `X-Correlation-ID`, 기대 `state_version`, 409 충돌 응답 정책을 유지한다. Visit 상태를 변경하는 두 요청은 Inquiry와 Visit Version을 같은 Transaction에서 검사하도록 `visit_state_version`도 받는다.

## 3. Payload·Guard 결정

- 추가 답변은 `answers[]`에 `question_id`와 `answer_text` 또는 `answer_payload`를 받는다. 열린 질문만 허용하고 중복 `question_id`는 거부한다.
- 상담 요청과 방문 시작은 추가 업무 값을 받지 않으며 Version만 받는다.
- 방문 완료는 `result_code`, `work_summary`, offset 포함 `completed_at`을 필수로 받는다. 결과 코드는 기존 `care-results.yaml`의 `NORMAL`, `FILTER_REPLACED`, `ISSUE_RESOLVED`를 단일 원천으로 사용하고 요약은 최대 4000자로 제한한다.
- 해결 피드백은 `resolved=true`, 선택 `comment` 최대 1000자로 제한한다.
- 미해결 보고는 `resolved=false`, 선택 `reason_code`와 `comment`를 받는다.
- 최종 완료는 선택 `final_note`만 허용한다. 최신 해결 피드백이 마지막 처리 완료보다 새로워야 하며 마지막 처리 담당자만 실행한다.
- 고객 해결 피드백만으로 `RESOLVED`가 되지 않는다. `FINALIZE_INQUIRY` 성공 후에만 종료한다.

## 4. State Machine·Version 판정

- State, Event, Transition, Guard, 완료 정책은 변경하지 않는다.
- 이번 PM 결정은 기존 Event에 정확한 OpenAPI Operation을 연결하는 비파괴 추가안이다.
- `contracts/VERSION`과 State Machine `1.0.0`은 유지한다.
- 현재 OpenAPI는 `0.8.0`, 32개 Path·33개 Operation이다.
- 현재 Crosswalk는 `RUNTIME_IMPLEMENTED=12`, `OPENAPI_CONFIRMED=7`, `CONTRACT_ONLY=0`, `DEFERRED=4`다.
- 승인한 8개 중 `SUBMIT_ANSWERS`는 Runtime 구현이 확인됐고, 나머지 7개는 `OPENAPI_CONFIRMED`로 유지한다.
- 계약 적용과 Runtime 완료를 동일시하지 않으며, Runtime 승격은 Source·Test 증거가 모두 있을 때만 허용한다.

## 5. 완료 판정

PM Action 결정, OpenAPI·Crosswalk 적용, Contract QA가 완료돼 3.2는 **완료**다. Runtime 이행 여부와 실제 소비자 검토는 WBS 구현 Task 및 3.3 Contract Baseline Gate에서 별도로 판정한다.
