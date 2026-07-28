# 3주차 Web 테스트 결과

- 기준일: 2026-07-28
- 실행 위치: `web/`
- 자동화 도구: Vitest, jsdom, React Testing Library

## 자동화 범위

| 구분 | 검증 내용 |
| --- | --- |
| 단위 | 상담 임시 저장·완료·방문 검토 Validation |
| 단위 | 방문 일정 저장·확정 필수값과 날짜 순서 Validation |
| 단위 | 요청별 `Idempotency-Key`, `X-Correlation-ID` 생성 |
| 컴포넌트 | `allowed_actions` 기반 버튼 노출 |
| 컴포넌트 | 완료 필수값과 필드 오류 연결 |
| 컴포넌트 | 409 충돌 후 입력 유지, 최신 `stateVersion` 반영 |
| 컴포넌트 | 허용 행동이 없는 상태의 버튼 미노출 |
| 컴포넌트 | 방문 전환 필드 노출, 입력 유지, Mock 저장·확정 |
| 통합 | 상담 큐에서 문의 선택 후 상세·상담 Form 전환 |
| 통합 | 위험도 필터로 위험 문의 두 건 조회 |
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

## 2026-07-28 실행 결과

- `npm.cmd run test`: **7개 Test File, 24개 Test 통과**
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
- 기존 `/consultant/inquiries/{id}` 상세 경로 회귀
- `/consultant/inquiries/DEMO-INQ-004/visit-transition` 직접 접근과 v13 레이아웃
- 방문 전환 필수값 오류, 희망일·기사 선택, Mock 저장·확정, `stateVersion` 증가

## 아직 자동화하지 않은 항목

- 실제 Backend API 통합
- 인증 토큰 만료와 실제 401 Redirect
- 브라우저 간 E2E
- API 확정 후 403·409·422 실제 응답 Mapper
