# 실제 카카오맵 적용

프로젝트 최상위 `local.properties`에 다음 값을 추가한다.

```properties
KAKAO_NATIVE_APP_KEY=재발급받은_네이티브_앱_키
BACKEND_BASE_URL=http://10.0.2.2:8000/
```

카카오 디벨로퍼스 Android 플랫폼에 다음 값을 등록한다.

- 패키지명: `com.skn29.watercare`
- 현재 개발 PC의 디버그 키 해시

키가 정상 등록되면 방문기사 화면에서 실제 카카오맵이 나타나고,
`ic_marker_technician.png`의 물방울 기사 캐릭터가 시연 좌표를 따라 이동한다.
