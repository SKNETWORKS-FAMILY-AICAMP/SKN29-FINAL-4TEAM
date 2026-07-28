# 3주차 상담 화면–API–DB 필드 매핑

- 기준일: 2026-07-28
- 대상: `CONS-01`, `CONS-02`, 상담 기록·행동 영역
- 상태: Web 검수용. API `consultation/**` 스키마와 `AllowedAction` OpenAPI Schema는 현재 빈 객체이므로 아래의 `OPEN` 항목을 확정 계약으로 사용하면 안 된다.
- DB 기준: `docs/database/watercare_table_dictionary.md`의 `Design Draft`

## 계약 해석 원칙

1. 화면은 상태로 행동을 계산하지 않고 Backend의 `allowed_actions`를 그대로 표시한다.
2. 모든 외부 쓰기는 최신 Inquiry `state_version`과 새 `Idempotency-Key`를 사용한다.
3. 409 충돌 시 입력을 보존하고 최신 상태·버전·허용 행동을 반영한 뒤 사용자가 재시도한다.
4. API에 없는 이름은 현재 Web Mock의 임시 이름이며 Backend 합의 후 Mapper에서 교체한다.

## 문의 목록·상세 표시

| 화면 정보 | Web View Model | API 계약 | DB 설계 기준 | 마스킹·비고 |
| --- | --- | --- | --- | --- |
| 문의 번호 | `CounselorInquiry.id` | `InquiryDetail.inquiry_id` | `support_inquiry.inquiry_no` 또는 공개 ID 매핑 필요 | 내부 UUID 직접 노출 금지 |
| 상태 | `status` | OpenAPI 상세 Schema에는 아직 없음 | `support_inquiry.status_code` | 표시명 Mapper 사용 |
| 상태 버전 | `stateVersion` | 상태 머신 `state_version` | `support_inquiry.state_version` | 쓰기 동시성 제어값 |
| 허용 행동 | `allowedActions` | 상태 머신 `allowed_actions[]` | Backend Guard 계산값, 직접 저장 필드 아님 | 상태 코드로 Web 재계산 금지 |
| 위험도 | `riskLevel` | OpenAPI 상세 Schema에는 아직 없음 | `support_inquiry.risk_level_code`, `support_symptom_assessment.risk_level_code` | Backend 반환값만 표시 |
| 우선순위 | `priority` | OpenAPI 상세 Schema에는 아직 없음 | `support_inquiry.priority_code`, `support_symptom_assessment.priority_code` | Web 점수 계산 금지 |
| 사용 안내 상태 | `usageStatus` | `usage_guidance_status` | `support_inquiry.usage_guidance_status` | 계약 Enum 사용 |
| 사용 안내 문구 | `usageMessage` | `usage_guidance_message` | `support_inquiry.usage_guidance_message` | 검증된 문구만 표시 |
| 제한 기능 | `restrictedFunctions` | `restricted_functions[]` | `support_inquiry.restricted_functions` | 내부 코드의 표시명 변환 필요 |
| 다음 행동 | `nextAction` | `next_action` | `support_inquiry.next_action` | 현재 API는 문자열, DB는 객체 초안으로 불일치 |
| 상담 필요 여부 | `requiresConsultation` | `requires_consultation` | `support_inquiry.requires_consultation` | Web 추론 금지 |
| 고객 표시명 | `customerName` | OPEN | `customers_customer_profile` 역할별 조회 | 합성 데이터 또는 마스킹 표시명만 사용 |
| 제품 모델 | `productCode` | OPEN | `catalog_product_model`, 구독 연결 | MVP 모델 오인 방지 |

## 상담 기록 Form과 쓰기 요청

| 화면 입력·제어 | Web 필드 / 임시 요청 필드 | API 상태 | DB 설계 후보 | 확정 전 확인사항 |
| --- | --- | --- | --- | --- |
| 상담 기록 | `consultationNote` / `consultation_note` | `SaveConsultationRequest` 비어 있음 · `OPEN` | `support_consultation.consultant_notes` | 최대 길이·필수 조건 |
| 추가 확인사항 | `additionalCheck` / `additional_check` | `OPEN` | 전용 컬럼 없음 · `OPEN` | 상담 메모 병합 여부 |
| 고객 안내 | `customerGuidance` / `customer_guidance` | `OPEN` | `support_guidance` 연계 후보 · 직접 컬럼 미확정 | 상담 안내 저장 주체와 구조 |
| 상담 결과 | `consultationResult` / `consultation_result` | `OPEN` | `support_consultation.disposition_code`, `next_action` 후보 | 코드와 자유문 분리 필요 |
| AI 요약 초안 | `aiSummaryOriginal` | 상담 조회 Schema 비어 있음 · `OPEN` | `support_consultation.ai_summary_draft` | 상담사 수정 불가 |
| 상담사 수정 요약 | `summaryRevision` / `summary_revision` | `OPEN` | `support_consultation.final_summary` 후보 | 임시 저장본과 확정본 분리 방식 |
| 상담사 확정 여부 | `summaryConfirmed` / `summary_confirmed` | `OPEN` | 전용 boolean 없음 · 상태/이력 후보 | 확정 이벤트와 감사 이력 필요 |
| 방문 필요 여부 | `visitRequired` / `visit_required` | `OPEN` | `support_consultation.visit_required` | `VISIT_REVIEW_REQUIRED` 전이와 정합성 |
| 처리 후 사용 안내 | `usageStatus` / `usage_guidance_status` | 상세 조회 Enum만 존재, 쓰기 `OPEN` | `support_inquiry.usage_guidance_status` | 상담 쓰기 API에서 수정 가능한지 확인 |
| 행동 코드 | `action.code` / `action_code` | 상태 머신 action catalog | 상태 이력·업무 이벤트 기록 | canonical code만 사용 |
| Operation | `action.operationId` / `operation_id` | 상태 머신 `operation_id` | 직접 저장 필드 아님 | 실제 Endpoint 연결 필요 |
| 상태 버전 | `stateVersion` / `state_version` | 동시성 계약 확정 | `support_inquiry.state_version` | 성공 쓰기마다 증가 |
| 멱등 키 | Request Context / `Idempotency-Key` | 동시성 계약 확정 | 저장 위치 구현 `OPEN` | 매 시도 새 키, 같은 요청 재전송 정책 준수 |
| 추적 ID | Request Context / `X-Correlation-ID` | Header 계약 존재 | 감사·로그 상관관계 | 개인정보 포함 금지 |

## 공식 근거 공개 범위

화면에는 문서명, 리비전, 페이지, 섹션, 요약, 안전·금지 행동, 검증 상태, 데이터 분류, 공식 URL만 표시한다. `chunk_id`, 내부 `document_id`, 검색 점수, 내부 파일 경로, 원문 전체, Prompt와 Trace는 표시하지 않는다.

## Backend 협의가 필요한 차단 항목

1. `SaveConsultationRequest`, `CompleteConsultationRequest`, `ConsultationRecord`, `ConsultationSummary` 속성 확정
2. OpenAPI `AllowedAction` 속성과 상태 머신 계약의 일치
3. 상담 임시 저장·요약 확정·완료·방문 검토별 Endpoint와 요청 Body 분리
4. `additional_check`, `customer_guidance`, 자유문 상담 결과의 저장 구조
5. 성공 응답의 최신 상세·`state_version`·`allowed_actions` 반환 방식
6. 403·409·422 오류의 `field_errors`, 최신 상태 스냅샷 형식

