# 5주차 대표 E2E Acceptance Criteria

> 확정일: 2026-08-12 KST
> PM 기준 Commit: `main@f781e92be75d09a1f5bf0464f9ae1fdf90e97bdc`
> 상태: **PM_CRITERIA_APPROVED · ROOT_E2E_EXECUTION_HOLD**
> 관련 업무: `윤승혁_5주차_업무_지침서.md` 5.1

## 1. 판정 범위

이 문서는 Root E2E가 통과했다고 주장하는 결과서가 아니다. 정상·비정상 Scenario의 입력, 단계, 기대 상태, DB·화면 증거와 수치형 PASS/HOLD 기준을 확정한다.

- 계약과 Fixture 기준 정의: 완료
- Root E2E Test 구현: 미착수
- 실제 Runtime 실행: `HOLD`
- 실행 해제 조건: 3.3 Contract Baseline, 3.5 Backend↔AI, 3.6 Web·Mobile Consumer Gate 통과

단위·계약·Mock Test 결과를 Root E2E PASS로 합산하지 않는다.

## 2. 단일 기준본

| 구분 | 기준 |
|---|---|
| 정상 Scenario | `SYN-JAC104-002` |
| 문의 번호 | `DEMO-INQ-002` |
| 제품 | `WPUJAC104DWH` |
| 증상 | 출수량 저하 |
| 공식 문서 | `MAN-SKMAGIC-WPU-JAC104D-JCC104D-REV00` |
| 공식 근거 | 38쪽, `RAG-WPUJAC104DWH-LOW-FLOW-001`, `EVD-WPUJAC104DWH-LOW-FLOW-001` |
| 최종 Inquiry 상태 | `RESOLVED` |
| 최종 Inquiry Version | `14` |
| 최종 Visit 상태·Version | `COMPLETED` · `5` |
| State 계약 | `contracts/state-machine/**` v1.0.0 |
| API 연결 | `contracts/api/action-operation-crosswalk.yaml` |

Root E2E는 다음 기존 Fixture를 복사하지 않고 직접 읽는다.

- `data/config/e2e/representative_case.json`
- `contracts/state-machine/examples/representative-e2e.yaml`
- `data/synthetic/fixtures/**`
- `data/synthetic/expected/**`

Fixture의 값이 서로 다르면 임의 보정하지 않고 `CONTRACT_DRIFT`로 중단한다.

## 3. Scenario ID

| 우선순위 | Scenario ID | 목적 | 기준 입력 | 준비 상태 |
|---|---|---|---|---|
| 필수 | `SYN-JAC104-002` | 정상 고객→AI→상담→방문→해결 | 대표 Fixture | 계약 확정·후반 Runtime 대기 |
| 필수 | `SYN-JAC104-004` | 누수 위험 감지와 상담 전환 | `danger_escalation.json` | Fixture 준비·실제 AI Gate 대기 |
| 필수 | `SYN-JAC104-022` | 공식 근거 없음과 판단 보류 | `no_evidence_fallback.json` | Fixture 준비·실제 Vector Gate 대기 |
| 권장 | `SYN-IDEMPOTENCY-CONFIRM-VISIT-CONFLICT` | 멱등키 Payload 충돌 409 | `api_idempotency_cases.json` | Fixture 준비 |
| 권장 | `W5-STATE-CONFLICT-001` | 오래된 `state_version` 충돌 409 | 정상 Scenario 10단계 직전 Snapshot | 동적 Fixture |
| 권장 | `W5-REOPENED-001` | 고객 미해결→재상담 | `reopened-inquiry.yaml` | `FIXTURE_REQUIRED` |

모든 결과 파일과 Screenshot 이름에는 위 Scenario ID를 사용한다.

## 4. 정상 Scenario Event–API–State Matrix

`allowed_actions`는 표에 적힌 대상 Actor의 응답 기준이다. Backend Guard 평가 후 표의 행동이 포함돼야 하며, 다른 역할의 행동이나 내부 Event가 노출되면 실패다.

