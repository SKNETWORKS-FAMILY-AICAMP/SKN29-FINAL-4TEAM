# Django REST API 방문 Runtime PostgreSQL Row Lock 수정·검증 보고서

> 작성·검증일: 2026-08-10 KST
> 담당: 최지용 — Backend·DB
> 상태: `AUTHOR_POSTGRESQL_VERIFIED / INDEPENDENT_QA_REQUIRED`
> 대상: 방문 검토·생성·불필요·일정 저장·방문일 확정 Runtime

## 1. 결론

QA가 확인한 PostgreSQL 방문 Runtime 500 오류를 실제 PostgreSQL 16.14에서
재현한 뒤 수정했다.

- 원인은 nullable `technician` 외부 조인까지 잠그는 무범위
  `select_for_update()`였다.
- 두 Lock Query를 Visit 본체 행만 잠그도록 변경했다.
- UTC `Z`와 KST `+09:00`을 문자열로 비교하던 상담사 상세 테스트는 동일
  시점 비교로 교정했다.
- QA의 기존 실패 5건은 같은 PostgreSQL 환경에서 `5 passed`로 전환됐다.
- 전체 Backend 회귀는 SQLite `901 passed, 15 skipped`, PostgreSQL
  `915 passed, 1 skipped`다.
- Model·Migration·Seed·Data 원본은 변경하지 않았다.

작성자 검증은 완료했지만 김은진의 독립 재검증 전까지 방문 Runtime 소비자
연결은 허용하지 않는다.

## 2. QA 회신과 수정 전 재현

QA 회신의 핵심 증거는 다음과 같았다.

```text
visit_exception_class=django.db.utils.NotSupportedError
visit_root_exception_class=psycopg.errors.FeatureNotSupported
visit_exception_message=FOR UPDATE cannot be applied to the nullable side of an outer join
postgresql_visit_runtime=FAIL
database_partial_write_evidence=false
```

수정 전 PostgreSQL 16.14·pgvector 0.8.6에서 동일 5개 Case를 실행했다.

| 구분 | 수정 전 결과 |
| --- | --- |
| 상담사 상세 | UTC `Z`와 KST `+09:00` 문자열 차이로 실패 |
| 방문 검토→생성→일정→확정 | nullable 외부 조인 Lock으로 500 |
| 방문 불필요 | 동일 Lock 오류로 500 |
| 비합성 기사·날짜 오류 경계 | 선행 방문 검토 Lock 오류로 실패 |
| 방문 생성 Rollback | 선행 방문 검토 Lock 오류로 실패 |

결과는 QA와 동일한 `5 failed`였으며 방문 오류의 Root Exception 메시지도
일치했다.

## 3. 직접 원인

[VisitRepository](../../../../backend/apps/visits/repositories/visit_repository.py)는
기사 정보를 같이 읽기 위해 `select_related("technician")`를 사용한다.
`technician`은 `ASSIGNING` 상태에서 `NULL`이 정상인 관계다.

수정 전 Query는 Lock 범위를 지정하지 않았다.

```python
Visit.objects.select_for_update().select_related("technician")
```

PostgreSQL은 nullable 외부 조인의 기사 측에 `FOR UPDATE`를 적용할 수 없다.
오류는 Mutation 이전 Context 구성 단계에서 발생했으며 QA DB의 Visit,
Handoff, History, Idempotency 행 증가량은 모두 0이었다.

따라서 이 문제는 QA DB 구성 오류나 Deadlock이 아니라 Backend ORM Query
결함이다. QA DB 재생성이나 데이터 복구는 필요하지 않다.

## 4. 코드 수정

다음 두 메서드에서 Visit 행만 잠그도록 범위를 제한했다.

1. `VisitRepository.lock_latest()`
2. `VisitRepository.lock_by_public_id()`

```python
Visit.objects.select_for_update(of=("self",)).select_related("technician")
```

유지한 업무 규칙은 다음과 같다.

- `ASSIGNING`은 기사 미배정이며 `technician=NULL`을 허용한다.
- 기사를 강제 생성하거나 가짜 기사로 대체하지 않는다.
- 기사 미배정 Visit을 조회에서 제외하지 않는다.
- Lock 오류를 정상 응답으로 숨기지 않는다.

## 5. 시간대 테스트 교정

QA가 기록한 두 값은 같은 시점이다.

```text
expected=2026-08-10T07:12:23.599002Z
actual=2026-08-10T16:12:23.599002+09:00
```

OpenAPI는 해당 값을 `format: date-time`으로 정의하며 UTC `Z`만 강제하지
않는다. 테스트에서 응답 문자열을 파싱한 aware DateTime과 DB DateTime을
비교하도록 변경했다.

변경하지 않은 항목:

- DB DateTime의 UTC 저장
- 업무 시간대 `Asia/Seoul`
- Public API Serializer
- `preferred_date`, `confirmed_date`의 date-only 계약

