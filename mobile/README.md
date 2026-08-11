# WaterCare Android — 3주차 모바일 구현 기준선

WaterCare Android 프로젝트는 `core`, `customer-app`, `technician-app` 3개 모듈로 구성되며 Kotlin, Jetpack Compose, Material 3, Navigation Compose, ViewModel, StateFlow, Kotlinx Serialization, Retrofit, OkHttp를 사용한다.

## 모듈 구성

- `core`: 실제 백엔드 인증·상태 확인·문의 네트워크, 토큰 재발급, 공통 모델, 오류 매핑, 고객 케어 Fake 데이터, 테마 및 공통 기본 UI를 담당한다.
- `customer-app`: CUST-01 고객 홈 → CUST-02 증상 입력 → CUST-04 AI 안전 안내 흐름을 담당한다.
- `technician-app`: 실제 기사 데모 인증과 아직 라우팅되지 않은 API의 명시적인 준비 중 화면을 담당한다.

Fake 구현체는 의도적으로 `FakeCustomerCareRepository`라는 이름을 사용한다. 이 구현체는 제품·구독 조회 및 AI 안내 API가 준비되었을 때 교체하는 지점이며 실제 개인정보를 포함하지 않는다.

## 구현된 3주차 고객 흐름

1. 실제 `GET /health` 상태 확인
2. `DEMO-CUSTOMER-001` 계정을 사용한 실제 `POST /api/v1/auth/demo-login`
3. CUST-01 테스트 제품 `WPUJAC104DWH` / `WPU-JAC104D`, 관리 유형, 문진 상태, 진행 중 문의 표시
4. CUST-02 복수 증상 선택, 고객 원문, 발생 조건, 화면·오류 문구, 진입 유형, 필수값 검증, 중복 제출 차단, 실패 후 입력값 유지
5. 409 상태 충돌이 발생해도 CUST-02 작성 내용을 유지하고 최신 상태, `state_version`, `allowed_actions`를 표시
6. `+09:00` API 시간을 중복 변환하지 않고 표시
7. CUST-04 안전 안내 표시 순서: 현재 행동 → 위험도·사용 제한 → 안전 행동 → 상담 전환 조건 → 근거 → 증상 요약 → 금지 행동
8. 정상, 주의, 위험, 근거 없음, AI 실패, 네트워크 실패 시나리오 제공
9. 위험·근거 없음·상담 필요 상태에서는 해결 완료 및 문의 종료 기능을 표시하지 않음
10. 근거 UI에는 문서명, 버전, 페이지, 구조화 요약, 검증 상태, 분류, 백엔드가 제공한 공식 URL만 표시한다. `chunk_id`, 원본 경로, 검색 원문, 전체 문서 원문은 표시하지 않는다.

## 백엔드 준비

현재 저장소에는 `START_WEEK3_BACKEND.cmd`가 없으므로 존재하지 않는 Script를 실행 방법으로 안내하지 않는다.

수동 실행 방법:

```cmd
cd /d C:\skn29\WaterCare

docker compose --env-file backend\.env -f docker-compose.yml -f docker-compose.local.yml up -d postgres
cd backend
.\.venv\Scripts\python.exe manage.py migrate --noinput
.\.venv\Scripts\python.exe manage.py seed_week3_demo
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

Django 서버는 `127.0.0.1:8000`에서 실행한다. `.env` 파일은 소스 압축 파일과 Git에 포함하지 않는다.

## 기기 네트워크 설정

`local.properties.example`을 `local.properties`로 복사하고 Git 추적 대상에서 제외한다.

실제 Android 기기:

```properties
BACKEND_BASE_URL=http://127.0.0.1:8000/
```

```cmd
"C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000
"C:\Users\Playdata\AppData\Local\Android\Sdk\platform-tools\adb.exe" reverse --list
```

Android 에뮬레이터:

```properties
BACKEND_BASE_URL=http://10.0.2.2:8000/
```

## 빌드 및 테스트

```cmd
cd /d C:\skn29\WaterCare\mobile