| # | Actor | Event | Operation·HTTP | 기대 Inquiry 상태·Version | Visit 상태·Version | 다음 Actor의 필수 `allowed_actions` | 현재 Runtime |
|---:|---|---|---|---|---|---|---|
| 1 | CUSTOMER | `START_INQUIRY` | `startInquiry` · `POST /inquiries` | `DRAFT` · 1 | 없음 | CUSTOMER: `SUBMIT_SYMPTOM`, `CANCEL_INQUIRY` | 구현 |
| 2 | CUSTOMER | `SUBMIT_SYMPTOM` | `submitSymptom` · `POST /inquiries/{id}/submit` | `QUESTIONNAIRE_IN_PROGRESS` · 2 | 없음 | CUSTOMER: `SUBMIT_ANSWERS`, `CANCEL_INQUIRY` | 구현 |
| 3 | CUSTOMER | `SUBMIT_ANSWERS` | `submitFollowUpAnswers` · `POST /inquiries/{id}/answers` | `QUESTIONNAIRE_IN_PROGRESS` · 3 | 없음 | SYSTEM Event 대기, 내부 Event 비노출 | 구현 |
| 4 | SYSTEM | `SAFE_GUIDANCE_READY` | 외부 HTTP 없음 | `AI_GUIDANCE` · 4 | 없음 | CUSTOMER: `CUSTOMER_REPORTED_SELF_RESOLVED`, `REQUEST_CONSULTATION` | 내부 Event |
| 5 | CUSTOMER | `REQUEST_CONSULTATION` | `requestConsultation` · `POST /inquiries/{id}/request-consultation` | `CONSULTATION_REQUIRED` · 5 | 없음 | CONSULTANT: `START_CONSULTATION` | 구현 |
| 6 | CONSULTANT | `START_CONSULTATION` | `startConsultation` · `POST /inquiries/{id}/start-consultation` | `CONSULTATION_IN_PROGRESS` · 6 | 없음 | CONSULTANT: `UPDATE_CONSULTATION_SUMMARY`, `CONFIRM_CONSULTATION_SUMMARY`, `CONSULTATION_COMPLETED`, `VISIT_REVIEW_REQUIRED` | 구현 |
| 7 | CONSULTANT | `VISIT_REVIEW_REQUIRED` | `requestVisitReview` · `POST /inquiries/{id}/visit-review` | `VISIT_REVIEW_PENDING` · 7 | 없음 | CONSULTANT: `VISIT_NEEDED`, `VISIT_NOT_NEEDED` | 구현 |
| 8 | CONSULTANT | `VISIT_NEEDED` | `createVisitRequest` · `POST /inquiries/{id}/visits` | `VISIT_SCHEDULING` · 8 | `ASSIGNING` · 1 | CONSULTANT: `UPDATE_VISIT_SCHEDULE` | 구현 |
| 9 | CONSULTANT | `UPDATE_VISIT_SCHEDULE` | `updateVisitSchedule` · `PATCH /visits/{visit_id}/schedule` | `VISIT_SCHEDULING` · 9 | `SCHEDULING` · 2 | CONSULTANT: `UPDATE_VISIT_SCHEDULE`, `CONFIRM_VISIT` | 구현 |
| 10 | CONSULTANT | `CONFIRM_VISIT` | `confirmVisit` · `POST /visits/{visit_id}/confirm` | `VISIT_SCHEDULED` · 10 | `CONFIRMED` · 3 | TECHNICIAN: `START_VISIT`; 리포트 Guard 충족 시 `UPDATE_PREVISIT_REPORT`, `CONFIRM_PREVISIT_REPORT` | 구현 |
| 11 | TECHNICIAN | `START_VISIT` | `startVisit` · `POST /visits/{visit_id}/start` | `VISIT_SCHEDULED` · 11 | `IN_PROGRESS` · 4 | TECHNICIAN: `VISIT_COMPLETED`, `REVISIT_NEEDED` | OpenAPI 전용 |
| 12 | TECHNICIAN | `VISIT_COMPLETED` | `completeVisit` · `POST /visits/{visit_id}/complete` | `COMPLETION_PENDING` · 12 | `COMPLETED` · 5 | CUSTOMER: `SUBMIT_RESOLUTION_FEEDBACK`, `CUSTOMER_REPORTED_UNRESOLVED`, `REQUEST_CONSULTATION` | OpenAPI 전용 |
| 13 | CUSTOMER | `SUBMIT_RESOLUTION_FEEDBACK` | `submitResolutionFeedback` · `POST /inquiries/{id}/resolution-feedback` | `COMPLETION_PENDING` · 13 | `COMPLETED` · 5 | 마지막 TECHNICIAN: `FINALIZE_INQUIRY` | OpenAPI 전용 |
| 14 | TECHNICIAN | `FINALIZE_INQUIRY` | `finalizeInquiry` · `POST /inquiries/{id}/finalize` | `RESOLVED` · 14 | `COMPLETED` · 5 | 없음 | OpenAPI 전용 |

