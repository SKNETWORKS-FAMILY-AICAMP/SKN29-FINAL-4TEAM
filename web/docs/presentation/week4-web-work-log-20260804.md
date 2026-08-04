# WaterBridge Web 수행 경과·정리 기록

결과보고서의 `프로젝트 수행 절차 및 방법`과 `프로젝트 수행 경과`에 넣을 수 있도록 Web 작업과 피드백 반영 내용을 시간순으로 정리한다.

## 수행 기록

| 기간 | 단계 | 진행한 일 | 피드백·문제 | 반영 결과 |
| --- | --- | --- | --- | --- |
| 7월 27일~7월 31일 | 화면 구현 | 상담 목록·상세·상담·방문·운영 Mock 화면 구현 | 화면 수가 많아도 실제 API 완료로 볼 수 없음 | Mock 화면과 실제 연동 상태를 분리하기로 결정 |
| 8월 3일 | 실행 기준선 | 현재 Commit에서 설치·Test·Lint·Build 재검증 | 과거 테스트 보고서 이후 Source가 크게 변경됨 | 26 files·109 tests, Lint·Build 성공 기록 |
| 8월 3일 | Runtime 정리 | 공식 경로를 `features/consultation/**`로 확정 | 과거 문의 구현과 Legacy CSS가 함께 존재 | Runtime 미사용 20 files와 Legacy CSS 2,406 lines 삭제 |
| 8월 3일 | README 교차 검토 | 정현님이 링크·환경변수·Node 버전 안내 확인 | 최소 지원 버전과 실제 검증 버전이 섞여 있었음 | README 문구를 분리하고 다른 팀원 실행 확인 완료 |
| 8월 4일 | Backend 계약 검토 | DEC-WEB-BE-001·004·009 재검토 회신 | 목록·상담·방문 Active 계약과 PM 승인이 없음 | 구현 순서·필드·오류·409 복구 계획을 작성하고 코드 구현 보류 |
| 8월 4일 | 발표 준비 | Water Bridge 명칭·역할 이미지·로고 제작 | 서비스명과 발표 화면의 브랜드 통일 필요 | 역할 이미지 4장, 로고 1장, 화면 캡처 5장 준비 |
| 8월 4일 | 결과보고서 정리 | 발표 기준·Fallback·수치 문서 작성 | 기존 문서가 실행 검증 중심이고 결과보고서 항목이 부족 | 개요·역할·절차·경과·자체평가 구조로 개편 |

## Web 구현 결과

- 상담사 목록 → 상세 → 공식 근거 → 409 → 방문 전환의 5단계 시연 흐름을 준비했다.
- 상담사와 운영 담당자 화면에 Water Bridge 서비스명을 반영했다.
- Mock 직접 Import를 Repository 경계로 옮기고 `MOCK_ONLY`·`BACKEND_BLOCKED`를 구분했다.
- 409 충돌 뒤 입력 유지와 자동 재전송 금지 동작을 Mock으로 확인했다.
- 발표 실패에 대비해 같은 순서의 캡처 5장을 준비했다.

## 정량 증거

| 항목 | 결과 |
| --- | ---: |
| Test files | 26 / 26 성공 |
| Test cases | 109 / 109 성공 |
| 실패·Skip | 0 |
| Lint 오류 | 0 |
| Build 변환 모듈 | 117 |
| 삭제한 과거 구현 | 20 files |
| 삭제한 Legacy CSS | 2,406 lines |
| 발표 캡처 | 5장 |

## 삭제한 과거 파일 20개

삭제 Commit: `600c9a6`

### 상담 큐 과거 구현 6개

1. `features/inquiry-queue/hooks/useInquiryQueueFilters.ts`
2. `features/inquiry-queue/hooks/useMockInquiryQueue.ts`
3. `features/inquiry-queue/model/inquiryQueueConstants.ts`
4. `features/inquiry-queue/model/inquiryQueueMock.ts`
5. `features/inquiry-queue/model/inquiryQueueModel.ts`
6. `features/inquiry-queue/model/inquiryQueueTypes.ts`

### 문의 상세 과거 구현 12개

1. `features/inquiry-detail/components/AiSummarySection.tsx`
2. `features/inquiry-detail/components/CustomerProductSection.tsx`
3. `features/inquiry-detail/components/EvidenceSection.tsx`
4. `features/inquiry-detail/components/InquiryHeader.tsx`
5. `features/inquiry-detail/components/InquirySectionError.tsx`
6. `features/inquiry-detail/components/StatusHistorySection.tsx`
7. `features/inquiry-detail/components/SymptomQuestionnaireSection.tsx`
8. `features/inquiry-detail/hooks/useInquiryResponseForm.ts`
9. `features/inquiry-detail/hooks/useMockInquiryDetail.ts`
10. `features/inquiry-detail/model/inquiryDetailMapper.ts`
11. `features/inquiry-detail/model/inquiryDetailMock.ts`
12. `features/inquiry-detail/model/inquiryDetailTypes.ts`

### 기타 과거 구현 2개

1. `features/consultation/components/ConsultantQueue.tsx`
2. `common/styles/legacy/styles.css` - 2,406 lines

모든 경로는 `web/src/` 기준이다.

## 남아 있는 큰 CSS

- 상담사 화면과 운영 화면의 현재 CSS는 동작·디자인 회귀 위험 때문에 유지했다.
- 발표 이후 중복 규칙을 공통 Token·Component CSS로 나누고 시각 회귀를 확인한다.

## 실제 API 대기 항목

1. 상담사용 목록·상세 Endpoint·DTO
2. 상담 시작·저장·완료와 409 계약
3. 방문 요청·기사 후보·일정 저장 계약
4. 운영 대시보드 집계 API

실제 업무 API 연결 수는 0개이며 `/health` 1개만 연결 상태 확인에 사용한다.

## 배운 점과 자체 평가

- 화면이 보이는 것과 실제 API가 동작하는 것은 다른 완료 기준이다.
- Backend가 상태와 허용 행동을 결정하고 Web은 그 계약을 표현해야 한다.
- 실패 시 입력을 보존하고 사용자가 다음 행동을 선택하게 하는 것이 안전하다.
- 테스트 수치뿐 아니라 문제·피드백·개선 과정을 함께 보여 줘야 결과보고서가 된다.

## 남은 일

1. 현재 Water Bridge 작업 Commit·Push
2. Backend Active 계약 승인 후 실제 상담·방문 저장 연결
3. 발표 피드백을 5주차 인계 문서에 추가

## 2026-08-04 최종 확인

- public npm Registry 사용 승인 후 `npm.cmd ci` 성공: 241 packages 설치, 242 packages 검사
- npm 설치 결과 high severity 취약점 3건 보고, 강제 수정은 하지 않음
- Test 26 files·109 cases, Lint, TypeScript·Production Build 모두 성공
- 상담사 목록 → 상세 → 공식 근거 → 409 입력 유지 → 방문 전환 흐름을 3회 반복 성공
- 상담사 역할의 관리자 화면 접근이 `/forbidden`으로 차단됨을 수동 확인

## 5주차에 이어서 할 내용

1. PM `FINAL_APPROVED`와 Active OpenAPI 확인
2. 실제 상담 목록·상세 Remote Repository 연결
3. 실제 상담 행동과 409 복구 검증
4. 실제 방문 요청·기사·일정 저장 연결
5. 운영 실제 집계 API 연결
6. 실제·Mock·Contract 테스트 결과 분리 기록
7. 발표 피드백·회귀 오류·최종 Commit을 인계 문서에 반영
