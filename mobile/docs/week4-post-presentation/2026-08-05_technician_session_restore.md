# 방문기사 앱 저장 세션 자동 복원

## 목적

방문기사 Demo 로그인 성공 후 앱을 종료하거나 다시 실행해도 저장된 인증
토큰을 확인하고 `/me`를 통해 방문기사 세션을 자동 복원한다.

새로운 Backend API를 추가하지 않고 이미 구현된 다음 계약만 사용한다.

- `AuthRepository.hasSession()`
- `AuthRepository.me()`
- `AuthRepository.logout()`
- Backend `GET /health`

방문 목록과 사전 점검 리포트는 계속 합성 Fixture다.

## 동작

### 저장 세션 없음

```text
Backend Health 확인
→ 로그인 화면
```

### 유효한 방문기사 세션

```text
Backend Health 확인
→ /me
→ role_code=TECHNICIAN 검증
→ 기사 홈 자동 진입
→ 합성 방문 목록 로드
```

### 다른 역할의 저장 세션

```text
/me 성공
→ role_code가 TECHNICIAN이 아님
→ 저장 토큰 폐기
→ 기사 앱 진입 차단
```

### 만료 세션

```text
/me 401 또는 403
→ 저장 토큰 폐기
→ 재로그인 안내
```

### Backend 연결 실패

저장 세션을 즉시 폐기하지 않는다. 사용자가 `다시 확인`을 실행하고
Backend가 복구되면 `/me`를 다시 호출해 세션을 복원한다.

## 테스트

- 저장된 방문기사 세션 자동 복원
- 저장된 CUSTOMER 세션 차단과 로그아웃
- 만료 세션 정리
- Backend 복구 후 세션 복원
- 정상 Demo 로그인
- 잘못된 역할 Demo 로그인 차단
- 오프라인 Fixture
- 방문 상세 조회와 닫기

## 제외 범위

- 방문 목록 실제 API
- 방문 수락·출발·도착·완료
- 지도·QR·OCR
- 위치 추적
- Backend·DB 변경
