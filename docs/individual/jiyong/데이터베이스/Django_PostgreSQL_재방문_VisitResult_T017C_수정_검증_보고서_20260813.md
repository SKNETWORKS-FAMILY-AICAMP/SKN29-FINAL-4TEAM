# PostgreSQL 재방문 VisitResult·T-017C 회귀 수정 검증 보고서

## 1. 문서 정보

| 항목 | 내용 |
| --- | --- |
| 작성일 | 2026-08-13 KST |
| 담당 | 최지용 — Backend·Database |
| 작업 상태 | jiyong 게시 대상·작성자 검증 완료, 독립 QA 대기 |
| 작업공간 | 별도 Git worktree·별도 Backend QA 브랜치 |
| 데이터베이스 | 폐기 가능한 PostgreSQL pytest 전용 QA DB |
| 원본 작업공간 | Web·AI 작업 파일 및 공용 DB 무변경 |

이 문서는 김은진 QA의 Backend 전체 회귀 실패 2건을 Web·AI 공동작업과
분리해 수정한 근거를 기록한다. 이 결과만으로 배포·소비자 연결·PM 최종 완료를
선언하지 않는다.

## 2. 결론

다음 두 결함을 재현하고 국소 수정했다.

1. 재방문 기사 교체 시 PostgreSQL 복합 FK가 과거 VisitResult를 현재 기사와
   계속 묶어 `PATCH /api/v1/visits/{id}/schedule`을 500으로 만들던 결함
2. 전체 Suite의 `transaction=True` 테스트가 Migration Seed 행을 flush한 뒤
   T-017C 동시성 테스트가 `AccountLifecycleLock(pk=1)`을 찾지 못하던 순서 의존

외부 API·DTO·State·OpenAPI·Web·AI 계약은 변경하지 않았다.

## 3. 재방문 Visit 결함

### 3.1 원인

기존 PostgreSQL 제약은 다음 두 값을 영구 결합했다.

```text
VisitResult(visit_id, submitted_by_id)
→ Visit(id, technician_id)
```

최초 방문 결과는 기사 A가 작성한다. 재방문에서는 같은 Visit을 유지하면서 현재
담당 기사를 B로 교체한다. 그러나 기존 FK는 기사 A의 역사적 결과까지 기사 B로
바꾸도록 강제해, 정상 재방문 Update를 FK 위반으로 거부했다.

### 3.2 수정 원칙

- 같은 Visit과 기존 `TR-INQ-028` 흐름을 유지한다.
- 결과 제출 시점에는 제출자가 현재 배정 기사인지 PostgreSQL에서 검증한다.
- 제출된 `visit_id`, `submitted_by_id`는 변경하지 못하게 한다.
- 이후 재방문 기사 교체는 허용한다.
- 기존 VisitResult의 제출자는 최초 기사로 보존한다.
- 과거 제출자를 교체 기사로 덮어쓰거나 결과를 삭제하지 않는다.

### 3.3 구현

신규 Visit Migration이 기존 복합 FK를 제출 시점 Trigger로 교체한다.

```text
INSERT VisitResult
→ Visit 행 FOR KEY SHARE
→ 현재 technician_id와 submitted_by_id 비교
→ 불일치 시 PostgreSQL FK 계열 오류
```

기존 결과 Update에서는 `visit_id`, `submitted_by_id` 변경을 거부한다. 정상적인
설명·후속관리 필드는 기존 모델 범위에서 유지된다.

`VisitResult.clean()`도 같은 의미로 정렬했다.

- 신규 객체: 제출자 역할과 현재 Visit 배정을 검증
- 기존 객체: DB에 저장된 Visit·제출자 키의 불변성을 검증
- 재방문 기사 교체 후 기존 결과의 `full_clean()`은 정상 통과

### 3.4 Rollback 정책

아직 기사 교체 이력이 없다면 이전 FK로 안전하게 되돌릴 수 있다. 이미 과거
제출자와 현재 기사가 다른 정상 데이터가 존재하면 이전 FK를 무손실로 복원할 수
없으므로 Rollback을 명시적으로 중단한다. 데이터를 임의 수정해 Rollback을
성공시키지 않는다.

## 4. T-017C 순서 의존 결함

### 4.1 원인

`AccountLifecycleLock(pk=1)`은 Migration에서 생성된다. PostgreSQL 전체 Suite의
앞선 `transaction=True` 테스트가 DB를 flush하면 이 Seed 행은 자동 복구되지
않는다. T-017C 동시성 테스트가 Migration 직후 단독 실행될 때는 PASS하지만,
전체 Suite에서는 Lock 행이 사라져 실패했다.

### 4.2 수정

T-017C PostgreSQL 동시성 테스트가 시작할 때 자신에게 필요한 Singleton 행을
명시적으로 준비한다.

```text
AccountLifecycleLock(pk=1, label=ACCOUNT_LIFECYCLE)
```

서비스의 `select_for_update().get(pk=1)`은 변경하지 않았다. 따라서 운영 DB에서
필수 Lock 행 누락을 조용히 자동 복구하거나 Fail-closed 경계를 약화하지 않는다.
Migration Seed 생성 책임은 기존 Migration 테스트가 별도로 검증한다.

