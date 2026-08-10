# 5주차 대표 E2E Action 결정

> 결정일: 2026-08-10 KST  
> 검토 기준: `main@ed989926b8a4e5fa2ec08593f18f5f5101e84a11`  
> 상태: **PM_DECISION_APPROVED · OWNER_APPLY_PENDING**  
> 범위: PM 결정과 구현 인계이며 OpenAPI·Crosswalk·Test·Runtime 적용 완료 선언이 아니다.

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

현행 WBS의 구현 날짜는 변경하지 않는다. 아래 HTTP 경계는 PM 승인안이며 `contracts/api/**` 주관 담당자인 최지용의 적용·검토 후 기계 계약으로 확정된다.

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
- 현재 OpenAPI `0.7.0`과 Crosswalk 분류는 유지한다.
- 최지용 적용 시 OpenAPI `0.8.0` 후보와 신규 Operation의 `x-runtime-status: NOT_IMPLEMENTED`를 검토한다.
- 김은진·최지용의 Contract/Backend Test 변경은 각 주관 담당자 검토 후 반영한다.

## 5. 완료 판정

PM Action 결정은 완료다. 다만 3.2 전체 산출물 중 갱신된 OpenAPI·Crosswalk·Contract Test는 담당자 적용 대기이므로 3.2 전체 상태는 `OWNER_APPLY_PENDING`이다. Runtime 이행 여부와 소비자 검토는 WBS 구현 Task 및 3.3 Contract Baseline Gate에서 별도로 판정한다.
