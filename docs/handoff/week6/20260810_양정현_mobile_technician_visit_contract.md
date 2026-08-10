# Mobile 3.5 Technician Visit API 계약 준비서

- 작성 기준 branch: `jeonghyun`
- T083 시작 기준 commit: `de36e048f7e992f797195201f621e0f2f79ea6a9`
- 포함된 latest main: `2198e9e90fe894fb848d551ef638fb3ae0a2b433`
- 담당 범위: Mobile
- 상태: **CONTRACT_READY / MOBILE_FAIL_CLOSED / BACKEND_ROUTE_PENDING**
- 원칙: 방문 Runtime이 실제 등록되기 전에는 기사 앱이 합성 방문 데이터를 실제 배정 방문처럼 사용하지 않는다.

---

## 1. 현재 Runtime 판정

현재 `/api/v1` 통합 URL에는 아래만 등록되어 있다.

- accounts
- subscriptions
- inquiries

따라서 visits 앱의 Model·Migration·OpenAPI/계약 자료가 존재하더라도
기사 방문 Runtime이 실제로 게시된 것은 아니다.

현재 Mobile이 실제 호출 가능한 기사 범위:

- Demo Technician 로그인
- `/api/v1/me` 역할 확인

현재 Mobile이 실제 호출할 수 없는 기사 방문 범위:

- 방문 목록
- 방문 상세
- 사전 점검/인계 Projection
- 방문 결과 등록

---

## 2. 기존 Backend SAFE_HANDOFF 기준

기존 Backend·Mobile 안전 연동 가이드에 명시된 방문 후보 경로:

```http
GET  /api/v1/technician/visits
GET  /api/v1/technician/visits/{id}
POST /api/v1/technician/visits/{id}/results
```

현재 상태는 **설계/계약 후보이며 Runtime Route가 아니다.**

Backend가 실제 Route·Serializer·Permission·Service·Test를 같은 변경 단위로
게시한 뒤 Mobile이 실제 Endpoint로 선언한다.

---

## 3. 현재 Mobile fail-closed 경계

### 실제 로그인 / REMOTE

기사 앱은 실제 로그인 이후 방문 데이터에
`BlockedTechnicianVisitRepository`를 사용한다.

방문 Runtime이 없으면:

```text
VISIT_RUNTIME_UNAVAILABLE
```

로 실패한다.

원칙:

- 방문 목록을 합성 Fixture로 자동 대체하지 않음
- 방문 상세를 합성 Fixture로 자동 대체하지 않음
- 실제 고객 이름/주소/전화번호를 추정하지 않음
- 실제 방문 완료/출발/도착 결과를 생성하지 않음

### Offline Preview

오프라인 미리보기에서만 `FakeTechnicianVisitRepository`를 사용한다.

화면에는 아래가 명확히 표시되어야 한다.

- 합성 Fixture
- Scenario ID
- 실제 고객 개인정보 미사용
- 실제 방문 업무 API 미제공

---

## 4. Mobile 표시 계약

현재 `TechnicianVisitSummary`가 필요로 하는 표시 필드:

- `visitId`
- `visitCode`
- `customerMaskedName`
- `maskedAddress`
- `productModel`
- `scheduledAt`
- `scheduleStatusCode`
- `symptomSummary`
- `risk`
- `usageRestrictionLabel`
- `isSynthetic`

현재 `TechnicianPrecheckReport` 표시 필드:

- `visitId`
- `visitCode`
- `customerMaskedName`
- `customerMaskedPhone`
- `maskedAddress`
- `productModel`
- `scheduledAt`
- `symptomSummary`
- `consultationSummary`
- `inspectionCandidates`
- `safetyNotice`
- `prohibitedActions`
- `evidence`
- `isSynthetic`

Mobile 내부 `scenarioId`는 Fixture/UI 검증용 식별자이며
Backend 실데이터 계약에 그대로 요구하지 않는다.

---

## 5. PROPOSED — 방문 목록

> 아래 Response shape은 Mobile 소비 관점 제안이다.
> 실제 Backend Serializer가 확정되면 해당 계약을 소스로 사용한다.

```http
GET /api/v1/technician/visits
Authorization: Bearer <access_token>
```

권한:

- `TECHNICIAN`
- 본인에게 배정된 방문만 반환