`OpenAPI 전용` 단계는 계약 기대값으로 확정하지만 Runtime Source·Test가 생기기 전에는 실제 E2E PASS가 불가능하다.

## 5. 단계별 DB Acceptance

모든 외부 쓰기는 새 `Idempotency-Key`와 `X-Correlation-ID`, 직전 응답의 `state_version`을 사용한다.

| 단계 | 필수 DB 변화 |
|---:|---|
| 1 | Inquiry 1건 생성, 상태 `DRAFT`, Inquiry History·Audit Event·Idempotency Record 생성 |
| 2 | 증상 원문·선택 증상 저장, 상태·Version 갱신, Inquiry History·Audit Event 생성, AI 실행 예약 또는 Run 연결 |
| 3 | 열린 질문에 대한 고객 Answer 원장 저장, 중복 `question_id` 없음, Audit Event 생성, Inquiry History 추가 금지 |
| 4 | 성공한 최신 AI Run과 Schema 검증 결과, Symptom Assessment, 공식 Retrieval/Evidence, 고객 공개 Guidance 저장; Inquiry History·Audit Event 생성 |
| 5 | 대기 상태 Consultation 1건 생성 또는 계약된 Upsert, Inquiry History·Audit Event 생성 |
| 6 | 같은 Consultation이 담당 상담사·진행 상태로 갱신, 중복 Consultation 생성 금지, Inquiry History·Audit Event 생성 |
| 7 | 방문 검토 사유 저장, Visit은 아직 생성되지 않음, Inquiry History·Audit Event 생성 |
| 8 | Visit 1건과 Handoff·고객 희망일 저장, Inquiry History·Visit History·Audit Event 생성 |
| 9 | 같은 Visit에 담당 기사·예정일 저장, Visit History·Audit Event 생성, Inquiry History 추가 금지 |
| 10 | 같은 Visit이 `CONFIRMED`, 확정 시각 저장, Inquiry History·Visit History·Audit Event 생성 |
| 11 | 같은 Visit이 `IN_PROGRESS`, 시작 시각 저장, Visit History·Audit Event 생성, Inquiry History 추가 금지 |
| 12 | Visit Result와 완료 시각 저장, Visit `COMPLETED`, Inquiry `completion_source=VISIT`, Inquiry History·Visit History·Audit Event 생성 |
| 13 | 해결됨 고객 Feedback 저장, Inquiry 상태 유지, Audit Event 생성, Inquiry History 추가 금지 |
| 14 | Inquiry `RESOLVED`, 종료 시각·최종 담당자 근거 저장, Inquiry History·Audit Event 생성 |

정상 Scenario 실행 전후 Delta의 최소 정량 기준은 다음과 같다.

- Inquiry: `+1`
- Consultation: `+1`, 같은 문의의 활성 중복 `0`
- Visit: `+1`, 같은 문의의 활성 중복 `0`
- Inquiry 상태 이력: 계약의 `record_inquiry_state_history`와 정확히 일치, 대표 흐름 기준 `10`
- Visit 상태 이력: `5`
- Business Audit Event: 14개 Event 모두 추적 가능
- 성공 외부 쓰기: 13개, 같은 키 Replay 외 중복 Business Record `0`
- AI Run: 최소 1개 성공 Run, 최신 Run의 Schema 검증 `PASSED`
- 공식 Evidence: `EVD-WPUJAC104DWH-LOW-FLOW-001`이 최신 Guidance와 연결

