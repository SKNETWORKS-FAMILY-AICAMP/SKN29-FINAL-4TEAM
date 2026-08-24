# 상담사 문의·상담 API 구현 가이드

> 관련 업무: 상담사 Workspace·전화 문의·미배정 대기열·Claim·상담 처리
> 정책 기준: 2026-08-23 윤승혁(PM) 결정 — 상담 요청은 자동배정하지 않고 미배정 대기열에 두며 상담사가 Claim한다.
> P0 데이터 경계: 현재 Runtime은 승인된 합성 사용자만 허용한다. 실제 고객·개인정보 Runtime은 별도 승인 전까지 NO-GO다.

## 1. 기능 범위

- 배정 문의 목록·상세 조회
- 미배정 상담 대기열 조회와 상담사 Claim
- 검색·필터·정렬·Pagination
- 역할·배정 기반 최소 Projection
- 상담사 전화 문의 등록
- Dashboard 합성 공지 목록·상세 조회
- 상담 시작·기록 저장·요약 확정·상담 완료
- 완료 후 동일 문의 재조회

## 2. 주요 경로

- `backend/apps/inquiries/**`
- `backend/apps/consultations/**`
- `backend/apps/operations/**`
- `contracts/api/paths/inquiries.yaml`
- `contracts/api/paths/consultations.yaml`
- `contracts/api/paths/operations.yaml`
- `backend/tests/api/test_consultant_inquiry_runtime.py`
- `backend/tests/api/test_consultation_claim_runtime.py`
- `backend/tests/integration/test_consultation_claim_postgresql.py`
- `backend/tests/api/test_consultation_visit_runtime.py`

## 3. 조회 경계

- CONSULTANT 역할과 본인 배정을 모두 확인한다.
- 기존 배정 목록·상세에서는 미배정 문의와 타 상담사 문의를 404로 은닉한다.
- 별도 미배정 대기열은 Claim에 필요한 합성 문의의 최소 정보만 반환한다.
- 대기열 응답에는 고객 이름·전화번호·주소·계약번호·내부 AI Trace를 넣지 않는다.
- 목록·상세에 `allowed_actions`와 최신 `state_version`을 제공한다.
- 내부 사용자 ID·전체 연락처·주소·AI 내부 Trace를 노출하지 않는다.
- `select_related`·`prefetch_related`로 Query 수 상한을 검증한다.

## 4. 전화 문의 등록

상담사가 승인된 합성 고객·구독을 선택해 문의와 최초 상태·이력·멱등 원장을
원자적으로 생성한다. 일반 고객 데이터나 임의 제품을 생성하지 않는다.

## 5. 미배정 대기열과 Claim

### API

```text
GET  /api/v1/inquiries/unassigned-consultations
POST /api/v1/inquiries/{inquiry_id}/claim-consultation
```

Claim 요청은 `Idempotency-Key`, `X-Correlation-ID`와 아래 Body를 사용한다.

```json
{"state_version": 4}
```

P0의 모든 승인 대상은 합성 문의이며, 이 범위의 `REQUEST_CONSULTATION`은
특정 상담사를 자동배정하지 않고 다음 상태로 저장한다.

```text
Inquiry: CONSULTATION_REQUIRED / assigned_user=null / assigned_role_code=NONE
Consultation: WAITING / consultant=null
```

`prepare_synthetic_e2e_assignment`는 대표 합성 문의를 표시할 뿐 배정하지 않는다.
출력의 `assignment_mode=UNASSIGNED_QUEUE_CLAIM`, `claim_required=true`를 따라
반드시 `requestConsultation` 후 `claimConsultation`을 실행한다. 사용되지 않는
직접 자동배정 메서드는 제거했다.

PM이 확정한 실제 서비스 방향도 대기열·Claim이다. 다만 이 결정은 실제 고객
개인정보 사용 승인이 아니다. 실제 고객 Runtime을 열 때에는 CustomerProfile의
합성 전용 제약, 권한·PII Projection, 운영 감사 정책을 별도 승인·검증한 뒤 같은
대기열·Claim 방식을 적용한다.

Claim 성공 시 로그인한 상담사를 Inquiry와 Consultation에 원자적으로 배정한다.
Inquiry 상태는 `CONSULTATION_REQUIRED`로 유지하고 `state_version`만 1 증가한다.
Consultation은 `ASSIGNED`가 되지만 `started_at`은 비워 둔다.

```text
REQUEST_CONSULTATION
→ CLAIM_CONSULTATION (배정만 수행)
→ START_CONSULTATION (실제 상담 시작)
```

Claim과 상담 시작을 합치지 않는 이유는 배정 시점과 실제 상담 시작 시점을
구분해 담당자·이력·동시성·SLA를 정확하게 추적하기 위해서다.

### 오류와 동시성 경계

- 같은 Key·같은 요청 Replay: 기존 성공 응답 200
- 같은 Key·다른 Payload: 409 `DUPLICATE-EVENT-01`
- 오래된 `state_version`: 409 `STATE-CONFLICT-01`
- 두 상담사의 동시 Claim: 한 명만 200, 다른 상담사는 404
- 미존재·이미 배정·Claim 불가 대상: 동일 404 은닉
- 타 대상 Key 재사용: 대상이 현재 Claim 가능하면 409, 비가시·Claim 불가면 404
- CONSULTANT 외 역할: 403
- 잘못된 입력: 422
- 중간 실패: 배정·상태 이력·멱등 원장을 모두 Rollback

### Web G4 Fixture 정합화

