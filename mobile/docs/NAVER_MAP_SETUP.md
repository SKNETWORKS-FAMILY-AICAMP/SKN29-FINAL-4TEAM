# 네이버 지도 설정

1. NAVER Cloud Platform에서 Maps 서비스와 Android 앱 등록
2. 앱 패키지명: `com.skn29.watercare`
3. 발급받은 Client ID를 `local.properties`에 입력

```properties
NAVER_MAP_CLIENT_ID=발급값
```

`AndroidManifest.xml`에는 Gradle manifest placeholder가 연결되어 있다.

경로와 ETA는 지도 SDK가 아니라 별도의 Directions API 또는 백엔드에서 계산해야 한다. 현재 starter는 발표 안정성을 위해 미리 저장된 경로와 단순 ETA 감소 로직을 사용한다.
