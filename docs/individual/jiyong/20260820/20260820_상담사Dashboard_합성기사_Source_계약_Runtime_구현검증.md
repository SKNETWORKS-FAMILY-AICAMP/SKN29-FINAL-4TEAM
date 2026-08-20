# 상담사 Dashboard 합성 기사 Source 계약·Runtime 구현 검증

- 작성일: 2026-08-20
- 담당: 최지용(Backend·DB)
- 기준선: `origin/main@a936cadcce30cdcd3a06f937dec86471dc100a7c`
- 판정: `BACKEND_CANDIDATE_VERIFIED / COMMIT_AND_MAIN_MERGE_PENDING`
- 범위: 로컬 합성 Web E2E용 기사 선택 Source

## 1. 목적

상담사 Web의 방문 일정 화면이 가짜 기사 ID를 만들지 않고 Backend가 반환한
합성 기사 공개 UUID를 기존 방문 일정 저장 API에 전달할 수 있도록 계약과
Runtime 경계를 정렬한다.

실제 운영 기사 배정·예약 시스템은 이번 범위가 아니다.

## 2. 확정한 연결

```text
GET /api/v1/consultant/dashboard
  data.technicians[].user_id
        ↓ 동일 UUID
PATCH /api/v1/visits/{visit_id}/schedule
  synthetic_technician_id
```

`technicians`에는 다음 조건을 모두 만족하는 계정만 노출한다.

- 활성 StaffDirectoryEntry
- `staff_type=TECHNICIAN`
- 활성 합성 사용자
- 실제 사용자 역할도 `TECHNICIAN`

따라서 응답의 모든 `user_id`는 `VisitRepository.synthetic_technician()`이
허용하는 방문기사 입력과 일치한다.

## 3. 구현 범위

| 영역 | 반영 내용 |
| --- | --- |
| OpenAPI Root | `/consultant/dashboard` 등록 |
| Operations Path | `getConsultantDashboard`, CONSULTANT 권한, Synthetic 전용 범위 |
| Response Schema | summary·notices·consultants·technicians·inquiries 닫힌 DTO |
| Visit Request | `synthetic_technician_id`가 합성 기사 공개 UUID임을 명시 |
| Runtime | StaffDirectory 역할과 실제 User 역할이 모두 TECHNICIAN인 행만 반환 |
| Test | Correlation, 권한, 422, 역할 불일치 제외, 방문 일정 입력 호환 검증 |

## 4. Web 소비 규칙

- API 필드 `technicians[].user_id`를 Web의 `userId`로 매핑한다.
- 사용자가 선택한 `userId`를 일정 저장 요청의
  `synthetic_technician_id`로 그대로 전달한다.
- Web이 UUID를 생성하거나 고정 기사 ID로 대체하지 않는다.
- 실제 운영 기사 배정·예약 완료로 표시하지 않는다.
- Backend가 반환한 `state_version`과 `allowed_actions`만 사용한다.

## 5. 검증 결과

| 검증 | 결과 |
| --- | --- |
| Dashboard 계약·Runtime·OpenAPI coverage | `10 passed` |
| 상담·방문 Runtime 회귀 | `13 passed, 1 skipped` |
| OpenAPI Validator | YAML 132, Ref 592, Path 42, Operation 47 `PASS` |
| Django System Check | 0 issue |
| Migration drift | `No changes detected` |
| 기존 Web Dashboard·Write 소비 Test | `5 passed` |
| `git diff --check` | PASS |

Skip 1건은 PostgreSQL 전용 Row Lock 검증이며 이번 Source 계약과 무관하다.

## 6. 남은 Gate

1. 후보 파일만 별도 Commit·jiyong Push
2. PM main 병합 및 최종 SHA 전달
3. 한예나가 최신 main에서 Web 첫 상세 패널에 Remote 컴포넌트 재사용
4. 합성 기사 선택 후 일정 저장 실제 Browser Smoke
5. 담당자 ACK 및 필요 시 독립 QA

## 7. 완료·미완료 경계

```text
backend_runtime_route=IMPLEMENTED_ON_MAIN
backend_formal_contract=LOCAL_CANDIDATE_VERIFIED
technician_source_mapping=VERIFIED
real_assignment_system=OUT_OF_SCOPE
web_first_panel_integration=NOT_IMPLEMENTED_BY_BACKEND
browser_runtime_smoke=NOT_RUN
main_merge=PENDING
```
