# Mobile Runtime API Update — 2026-08-01

## 적용 범위

Backend 파일은 수정하지 않고 `mobile/**`만 변경한다.

### RUNTIME

- `POST /api/v1/inquiries`
- `POST /api/v1/inquiries/{inquiry_id}/cancel`
- 기존 Auth, `/me`, `/health`

### MOCK/BLOCKED 유지

- CUST-03 추가 질문
- CUST-04 Guidance
- CUST-05 상담·방문 전환
- CUST-06 문의 상세·Timeline
- 방문기사 Work List·상세·결과
- 지도·위치 추적

## 주요 변경

1. CUST-02는 `FakeCustomerCareRepository.submitIntake()`를 사용하지 않는다.
2. 확정 DTO인 `CreateInquiryRequest`를 `RemoteInquiryRepository`로 전송한다.
3. 응답의 Public UUID, 업무 코드, 서버 상태 원문, `state_version`, `allowed_actions`, `correlation_id`를 앱 세션에 보존한다.
4. 같은 Payload 재시도는 같은 `Idempotency-Key`를 사용한다. 입력이 바뀌면 새 Key를 만든다.
5. 문의 취소는 Backend가 반환한 `CANCEL_INQUIRY`가 있을 때만 호출한다.
6. 401·403·404·409·422 오류를 공통 처리하고 409 시 입력을 보존한다.
7. 서버 Canonical 상태와 Mobile 표시 상태를 별도 모델로 관리하고 Unknown 원문을 보존한다.
8. Guidance와 상담 화면은 실제 Endpoint가 아니므로 화면에 `Mock/Blocked`를 명시한다.

## 로컬 설정

`mobile/local.properties`에 Backend Demo 고객의 실제 활성 구독 Public UUID를 넣는다.

```properties
BACKEND_BASE_URL=http://127.0.0.1:8000/
DEMO_SUBSCRIPTION_ID=<활성 구독 Public UUID>
```

구독 조회 Runtime이 아직 없기 때문에 이 값은 로컬 Smoke 전용이다. `local.properties`는 Git에 올리지 않는다.

## 검증 순서

```cmd
cd /d C:\skn29\WaterCare\mobile
gradlew.bat :core:test
gradlew.bat :customer-app:testDebugUnitTest
gradlew.bat :customer-app:assembleDebug
```

실기기 연결 후:

1. Demo 고객 로그인
2. CUST-02에서 실제 문의 생성
3. 접수 결과에서 `inquiry_code`, `state_version`, `allowed_actions`, `correlation_id` 확인
4. `CANCEL_INQUIRY`가 표시되면 실제 취소
5. Guidance 미리보기에는 `Mock/Blocked` 표시 확인


## Backend 2026-08-01 회신 반영

- 문의 업무 API 선언과 Repository는 `customer-app` 전용 경계에 둡니다.
- 기존 공통 인증·토큰 인프라는 3모듈 기준선을 깨지 않기 위해 `core`에 유지합니다.
- 409 `allowed_actions`는 객체와 코드 문자열을 모두 읽되, 코드만 받은 경우 label·operation·확인 문구를 생성하지 않습니다.
- 완전한 객체형 행동을 받기 전에는 취소 등 상태 변경 버튼을 비활성화합니다.
- `DEMO_SUBSCRIPTION_ID`는 `local.properties`에서만 주입하며 소스·문서·Git 파일에 실제 UUID를 기록하지 않습니다.
- 정식 구독 조회 `GET /api/v1/me/subscriptions`와 문의 증상 제출 후보 Endpoint는 공유 Runtime 확정 전까지 호출하지 않습니다.

