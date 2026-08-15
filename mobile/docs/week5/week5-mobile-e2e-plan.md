# 5주차 모바일 E2E 계획

시나리오: W5-MOBILE-P0-001

1. `DEMO-CUSTOMER-001` 실제 로그인
2. 실제 활성 `WPUJAC104DWH` 구독 조회
3. 구독 상세 조회
4. `"출수량이 줄었어요"` 내용으로 문의 생성
5. 반환된 `state_version`으로 증상 제출
6. 실제 Snapshot/Questions를 조회하고 계약에서 제공된 Follow-up 답변만 실제 API로 제출
7. 백엔드가 Guidance를 제공하면 고객 공개용 DTO/Evidence만 표시
8. 백엔드가 상담 요청 API를 제공하면 실제 API로 요청
9. 백엔드가 Visit을 생성·배정하면 `DEMO-TECHNICIAN-001`이 동일 Visit 조회
10. 서버가 제공한 허용 동작만 수행

원칙:
- 모바일에서 DB에 직접 쓰지 않는다.
- Fake 자동 대체를 사용하지 않는다.
- Secret/Token을 검증 근거로 남기지 않는다.
- 외부 공개 ID, `state_version`, `allowed_actions`만 업무 흐름 검증 근거로 사용한다.
