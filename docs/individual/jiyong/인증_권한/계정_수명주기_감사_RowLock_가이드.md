# 계정 수명주기·감사·Row Lock 구현 가이드

> 관련 업무: 계정 활성화·잠금·회수·감사
> 핵심 불변식: 실사용 가능한 관리자 1명 이상 유지

## 1. 구현 범위

- 계정 상태 변경과 Token Generation 증가
- 접근 회수·재활성화의 Transaction 처리
- 마지막 실사용 관리자 보호
- 변경 전후 값과 Actor를 감사 원장에 기록
- 민감정보 Redaction과 감사 불변성
- PostgreSQL 동시 요청 직렬화

## 2. 주요 경로

- `backend/apps/accounts/services/account_lifecycle_service.py`
- `backend/apps/accounts/models/account_audit_event.py`
- `backend/apps/accounts/migrations/**`
- `backend/tests/integration/accounts/test_t017c_lifecycle_postgresql.py`

## 3. Transaction 순서

1. 수명주기 Singleton Lock 행 잠금
2. 대상 계정 잠금
3. Actor 권한과 대상 상태 재검증
4. 마지막 관리자 불변식 확인
5. 상태·Token Generation 변경
6. 감사 이벤트 저장
7. 전체 Commit 또는 Rollback

## 4. Singleton Lock

Migration이 생성한 Lock 행은 Runtime 불변식이다. `TransactionTestCase`의
Flush 뒤에는 테스트 준비 단계에서 `pk=1` 행을 명시적으로 보장한다.
서비스에서 무조건 `get_or_create`하여 동시성 오류를 숨기지 않는다.

## 5. 검증 Matrix

| Case | 기대 결과 |
| --- | --- |
| 정상 회수 | 상태·Generation·Audit 1회 저장 |
| Replay | 중복 변경·감사 0 |
| 실패 주입 | 상태·감사 전체 Rollback |
| 마지막 관리자 | 회수 거부 |
| 관리자 2명 동시 회수 | 정확히 1명만 성공 |
| 감사 변경·삭제 | 거부 |
| 민감 필드 | 로그·감사 원장 비노출 |
| Suite 순서 | 단독·전체 실행 결과 동일 |

## 6. 재현

```powershell
$env:POSTGRESQL_CONCURRENCY_TEST='1'
.\backend\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  .\backend\tests\integration\accounts\test_t017c_lifecycle_postgresql.py
```

실제 PostgreSQL에서 Lock Case가 skip되지 않아야 한다.

## 7. 판정

Migration Roundtrip, Token 회수, Rollback, 마지막 관리자 보호, 감사 불변성과
동시성·Suite 순서 독립성이 통과하면 구현 완료다.
