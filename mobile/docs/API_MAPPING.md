# 백엔드 API와 모바일 기능 대응표

| 백엔드 경로 | 고객 앱 | 방문기사 앱 | 구현 상태 |
|---|---|---|---|
| `GET /health` | 연결 상태 표시 | 연결 상태 표시 | 실제 연동 |
| `POST /api/v1/auth/demo-login` | 데모 고객 | 데모 방문기사 | 실제 연동 |
| `POST /api/v1/auth/refresh` | 401 이후 1회 자동 갱신 | 401 이후 1회 자동 갱신 | 실제 core 인증 처리 |
| `POST /api/v1/auth/logout` | 로그아웃 | 로그아웃 | 실제 연동 |
| `GET /api/v1/me` | 인증 사용자 정보 | 역할 정보 | 실제 연동 |
| `POST /api/v1/inquiries` | 원격 Repository 교체 지점 | 사용하지 않음 | 실제 계약/클라이언트 |
| `POST /api/v1/inquiries/{id}/cancel` | 원격 Repository 교체 지점 | 사용하지 않음 | 실제 계약/클라이언트 |
| 제품/구독 조회 | CUST-01 합성 Fixture | 대기 | 백엔드 경로 없음 |
| 문진/안내 | CUST-02/04 결정적 Fake | 조치 결과 대기 | 백엔드 경로 없음 |
| 상담/방문/위치 | 버튼/대기 상태만 표시 | 대기 카드 | 백엔드 경로 없음 |

지원되지 않는 비밀번호 로그인, 회원가입, 고객 프로필 경로는 `backend/config/api_urls.py`에 존재하지 않으므로 Retrofit 인터페이스에서 제거했습니다.

UI는 Repository 인터페이스에 의존합니다. 계약과 백엔드 경로가 병합되면 화면이나 ViewModel을 다시 작성하지 않고 원격 구현을 추가한 뒤 Repository 할당만 교체합니다.
