# 3주차 Web 테스트 결과

- 기준일: 2026-07-29
- 실행 위치: `web/`
- 자동화 도구: Vitest, jsdom, React Testing Library

## 자동화 범위

| 구분 | 검증 내용 |
| --- | --- |
| 단위 | 상담 임시 저장·완료·방문 검토 Validation |
| 단위 | 방문 일정 저장·확정 필수값과 날짜 순서 Validation |
| 단위 | 요청별 `Idempotency-Key`, `X-Correlation-ID` 생성 |
| 단위 | 공통 API Wrapper·HTTP 오류 분류·PageInfo 정규화 |
| 단위 | 담당자·우선순위·기간 필터와 페이지 범위 보정 |
| 단위 | UUID `inquiry_id`와 표시용 `inquiry_code` 분리·검증 |
| 컴포넌트 | `allowed_actions` 기반 버튼 노출 |
| 컴포넌트 | 완료 필수값과 필드 오류 연결 |
| 컴포넌트 | 409 충돌 후 입력 유지, 최신 `stateVersion` 반영 |
| 컴포넌트 | 허용 행동이 없는 상태의 버튼 미노출 |
| 컴포넌트 | 방문 전환 필드 노출, 입력 유지, Mock 저장·확정 |
| 컴포넌트 | 공통 EvidenceCard 공개 필드·HTTPS 링크 제한 |
| 컴포넌트 | 공통 DataTable 행·빈 상태 접근성 |
| 통합 | 상담 큐에서 문의 선택 후 상세·상담 Form 전환 |
| 통합 | 위험도 필터로 위험 문의 두 건 조회 |
| 통합 | 담당자·페이지 조건 URL Query 복원 |
| 통합 | 목록 선택 후 UUID `/consultant/inquiries/{inquiry_id}` 상세 경로 전환 |
| 통합 | 표시용 `inquiry_code`의 상세 URL 리소스 ID 사용 차단 |
| 통합 | 상세 근거 부분 실패 시 다른 영역 유지 |
| 통합 | 방문 행동이 없는 문의의 CONS-03 진입 차단 |
| 통합 | 미인증 사용자의 로그인 이동 |
| 통합 | Mock 로그인 후 원래 요청 경로 복귀 |
| 통합 | 상담사·운영자 Route 역할 허용과 403 차단 |
| 통합 | ADMIN-01 Placeholder 접근 |
| 통합 | 등록되지 않은 경로의 404 분리 |

## 실행 명령

```powershell
npm.cmd run test
npm.cmd run lint
npm.cmd run build
```

## 2026-07-29 실행 결과

- `npm.cmd test`: **12개 Test File, 44개 Test 통과**
- `npm.cmd run lint`: 통과
- `npm.cmd run build`: 통과
- Production 번들: Vite Build 성공

## 수동 브라우저 검증 병행 항목

- 상담 진행 문의 Form 레이아웃
- 빈 값 완료 처리 시 필드별 오류
- Mock 성공 후 `stateVersion` 증가
- 409 충돌 후 작성 내용 유지와 자동 재시도 방지
- 문진 상태에서 행동 버튼 미노출
- 공식 근거에서 `chunk_id`, 내부 `document_id` 미노출
- UUID `/consultant/inquiries/{inquiry_id}` 상세 경로 회귀
- `/consultant/inquiries/a6bdf6b7-b9ba-553a-8447-f928384c1ad1/visit-transition` 직접 접근과 v13 레이아웃
- 방문 전환 필수값 오류, 희망일·기사 선택, Mock 저장·확정, `stateVersion` 증가
- 검색·상태·위험도·우선순위·담당자·기간·정렬 조건의 URL 유지
- 목록 페이지 이동 후 상세 진입과 검색 조건 복귀

## 아직 자동화하지 않은 항목

- 실제 Backend API 통합
- 인증 토큰 만료와 실제 401 Redirect
- 브라우저 간 E2E
- API 확정 후 403·409·422 실제 응답 Mapper
