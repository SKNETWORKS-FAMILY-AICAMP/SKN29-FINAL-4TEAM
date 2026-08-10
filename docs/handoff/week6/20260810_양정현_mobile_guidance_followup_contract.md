# Mobile 3.4 Guidance / Follow-up API 계약 준비서

- 작성 기준 branch: `jeonghyun`
- T082 시작 기준 commit: `4b8048ac0ea28490a36b44105da49b89e3202797`
- 포함된 latest main: `2198e9e90fe894fb848d551ef638fb3ae0a2b433`
- 담당 범위: Mobile
- 상태: **CONTRACT_READY / BACKEND_ROUTE_PENDING / MOBILE_FAIL_CLOSED**
- 원칙: Backend에 실제 route가 열리기 전에는 Mobile이 endpoint, 응답, AI 결과를 임의 생성하지 않는다.

---

## 1. 현재 실제 Runtime

현재 `/api/v1` 하위 실제 등록 도메인:

- accounts
- subscriptions
- inquiries

현재 Inquiry 실제 route:

- `POST /api/v1/inquiries`
- `GET /api/v1/inquiries/{inquiry_id}` — 현재 consultant projection
- `POST /api/v1/inquiries/{inquiry_id}/cancel`
- `POST /api/v1/inquiries/{inquiry_id}/submit`

따라서 아래 기능은 **현재 실제 Runtime endpoint가 아니다**.

- Customer Guidance 조회
- Guidance Evidence 조회
- Follow-up 조회/응답
- Consultation request
- Technician Visit

---

## 2. Backend에 이미 존재하는 데이터 구조

### Guidance

실제 DB 모델 기준 필드:

- `public_id`
- `inquiry_id`
- `guidance_version`
- `review_status_code`
- `title`
- `summary_text`
- `safety_notice`
- `evidence_sufficiency_code`
- `requires_consultation`
- `generated_by_ai_run_id`
- `reviewed_by_id`
- `reviewed_at`

제약:

- `(inquiry_id, guidance_version)` unique
- AI Run을 참조할 경우 같은 Inquiry여야 함
- review 사용자와 review 시각은 함께 존재하거나 함께 null

### GuidanceItem

- `public_id`
- `guidance_id`
- `step_no`
- `action_type_code`
- `instruction_text`
- `caution_text`
- `requires_confirmation`

제약:

- `(guidance_id, step_no)` unique
- `step_no > 0`

### FollowupConfirmation

- `public_id`
- `followup_code`
- `inquiry_id`
- `guidance_public_id`
- `consultation_id`
- `visit_id`
- `channel_code`
- `resolution_status_code`
- `state_version`
- `customer_response`
- `unresolved_reason`
- `next_action`
- `requested_at`
- `responded_at`
- `confirmed_at`

실제 resolution 값:

- `PENDING`
- `RESOLVED`
- `UNRESOLVED`
- `REOPENED`

실제 next_action 값:

- `FINALIZE_INQUIRY`
- `RESUME_CONSULTATION`
- `NONE`

---

## 3. Mobile에 이미 존재하는 Guidance projection

현재 Mobile `GuidanceData`는 아래 고객 표시 계약을 기대한다.

- `inquiry_id`
- `inquiry_code`
- `symptom_summary`
- `risk_level`
- `usage_guidance_status`
- `usage_guidance_message`
- `restricted_functions`
- `safe_actions`
- `escalation_conditions`
- `prohibited_actions`
- `next_action`
- `requires_consultation`
- `evidence`
- `allowed_actions`

Backend DB의 `Guidance` row와 Mobile `GuidanceData`는 1:1 동일 모델이 아니다.
Backend API가 **고객 표시용 projection**을 제공해야 한다.

Mobile은 DB 모델을 직접 조합하지 않으며 AI/LLM/VectorDB에도 직접 접근하지 않는다.

---

## 4. 현재 Mobile Runtime 안전정책

### REMOTE

Guidance customer route가 실제 등록되기 전에는:

- Fixture Guidance로 자동 fallback하지 않는다.
- `GUIDANCE_ROUTE_UNAVAILABLE` 실패로 처리한다.
- 사용 가능 여부, 자가조치, 위험도를 Mobile이 추정하지 않는다.
- Inquiry 접수 결과 자체는 그대로 유지한다.

### FAKE / Offline Preview

- 명확히 합성 Fixture 미리보기로 표시한다.
- 실제 Backend 결과로 표현하지 않는다.
- 실제 문의를 전송하지 않는 Offline Preview에서는 Fixture 화면 검증만 허용한다.

---

## 5. PROPOSED — Guidance 조회 계약

> 아래 URL/operation 이름은 **제안안**이며 현재 실제 Backend route가 아니다.
> Backend 담당자가 route 이름을 확정하면 Mobile이 그 실제 계약에 맞춰 연결한다.

### 제안