구현상 부가 Audit가 있더라도 위 14개 Business Event와 구분 가능해야 한다.

## 6. 화면 Acceptance

### Customer Mobile

- 실제 고객 계정으로 본인 구독과 `DEMO-INQ-002`만 조회한다.
- 증상·추가 답변이 새로고침 후 유지된다.
- `AI_GUIDANCE`에서는 사용 안내 상태, 제한 범위, 공식 Evidence, 다음 행동을 표시한다.
- 버튼은 Backend `allowed_actions`를 기준으로 노출한다.
- 상담 요청 후 상태·담당 주체·다음 단계를 갱신한다.
- 방문 희망일과 확정일을 구분한다.
- 방문 완료 후 해결 피드백을 제출하고 담당자 최종 완료 전까지 `COMPLETION_PENDING`을 표시한다.
- `RESOLVED`에서 쓰기 행동을 노출하지 않는다.

### Consultant Web

- 실제 상담사 계정으로 같은 문의를 목록과 상세에서 조회한다.
- 위험도·우선순위·고객 원문·추가 답변·공식 Evidence를 구분한다.
- 상담 시작, 방문 검토, Visit 생성·일정·확정 결과가 새로고침 후 유지된다.
- `allowed_actions`에 없는 행동을 숨기거나 비활성화한다.
- 409 발생 시 입력을 보존하고 최신 상태·Version·행동으로 화면을 다시 그린다.

### Technician Mobile

- 배정된 기사만 같은 Visit을 조회하며 미배정·타 기사 접근은 차단된다.
- 고객 PII·내부 원문 경로·전체 문서 원문은 노출하지 않는다.
- 방문 시작·완료 행동은 Backend `allowed_actions`를 사용한다.
- 결과 필수값 누락 시 완료를 차단한다.
- 완료 후 Visit과 Inquiry 상태를 다시 조회해 `COMPLETED`·`COMPLETION_PENDING`을 확인한다.

Screenshot 파일에는 Scenario ID·단계 번호·Actor를 포함하고 Token·Secret·실제 PII를 포함하지 않는다.

## 7. 필수 비정상 Scenario

### 7.1 위험 감지 — `SYN-JAC104-004`

| 항목 | 기대값 |
|---|---|
| 입력 | 제품 아래 물 고임·누수 위험 입력 |
| AI | `danger_detected=true`, 검증된 Safety Rule ID 존재 |
| Event | `DANGER_DETECTED` |
| State | `QUESTIONNAIRE_IN_PROGRESS` → `CONSULTATION_REQUIRED` |
| 사용 안내 | `TOTAL_STOP` |
| 공개 결과 | 일반 자가조치·사용 가능 안내 노출 금지 |
| 다음 행동 | 고객 상담 확인 또는 담당 상담사의 `START_CONSULTATION` |
| PASS | 위험 누락 0, 일반 안내 노출 0, Backend 이외 State 직접 변경 0 |

### 7.2 근거 없음 — `SYN-JAC104-022`

| 항목 | 기대값 |
|---|---|
| 입력 | 앱 필터 상태 조회처럼 공식 근거가 없는 범위 |
| Retrieval | 검색 완료, 사용 가능한 공식 Evidence `0` |
| Event | `NO_EVIDENCE` |
| State | `QUESTIONNAIRE_IN_PROGRESS` → `CONSULTATION_REQUIRED` |
| 사용 안내 | `PENDING_CONSULTATION` |
| 공개 결과 | 임의 진단·자가조치·가짜 Citation 생성 금지 |
| PASS | Invented Guidance 0, 미검증 Evidence 0, 상담 전환 누락 0 |

## 8. 권장 비정상 Scenario

### 8.1 State Version 충돌 — `W5-STATE-CONFLICT-001`

