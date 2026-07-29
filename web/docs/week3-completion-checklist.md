# 한예나 3주차 Web 완료 기준 대조표

- 기준일: 2026-07-29
- 범위: `web/**` 상담사 P0, 공통 Web 기반, 검토 산출물
- 판정 원칙: Backend Runtime이 없는 항목은 지침서가 허용한 Mock·교체 구조·문서화까지를 Web 완료로 판정한다.

## 필수 업무 판정

| 지침서 | Web 완료 내용 | 판정 |
| --- | --- | --- |
| 3.1 실행 환경·Router·권한·오류 | Vite·TypeScript 실행, AuthGuard·RoleGuard, 메모리 인증 세션, Demo Auth 계약 Client, 상담사·운영자·403·404 경로, env와 README | 완료 |
| 3.2 공통 API·상태·근거 UI | ApiResponse·ApiError·PageInfo·httpClient·Authorization·Correlation·401 Refresh single-flight·RequestContext, 공통 Badge·DataTable·Pagination·Feedback·EvidenceCard | 완료 |
| 3.3 CONS-01 목록 | 검색, 상태·위험도·우선순위·담당자·기간 필터, 시간 정렬, URL Query, 페이지네이션, 결과 없음, 상세 이동 | 완료 |
| 3.4 CONS-02 상세 | 고객·제품·원문·문진·조치·사용 안내·AI 초안/확정본·공식 근거·이력, 직접 경로, 403·404·부분 실패 Mock | 완료 |
| 3.5 상담 Form·행동 | 필수값, 입력 유지, allowed_actions, 저장 중 중복 클릭 차단, 성공·403·409·422·네트워크 Mock, stateVersion·추적·멱등 구조 | 완료 |
| 3.6 테스트·매핑·문서 | 단위·컴포넌트·통합 테스트, 필드 매핑, 기술 결정, 미해결 이슈, 테스트 결과, 검토 문서, 실행 README | 완료 |

## 조기 완료 추가 범위

| 항목 | 판정 |
| --- | --- |
| CONS-03 방문 사유·희망일·가상 기사·인계·확정일 Form | 완료 |
| 방문 필수값·날짜 순서·Mock 저장·확정 | 완료 |
| allowed_actions 기반 진입·버튼 제어 | 완료 |
| ADMIN-01 Route·RoleGuard·정보 구조 Placeholder | 완료 |

## 실제 연동 대기 항목

아래는 Web 미구현이 아니라 외부 계약·Runtime 준비 후 교체할 항목이다.

- 실제 Backend 로그인·Refresh rotation·만료·로그아웃·`/me` 브라우저 E2E
- 상담 목록·상세·저장·완료·방문 API
- 실제 409·422 Wrapper와 OpenAPI 생성 타입
- 운영 대시보드 집계·예외 API
- 실제 API 기반 브라우저 E2E

강제 가정으로 구현하지 않고 [week3-open-issues.md](./week3-open-issues.md)에 연결 정보를 남긴다.