`GET /api/v1/inquiries/{inquiry_id}/guidance`

### 인증/권한

- CUSTOMER 본인 소유 Inquiry만 조회
- CONSULTANT/운영자 projection과 고객 projection을 혼용하지 않음
- 다른 고객 Inquiry 조회 시 프로젝트 표준 ownership error

### 준비 완료 응답 — 200

```json
{
  "success": true,
  "data": {
    "inquiry_id": "uuid",
    "inquiry_code": "INQ-...",
    "guidance_id": "uuid",
    "guidance_version": 1,
    "review_status_code": "APPROVED",
    "symptom_summary": "출수량 저하",
    "risk_level": "general",
    "usage_guidance_status": "NORMAL",
    "usage_guidance_message": "사용 가능 여부 안내",
    "restricted_functions": [],
    "safe_actions": [],
    "escalation_conditions": [],
    "prohibited_actions": [],
    "next_action": "안내 확인",
    "requires_consultation": false,
    "evidence": [],
    "allowed_actions": []
  }
}
```

### 아직 생성/검토 중

Backend가 202/processing 등 프로젝트 표준 응답을 확정한다.

Mobile 요구사항:

- Guidance가 준비되지 않았는데 200 + 임의 안내 문구를 주지 않음
- processing 상태에서는 사용 가능 여부를 추정하지 않음
- 위험/근거없음/알 수 없는 코드에서는 fail-closed

### Evidence

Mobile 표시 최소 필드:

- `document_name`
- `version`
- `page`
- `structured_summary`
- `verification_status`
- `data_classification`
- `official_url`

공식 근거가 0건이면 Mobile은 자가조치를 추정하지 않는다.

---

## 6. PROPOSED — Follow-up 계약

> 아래 URL은 제안안이며 아직 실제 route가 아니다.

### Pending Follow-up 조회

`GET /api/v1/inquiries/{inquiry_id}/follow-up`

최소 응답:

```json
{
  "success": true,
  "data": {
    "followup_id": "uuid",
    "followup_code": "FUP-...",
    "inquiry_id": "uuid",
    "guidance_public_id": "uuid",
    "resolution_status_code": "PENDING",
    "state_version": 1,
    "requested_at": "ISO-8601",
    "allowed_actions": []
  }
}
```

### 고객 응답

`POST /api/v1/inquiries/{inquiry_id}/follow-up/{followup_id}/respond`

Headers:

- `Authorization: Bearer ...`
- `Idempotency-Key: <uuid>`

제안 Request:

```json
{
  "state_version": 1,
  "resolution_status_code": "RESOLVED",
  "customer_response": "안내 후 증상이 해결되었습니다.",
  "unresolved_reason": null
}
```

규칙:

- `RESOLVED` → confirmed 시각 필요
- `UNRESOLVED` / `REOPENED` → unresolved_reason 필수
- stale `state_version` → 409 + 최신 `state_version` / `allowed_actions`
- 동일 `Idempotency-Key` 재전송 → 동일 결과 replay
- 고객이 직접 임의로 `next_action`을 지정하지 않음
- `next_action`은 Backend workflow가 계산

---

## 7. Mobile 구현 Gate

- [x] 고객 P0 Inquiry create/submit 실단말 PASS
- [x] Guidance UI / Mapper 존재
- [x] Evidence fail-closed Mapper 존재
- [x] Guidance / Follow-up API 계약 준비
- [x] REMOTE Guidance Fixture 자동 fallback 차단
- [x] FAKE / Offline Preview Fixture 격리
- [ ] Guidance customer route 실제 등록
- [ ] Guidance serializer 실제 응답 확정
- [ ] Evidence customer projection 실제 응답 확정
- [ ] Follow-up GET route 실제 등록
- [ ] Follow-up respond route 실제 등록
- [ ] ownership/role guard test
- [ ] 401 refresh regression
- [ ] 409 state-version regression
- [ ] Idempotency replay regression
- [ ] Guidance 실제 Galaxy Backend instrumentation

---

## 8. Mobile 연결 순서

Backend가 route를 제공하면 Mobile은 아래 순서만 수행한다.

1. latest main → jeonghyun 통합
2. 실제 route와 serializer 확인
3. `WaterCareApi`에 **실제 route만** 추가
4. DTO 작성
5. Remote repository 연결
6. Fixture fallback 금지
7. Unit Test
8. Backend REST Smoke
9. Galaxy instrumentation
10. Runtime Matrix 갱신
11. `jeonghyun` normal push

---

## 9. 현재 결론

### 3.3

`고객 로그인 → 실제 구독 → Inquiry 생성 → 증상 제출`

**PASS / REAL_DEVICE**

### 3.4

Guidance / Follow-up

**CONTRACT_READY / MOBILE_FAIL_CLOSED / BACKEND_ROUTE_PENDING**

### 3.5

Technician Visit

**BACKEND_ROUTE_PENDING**
