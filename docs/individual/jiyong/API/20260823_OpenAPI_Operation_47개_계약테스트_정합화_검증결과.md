# OpenAPI Operation 47개 계약 테스트 정합화 검증 결과

> 작업일: 2026-08-23
> 담당: 최지용(Backend·DB)
> 작업 기준: `origin/main@284916d607f976d38ac10617831d0f346880864f`
> 선행 독립 QA 기준: `fb83e2dd56182d87a95c0691cf130d44d5ea4273`
> 판정: `PASS`

## 1. 작업 목적

김은진 독립 QA에서 Backend 회귀는 `87 passed / 1 skipped / 1 known failed`였다.
유일한 실패는 OpenAPI 실제 Operation 47개와 G2 계약 테스트 기대값 46개의 수치
불일치였다. 이번 작업은 이미 구현된 계약을 변경하지 않고 오래된 테스트 기대값만
현재 계약과 맞추는 증분 정합화다.

## 2. 원인과 근거

- `GET /api/v1/consultant/dashboard`가 정식 계약에 추가돼 전체 Operation은 47개다.
- 이 API의 `operationId`는 `getConsultantDashboard`다.
- `contracts/api/paths/operations.yaml`은 이 경로를 `CONFIRMED`·`IMPLEMENTED`로 관리한다.
- OpenAPI Validator와 Runtime Coverage 테스트는 이미 47개를 기대한다.
- `backend/tests/api/test_g2_machine_contract.py`의 두 Assertion만 이전 값 46을 유지했다.

따라서 원인은 Runtime·DB·Migration 장애가 아니라 테스트 Inventory 수치 드리프트다.
Dashboard API를 삭제하거나 계약을 46개로 되돌리는 방식은 사용하지 않았다.

## 3. 변경 범위

다음 두 기대값만 `46`에서 `47`로 변경했다.

1. 전체 OpenAPI Operation 수
2. 고유 `operationId` 수

변경하지 않은 범위는 다음과 같다.

- OpenAPI 경로·Schema·Example
- Backend Route·View·Serializer·Service·Repository
- State Machine과 공개 API 동작
- DB Schema·Migration·Seed·Evidence
- Mobile·Web·AI 코드
- PostgreSQL Volume과 Runtime 데이터
- P1 HOLD인 `visits.0005`

## 4. 자체 검증 결과

| 검증 | 결과 |
| --- | --- |
| OpenAPI·Dashboard·Runtime Coverage·Contract Validator 표적 | `21 passed / 0 failed`, Exit 0 |
| 기존 G1~G5 Backend 회귀 목록 | `88 passed / 1 skipped / 0 failed`, Exit 0 |
| Skip 사유 | PostgreSQL Row Lock 전용 증거 1건 |
| OpenAPI Validator | PASS, YAML 132, Ref 592, Path 42, Operation 47 |
| 고유 `operationId` | 47개 |
| `getConsultantDashboard` | 존재 및 계약 연결 확인 |
| Django Check | PASS, issue 0 |
| Migration drift | `No changes detected` |
| Data QA | PASS, 60 files / 990 records / error 0 / warning 0 |
| 대표 E2E Data 검사 | 17/17 PASS |
| Data 재현성 | 변경·재생성 파일 0건 |
| `git diff --check` | PASS |

기존 known failed 1건은 같은 QA 회귀 목록에서 PASS로 전환됐다. Skip 1건은 이번
정합화와 무관한 PostgreSQL Row Lock 전용 Test Host 조건이며 실패로 승격하지 않는다.

## 5. Troubleshooting

첫 Backend 회귀 실행은 테스트 코드가 아니라 Windows 임시 폴더 ACL 때문에
`PermissionError`로 종료됐다. 동일 테스트 목록을 접근 가능한 격리 임시 경로에서
다시 실행했고 `88 passed / 1 skipped / 0 failed`, Exit 0을 확인했다.

이 환경 오류는 저장소 코드·DB·계약 실패로 기록하지 않았으며, 재실행 결과와 구분했다.

## 6. 최종 판정

```text
openapi_operation_count=47
unique_operation_id_count=47
dashboard_operation=getConsultantDashboard
stale_contract_assertion=RESOLVED
backend_regression=88_PASSED_1_SKIPPED_0_FAILED
runtime_or_database_change=NONE
migration_drift=NONE
data_reproducibility=PASS
fresh_e2e_required=NO
incremental_qa_required=YES_AFTER_MAIN_MERGE
```

이번 변경은 G2~G4 Runtime 데이터 경로를 다시 실행하는 기능 변경이 아니다.
PM main 병합 후 김은진이 병합 SHA에서 Operation 47/47, 기존 실패 해소,
DB·Migration·Evidence 변경 없음만 증분 QA로 확인하면 된다.
