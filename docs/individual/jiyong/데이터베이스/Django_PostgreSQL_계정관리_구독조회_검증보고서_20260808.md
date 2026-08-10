# Django·PostgreSQL 계정관리·구독조회 검증보고서 — 2026-08-08

> 대상: T-017B와 T-018 R1 GET
>
> 성격: 작성자 로컬 실행 증거·독립 QA 재현 입력
>
> 비밀정보: Password·DSN·`.env` 원문·Token 미기록

## 1. 최종 판정

- T-017B 구현과 로컬 PostgreSQL 적용: PASS
- T-018 R1 목록·상세 Runtime: PASS
- T-017C: NOT_STARTED
- T-018 등록·수정·기본 제품: NOT_IMPLEMENTED
- 독립 QA: NOT_RUN

즉 코드·작성자 검증은 완료됐지만 독립 QA와 공식 WBS 완료 판정은 별도다.

## 2. 실행 환경 식별

| 항목 | 확인값 |
| --- | --- |
| Machine | 최지용 로컬 PC |
| Repository | `C:\python-src\Final_PROJECT\SKN29-FINAL-4TEAM` |
| Branch | `jiyong` |
| Python | `backend/.venv/Scripts/python.exe`, 3.13.13 |
| Django | 5.2.16 |
| Docker Context | `desktop-linux` |
| Container | `watercare-local-postgres-1` |
| Image | `pgvector/pgvector:0.8.6-pg16-bookworm` |
| Backend DB | `waterbridge` |
| Schema | `public` |
| PostgreSQL | 16.14 |

작업 식별은 기준일·Branch·변경 파일·Migration 이름·실행 명령·건수를
사용한다.

## 3. 초기 연결 판정

- Backend 실제 연결 DB: `waterbridge`
- Docker Cluster에 `waterbridge` 존재
- `waterbridge.public` 기본 테이블: 45
- 기존 Django Migration 기록: 70
- 기존 사용자: 20
- 적용 전 Accounts 최신: `0003_promote_integer_primary_keys`

QA 담당자가 이전에 확인한 `execution_machine=DESKTOP-QEBK84A`,
`configured_database_source=BACKEND_ENV`, `actual_connected_database=watercare`
환경과 이 PC는 다른 실행 환경이다. QA의 `watercare`가 비어 있었던 것은
이번 최지용 로컬 `waterbridge`의 손상 증거가 아니다. 독립 QA에서는 자신의
DB를 새로 Migration하거나 승인된 검증 DB를 사용해야 한다.

## 4. 검증 DB 구성

원본을 바로 변경하지 않고 아래 두 DB를 만들었다.

| 검증 DB | 목적 |
| --- | --- |
| `waterbridge_t017b_empty_20260808` | 빈 DB 전체 Migration·Rollback |
| `waterbridge_t017b_existing_20260808` | 기존 `waterbridge` 복제 Backfill |

두 DB는 검증 완료 후 이름을 재확인하고 삭제했다. 현재 Cluster에 남아 있지
않으며 원본 `waterbridge`와 다른 기존 검증 DB는 삭제하지 않았다.

## 5. 빈 DB 결과

1. 전체 Migration 적용 PASS
2. `accounts.0004_add_user_is_synthetic` 적용 PASS
3. 사용자 `0`
4. `is_synthetic` 컬럼 `1`
5. `accounts 0003` Rollback PASS
6. Rollback 후 컬럼 `0`
7. `accounts 0004` 재적용 PASS
8. 최종 `migrate --check` PASS

빈 DB는 판정 대상 사용자가 없으므로 Backfill `0 → 0`이 정상이다.

## 6. 기존 DB 복제 결과

| 검증값 | 결과 |
| --- | ---: |
| 기존 사용자 | 20 |
| `is_synthetic=True` | 20 |
| false 또는 null | 0 |
| 미판정 | 0 |
| 중복·Ledger 충돌 | 0, Migration 중단 없음 |
| 목표 Migration | `0004_add_user_is_synthetic` |

Rollback 후:

- 사용자 20명 보존
- `is_synthetic` 컬럼 제거
- Accounts 최신 `0003_promote_integer_primary_keys`

재적용 후 20/20 분류가 다시 PASS했다.

## 7. 원본 로컬 DB 적용 결과

복제 검증을 통과한 뒤 원본 `waterbridge`에 적용했다.

| 항목 | 결과 |
| --- | --- |
| Accounts 최신 | `0004_add_user_is_synthetic` |
| 사용자 | 20 |
| synthetic true | 20 |
| false 또는 null | 0 |
| Django Admin Migration | 3개 적용 |
| Django Session Migration | 1개 적용 |
| `migrate --check` | PASS |
| `makemigrations --check --dry-run` | No changes detected |

## 8. Test 결과

| 범위 | 결과 |
| --- | --- |
| 변경 전 Accounts+T-018 계약 기준선 | `77 passed` |
| T-017B Accounts+공식 Importer | `89 passed` |
| T-017B Migration 기존/미판정/Rollback | `2 passed` |
| T-018 계약+Runtime | `12 passed` |
| PostgreSQL T-017B Admin+T-018 Runtime | `16 passed` |
| 관련 도메인 회귀 | `145 passed, 2 skipped` |
| 전체 Backend | `817 passed, 13 skipped` |

13개 Skip은 기존 테스트에 PostgreSQL·pgvector·Row Lock 전용으로 명시된
항목이다. T-018 Runtime은 별도 PostgreSQL Test에서 PASS했다.

## 9. QA 재현 절차

QA는 공식/공유 DB가 아닌 자신의 격리 DB에서 수행한다.

```powershell
cd C:\Users\Playdata\Documents\SKN29-Final-4team\backend
$env:POSTGRES_DB='QA가 생성한 빈 검증 DB명'
python manage.py migrate --noinput --settings=config.settings.local
python manage.py migrate --check --noinput --settings=config.settings.local
python manage.py makemigrations --check --dry-run --settings=config.settings.local
python -m pytest -q tests/unit/accounts tests/api/test_t018_subscription_runtime.py
```

기존 데이터 Backfill을 검증하려면 승인된 합성 데이터 DB를 복제하고 같은
명령을 실행한다. QA Engine의 비어 있는 `watercare`를 공식 원본처럼
동일화할 필요는 없다. 빈 DB 검증 목적이면 그대로 전체 Migration을 적용하고,
기존 DB Backfill 목적이면 승인된 `waterbridge` 계열 복제본이 필요하다.

Rollback:

```powershell
python manage.py migrate accounts 0003 --noinput --settings=config.settings.local
python manage.py migrate accounts 0004 --noinput --settings=config.settings.local
```

## 10. QA 확인 요청

방향 승인이나 새 정책 결정이 아니라 다음 결과만 확인한다.

1. 빈 DB Forward·Rollback·재적용
2. 기존 합성 DB의 사용자 분류 100%, 미판정·중복·충돌 0
3. Admin 비staff·비OPERATOR·Permission 미보유 차단
4. 물리 삭제·Superuser 변경·CSRF 없는 POST 차단
5. T-018 본인 ACTIVE 지원 모델만 조회
6. 타 고객·비활성·미지원·삭제 고객 동일 404
7. unknown Query 422와 민감정보 미노출

QA의 독립 PASS가 오면 T-017B 공식 완료 확인 자료로 사용한다. T-017C나
T-018 등록·수정까지 승인됐다고 해석하지 않는다.