## 5. 변경 파일

| 파일 | 목적 |
| --- | --- |
| `backend/apps/visits/migrations/0005_replace_visit_result_assignment_fk.py` | 복합 FK를 제출 시점 Guard Trigger로 교체 |
| `backend/apps/visits/models/visit_result.py` | 신규 제출 검증과 과거 키 불변 검증 분리 |
| `backend/tests/unit/visits/test_migration_0005_visit_result_assignment.py` | Forward·Reverse·Reapply·안전한 Reverse 거부 |
| `backend/tests/unit/visits/test_visit_result.py` | Trigger 구조·무결성·역사 보존·동시성 검증 |
| `backend/tests/api/test_consultation_visit_runtime.py` | 재방문 후 최초 제출자 보존 확인 |
| `backend/tests/integration/accounts/test_t017c_lifecycle_postgresql.py` | Singleton 테스트 준비 데이터 격리 |

## 6. 검증 결과

### 6.1 원본 결함 재현

| 항목 | 결과 |
| --- | --- |
| 재방문 기사 교체 | `500`, PostgreSQL FK 위반 재현 |
| 앞선 Transaction 테스트 후 T-017C | Lock Singleton 누락 실패 재현 |

### 6.2 수정 후 표적·관련 범위

| 검증 | 결과 |
| --- | --- |
| 초기 PostgreSQL 표적 | 12 passed |
| SQLite 관련 범위·Django Check·Migration Drift | 43 passed, 5 PostgreSQL 전용 skipped, Check PASS, Drift 없음 |
| PostgreSQL Visit·T-017C 관련 범위 | 48 passed |
| Migration SQLite·PostgreSQL | SQLite 1 passed/1 skipped, PostgreSQL 2 passed |
| 모델 정합·Trigger 동시성 보강 후 PostgreSQL 표적 | 18 passed / failed 0 / exit 0 |

### 6.3 Backend 전체 회귀

첫 실행은 로컬 `.env`의 데모 로그인·CORS 값이 테스트 기본 기대와 달라 관련
3건만 실패했다. 코드 결함과 분리하기 위해 환경파일을 수정하지 않고 테스트
프로세스에 다음 두 조건만 명시했다.

```text
DJANGO_DEMO_LOGIN_ENABLED=false
DJANGO_CORS_ALLOWED_ORIGINS=https://approved.example
```

환경 고정 후 전체 회귀 결과:

```text
1120 passed / 2 skipped / exit 0
```

두 번째 전체 회귀에서는 별도 Mobile Live HTTP Smoke 한 요청이 5초 Timeout으로
실패했다. Visit·T-017C 실패는 재발하지 않았으며, 해당 실제 Socket Case는 이번
변경 경로와 직접 관련이 없다.

이후 VisitResult 모델 정합성과 PostgreSQL 동시성 Case를 보강했다. 격리 후보의
전체 회귀는 두 번 연속 통과했다.

```text
1123 passed / 2 skipped / failed 0 / exit 0
1123 passed / 2 skipped / failed 0 / exit 0  # 재실행
```

최신 `jiyong`에 같은 7개 파일을 반영한 뒤 표적 18건이 PASS했다. 첫 전체 회귀는
기존 Mobile Live HTTP Smoke의 5초 Socket Timeout 1건만 실패했고, 해당 Case는
코드 변경 없이 단독 재실행에서 PASS했다. 전체 회귀 재실행 결과는 다음과 같다.

```text
1149 passed / 2 skipped / failed 0 / exit 0
```

Skip 2건은 이번 수정의 실패가 아니다.

- AI Uvicorn Mock 서버를 별도로 기동해야 하는 실제 Socket Gate
- TEAM_INTEGRATION PostgreSQL Role 자격증명이 필요한 별도 Gate

## 7. Web·AI 무영향 경계

- Web 파일 변경 0건
- AI 파일 변경 0건
- Inquiry AI Service·Crosswalk·Readonly View 변경 0건
- 상담 목록·상세·Start·기록·완료 API 변경 0건
- Visit API Method·Path·Request·Response 변경 0건
- State·Event·Allowed Action 변경 0건
- 공용 Web Runtime DB·AI pgvector DB Migration/Flush/Drop 0건
- `.env` 파일 변경 0건
- 격리 후보 7개 경로와 확인 시점 `origin/main`·`origin/jiyong` 변경의 직접 파일
  교집합 0건

테스트는 별도 worktree와 pytest 전용 PostgreSQL DB에서 수행했다.

## 8. 남은 절차

1. 김은진에게 이 보고서와 `jiyong` 후보의 독립 QA 요청
2. 재방문·T-017C 표적과 전체 Suite 영향 범위 재검증
3. QA PASS 후 T-016·T-017C 상태를 PM에게 분리 전달
4. PM 승인 경로로 main 반영

T-005는 이미 독립 PostgreSQL QA APPROVE이므로 이번 수정 때문에 재검증하지
않는다.

현재 판정은 `BACKEND_CANDIDATE=AUTHOR_VERIFIED`, `INDEPENDENT_QA=REVALIDATION_PENDING`이다.
독립 QA와 main 반영 전에는 팀 완료나 배포 가능으로 승격하지 않는다.
