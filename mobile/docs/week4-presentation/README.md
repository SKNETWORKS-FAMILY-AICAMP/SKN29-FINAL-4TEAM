# 4주차 모바일 중간 발표 자료

## 발표 기준선

- 대상 앱: 고객용 Android 앱
- 기준 브랜치: `personal/mobile-extension`
- 기능 기준 커밋: `e14893e`
- APK: `mobile/customer-app/build/outputs/apk/debug/customer-app-debug.apk`
- 검증 기기: Samsung SM-F721N / Android 16
- Backend 연결: `adb reverse tcp:8000 tcp:8000`

## 현재 준비 상태

- [x] 고객 앱 Debug APK 생성
- [x] 실기기 설치 및 실행
- [x] 저장 Token Cold Start 재사용 확인
- [x] 단위 테스트·Lint·Compose UI Test 통과
- [x] 상담 Runtime 미제공 상태 안전 처리
- [ ] 고객 시연 실행 순서 문서
- [ ] 모바일 구현 상태표
- [ ] 발표 화면 캡처
- [ ] 1~2분 Fallback 영상

## 관련 문서

- 검증 결과: `../week4-mobile-verification.md`
- 제한사항: `../week4-mobile-limitations.md`
- 업무 지침: `../week4-work-guideline.md`

## 발표 원칙

- 실제 API 연동과 Mock·Blocked 화면을 명확히 구분한다.
- Runtime API가 없는 기능을 완료 기능처럼 설명하지 않는다.
- UUID, Token, 사용자 내부 ID가 포함된 로그와 캡처는 배포하지 않는다.
