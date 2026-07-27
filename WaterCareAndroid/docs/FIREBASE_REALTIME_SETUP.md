# Firebase Realtime Database 연결 절차

starter는 빌드 즉시 실행되도록 인메모리 실시간 저장소를 사용한다. Firebase를 붙일 때 다음 순서로 교체한다.

1. Firebase Console에서 Android 앱 `com.skn29.watercare` 등록
2. `google-services.json`을 `app/`에 추가
3. Google Services Gradle plugin 추가
4. Firebase Android BoM과 `firebase-database` 의존성 추가
5. `TrackingRepository`를 `FirebaseVisitTrackingRepository`로 교체

권장 경로:

```text
visitTracking/{visitId}/latest
visitTracking/{visitId}/members/{uid}
```

보안 규칙은 해당 방문의 고객과 담당 기사만 읽고 쓸 수 있도록 제한해야 한다. 기사 위치는 `EN_ROUTE` 동안만 저장하고 `IN_PROGRESS`, `COMPLETED`, `CANCELLED` 진입 시 삭제 또는 만료 처리한다.
