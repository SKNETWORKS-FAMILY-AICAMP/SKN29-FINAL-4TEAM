# 카카오맵 설정

## 네이티브 앱 키

`local.properties`:

```properties
KAKAO_NATIVE_APP_KEY=발급값
```

## 카카오 Developers 등록

```text
앱 → 플랫폼 키 → 네이티브 앱 키
```

Android 앱 정보:

```text
패키지명: com.skn29.watercare
키 해시: Logcat의 KAKAO_KEY_HASH 값
```

## 인증 오류 확인

지도 화면이 비어 있거나 인증 오류가 발생하면 다음을 확인합니다.

1. 네이티브 앱 키 사용 여부
2. 패키지명 일치 여부
3. 디버그 키 해시 등록 여부
4. 인터넷 연결 여부
5. Logcat의 `k3f`, `KAKAO_MAP` 로그