`create_web_consultation_e2e_fixture`도 DB 필드를 직접 배정하지 않고
`ConsultationClaimService`를 호출한다. 따라서 Fixture 시작 경계는
`state_version=3`, `consultation_status=ASSIGNED`,
`allowed_actions=[START_CONSULTATION]`이다. Web 소비자는 main 병합 후 이 값을
읽도록 별도 담당 범위에서 갱신해야 한다.

## 6. 상담 Write

```text
startConsultation
→ saveConsultationSummary
→ confirmConsultationSummary
→ completeConsultation
```

작성 중 기록과 확정 기록을 구분한다. 서버 자동저장·Draft 기능은 승인 없이
확대하지 않는다.

## 7. 검증

| 구간 | 확인 |
| --- | --- |
| 목록·상세 | 배정·Projection·Pagination·N+1 |
| 전화 문의 | 합성 고객·구독·Transaction·Replay |
| 대기열·Claim | 최소 Projection·404 은닉·Replay·동시 Claim·Rollback |
| 상담 Write | 권한·상태·Version·History |
| 오류 | 403·404·409·422 |
| Rollback | 문의·상담·이력·멱등 원자성 |

검증 결과:

- Backend 표적 회귀: 116 passed / 1 PostgreSQL-only skipped
- Claim·G4 Fixture 표적 회귀: 43 passed
- Backend 전체 회귀: 1459 passed / 40 external·PostgreSQL-only skipped
- 계약 검증: 46 passed
- PostgreSQL 16 + pgvector 동시 Claim: 1 passed
- Django Check: PASS
- Migration drift: 없음
- State Machine: 13 states / 33 events / 37 transitions / 42 guards
- 대표 E2E: 15 steps, final state version 15

이번 변경은 기존 모델을 사용하므로 DB Schema와 Migration을 추가하지 않는다.
Web·Mobile·AI 코드는 변경하지 않는다.

## 8. 판정

실제 PostgreSQL과 HTTP에서 조회·등록·Claim·상담 흐름이 재현되면 Backend 구현
완료다. Web 화면 소비 완료는 한예나 담당 결과로 별도 판정한다.

## 9. 2026-08-24 공지 상세·Web 단일 화면 연동

Dashboard 목록 DTO에는 공지 본문이 있었지만 한 건을 다시 조회할 경로가 없어
직접 URL·새로고침에 불리했다. 기존 `DashboardNotice`를 그대로 사용해 Schema 변경
없이 아래 읽기 API를 추가했다.

```text
GET /api/v1/consultant/notices/{notice_id}
```

- 활성 CONSULTANT만 접근한다.
- 게시 중인 합성 공지만 반환한다.
- 미게시·미래 게시·미존재 UUID는 모두 404로 숨긴다.
- Query parameter는 422로 거절한다.
- 응답은 `notice_id`, 분류, 제목, 본문, 부서, 게시일만 포함한다.
- 기존 Dashboard·Claim·상담 API와 DB Migration은 변경하지 않는다.

Web은 문의 상세 화면 한 곳에서 기존 조회·상담 시작·저장·확정·완료 API를 순서대로
호출할 수 있다. 화면 구조는 Web 책임이며, 상태 권한은 계속 Backend의
`allowed_actions`와 최신 `state_version`을 따른다. 409에서는 입력을 보존하고
상세를 다시 조회하며 임의 성공 처리나 자동 재시도는 하지 않는다.

검증 결과는 공지 Runtime·권한·404·계약·OpenAPI·Seed 표적 `25 passed`, 전체
`1459 passed / 40 skipped`, OpenAPI `59 operations`, Django Check PASS다. 실제
Web 클릭·화면 이동은 Web 담당 검증 범위다.

## 10. 2026-08-24 상담사 통합 상세 Projection 보완

Claim 후 `GET /api/v1/inquiries/{inquiry_id}` 한 번으로 통합 상세 정보를 조회하며 기존 필드는 유지하고 다음 안전한 필드를 추가했다.
| 화면 영역 | 응답 계약 |
| --- | --- |
| 고객 | `display_name`, `phone_masked` (`phone`은 같은 마스킹 값의 호환 필드) |
| 제품·관리 | `product_model`(코드), `product_model_name`, 구독·관리·최근 관리일 |
| 증상·문진 | `symptom_summary`, `answers[].question_code/question_text/answer` |
| 사용 안내 | 원본 `usage_guidance_status`, 한글 `usage_guidance_display_label`, 안내·제한 기능 |
| 상담·방문 | 상담 기록과 최신 합성 `visit`; 방문이 없으면 `null` |
| 업무 처리 | 문의 번호·상태·버전과 Backend `allowed_actions` |
상태 표시 계약은 `NORMAL=정상 사용 가능`, `PARTIAL_STOP=일부 기능 사용 중단`,
`TOTAL_STOP=제품 사용 중단`, `PENDING_CONSULTATION=상담 확인 필요`다. Web은 원본
코드로 분기하고 한글 필드는 화면 표시용으로만 사용한다. 방문 필요 여부는
`consultation.result_code=VISIT_REQUIRED`와 최신 `visit` 존재 여부로 구분한다.
DEC-008 공개 Evidence는 아직 이 상세 계약에서 제외된다. Backend 내부 Chunk,
원문, 경로, 점수로 임의 화면 데이터를 만들지 않는다. 이번 보완은 Migration과
Web·AI 소스를 변경하지 않으며 원문 고객 연락처도 응답하지 않는다. 상세·계약·
OpenAPI·Demo Seed는 `42 passed`, 인접 회귀는 `18 passed / 1 PostgreSQL-only skipped`,
전체 Backend 회귀는 `1459 passed / 40 external·PostgreSQL-only skipped`다.
