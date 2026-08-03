# 4주차 Web Runtime Source Map

## 실제 앱 진입 경로

```text
src/main.tsx
└─ app/App.tsx
   ├─ app/providers/AppProviders.tsx
   │  └─ AuthProvider
   └─ app/router/AppRouter.tsx
      ├─ /consultant/inquiries
      │  └─ pages/consultant/ConsultantDashboardPage.tsx
      ├─ /consultant/inquiries/:inquiryId
      │  └─ pages/consultant/InquiryDetailPage.tsx
      ├─ /consultant/inquiries/:inquiryId/visit-transition
      │  └─ pages/consultant/VisitTransitionPage.tsx
      └─ /admin
         └─ pages/admin/OperationsDashboardPage.tsx
```

`src/main.tsx`에서 정적 Import를 따라 조사했다. Repository 추가 후 도달 파일은 앱 13개, 공통 26개, 페이지 15개, Feature 41개, Entity 2개와 진입 파일이다.

## 화면별 공식 구현과 데이터 상태

| 화면 | 공식 Runtime 구현 | 데이터 상태 |
| --- | --- | --- |
| 상담사 목록 | `consultantWorkspaceRepository.ts` → `features/consultation/**` | Repository의 Mock Source, `MOCK_ONLY` |
| 상담사 상세 | `consultantWorkspaceRepository.ts` → `features/consultation/**` | Repository의 Mock Source, `MOCK_ONLY` |
| 상담 저장 | `useSaveConsultation.ts` → Repository 행동 조회 + `consultationMockApi.ts` | `MOCK_ONLY`, 계약 차단 |
| 방문 전환 | Repository 문의 조회 + `features/visit-transition/**` | 방문 저장은 `MOCK_ONLY` |
| 운영 대시보드 | `consultantWorkspaceRepository.ts` → `features/operations-dashboard/**` | 상담 합성 Mock 재사용, `MOCK_ONLY` |
| 인증 | `features/auth/api/authApi.ts` | Mock/API 모드 분기 존재 |
| Backend 상태 | `features/runtime-status/api/runtimeStatusApi.ts` | `/health` 실제 호출 |

상담사·방문·운영 Runtime 화면은 `consultantWorkspaceMock.ts`를 직접 Import하지 않는다. `consultantWorkspaceRepository.ts`가 현재 데이터 Source를 한곳에서 선택한다. `VITE_USE_MOCK_API=false`일 때 실제 Endpoint를 추측하지 않고 `BACKEND_BLOCKED` 상태와 Mock 미리보기를 유지한다.

Repository 경계는 완성됐지만 실제 Remote Repository는 Backend 계약 확정 뒤 구현한다.

## API 계약 상태

| 기능 | 계약 파일 | 상태 |
| --- | --- | --- |
| 고객 문의 생성·문진·자가조치·제출 | `contracts/api/paths/inquiries.yaml` | `CONTRACT_ONLY` 또는 일부 Runtime |
| 상담사 목록·상세 조회 | 미확정 | `BACKEND_BLOCKED` |
| 상담 결과 저장·완료 | `contracts/api/paths/consultations.yaml` | `{}` → `BACKEND_BLOCKED` |
| 기사 배정·방문 일정 | `contracts/api/paths/visits.yaml` | `{}` → `BACKEND_BLOCKED` |
| 운영 집계 | `contracts/api/paths/operations.yaml` | `{}` → `BACKEND_BLOCKED` |

현재 `inquiries.yaml`에 있는 Endpoint는 고객 문의 생성·문진·자가조치·제출용이다. 이를 상담사용 목록·상세 Endpoint로 추측해서 사용하지 않는다.

## Runtime에서 사용하지 않는 과거 구현 삭제

아래 파일은 `src/main.tsx`의 Import Graph와 테스트에서 사용되지 않음을 확인한 뒤 2026-08-03에 삭제했다.

### 삭제한 Feature

- `features/inquiry-queue/**`: 6 files
- `features/inquiry-detail/**`: 12 files
- `features/consultation/components/ConsultantQueue.tsx`: 1 file

### 삭제한 CSS

- `common/styles/legacy/styles.css`: 2,406 lines, 삭제 완료

## 공식 CSS 적용 순서

| 화면 | 적용 순서 | 상태 |
| --- | --- | --- |
| 상담사 목록 | `ConsultantDashboardPage.css` → `ConsultantDashboardTheme.css` | 공식 사용 |
| 상담사 상세 | `fix-base.css` → `staff-desktop-v6.css` → `InquiryDetailPage.css` | 공식 사용, Legacy 의존 |
| 방문 전환 | `fix-base.css` → `staff-desktop-v6.css` → `VisitTransitionPage.css` | 공식 사용, Legacy 의존 |
| 운영 대시보드 | `OperationsDashboardPage.css` → `OperationsDashboardTheme.css` | 공식 사용 |

주요 파일 크기는 다음과 같다.

- `ConsultantDashboardPage.css`: 2,919 lines
- `ConsultantDashboardTheme.css`: 316 lines
- `OperationsDashboardPage.css`: 811 lines
- `OperationsDashboardTheme.css`: 302 lines
- `staff-desktop-v6.css`: 441 lines

## 다음 변경 규칙

1. 상담 화면의 `Repository Interface` 경계는 유지하고, 계약 확정 후 Remote 구현만 추가한다.
2. 화면 컴포넌트에서 환경변수나 Mock 여부를 직접 판단하지 않는다.
3. Backend가 반환한 `status`, `risk_level`, `priority`, `current_assignee`, `allowed_actions`, `state_version`을 사용한다.
4. Endpoint와 DTO를 담당자 확인 없이 만들지 않는다.
5. 삭제한 과거 구현 경로는 다시 사용하지 않는다.

`eslint.config.js`는 Runtime Source에서 삭제한 과거 Feature 경로, `consultantWorkspaceMock.ts`, 삭제한 `legacy/styles.css`를 새로 직접 Import하면 실패하도록 보호한다. Repository 폴더만 Mock 원천 접근을 허용한다.
