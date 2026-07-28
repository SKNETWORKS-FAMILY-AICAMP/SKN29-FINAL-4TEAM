# WaterCare Android 분리 구조

기존 단일 `app` 모듈을 실제 소스 기준으로 다음 세 모듈로 분리한 결과입니다.

```text
mobile2/
├─ customer-app/       # 기존에 실제로 실행되던 고객 앱
├─ technician-app/     # 방문기사 독립 앱
└─ core/               # 두 앱이 공유하는 순수 Kotlin 모델·상태 전이
```

## 실행

```bat
setup-local-properties.bat
verify-build.bat
```

카카오 네이티브 키가 없더라도 고객 앱은 시연용 지도로 대체됩니다.

## 중요한 판단

원본의 `app/`, `feature/customer/`, `feature/technician/`,
`core/` 하위 파일 다수는 내용이 없는 6줄짜리 골격이며
패키지도 `com.skn29.watercare.skn29.watercare...`로 중복되어 있었습니다.

실제로 실행되는 고객 앱은 다음 코드였습니다.

```text
MainActivity.kt
WaterPurifierDealerApplication.kt
camera/
data/
model/
tracking/
ui/
util/
```

따라서 빈 골격을 기계적으로 이동하지 않고,
실제 실행 코드만 고객 앱에 보존했습니다.

고객 앱의 기존 `applicationId=com.skn29.watercare`는 유지하고, 기사 앱만 별도 ID를 사용합니다.
