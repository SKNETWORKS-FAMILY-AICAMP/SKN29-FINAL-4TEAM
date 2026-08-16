# 5주차 모바일 E2E 결과

## 실단말 검증 완료

- 기기: Samsung SM-F721N / Android 16
- 고객 로그인: PASS
- 활성 구독 목록/상세: PASS
- 문의 생성: PASS
- 증상 제출: PASS
- 고객 문의 Snapshot: PASS
- 고객 미답변 Questions: PASS
- 고객 Follow-up Answers POST: PASS
- Follow-up `state_version` 증가: PASS
- Follow-up 제출 후 Snapshot/Questions 재조회: PASS
- REMOTE에서 Guidance 미제공 시 fail-closed: PASS
- 방문기사 로그인 + `/me`: PASS

## 모바일 안전 경계

- REMOTE에서 고객 Guidance Fixture: **차단**
- Offline/FAKE 미리보기에서 Guidance Fixture: **허용 + 표시**
- REMOTE에서 방문기사 Visit Fixture: **차단**
- 오프라인 미리보기에서 방문기사 Visit Fixture: **허용 + 표시**

## 런타임 대기 항목

- 고객 Guidance 실제 API
- 상담 실제 API
- 방문기사 Visit 실제 API

## 판정

현재 모바일이 실제 백엔드로 검증한 범위는:

`고객 로그인 → 구독 → 문의 생성 → 증상 제출 → Snapshot → Questions → Follow-up Answers → Snapshot/Questions 재조회`

및:

`방문기사 로그인 → 역할 검증`

이다.

Guidance와 Visit은 실제 Runtime이 게시될 때까지
합성 Fixture를 실제 결과로 자동 대체하지 않는 **fail-closed** 상태다.
