# WaterCare 고객 앱

## Backend 연결 방식

고객 앱은 Backend 환경별 Android Product Flavor를 사용합니다.

### Local Debug

- Variant: `localDebug`
- Package: `com.skn29.watercare.customer.local`
- Backend: `mobile/local.properties`의 `LOCAL_BACKEND_BASE_URL`
- 현재 개발 예시: `http://192.168.0.25:8000/`
- Debug에서만 평문 HTTP 허용
- 같은 Wi-Fi에서 USB/`adb reverse` 없이 사용 가능

빌드:

```powershell
.\gradlew.bat :customer-app:assembleLocalDebug
```

APK:

```text
customer-app/build/outputs/apk/local/debug/customer-app-local-debug.apk
```

### AWS Debug

- Variant: `awsDebug`
- Package: `com.skn29.watercare.customer`
- Backend: `https://waterbridge.site/`
- Mobile은 RDS 또는 AI Runtime 8001에 직접 연결하지 않음
- 모든 고객 기능은 WaterBridge Backend API를 통해 호출

빌드:

```powershell
.\gradlew.bat :customer-app:assembleAwsDebug
```

APK:

```text
customer-app/build/outputs/apk/aws/debug/customer-app-aws-debug.apk
```

## 버전 관리

`mobile/gradle.properties`에서 관리합니다.

```text
WATERBRIDGE_VERSION_CODE=2
WATERBRIDGE_VERSION_NAME=1.0.1
```

배포 업데이트 시 `versionCode`는 반드시 증가시킵니다.

## Release 서명

AWS Release APK는 팀에서 확정한 동일한 공식 JKS를 계속 사용합니다.

- 예시 설정: `mobile/keystore.properties.example`
- 실제 설정: `mobile/keystore.properties`
- 공식 JKS 예시 위치: `mobile/signing/waterbridge-release.jks`
- 실제 JKS와 비밀번호는 Git에 커밋하지 않음

기존 Release APK 위에 업데이트하려면 동일한 `applicationId`, 동일한 서명키, 더 높은 `versionCode`가 필요합니다.

공식 JKS가 준비되기 전에는 임의 키로 최종 Release APK를 만들지 않습니다.

## 네트워크 보안

- Release: 평문 HTTP 차단
- Debug: Local 개발용 HTTP 허용
- AWS Backend: `https://waterbridge.site/`
- RDS 및 AI Runtime은 Mobile에서 직접 호출하지 않음
