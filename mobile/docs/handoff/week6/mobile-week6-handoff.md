# 모바일 6주차 인계 문서

## 5주차 고정 기준

고객:

```text
실제 인증
→ 실제 구독 목록/상세
→ 실제 subscription_id 선택
→ 실제 문의 생성
→ 실제 증상 제출
```

방문기사:

```text
실제 인증
→ Visit Runtime 미제공 시 fail-closed
→ 명시적 Offline Preview에서만 synthetic Fixture
```

## 백엔드 Runtime 개방 즉시 연결 순서

1. 고객 Follow-up
2. 고객 Guidance / Evidence
3. 고객 상담 요청
4. 방문기사 배정 Visit 목록/상세
5. 방문기사 Visit 시작/완료/결과
6. 전체 고객 → AI → 상담 → 방문 → 방문기사 E2E

## 6주차 모바일 허용 범위

- 잔여 UI/UX 버그
- 배포 백엔드 Base URL 반영
- 접근성 / 긴 문구 / Touch target 마감
- 성능·안정성
- Release APK 또는 시연 APK 검증
- 문서·스크린샷·발표 지원

## 금지

- 모바일 전용 가짜 Endpoint 생성
- Remote 실패 시 Fixture 자동 대체
- Visit 상태 임의 생성
- `WAITING_COMPLETION`을 `COMPLETED`로 처리
- AI FastAPI / LLM / Vector DB 직접 호출
- 실제 Token / Secret / 개인정보 로그 출력
- E2E 통과를 위한 DB 직접 수정

```text
MOBILE_INDEPENDENT_ACTIONABLE_ITEMS = COMPLETE
INDEPENDENT_MOBILE_WEEK5 = PASS
FULL_P0_FEATURE_COMPLETE = BLOCKED_BY_BACKEND
```
