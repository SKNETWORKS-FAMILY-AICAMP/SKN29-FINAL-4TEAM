# 방문기사 앱 T-042 최소 골격

## 작업 목적

중간 발표용 고객 앱 기준선 `da6fe43` 이후 방문기사 앱의 정적 Demo 화면을
`TechnicianViewModel`과 `StateFlow` 기반 구조로 전환한다.

Backend 방문 API가 아직 제공되지 않았으므로 방문 목록과 사전 점검 리포트는
명시적인 합성 Fixture로 구성한다. 실제 고객 정보나 방문 완료 성공 처리를
가짜로 만들지 않는다.

## 구현 범위

- 방문기사 Demo 로그인
- Backend Health 상태 표시
- 합성 Fixture 미리보기
- 배정 방문 목록
- 방문 상태와 위험도 표시
- 고객 이름·전화번호·주소 마스킹
- 읽기 전용 사전 점검 리포트
- 상담 확인 내용
- 우선 점검 후보
- 안전·사용 제한
- 금지 행동
- 공식 근거
- Repository·ViewModel 단위 테스트

## 제외 범위

- 지도와 길찾기
- 기사 위치 추적
- QR·OCR
- 방문 수락·출발·도착·완료
- 고객 서명
- 실제 방문 API 성공 처리

## 데이터 출처

Demo 로그인은 실제 Backend 인증을 사용한다.

방문 목록과 사전 점검 리포트는 다음과 같이 화면에 출처를 표시한다.

```text
Demo 인증 + 합성 방문 Fixture
방문 API 미제공
실제 고객 개인정보 미사용
Scenario ID 표시
```

## 구조

```text
TechnicianApp
    ↓ StateFlow 구독
TechnicianViewModel
    ├─ AuthRepository
    ├─ BackendStatusRepository
    └─ TechnicianVisitRepository
            └─ FakeTechnicianVisitRepository
```

방문 API가 제공되면 `TechnicianVisitRepository` 인터페이스는 유지하고
Remote 구현체를 추가한다.

## 검증 명령

```powershell
cd C:\skn29\WaterCare\mobile

.\gradlew.bat `
  :technician-app:testDebugUnitTest `
  :technician-app:assembleDebug `
  --no-daemon
```

고객 앱 회귀 확인:

```powershell
.\gradlew.bat `
  :core:test `
  :customer-app:testDebugUnitTest `
  :customer-app:assembleDebug `
  --no-daemon
```

## 완료 기준

- `TechnicianApp`이 화면 내부 Coroutine으로 인증 상태를 직접 관리하지 않는다.
- `TechnicianViewModel`이 실제 화면에서 사용된다.
- 방문 목록이 Composable 내부 상수로 직접 선언되지 않는다.
- 방문 상세 화면은 읽기 전용이다.
- 실제 고객 개인정보가 포함되지 않는다.
- 미지원 기능을 성공한 기능처럼 표시하지 않는다.
- 기사 앱 단위 테스트와 Debug APK 빌드가 성공한다.
- 고객 앱 회귀 테스트와 APK 빌드가 성공한다.
