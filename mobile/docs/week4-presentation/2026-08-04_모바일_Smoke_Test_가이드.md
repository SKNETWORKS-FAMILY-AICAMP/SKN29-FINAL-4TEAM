# 4주차 모바일 발표 Smoke Test 가이드

## 1. 목적

이 문서는 2026년 8월 6일 중간 발표 전에 고객 앱의 빌드·설치·실행 환경을 반복해서 검증하기 위한 기준을 정한다.

검증 대상은 다음과 같다.

- `jeonghyun` 브랜치 여부
- `local.properties` Runtime 설정
- Core 단위 테스트
- 고객 앱 단위 테스트
- 고객 Debug APK 빌드
- Backend Health
- 선택적 ADB 설치와 앱 실행
- 발표용 고객 흐름 수동 확인

지도·GPS·QR은 이번 검증 대상이 아니다. 해당 기능은 확장 기능이므로 `personal/mobile-extension`에서만 진행한다.

## 2. 사전 설정

### 2.1 실제 기기

실제 기기에서 PC의 Backend에 접근할 때는 다음 설정을 사용한다.

```properties
BACKEND_BASE_URL=http://127.0.0.1:8000/
CUSTOMER_CARE_MODE=REMOTE
DEMO_SUBSCRIPTION_ID=<Demo 고객의 실제 활성 구독 Public UUID>
SHOW_DEVELOPER_TOOLS=false
```

스크립트에 `-Install`을 주면 `adb reverse tcp:8000 tcp:8000`을 적용한다.

### 2.2 Android Emulator

```properties
BACKEND_BASE_URL=http://10.0.2.2:8000/
CUSTOMER_CARE_MODE=REMOTE
DEMO_SUBSCRIPTION_ID=<Demo 고객의 실제 활성 구독 Public UUID>
SHOW_DEVELOPER_TOOLS=false
```

`DEMO_SUBSCRIPTION_ID`는 Git에 커밋하지 않는다.

## 3. Build 전용 검증

실제 Backend와 Demo 구독 UUID가 준비되지 않았지만 컴파일과 단위 테스트만 확인할 때 사용한다.

```powershell
cd C:\skn29\WaterCare
powershell -ExecutionPolicy Bypass `
  -File .\mobile\scripts\week4-mobile-smoke-test.ps1 `
  -RepoPath C:\skn29\WaterCare `
  -BuildOnly
```

실행 항목:

```text
:core:test
:customer-app:testDebugUnitTest
:customer-app:assembleDebug
```

## 4. 발표용 실제 검증

Backend가 실행 중이고 실제 Demo 구독 UUID가 설정된 상태에서 실행한다.

```powershell
cd C:\skn29\WaterCare
powershell -ExecutionPolicy Bypass `
  -File .\mobile\scripts\week4-mobile-smoke-test.ps1 `
  -RepoPath C:\skn29\WaterCare `
  -Install
```

앱 데이터를 초기화하고 처음부터 시연할 때는 다음 옵션을 추가한다.

```powershell
-ResetAppData
```

기기가 여러 대 연결된 경우:

```powershell
-DeviceSerial <adb devices에 표시된 Serial>
```

Compose 실기기 테스트까지 실행할 경우:

```powershell
-RunConnectedTest
```

## 5. 자동 검증 완료 기준

다음 항목이 모두 PASS여야 한다.

- 현재 브랜치가 `jeonghyun`
- `BACKEND_BASE_URL`이 올바른 URL이며 `/`로 종료
- REMOTE 모드에서 `DEMO_SUBSCRIPTION_ID`가 UUID 형식
- 발표 검증에서 `SHOW_DEVELOPER_TOOLS=false`
- Core 단위 테스트 성공
- 고객 앱 단위 테스트 성공
- 고객 Debug APK 생성
- Backend `GET /health` 성공
- `-Install` 사용 시 APK 설치와 MainActivity 실행 성공

결과 파일은 다음 위치에 생성된다.

```text
mobile/build/reports/week4-mobile-smoke-test.txt
```

이 결과 파일은 로컬 실행 증빙이며 Git 커밋 대상이 아니다.

## 6. 수동 시연 확인 순서

1. 합성 Demo 고객으로 로그인한다.
2. 고객 홈에서 Backend 연결 상태와 데이터 출처를 확인한다.
3. 제품 모델 `WPUJAC104DWH`와 합성 데이터 표시를 확인한다.
4. 문진 시작 버튼이 실제 Demo 구독 UUID 설정 시에만 활성화되는지 확인한다.
5. 출수량 저하 증상을 입력한다.
6. 실제 문의 생성과 증상 제출을 실행한다.
7. 처리 중 또는 현재 지원되는 안내 화면으로 이동하는지 확인한다.
8. 네트워크를 끊었을 때 Remote 실패가 Fake 성공으로 변경되지 않는지 확인한다.
9. 앱을 다시 실행해 로그인과 주요 상태를 확인한다.

## 7. 실패 시 판단 기준

| 증상 | 우선 확인 |
| --- | --- |
| Health 실패 | Django 실행 여부, 포트 8000, Docker·DB 상태 |
| 실제 기기 연결 실패 | `adb reverse --list`, USB 디버깅 허용 |
| Emulator 연결 실패 | `BACKEND_BASE_URL=http://10.0.2.2:8000/` 여부 |
| 문진 시작 비활성 | `DEMO_SUBSCRIPTION_ID` UUID 설정 여부 |
| 문의 생성 404 | Demo 고객 소유의 활성 구독 UUID인지 확인 |
| 문의 생성 401 | Access Token 만료·Refresh 실패·Demo 재로그인 |
| 문의 생성 409 | 최신 `state_version`, `allowed_actions` 표시 확인 |
| 안내가 Fixture로 표시 | AI 안내 Runtime Endpoint 미제공 상태인지 확인 |

## 8. 발표 당일 원칙

- 발표 기준 Commit을 먼저 기록한다.
- 발표 당일 Dependency와 SDK Version을 변경하지 않는다.
- 차단 결함 수정 후에는 Smoke Test 전체를 다시 실행한다.
- 실제 API, Fixture, 준비 중 기능을 발표 자료에서 구분한다.
- Runtime 실패를 자동 Fake 성공으로 숨기지 않는다.
