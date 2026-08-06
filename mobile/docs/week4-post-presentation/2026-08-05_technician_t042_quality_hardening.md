# 방문기사 앱 T-042 품질 보강 2차

## 목적

T-042 최소 골격 완료 이후 프로덕션 기능을 늘리지 않고 테스트 누락과
반복 수동 검증 비용을 줄인다.

방문 목록과 사전 점검 리포트는 계속 합성 Fixture이며, 실제 방문 API가
제공되기 전에는 방문 상태를 변경하는 기능을 추가하지 않는다.

## 변경 범위

### 단위 테스트

- `ExperimentalCoroutinesApi` 명시적 Opt-in
- 정상 방문기사 Demo 로그인
- CUSTOMER 역할 로그인 차단
- Backend 연결 실패 후 재시도
- 오프라인 합성 Fixture 진입
- 사전 점검 리포트 조회
- 상세 화면 닫기 시 선택 상태 초기화

### 자동 Smoke 검증

`mobile/scripts/verify-technician-t042.ps1`은 다음을 한 번에 수행한다.

1. `jeonghyun` 브랜치 확인
2. Backend `/health` HTTP 200 확인
3. 기사 앱 단위 테스트
4. 기사 앱 Debug APK 빌드
5. 연결된 실물 단말 선택
6. `adb reverse tcp:8000 tcp:8000`
7. 기사 APK 설치와 앱 데이터 초기화
8. `MainActivity` 실행
9. Logcat에서 `/health` 요청과 HTTP 200 응답 확인
10. 시작 화면 캡처와 Smoke 보고서 생성

## 실행

Backend가 `127.0.0.1:8000`에서 실행되고 실물 단말이 ADB `device`
상태일 때 저장소 루트에서 실행한다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

& .\mobile\scripts\verify-technician-t042.ps1 `
  -RepoPath "C:\skn29\WaterCare"
```

특정 단말을 지정할 때:

```powershell
& .\mobile\scripts\verify-technician-t042.ps1 `
  -RepoPath "C:\skn29\WaterCare" `
  -DeviceSerial "R3CT8076D7B"
```

정상 결과:

```text
TECHNICIAN_T042_SMOKE_PASS
Report: ...\mobile\build\reports\technician-t042-smoke\...\smoke-report.txt
```

## 제외 범위

- 실제 방문 목록 API
- 방문 수락·출발·도착·완료
- 기사 위치 추적
- 지도와 길찾기
- QR·OCR
- 고객 서명
- Backend·DB 환경 변경

## 완료 기준

- 기사 앱 단위 테스트에 Coroutine Opt-in 경고가 없다.
- CUSTOMER 역할이 기사 화면에 진입하지 못한다.
- Backend 재연결 후 `backendAvailable=true`로 갱신된다.
- 상세 화면을 닫으면 선택된 방문과 리포트 상태가 제거된다.
- 자동 Smoke 검증이 실물 단말에서 HTTP 200 로그를 확인한다.
- 고객 앱 회귀 테스트와 APK 빌드가 유지된다.
