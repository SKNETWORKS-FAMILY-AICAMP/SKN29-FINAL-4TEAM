# Django 방문 Runtime PostgreSQL Row Lock QA 재검증 요청서

> 발신: 최지용 — Backend·DB
> 수신: 김은진 — Data·QA·DevOps
> 작성일: 2026-08-10 KST
> 요청 상태: `AUTHOR_POSTGRESQL_VERIFIED / INDEPENDENT_QA_REQUIRED`
> 소비자 연결: `QA PASS 전 금지`

## 1. 요청 목적

기존 `CHANGE_REQUEST`의 nullable 기사 외부 조인 Row Lock 오류와 상담사 상세
시간대 문자열 비교를 수정했다. 기존 QA DB에서 영향 Case를 독립 재검증해
달라고 요청한다.

QA DB·Container는 삭제하거나 초기화하지 않는다. 기존 실패 요청의 부분 저장
증거가 없으므로 같은 DB를 유지한다.

## 2. 수정 범위

| 파일 | 변경 |
| --- | --- |
| `backend/apps/visits/repositories/visit_repository.py` | 두 Lock Query를 `of=("self",)`로 Visit 행에 제한 |
| `backend/tests/api/test_consultant_inquiry_runtime.py` | UTC·KST 문자열이 아닌 동일 시점 비교 |
| `backend/tests/api/test_consultation_visit_runtime.py` | 기사 미배정 PostgreSQL Row Lock 회귀 추가 |

Model·Migration·계약·Seed·Data 원본은 변경하지 않았다.

## 3. 작성자 검증

| 검증 | 결과 |
| --- | --- |
| 기존 QA 실패 5건 | `5 passed` |
| PostgreSQL 상담사 조회+상담·방문 | `18 passed` |
| Forward Migration·Drift | PASS·변경 0 |
| 계약·Runtime Coverage | `24 passed` |
| SQLite Backend 전체 | `901 passed, 15 skipped` |
| PostgreSQL Backend 전체 | `915 passed, 1 skipped` |

PostgreSQL Skip 1건은 이번 요청 범위 밖 TEAM_INTEGRATION Role 검증이다.

## 4. 필수 재검증 Case

- [ ] `test_consultant_detail_returns_closed_assigned_projection`
- [ ] `test_visit_review_create_schedule_confirm_date_only_flow`
- [ ] `test_visit_not_needed_completes_without_creating_visit`
- [ ] `test_visit_schedule_rejects_non_synthetic_technician_and_missing_date`
- [ ] `test_visit_creation_rolls_back_visit_handoff_history_and_key`
- [ ] `test_postgresql_visit_lock_targets_visit_row_only_for_null_technician`

## 5. 추가 확인

- [ ] `requestVisitReview`가 PostgreSQL 500 없이 동작한다.
- [ ] `createVisitRequest`가 `ASSIGNING`, `technician=NULL`을 저장한다.
- [ ] `markVisitNotNeeded`가 Visit을 만들지 않는다.
- [ ] `updateVisitSchedule`이 합성 기사와 date-only 일정을 저장한다.
- [ ] `confirmVisit`이 방문일을 확정한다.
- [ ] 같은 멱등 키 Replay에서 업무 행이 증가하지 않는다.
- [ ] 동시 요청에서 상태 버전 경계가 유지된다.
- [ ] 실패 시 Visit·Handoff·History·Idempotency가 함께 Rollback된다.
- [ ] UTC `Z`와 KST `+09:00`을 같은 시점으로 판정한다.
- [ ] Migration Drift가 0이다.

## 6. 권장 실행

실제 환경값과 비밀은 문서·로그·Git에 남기지 않는다.

```powershell
python -m pytest `
  backend/tests/api/test_consultant_inquiry_runtime.py `
  backend/tests/api/test_consultation_visit_runtime.py `
  -q -p no:cacheprovider

python backend/manage.py migrate --check
python backend/manage.py makemigrations --check --dry-run
```

실행은 PostgreSQL 16.x·pgvector 환경에서 수행한다. SQLite 결과만으로 Visit
Row Lock PASS를 판정하지 않는다.

## 7. 회신 형식

```text
reviewer=김은진
reviewed_at=<YYYY-MM-DD KST>
consultant_inquiry_runtime=PASS | CHANGE_REQUEST
consultation_runtime=PASS | CHANGE_REQUEST
visit_runtime=PASS | CHANGE_REQUEST
postgresql_lock_regression=PASS | FAIL
timezone_instant_comparison=PASS | FAIL
migration_drift=PASS | FAIL
idempotency_replay=PASS | FAIL
rollback=PASS | FAIL
failed_test_ids=<없음 또는 목록>
remaining_blockers=<없음 또는 목록>
consumer_connection=ALLOWED | NOT_ALLOWED
recommendation=PM_MERGE_ALLOWED | HOLD
```

## 8. 전달 순서

1. 김은진이 영향 Case를 기존 QA DB에서 재현한다.
2. 실패하면 최지용에게 실패 Case와 첫 Root Exception만 회신한다.
3. 모두 통과하면 Operation별 PASS와 소비자 연결 허용 여부를 회신한다.
4. 최지용이 QA 결과를 윤승혁에게 전달한다.
5. 윤승혁이 팀 기준선에 반영한다.
6. 반영본에서 짧은 확인 테스트 후 Web·Mobile 방문 연결을 허용한다.

## 9. 근거 문서

- [방문 Runtime PostgreSQL Row Lock 수정·검증 보고서](../API/Django_REST_API_방문_Runtime_PostgreSQL_Row_Lock_수정_검증_보고서_20260810.md)
- [상담사 문의 조회 Runtime 구현·검증 가이드](../API/Django_REST_API_상담사_문의조회_Runtime_구현_검증_가이드.md)