gradlew.bat clean
gradlew.bat :core:testDebugUnitTest
gradlew.bat :customer-app:testDebugUnitTest
gradlew.bat :customer-app:assembleDebug
gradlew.bat :technician-app:assembleDebug
```

실제 기기 Compose 테스트:

```cmd
gradlew.bat :customer-app:connectedDebugAndroidTest
```

APK 생성 경로:

- `customer-app\build\outputs\apk\debug\customer-app-debug.apk`
- `technician-app\build\outputs\apk\debug\technician-app-debug.apk`

## 실제 연동과 Fake 구현 경계

모바일에서 사용하는 실제 백엔드 경로:

- `GET /health`
- `POST /api/v1/auth/demo-login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/me`
- `POST /api/v1/inquiries`
- `POST /api/v1/inquiries/{inquiry_id}/submit`
- `POST /api/v1/inquiries/{inquiry_id}/cancel`

제품·구독 조회, AI 안내·공식 근거 조회, 상담, 방문 관련 경로는 현재 모바일에서 사용할 수 있는 확정 Runtime Endpoint가 없다. 존재하지 않는 운영 Endpoint를 임의로 만들지 않고 Fake 구현 또는 `API 준비 중` 화면으로 유지한다.

## 4주차 부분 Remote 연결 상태

4주차 연동에서는 CUST-02 기본 제출 흐름을 다음 두 Runtime Endpoint에 연결한다.

1. `POST /api/v1/inquiries`로 문의를 `DRAFT` 상태로 생성한다.
2. 생성 응답의 `inquiry_id`, `state_version`을 사용해 `POST /api/v1/inquiries/{inquiry_id}/submit`을 호출한다.
3. 증상 제출 성공 후 `QUESTIONNAIRE_IN_PROGRESS`, 새 `state_version`, `allowed_actions`를 보관한다.

- 고객 문의 생성·증상 제출: Remote
- 인증·Health: Remote
- 고객 홈 제품·구독 조회: 명시적 Mock — Runtime Endpoint 대기
- AI 안내·공식 근거 조회: 명시적 Mock — Runtime Endpoint 대기
- 상담 요청: `API 준비 중` 안내 — 빈 Callback 및 가짜 성공 처리 금지

문의 생성 성공 후 증상 제출이 실패하면 동일 문의와 동일 제출용 Idempotency Key로 재시도한다. Remote 요청 실패를 Mock 성공 결과로 자동 대체하지 않는다.

현재 고객 홈의 구독 ID는 명시적 Mock이므로 실제 Runtime 검증에서는 Demo 고객의 활성 구독 UUID를 일시 적용하고 검증 직후 복구했다. 운영용 활성 구독 ID 공급 경로는 Backend 계약 확정 전까지 `REVIEW_REQUEST / IMPLEMENTATION_HOLD`로 유지한다.

상세 검증 결과는 `docs/week4-mobile-verification.md`에서 확인한다.


## 4주차 발표 Smoke Test

발표 전 모바일 검증은 다음 PowerShell Script를 사용한다.

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\scripts\week4-mobile-smoke-test.ps1 `
  -RepoPath C:\skn29\WaterCare `
  -BuildOnly
```

실제 Backend와 단말을 함께 검증할 때는 `-Install`을 사용한다.

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\scripts\week4-mobile-smoke-test.ps1 `
  -RepoPath C:\skn29\WaterCare `
  -Install
```

관련 문서:

- `docs/week4-presentation/2026-08-04_모바일_Smoke_Test_가이드.md`
- `docs/week4-presentation/2026-08-04_모바일_구현_상태표.md`
- `docs/week4-presentation/2026-08-04_모바일_제한사항.md`
- `docs/week4-presentation/2026-08-04_모바일_Smoke_Test_체크리스트.md`

<!-- WEEK5_MOBILE_STATUS_BEGIN -->
## Week 5 Mobile Remote status

- Customer: actual auth + subscription list/detail/select + inquiry create/submit
- Technician: actual auth; Visit Runtime absent → Remote fails closed
- Fake/Fixture: explicit offline/demo mode only, never automatic Remote success
- Current Runtime matrix: mobile/docs/week5/week5-mobile-api-runtime-matrix.md
- Regression: mobile/docs/week5/week5-mobile-regression.md
- Full E2E: $fullE2E
<!-- WEEK5_MOBILE_STATUS_END -->