1. 두 Client가 Step 9 이후 `state_version=9` Snapshot을 가진다.
2. Client A가 `CONFIRM_VISIT`에 성공해 Version 10을 만든다.
3. Client B가 오래된 Version 9로 같은 Operation을 요청한다.

기대 결과:

- HTTP `409`, 공개 코드 `STATE-CONFLICT-01`
- `details.current_status=VISIT_SCHEDULED`
- `details.current_state_version=10`
- `details.allowed_actions`는 최신 Actor 기준 행동 코드 배열
- Inquiry·Visit·History·Audit·업무 Record 추가 변화 `0`
- Web·Mobile 입력 보존, 최신 Snapshot 재조회, 자동 무한 재시도 `0`

### 8.2 Idempotency Payload 충돌

`SYN-IDEMPOTENCY-CONFIRM-VISIT-CONFLICT`를 사용한다.

- 이미 성공한 Key를 다른 Payload에 재사용한다.
- HTTP `409`, 공개 코드 `DUPLICATE-EVENT-01`
- History 추가 `0`, Visit 중복 변화 `0`
- 같은 Key·같은 Payload Replay는 최초 응답과 동등하며 업무 Record 추가 `0`

### 8.3 고객 미해결→재상담 — `W5-REOPENED-001`

| 단계 | Actor | Event·Operation | 기대 상태 |
|---:|---|---|---|
| 1 | CUSTOMER | `CUSTOMER_REPORTED_UNRESOLVED` · `reportUnresolved` | `COMPLETION_PENDING` → `REOPENED` |
| 2 | CONSULTANT | `RESUME_CONSULTATION` · `resumeConsultation` | `REOPENED` → `CONSULTATION_REQUIRED` |

- 이전 Consultation·Visit·History를 삭제하지 않는다.
- 해결됨 Feedback과 최종 완료 자격을 무효화한다.
- `REOPENED`에서 CONSULTANT `RESUME_CONSULTATION`만 노출한다.
- `CONSULTATION_REQUIRED`에서 담당 상담사 `START_CONSULTATION`을 노출한다.
- 현재 `data/synthetic/scenarios/reopened_inquiry.json`이 비어 있으므로 Fixture가 생성되기 전에는 `NOT_RUN`으로 기록한다.

## 9. Correlation·보안 기준

- 각 사용자 요청은 하나의 `X-Correlation-ID`를 요청·응답·Audit·AI Run·Retrieval까지 추적할 수 있어야 한다.
- 비동기 AI 내부 호출은 부모 Correlation과 연결되는 Trace 근거를 남긴다.
- 고객은 다른 고객 문의에 `403` 또는 존재 은닉 `404` 정책대로 접근하지 못한다.
- 기사는 미배정·타 기사 Visit에 접근하지 못한다.
- API 응답과 Screenshot에 Access/Refresh Token, Secret, DSN, 내부 `source_path`, 전체 원문을 노출하지 않는다.
- 모든 고객·계정·문의 데이터는 합성 Data Classification을 사용한다.

## 10. PASS·HOLD 기준

### 정상 Scenario PASS

다음 조건을 모두 만족해야 한다.

| 지표 | PASS 기준 |
|---|---:|
| 필수 단계 성공 | `14/14` |
| 외부 API 성공 | `13/13` |
| 최종 Inquiry 상태·Version | `RESOLVED / 14` |
| 최종 Visit 상태·Version | `COMPLETED / 5` |
| State Drift | `0` |
| Contract Drift | `0` |
| 누락 Business Event | `0` |
| 중복 Business Record | `0` |
| Unauthorized Data Leak | `0` |
| Unexplained Mock/Fake Fallback | `0` |
| 직접 DB 수정·수동 상태 전이 | `0` |
| 추적 불가 필수 Correlation | `0` |
| 필수 화면 Actor 누락 | `0` |

### 비정상 Scenario PASS

