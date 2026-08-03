# 4주차 Web 열린 이슈

## 우선순위 요약

| 우선순위 | 이슈 | 현재 상태 | 다음 행동·협업 |
| --- | --- | --- | --- |
| P0 | 상담사 목록·상세 API 없음 | `BACKEND_BLOCKED` | 최지용과 Endpoint·DTO·오류 계약 확정 |
| P0 | 상담 저장 계약 비어 있음 | `consultations.yaml = {}` | 최지용·윤승혁과 행동별 Payload, `allowed_actions`, `state_version` 확정 |
| P0 | 기사 배정·방문 일정 계약 비어 있음 | `visits.yaml = {}` | Endpoint·기사 목록·일정 저장/확정 응답 합의 |
| P1 | 실제 Remote Repository 없음 | Mock Repository 경계와 모드 상태 구현 완료 | 계약 확정 후 Remote 구현 추가 |
| P1 | 운영 집계 계약 비어 있음 | `operations.yaml = {}` | 상담사 P0 완료 뒤 진행 |
| P1 | npm high 취약점 2건 | 미해결 | 공개 Registry 전송 승인 후 상세 Audit 또는 담당자 환경에서 확인 |
| P2 | CSS 대형·중복 | 동작 중, 정리 보류 | 발표 이후 시각 회귀 확인과 함께 분리 |
| P2 | 다른 팀원 재현 확인 | 양정현 README 검토 완료, 실제 명령 실행 여부 미확인 | 양정현 또는 다른 팀원이 README 명령으로 교차 실행 |

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

`npm.cmd ci`는 high severity 취약점 2건을 보고했다. 현재 환경에서는 상세 `npm audit`가 private workspace의 의존성 Metadata를 공개 npm Registry로 전송하므로 자동 실행하지 않았다. 사용자가 승인하거나 팀의 안전한 CI/개발 환경에서 상세 Package와 Upgrade 영향을 확인해야 한다.

`npm audit fix --force`는 실행하지 않는다.