최소 응답 Projection:

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "visit_id": "uuid",
        "visit_code": "VIS-...",
        "customer_masked_name": "김○○",
        "masked_address": "서울시 ...",
        "product_model": "WPUJAC104DWH",
        "scheduled_at": "ISO-8601",
        "schedule_status_code": "CONFIRMED",
        "symptom_summary": "출수량 저하",
        "risk_level": "GENERAL",
        "usage_restriction_label": "현재 즉시 사용 중지 징후 없음",
        "visit_state_version": 1,
        "inquiry_state_version": 3
      }
    ]
  }
}
```

Mobile 요구:

- 고객 개인정보는 Masked Projection으로만 전달
- 기사 본인 배정 여부는 Backend 권한으로 검증
- `UNKNOWN` 위험도는 정상으로 추정하지 않음

---

## 6. PROPOSED — 방문 상세 / 사전 점검

```http
GET /api/v1/technician/visits/{visit_id}
Authorization: Bearer <access_token>
```

최소 요구:

- 방문 Public ID / Code
- Masked 고객 표시정보
- 제품 모델
- 방문 예정 시각/상태
- 고객 증상 요약
- 상담 인계 요약
- 우선 점검 후보
- 안전/사용 제한
- 금지 행동
- 검증된 Evidence
- `visit_state_version`
- `inquiry_state_version`

중요:

Backend SAFE_HANDOFF 기준상 방문 결과 처리에는
**Inquiry version과 Visit version을 구분**해야 한다.

Mobile은 두 version을 하나의 숫자로 합치지 않는다.

---

## 7. PROPOSED — 방문 결과 등록

기존 후보:

```http
POST /api/v1/technician/visits/{visit_id}/results
```

그러나 기존 Backend 인계 기준에서는
정상 완료와 재방문을 행동별 Endpoint로 분리하는 방향도 언급되어 있으므로
**실제 Backend 계약 확정 전 Mobile에 Endpoint를 추가하지 않는다.**

최소 공통 요구:

Headers:

- `Authorization`
- `Idempotency-Key`
- `X-Correlation-ID`

Concurrency:

- `visit_state_version`
- `inquiry_state_version`

Conflict:

- stale version → 409
- 최신 상태/version/allowed_actions 반환

Mobile은 현장 결과 처리 Runtime이 열리기 전까지:

- 완료 버튼 실제 전송 금지
- 재방문 확정 금지
- 위치/ETA/GPS/Tracking 기능 추가 금지

---

## 8. 검증 Gate

완료:

- [x] 실제 Technician 로그인
- [x] `/me` role = `TECHNICIAN`
- [x] REMOTE Visit repository fail-closed
- [x] 방문 목록 fail-closed Unit Test
- [x] 방문 상세 fail-closed Unit Test
- [x] Offline Fixture repository 분리
- [x] 실제 고객 개인정보 미사용
- [x] Visit API 계약 준비

Backend 대기:

- [ ] visits 앱 `/api/v1` 등록
- [ ] technician visits list route
- [ ] visit detail route
- [ ] masked customer projection 확정
- [ ] assigned-technician permission test
- [ ] result endpoint 확정
- [ ] dual state-version conflict test
- [ ] idempotency replay
- [ ] Galaxy actual Visit Runtime instrumentation

---

## 9. Backend Route 게시 후 Mobile 작업 순서

1. latest main → jeonghyun 통합
2. 실제 URL/Serializer/OpenAPI 확인
3. `WaterCareApi`에 실제 route만 추가
4. Visit DTO/Mapper 작성
5. `RemoteTechnicianVisitRepository` 구현
6. `BlockedTechnicianVisitRepository`를 Runtime 구현으로 교체
7. 401/403/404/409 Error Mapper
8. Unit Test
9. Backend REST Smoke
10. Galaxy instrumentation
11. Runtime Matrix 갱신
12. `jeonghyun` normal push

---

## 10. 현재 판정

### 3.3 Customer P0

**PASS / REAL_DEVICE**

### 3.4 Guidance / Follow-up

**CONTRACT_READY / MOBILE_FAIL_CLOSED / BACKEND_ROUTE_PENDING**

### 3.5 Technician Visit

**CONTRACT_READY / MOBILE_FAIL_CLOSED / BACKEND_ROUTE_PENDING**
