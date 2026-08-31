# 2026-08-31 상담사 Web UI 수정

작업 브랜치: `yena`. Web 프론트엔드만 수정했으며 커밋·푸시·배포는 수행하지 않았습니다.

로컬 확인: [상담사 대시보드](http://127.0.0.1:5174/consultant/dashboard), [직원 연락처](http://127.0.0.1:5174/consultant/contacts).

이 링크는 기존 디자인 미리보기 모드입니다. 실제 화면 컴포넌트·CSS에 웹 내부 샘플 데이터를 연결하며 운영 API로 요청을 전달하지 않습니다. 저장·등록 등 변경 요청은 차단됩니다. 성공·실패·상태 전환 요청은 별도의 Web 테스트에서 검증했습니다.

## 요청별 반영

| 번호 | 반영 내용 |
| --- | --- |
| 1 | 공지사항 전체 배경과 총 건수·페이지·이전/다음 영역을 문의 목록의 연한 배경·남색 페이지 표시로 통일. 상세 열기와 페이지 이동 유지. |
| 2 | 사이드바에 직원 연락처 추가. 전체 직원·방문기사 목록, 구분·부서/지점 필터, 제출식 검색, 오류·권한·빈 상태 및 작은 화면 카드 배치 구현. 기존 대시보드 연락처 API 재사용. |
| 3 | 로그인 입력의 자동 대문자화·자동 교정·맞춤법 검사를 끄고 아이디/비밀번호 대소문자 원문 전달 검증. **서버 아이디 비교 방식 변경은 백엔드 협의 필요.** |
| 4 | 공통 드롭다운의 흰 입력창·둥근 연회색 옵션·남색 활성 항목 스타일 적용. 키보드 선택, 비활성 상태, 바깥 클릭, 스크롤 영역 밖 팝업 배치 지원. |
| 5 | 방문 정보 카드와 별도 상담 내용 수정본 입력란 제거. 상담 기록은 전폭 단일 입력란으로 표시하고 기본 비활성 → 상담 내용 수정 → 편집 → 저장 성공 후 다시 비활성. 실패/취소는 작성 내용 유지. |
| 6 | 상담 내용 확정 요청이 성공하면 처리 완료된 문의 목록으로 이동. 실제 문의 상태와 목록 집계는 서버 응답을 그대로 유지. |
| 7 | 방문 검토로 연결하던 `VISIT_REVIEW_REQUIRED`/`VISIT_NEEDED` 버튼 숨김. 해당 액션만 남으면 빈 화면 대신 진행할 작업 없음 안내. |
| 8 | 문의 검색 버튼의 채움·테두리·그림자 제거. 검색 제출 동작 유지. |
| 9 | 미배정 목록을 구분선 중심으로 간소화. 영문 긴급도·고객명·제품 문구는 목록에서 제거하고 한글 긴급도/대기 시간/문의 내용 표시. 페이지 크기 20건, 하단 페이지 이동 고정. 문의 미리보기와 배정 권한 검증 유지. |
| 10 | 전화 문의 등록 성공 후 처리 완료된 문의 목록으로 이동. 등록 오류 시 입력 유지, 실제 상태를 임의 완료 처리하지 않음. |
| 11 | NEW를 흰 글자와 빨간색 둥근 사각 배지로 표시. |

## 상담 내용 일치 및 상태 전환

- 화면에서 합친 상담 기록은 저장 시 기존 공개 계약의 `consultation_note`, `customer_guidance`, `additional_check`, `summary`에 같은 원문으로 매핑합니다. 기존 세 필드가 다르면 항목명과 함께 합쳐 원문을 보존합니다.
- 화면 기록과 서버의 저장된 요약이 다르거나 AI 초안만 있으면, 명시적으로 수정·저장한 뒤 확정하도록 안내합니다. 입력 문자를 바꾸지 않고 저장해도 보이는 내용이 저장됩니다.
- 저장 성공 응답의 실제 `state_version`으로 확인된 내용만 저장 완료로 취급합니다. 실패·취소 시 확정 화면 이동을 하지 않습니다.
- 상담 요약 확정 API는 `/consultation-summary/confirm`이며 그 자체가 최종 완료 API는 아닙니다. 전화 등록 API의 현재 응답 상태도 `CONSULTATION_REQUIRED`입니다.
- 따라서 6·10번은 **완료 목록으로 이동**하는 요청으로 반영했습니다. 아직 완료되지 않은 상태라면 그 실제 상태와 “실제 완료 처리 전에는 완료 목록에 표시되지 않습니다” 안내, 해당 문의 다시 열기를 제공합니다.
- 백엔드의 `allowed_actions`, `/finalize`, `state_version`, 409 처리, 중복 클릭/멱등키, 성공 후 조회 동작을 임의로 바꾸지 않았습니다. 자동 최종 완료 요청도 추가하지 않았습니다.

## 백엔드 인계 필요

```text
[담당 영역 문제 발견]
- 영역: 백엔드
- 관련 파일: backend/apps/accounts/services/p1_auth_service.py:939
- 웹에서 확인된 현상: Web은 입력한 아이디 대소문자를 그대로 전송하지만 서버 로그인 조회는 대소문자 무시 방식이다.
- 예상 원인: username__iexact=username 사용. 비밀번호는 check_password로 검증된다.
- 필요한 협의: 아이디를 대소문자까지 정확히 일치시킬 정책인지 결정하고, 기존 계정과 DB 비교 규칙을 고려한 서버 조회·인증 테스트를 담당자가 수정해야 한다.
- 웹 임시 대응: 자동 대문자화·자동 교정 방지와 원문 전달. 프론트에서 임의 계정 목록 또는 로그인 성공 후 차단으로 서버 인증을 대체하지 않는다.
```

문의 등록·상담 확정 자체를 서버에서도 곧바로 최종 완료 상태로 만들려는 요구라면 고객 결과 선택·방문 처리·최종 완료 권한 계약의 별도 협의가 필요합니다. 이번 작업에서는 변경하지 않았습니다.

## 검증

최종 소스 기준 검증 결과:

- `npm.cmd test -- --maxWorkers=2`: 60개 파일, **400건 통과 · 기존 4건 건너뜀**.
- `npm.cmd run typecheck`: 통과.
- `npm.cmd run typecheck:e2e`: 통과. E2E 테스트 코드의 타입 검사이며 전체 Playwright 실행 결과를 뜻하지 않습니다.
- `npm.cmd run lint`: 통과.
- `npm.cmd run build`: 통과. 운영 번들에 디자인 미리보기 전용 오류 코드와 샘플 문의 식별자가 포함되지 않음도 확인.
- `git diff --check`: 통과. 변경·추가 경로는 모두 `web/` 내부이며 다른 담당 영역 변경 0건.

- 브라우저: 공지 1/2 → 2/2 페이지와 상세 열기, 연락처 전체 12명·직원 8명·부서 필터 2명, 사이드바 이동 확인.
- 브라우저: 문의 검색 버튼 투명 배경, NEW 흰 글자/둥근 사각형, 미배정 구분선·하단 페이지 이동 확인.
- 브라우저: 상담 기록 기본 잠금과 수정 버튼으로 활성화, 제거된 방문 정보/수정본/방문 검토 버튼 확인. 전화 입력·상담 모달의 드롭다운 팝업이 잘리지 않는지 확인.
- 반응형: 1280px, 650px, 390px. 연락처 화면 잘림을 수정했고 좁은 창의 사이드바 텍스트 한 줄과 페이지 가로 넘침 없음을 확인.
- 운영 로그인·운영 문의 변경·실제 RDS 저장 확인은 수행하지 않았습니다.

## 이번 요청에서 수정·추가한 Web 파일

### 라우팅·화면

- `src/app/router/AppRouter.tsx`
- `src/app/router/routePaths.ts`
- `src/pages/auth/LoginPage.tsx`
- `src/pages/consultant/ConsultantDashboardPage.tsx`
- `src/pages/consultant/ConsultantInquiryListPage.tsx`
- `src/pages/consultant/ConsultantInquiryListPage.css`
- `src/pages/consultant/ConsultantNoticePage.tsx`
- `src/pages/consultant/ConsultantNoticePage.css`
- `src/pages/consultant/ConsultantContactsPage.tsx`
- `src/pages/consultant/ConsultantContactsPage.css`
- `src/pages/consultant/ConsultantDirectoryLayout.css`
- `src/pages/consultant/PhoneInquiryCreatePage.tsx`
- `src/pages/consultant/PhoneInquiryCreatePage.css`

### 공통·상담·운영 UI

- `src/common/components/form/FormSelect.tsx`
- `src/common/components/form/FormSelect.css`
- `src/features/consultation/components/ConsultantQueueSidebar.tsx`
- `src/features/consultation/components/ConsultantQueueSidebar.css`
- `src/features/consultation/components/ConsultantCompletionNotice.tsx`
- `src/features/consultation/components/ConsultantCompletionNotice.css`
- `src/features/consultation/components/ConsultationActionPanel.tsx`
- `src/features/consultation/components/RemoteConsultationActionPanel.tsx`
- `src/features/consultation/components/RemoteConsultantFirstDetailPanel.tsx`
- `src/features/consultation/components/RemoteConsultantInquiryDetail.tsx`
- `src/features/consultation/components/RemoteConsultantInquiryDetail.css`
- `src/features/consultation/components/UnassignedConsultationQueue.tsx`
- `src/features/consultation/components/UnassignedConsultationQueue.css`
- `src/features/consultation/hooks/useConsultantSidebarSummary.ts`
- `src/features/consultation/model/consultantCompletionNavigation.ts`
- `src/features/operations-dashboard/components/OperationsDashboardFilters.tsx`
- `src/features/visit-transition/components/RemoteVisitTransitionPanel.tsx`

### 테스트·문서

- `tests/component/ConsultantCompletionNotice.test.tsx`
- `tests/component/ConsultantQueueSidebar.test.tsx`
- `tests/component/ConsultationActionPanel.test.tsx`
- `tests/component/FormSelect.test.tsx`
- `tests/component/LoginPage.test.tsx`
- `tests/component/OperationsDashboardFilters.test.tsx`
- `tests/component/RemoteConsultationActionPanel.test.tsx`
- `tests/component/RemoteVisitTransitionPanel.test.tsx`
- `tests/component/UnassignedConsultationQueue.test.tsx`
- `tests/integration/ConsultantContactsPage.test.tsx`
- `tests/integration/ConsultantDashboardPage.test.tsx`
- `tests/integration/ConsultantFirstDetailRemoteFlow.test.tsx`
- `tests/integration/ConsultantInquiryListPage.test.tsx`
- `tests/integration/ConsultantNoticePage.test.tsx`
- `tests/integration/DesignPreviewProductionLayout.test.tsx`
- `tests/integration/PhoneInquiryCreatePage.test.tsx`
- `tests/unit/RemoteConsultantInquiryDetail.test.tsx`
- `tests/unit/authApi.test.ts`
- `docs/20260831-web-ui-update.md`

기존 로컬 미리보기 작업의 `README.md`, env/auth 관련 파일, `vite.config.ts`, `preview/`, 관련 테스트/문서는 보존했습니다. 해당 선행 작업의 설명은 [로컬 미리보기 안내](local-design-preview.md)를 참고합니다. 기존 `web/debug.log`도 수정하지 않았습니다.

Backend·Mobile·AI·DB/RDS/Seed·Infra·공용 계약 변경 0건. 패키지·Lockfile·CI/CD·Git hook 변경 없음.
