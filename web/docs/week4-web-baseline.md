# 4주차 Web 기준선

## 한 줄 결론

2026-08-03 현재 Web은 **Mock 기준 화면·테스트·빌드는 정상**이지만, 상담사 목록·상세·상담 저장·방문 전환의 실제 Backend API는 아직 연결되지 않았다.

## 검증 기준

| 항목 | 값 |
| --- | --- |
| 검증 날짜 | 2026-08-03 |
| 브랜치 | `yena` |
| 기준 Commit | `d4bb32eaf75dc859830238526855362cfa7ad7a6` |
| Commit 제목 | `2026-08-03 \| 예나 브랜치 병합` |
| 검증 Source | 기준 Commit + Repository 경계 작업 트리 |
| Node.js | `v26.4.0` |
| npm | `11.17.0` |
| Vite | `8.1.5` |
| 설치 결과 | 241 packages 설치, 242 packages 검사 |

Vite의 Node.js 요구사항은 `^20.19.0 || >=22.12.0`이며 현재 검증 버전은 이를 만족한다. 팀 공통 개발 버전은 지침서 권장값인 Node.js `22.22.2` 이상으로 별도 합의가 필요하다.

## 현재 검사 결과

| 검사 | 결과 |
| --- | --- |
| `npm.cmd ci` | 성공 |
| `npm.cmd test -- --run` | 26 files, 109 tests 모두 성공 |
| `npm.cmd run lint` | 성공 |
| `npm.cmd run build` | TypeScript 검사와 Production Build 성공 |

세부 결과는 [week4-test-result.md](./week4-test-result.md)에 기록한다.

## 공식 화면 경로

- 상담사 목록: `/consultant/inquiries`
- 상담사 상세: `/consultant/inquiries/:inquiryId`
- 방문 전환: `/consultant/inquiries/:inquiryId/visit-transition`
- 운영 대시보드: `/admin`

모든 경로는 `src/main.tsx` → `App` → `AppProviders` → `AppRouter`를 통해 실행된다. 상세 Import 경로와 과거 구현 삭제 기록은 [week4-runtime-source-map.md](./week4-runtime-source-map.md)를 따른다.

## 완료와 미완료 구분

| 범위 | 상태 | 설명 |
| --- | --- | --- |
| Mock 화면 | 완료 | 상담사·방문·운영 화면과 합성 데이터 흐름이 동작한다. |
| 자동 테스트 | 완료 | 단위·컴포넌트·통합 테스트 109개가 성공한다. |
| Production Build | 완료 | TypeScript 검사와 Vite 번들이 성공한다. |
| 인증 API Client | 구현됨 | 실제 `/auth/*`, `/me` Client가 있으나 기본 실행은 Mock 인증이다. |
| `/health` 확인 | 구현됨 | Backend 연결 여부만 확인한다. |
| 상담사 목록·상세 API | 차단 | 상담사용 조회 Endpoint와 DTO가 확정되지 않았다. |
| 상담 결과 저장 API | 차단 | `consultations.yaml`이 비어 있다. |
| 방문 배정·일정 API | 차단 | `visits.yaml`이 비어 있다. |
| 운영 집계 API | 차단 | `operations.yaml`이 비어 있다. |

## 오늘 기준 결정

1. 현재 공식 상담사 구현은 `features/consultation/**`이며 화면 데이터 접근은 `consultantWorkspaceRepository.ts` 한곳을 통한다.
2. Runtime에서 사용하지 않던 `features/inquiry-queue/**`, `features/inquiry-detail/**`, `ConsultantQueue.tsx`, `legacy/styles.css`는 2026-08-03에 삭제했다.
3. Runtime 화면의 Mock 직접 Import는 제거했다. Repository는 `VITE_USE_MOCK_API`에 따라 `MOCK_ONLY` 또는 `BACKEND_BLOCKED`를 표시하며 실제 Endpoint가 없을 때 Mock 미리보기만 제공한다.
4. 실제 Endpoint를 추측해서 추가하지 않는다.
5. Mock 성공, 실제 API 성공, 정적 화면 성공을 문서와 발표에서 분리한다.

## 재현 방법

```powershell
cd web
npm.cmd ci
npm.cmd test -- --run
npm.cmd run lint
npm.cmd run build
```

다른 팀원은 같은 Commit과 Node.js 지원 버전에서 위 명령을 순서대로 실행한다.