## 6. 재발 방지 테스트

[상담·방문 Runtime 테스트](../../../../backend/tests/api/test_consultation_visit_runtime.py)에
PostgreSQL 전용 회귀 Case를 추가했다.

```text
test_postgresql_visit_lock_targets_visit_row_only_for_null_technician
```

이 Case는 다음을 실제 Row Lock으로 확인한다.

- `technician=NULL`인 `ASSIGNING` Visit 생성
- `lock_latest()` 실행 성공
- `lock_by_public_id()` 실행 성공
- 두 조회 모두 Visit 본체를 반환
- Nullable 기사 관계를 Lock 대상으로 확장하지 않음

SQLite에서는 PostgreSQL 전용임을 명시하고 Skip한다.

## 7. 검증 환경

| 항목 | 값 |
| --- | --- |
| OS | Windows PowerShell |
| Python | 3.13.13 |
| Django | 5.2.16 |
| PostgreSQL | 16.14 |
| pgvector | 0.8.6 |
| PostgreSQL TimeZone | `Etc/UTC` |
| Django 업무 TimeZone | `Asia/Seoul` |
| DB 용도 | 루프백 전용 일회성 작성자 검증 DB |

첫 실행에 사용한 일반 PostgreSQL 이미지는 `vector` 확장이 없어 Migration
단계에서 중단됐다. 코드 실패로 집계하지 않고 pgvector 포함 PostgreSQL
16.14 환경으로 교체한 뒤 재실행했다.

## 8. 검증 결과

| 단계 | 결과 |
| --- | --- |
| 수정 전 QA 실패 5건 재현 | `5 failed` |
| 수정 후 동일 5건 | `5 passed` |
| PostgreSQL 상담사 조회+상담·방문 파일 | `18 passed` |
| PostgreSQL Forward Migration | PASS |
| `migrate --check` | PASS |
| Migration Drift | `No changes detected` |
| SQLite 상담사 조회+상담·방문 | `17 passed, 1 skipped` |
| Runtime Coverage·G2·Contract | `24 passed` |
| SQLite Backend 전체 | `901 passed, 15 skipped` |
| PostgreSQL Backend 전체 | `915 passed, 1 skipped` |

PostgreSQL 전체 회귀의 Skip 1건은 별도 승인과 Role 입력이 필요한
TEAM_INTEGRATION Role 검증이다. 경고 33건은 일회성 검증용 JWT Secret 길이
경고였으며 기능 실패는 0건이다.

전체 PostgreSQL 1차 실행 중 CORS 허용 Origin을 개발값으로 넣어 Health Test
2건이 실패했다. 방문 수정과 무관한 환경 입력 오류로 분리했고, 테스트 계약의
허용 Origin으로 교정한 재실행에서 `915 passed, 1 skipped`를 확인했다.

## 9. 변경 파일

- `backend/apps/visits/repositories/visit_repository.py`
- `backend/tests/api/test_consultant_inquiry_runtime.py`
- `backend/tests/api/test_consultation_visit_runtime.py`
- 본 검증 보고서
- `docs/individual/jiyong/README.md`
- 상담사 문의 조회 Runtime 구현·검증 가이드의 QA 후속 기록

Model·Migration·OpenAPI·State Machine·Data 산출물은 변경하지 않았다.

## 10. QA 재검증 Gate

김은진은 기존 QA DB를 삭제하지 않고 다음 순서로 영향 범위만 재검증한다.

1. QA가 기존에 회신한 실패 5건
2. 신규 PostgreSQL Visit Lock 회귀 Case
3. 상담·방문 Runtime 파일 전체
4. Migration Drift
5. 멱등 Replay·동시성·Rollback
6. 관련 Backend 회귀

독립 QA 회신은 다음과 같이 Operation별로 분리한다.

```text
consultant_inquiry_runtime=PASS | CHANGE_REQUEST
consultation_runtime=PASS | CHANGE_REQUEST
visit_runtime=PASS | CHANGE_REQUEST
database_partial_write_evidence=false | true
consumer_connection=ALLOWED | NOT_ALLOWED
```

## 11. 현재 Gate

```text
cause_analysis=CONFIRMED
fix_applied_in_author_candidate=true
author_postgresql_verification=PASS
independent_qa=PENDING
visit_runtime_release=HOLD
consumer_connection=NOT_ALLOWED
database_reset_required=false
```

김은진의 독립 QA PASS 후 PM이 팀 기준선에 반영하고, 반영된 작업본에서 짧은
확인 테스트를 통과한 뒤에만 Web·Mobile 방문 소비를 허용한다.

## 12. Rollback

문제가 생기면 두 Repository Query의 `of=("self",)` 변경과 두 테스트 보강만
원복한다. DB 구조와 데이터는 바뀌지 않았으므로 Migration Rollback이나 QA DB
초기화는 수행하지 않는다.
