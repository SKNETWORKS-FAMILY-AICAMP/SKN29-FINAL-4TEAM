# 2026-08-10 양정현 Mobile Week5 → Week6 Handoff

## 1. Fixed baseline

### Customer actual Backend

- `SYN-CUSTOMER-001` 실제 로그인
- `/me` CUSTOMER 역할 확인
- ACTIVE `WPUJAC104DWH` 구독 목록/상세/select Remote
- Inquiry create 실제 API
- Symptom submit 실제 API
- Samsung Galaxy SM-F721N / Android 16 실단말 검증
- Customer Remote instrumentation P0 flow PASS

검증된 실제 흐름:

```text
login
→ active subscription
→ inquiry create
→ symptom submit
```

### Guidance / Evidence

현재 Customer Guidance Runtime route는 게시되지 않았다.

Mobile 상태:

- API 계약 준비 완료
- REMOTE에서 Fixture 자동 fallback 차단
- `GUIDANCE_ROUTE_UNAVAILABLE` fail-closed
- Offline/FAKE Preview에서만 합성 Guidance 허용
- 합성 Preview provenance 표시
- Galaxy REMOTE fail-closed instrumentation PASS

상태:

```text
CONTRACT_READY
MOBILE_FAIL_CLOSED
BACKEND_ROUTE_PENDING
```

### Technician

- Demo Technician 실제 로그인
- `/me` TECHNICIAN 역할 확인
- Samsung Galaxy 실단말 Auth PASS
- REMOTE Visit list/detail은 `VISIT_RUNTIME_UNAVAILABLE` fail-closed
- Offline Preview에서만 synthetic Visit Fixture 사용
- Visit API 계약 준비 완료

상태:

```text
CONTRACT_READY
MOBILE_FAIL_CLOSED
BACKEND_ROUTE_PENDING
```

---

## 2. Week5 completion decision

### 3.1 Mobile baseline/runtime matrix

**DONE**

- build/test/APK gate 재검증
- 최신 main 포함
- Runtime / Contract / Blocked 구분

### 3.2 Customer subscription Remote

**DONE / REAL_DEVICE_PASS**

### 3.3 Inquiry + symptom actual flow

**DONE / REAL_DEVICE_PASS**

### 3.4 Guidance / Follow-up

**MOBILE PREWORK DONE**

Backend Runtime 미게시로 실제 Guidance/Follow-up E2E는 차단됨.

Mobile은 Fake 성공으로 대체하지 않고 다음까지 완료:

- 계약 준비
- fail-closed
- Offline Fixture 격리
- real-device fail-closed regression

### 3.5 Technician Visit

**MOBILE PREWORK DONE**

Backend Runtime 미게시로 실제 Visit E2E는 차단됨.

Mobile은 다음까지 완료:

- 실제 Technician auth
- Visit fail-closed boundary
- Offline Fixture 격리
- Visit 계약 준비

---

## 3. Remaining Backend dependencies

다음은 Mobile이 임의 구현하지 않는다.

- Customer-authorized inquiry read/recovery
- Follow-up/questionnaire Runtime
- Guidance/Evidence Runtime
- Consultation request Runtime
- Technician Visit list/detail/action/result Runtime

실제 Route·Serializer·Permission·Test가 main에 게시되면
Mobile은 latest main을 다시 통합하고 Remote Repository를 연결한다.

---

## 4. Real-device evidence

Device:

```text
Samsung SM-F721N
Android 16
```

Customer:

```text
CustomerRemoteBackendSmokeTest
- guidanceWithoutCustomerRoute_remoteModeFailsClosed
- login_subscriptionDetail_createAndSubmit_realBackend

OK (2 tests)
```

Technician:

```text
TechnicianRemoteAuthSmokeTest
OK (1 test)
```

---

## 5. Safety boundary

- 실제 API 실패를 Fake 성공으로 숨기지 않는다.
- Backend가 제공하지 않은 State/Action/AI 결과를 Mobile이 생성하지 않는다.
- Customer Guidance Fixture는 Offline/FAKE에서만 사용한다.
- Technician Visit Fixture는 Offline Preview에서만 사용한다.
- Mobile은 AI/LLM/VectorDB를 직접 호출하지 않는다.
- 실제 고객 개인정보를 synthetic Fixture로 대체해 실제 데이터처럼 표현하지 않는다.
- Visit 위치추적/ETA/GPS는 현재 Runtime 범위로 선언하지 않는다.

---

## 6. Week6 first action

Backend main에 신규 Runtime이 들어오면 아래 순서로 진행한다.

1. main → jeonghyun 통합
2. 실제 Route/Serializer/OpenAPI 확인
3. DTO/Repository 실제 연결
4. 401/403/404/409/Error Mapper 검증
5. state version / idempotency 검증
6. Backend REST smoke
7. Galaxy instrumentation
8. Runtime Matrix 갱신
9. `jeonghyun` normal push

---

## 7. Release rule

현재 Mobile Week5 범위는 **가능한 실제 Runtime까지 연동 완료**되었다.

그러나 아래가 미게시이므로 전체 서비스 Feature Complete로 선언하지 않는다.

```text
Guidance / Follow-up
Consultation
Technician Visit
```

현재 최종 판정:

```text
Customer P0: REAL_DEVICE_PASS
Guidance: CONTRACT_READY / MOBILE_FAIL_CLOSED / BACKEND_ROUTE_PENDING
Follow-up: CONTRACT_READY / BACKEND_ROUTE_PENDING
Technician Visit: CONTRACT_READY / MOBILE_FAIL_CLOSED / BACKEND_ROUTE_PENDING
Overall full E2E: BLOCKED_BY_BACKEND
```