- 위험과 근거 없음 Scenario 각각 `1/1` 실행 성공
- 위험 시 안전하지 않은 안내 노출 `0`
- 근거 없음 시 생성된 가짜 Evidence `0`
- 409를 실행한 경우 업무 Record 변화 `0`, 입력 유실 `0`
- Mock을 사용한 Fallback은 계약에 정의된 공식 장애 경로에서만 허용하며 결과에 `FALLBACK`을 표시한다.

### HOLD

다음 중 하나라도 해당하면 정상 E2E는 `HOLD`다.

- 14단계 중 실제 Runtime이 없는 단계가 있음
- 실제 LLM 또는 팀 pgvector를 정상 Scenario에서 사용하지 못함
- Web·Mobile Remote 대신 Mock/Fake를 사용함
- DB 직접 수정이나 수동 상태 전이로 단계를 건너뜀
- State·Version·Action·History 중 하나라도 계약과 다름
- 실제 화면 또는 Backend DB 증거가 같은 Inquiry·Visit·Commit을 가리키지 않음
- 서로 다른 Commit의 결과를 합침
- 실제 Secret·PII 노출이 발견됨

`CONDITIONAL_PASS`는 정상 14단계에 적용하지 않는다. 선택 Scenario 또는 Screenshot 일부만 누락됐고 정상 Runtime·DB·계약 결과가 모두 PASS한 경우에만 별도 PM 판단 대상으로 남긴다.

## 11. Evidence 규칙

결과는 다음 값을 포함한다.

```text
scenario_id=<고정 ID>
baseline_commit=<40자리 SHA>
started_at=<KST>
finished_at=<KST>
service_modes=<backend, ai, web, mobile>
database=<PostgreSQL과 팀 pgvector 식별 정보, Secret 제외>
steps=<각 단계 HTTP·Event·State·Version·allowed_actions>
db_delta=<Record별 전후 수치>
correlation_ids=<단계별 공개 UUID>
screenshots=<Token·PII 제거 경로>
mock_fallback=<NONE 또는 공식 Fallback>
direct_db_mutation=NONE
result=PASS | FAIL | HOLD | NOT_RUN
blocker=<없으면 NONE>
```

## 12. Root E2E 구현 인계 기준

김은진이 구현할 Root 구조는 다음 책임으로 분리한다.

```text
tests/e2e/
├─ consultation-resolution/
├─ danger-escalation/
├─ no-evidence-fallback/
├─ reopened-inquiry/
├─ self-resolution/
└─ visit-resolution/

tests/fixtures/
└─ 기존 data/config·data/synthetic 기준본을 읽는 Loader

tests/helpers/
├─ 서비스 Preflight
├─ Actor 인증 Client
├─ State·Version·Action Assertion
├─ DB Delta·History Assertion
└─ Correlation·비밀값 검사
```

구현 순서:

1. 기존 대표 Fixture와 Contract Example의 Drift를 먼저 검사한다.
2. 실제 서비스 Health·DB·Seed를 확인하고 실패 시 Scenario를 시작하지 않는다.
3. 정상 14단계를 API와 Remote Client로 실행한다.
4. 각 단계 직후 State·Version·`allowed_actions`와 DB Delta를 검증한다.
5. 위험·근거 없음 Scenario를 독립 Fixture로 실행한다.
6. 409와 재상담은 준비된 경우 별도 Test로 실행한다.
7. 결과를 단계별로 남기고 하나라도 강제 우회하면 전체 정상 Scenario를 `HOLD`로 종료한다.

각 영역 Unit Test는 사전 조건으로 사용할 수 있지만 Root E2E 결과를 대신하지 않는다.

## 13. PM 승인

다음 항목을 5.1 기준으로 확정한다.

- 정상 Scenario의 Actor·API·Event·State·Version·행동 기대값
- 정상 Scenario의 DB·화면 기대값
- 위험·근거 없음 필수 Scenario
- 409·재상담 권장 Scenario
- Mock·직접 DB 수정 금지와 수치형 PASS/HOLD 기준
- 전 팀 공통 Scenario ID와 Evidence 형식

Acceptance Criteria 정의는 완료됐다. 실제 Root E2E 구현과 실행 승인은 3.3·3.5·3.6 Gate가 통과한 뒤 별도로 연다.
