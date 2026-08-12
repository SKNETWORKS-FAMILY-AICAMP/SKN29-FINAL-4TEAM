# T-020 다음 케어일 계산·재산정 구현·검증 가이드

## 1. 최신 판정

- 작성일: 2026-08-12 KST
- 기준: origin/main@8b5bb6292e087fd15558f53c530b06653edc4d29
- 상태: AUTHOR_SKELETON_VERIFIED / OFFICIAL_RULE_DATA_PENDING
- 공개 API: 추가하지 않음
- 공식 WBS 완료: 금지

공식 주기 상수를 저장소에서 확인할 수 없어 임의 날짜를 만들지 않았다.
대신 출처·버전이 있는 승인 규칙을 입력받는 계산 Service와 일정 재산정
저장 경계를 구현했다. 규칙이 없으면 CONFIRMATION_REQUIRED를 반환한다.

## 2. 계산 입력·출력

입력 CareCycleRule:

- care_type_code
- interval_months (1..120)
- basis: OFFICIAL 또는 TEAM_RULE
- source_reference, source_version

출력 NextCareSchedule:

- status: SCHEDULED 또는 CONFIRMATION_REQUIRED
- next_care_on, basis, base_on, care_type_code
- source_reference, source_version

근거가 없으면 날짜·Basis·Source를 null로 반환하고 기존 DB 일정을 자동
삭제하거나 임의로 덮어쓰지 않는다.

## 3. 계산 규칙

- 최근 동일 케어 유형의 COMPLETED 이력 날짜를 기준일로 사용
- 완료 이력이 없으면 구독 시작일을 기준일로 사용
- Calendar month를 더하고 월말은 해당 월의 마지막 유효일로 보정
- 윤년 1월 31일 + 1개월은 2월 29일
- 비ACTIVE·미지원 제품 구독은 재산정 대상에서 제외
- 공식 주기 자체는 코드에 하드코딩하지 않음

## 4. 저장·변경 이력

T-005 물리 계약에 따라 새 일정 테이블을 만들지 않았다.

- 현재 예정일 Cache: CustomerSubscription.next_care_on
- 일정·변경 이력: 기존 CareRecord
- 동일 규칙·동일 날짜 재호출: 새 Row 0
- 날짜·규칙 변경: 기존 미완료 동일 유형 일정을 CANCELLED로 보존
- 취소 Row의 cancellation_reason에 재산정 사유 기록
- 새 SYSTEM/SCHEDULED CareRecord 생성
- 모든 미완료 일정 중 가장 빠른 날짜를 next_care_on에 동기화
- Model·Migration 변경 없음

## 5. 구현·계약 증거

- [계산 계약 객체](../../../../backend/apps/care/models/care_schedule.py)
- [계산·재산정 Service](../../../../backend/apps/care/services/care_schedule_service.py)
- [일정 Repository](../../../../backend/apps/care/repositories/care_schedule_repository.py)
- [NextCareSchedule Schema](../../../../contracts/api/components/schemas/care/NextCareSchedule.yaml)
- [CareCycleRule Schema](../../../../contracts/api/components/schemas/care/CareCycleRule.yaml)
- [계산·저장 Test](../../../../backend/tests/unit/care/test_care_schedule_service.py)
- [계약 Test](../../../../backend/tests/unit/care/test_t020_care_schedule_contract.py)
- [후행 Gate Auditor](../../../../scripts/contracts/audit_overdue_backend_runtime_gates.py)

## 6. 작성자 검증

| 검증 | 결과 |
|---|---:|
| 계산·계약·Gate Test | 14 passed / 0 failed |
| 월말·윤년 | PASS |
| 동일 재계산 중복 0 | PASS |
| 변경 시 기존 일정 취소 이력 | PASS |
| 근거 없음 확인 필요·기존 일정 보존 | PASS |
| T-019/T-020 Gate | READY |
| T-021 Gate | BLOCKED 유지 |
| Django Migration drift | No changes detected |
| 전체 Backend 회귀 | 1076 passed / 19 skipped / 0 failed |

재현 위치는 backend다.

    .\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/unit/care/test_care_schedule_service.py tests/unit/care/test_t020_care_schedule_contract.py tests/unit/care/test_overdue_backend_runtime_gates.py
    .\.venv\Scripts\python.exe -B ..\scripts\contracts\audit_overdue_backend_runtime_gates.py
    .\.venv\Scripts\python.exe -B ..\scripts\contracts\validate_openapi.py

## 7. 미완료·금지선

- 공식 운영 주기 Dataset·출처·적용 모델은 아직 저장소에 없음
- 실제 Rule Registry 적재와 운영자 변경 절차는 별도 승인 필요
- 공개 조회 DTO에 next_care_status·basis를 연결하지 않음
- PostgreSQL 동시 재산정·독립 QA는 미실행
- Visit 결과 연계와 2차 완료는 T-044 범위
- 공식 규칙·PostgreSQL·독립 QA 전 T-020 완료나 고객 알림 사용 가능을
  주장하지 않는다.
