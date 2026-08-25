# Web 공지 API·Playwright 작업 결과

## 한 줄 요약

최신 main의 공지 상세 API와 Playwright 계약 변경은 Web에 반영·Push했으며, 일반 Web 검증은 모두 통과했지만 실제 G4는 새 격리 Runtime과 테스트 Fixture가 없어 BLOCKED 상태입니다.

## 1. 반영 정보

- 브랜치: `yena`
- 최신 main SHA: `64a0539d1ec816ac3ec4a77480dbecd68a7ae927`
- Web Commit SHA: `873cb775ee5cdc586332700e2de56e5e65158587`
- 원격 `yena` 브랜치 Push: 완료

## 2. Web 작업 내용

- Dashboard의 `notice_id`를 이용해 공지 상세 API를 호출하도록 연결했습니다.
  - `GET /api/v1/consultant/notices/{notice_id}`
- 공지가 없거나 게시되지 않은 경우의 `404` 화면을 반영했습니다.
- 권한이 없는 경우의 `403` 화면을 반영했습니다.
- 최신 Backend Fixture에 맞춰 Playwright의 상담 상태를 `WAITING`에서 `ASSIGNED`로 변경했습니다.
- 제거된 `전체 기록 보기` 버튼과 별도 화면 대신, 문의 목록 안의 통합 상담 처리 화면을 기준으로 Playwright 검증을 수정했습니다.

## 3. 검증 결과

| 검증 항목 | 결과 |
| --- | --- |
| Web Test | `252 passed / 4 skipped` |
| Lint | PASS |
| TypeCheck | PASS |
| E2E TypeCheck | PASS |
| Production Build | PASS |
| 실제 Playwright G4 | BLOCKED |

## 4. Playwright G4 BLOCKED 사유

기존 증거 보존용 DB와 Volume을 재사용하거나 변경하지 않기 위해 실제 G4 실행은 시작하지 않았습니다.

현재 실제 실행에 필요한 준비 사항은 다음과 같습니다.

- 기존 보존 Volume과 이름이 겹치지 않는 최신 main 전용 새 격리 Runtime
- 상담사가 가져가기 전 상태의 새 `WPUJAC104DWH` 합성 문의 Fixture
- `WPUIAC425SNW`, `WPUIAC606SNW` 미승인 제품 차단 검증 Fixture 또는 공식 절차
- `WPUJCC104D` 잘못된 별칭 거절 검증 Fixture 또는 공식 절차

따라서 이번 작업에서는 실제 G4 수치, Screenshot, Trace가 생성되지 않았습니다.

## 5. 보존 사항

- 기존 DB 변경 없음
- 기존 PostgreSQL Volume 변경 없음
- Migration 적용 없음
- Seed 실행 없음
- 기존 증거 Runtime 재사용 없음
- `web/debug.log`는 Commit과 Push에서 제외

## 6. 수정 파일

- `web/src/features/notice/api/consultantNoticeApi.ts`
- `web/src/pages/consultant/ConsultantNoticePage.tsx`
- `web/e2e/support/backendFixture.ts`
- `web/e2e/specs/consultation-workflow.spec.ts`
- `web/tests/integration/ConsultantNoticePage.test.tsx`
- `web/tests/unit/consultantDashboardApi.test.ts`
- `web/tests/unit/e2eBackendFixture.test.ts`

## 7. 다음 진행 조건

Backend·DB 담당자가 위 새 격리 Runtime과 Fixture를 제공하면, 새로운 `run_id`와 문의로 실제 Playwright G4를 실행하고 수치·Screenshot·Trace를 추가 전달할 수 있습니다.
