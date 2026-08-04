# 4주차 Web 열린 이슈

## 우선순위 요약

| 우선순위 | 이슈 | 현재 상태 | 다음 행동·협업 |
| --- | --- | --- | --- |
| P0 | 상담사 목록·상세 Active API 없음 | Web `REVIEWED`, `IMPLEMENTATION_HOLD` | PM 승인 뒤 Active Endpoint·DTO·오류 계약 반영 |
| P0 | 상담 저장 Active 계약 비어 있음 | `consultations.yaml = {}` | PM 승인 뒤 행동별 Payload, `allowed_actions`, `state_version` 반영 |
| P0 | 기사 배정·방문 일정 Active 계약 비어 있음 | `visits.yaml = {}` | PM 승인 뒤 방문 공통 Wrapper·기사·일정 계약 반영 |
| P1 | 실제 Remote Repository 없음 | Mock Repository 경계와 모드 상태 구현 완료 | 계약 확정 후 Remote 구현 추가 |
| P1 | 운영 집계 계약 비어 있음 | `operations.yaml = {}` | 상담사 P0 완료 뒤 진행 |
| P1 | npm high 취약점 3건 | 미해결 | 상세 Audit 또는 팀의 안전한 환경에서 Package·Upgrade 영향 확인 |
| P2 | CSS 대형·중복 | 동작 중, 정리 보류 | 발표 이후 시각 회귀 확인과 함께 분리 |
| 완료 | 다른 팀원 재현 확인 | README 기준 교차 실행 성공 확인 | 추가 행동 없음 |

## 2026-08-04 Web 단독 준비 완료

- DEC-WEB-BE-001·004·009 재검토 회신 작성·Push
- 단계별 화면–API 필드 매핑과 수정 파일 순서 작성
- 실제·Mock·Contract 테스트 분리 계획 작성
- 401·403·404·409·422·5xx·Network 오류 UX 기준 작성
- 승인 전 Endpoint·Payload를 코드에 넣지 않는 구현 Gate 기록

상세 계획은 [실제 API 구현 준비표](./week4-web-implementation-readiness.md)와 [계약 테스트 계획](./week4-web-contract-test-plan.md)을 따른다.

## API 차단 상세

### 해결된 구조 문제

- 상담사·방문·운영 Runtime 화면의 `consultantWorkspaceMock.ts` 직접 Import 제거
- `consultantWorkspaceRepository.ts`에서 Mock Source와 연동 상태를 한곳에서 관리
- `VITE_USE_MOCK_API=true`: `MOCK_ONLY`
- `VITE_USE_MOCK_API=false`: 실제 Endpoint를 추측하지 않고 `BACKEND_BLOCKED`
- ESLint로 삭제한 과거 Feature 경로와 Mock 원천의 신규 직접 Import 차단
- Repository 단위 테스트 3개 추가

### 상담사 목록·상세

- 현재 `contracts/api/paths/inquiries.yaml`은 고객 문의 생성·문진·자가조치·제출 계약이다.
- 상담사용 목록·상세 조회 Endpoint가 아니다.
- `waiting_seconds`, 담당자, 위험도, 우선순위, 허용 행동을 Web에서 임의 계산하면 안 된다.

필요한 답:

1. 목록·상세 URL과 HTTP Method
2. Request Query와 Pagination
3. 응답 DTO와 누락 필드 표시 정책
4. 401·403·404·5xx·Network 오류 형식
5. `allowed_actions`, `state_version` Source

### 상담 결과 저장

- 현재 Runtime은 `consultationMockApi.ts`다.
- `consultations.yaml`이 비어 있어 실제 성공으로 표시할 수 없다.
- 409 충돌 시 자동 덮어쓰기·자동 재전송을 금지한다.

필요한 답:

1. 상담 시작·초안 저장·완료 Endpoint
2. `state_version`, `idempotency_key`, `correlation_id` 위치
3. 성공 Snapshot과 `allowed_actions`
4. 409 종류별 Error Code·Details

### 방문 전환

- 현재 기사 목록·배정·일정 저장·확정은 `visitTransitionMock.ts`다.
- `visits.yaml`이 비어 있어 실제 저장이 아니다.

## 해결된 과거 구현 정리

- `features/inquiry-queue/**`: Runtime 미사용 6 files 삭제
- `features/inquiry-detail/**`: Runtime 미사용 12 files 삭제
- `features/consultation/components/ConsultantQueue.tsx`: Runtime 미사용 파일 삭제
- `common/styles/legacy/styles.css`: Runtime 미사용 2,406 lines 삭제

현재 사용하는 상담사·관리자 화면 CSS와 Repository 구조는 변경하지 않았다.

## 보안·의존성

public npm Registry 사용 승인 후 `npm.cmd ci`를 실행했고 high severity 취약점 3건을 보고했다. 설치와 자동 검증은 성공했지만 상세 Package·Upgrade 영향 검토는 별도 작업으로 남긴다.

`npm audit fix --force`는 실행하지 않는다.
