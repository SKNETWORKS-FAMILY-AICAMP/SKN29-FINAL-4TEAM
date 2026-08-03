# Django JWT·RBAC T-017 QA 검토 인계서

- 담당: 최지용(Backend·Database) → 김은진(Data·QA)
- 검토 범위: `T017_AUTH_RBAC_COMPLETION`
- 출발 Main: `d93779bb2afde266d7fbeae3b8f8b8687db43100`
- 검토 후보: 전달받은 `origin/jiyong` Commit SHA
- 현재 상태: 기능 검증 PASS / 고정 후보 QA 재현 대기

## 인계 목적

기존 QA에서는 Runtime·PostgreSQL이 통과했지만 기준 SHA에 Matrix 파일이 없어 `submission_decision=HOLD`였습니다. 이번 후보에는 Matrix 테스트를 포함했으므로 같은 SHA에서 최종 재현을 요청합니다.

## 후보 파일

1. `backend/tests/unit/accounts/test_auth_role_matrix.py`
2. `docs/individual/jiyong/인증_권한/Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md`
3. `docs/individual/jiyong/인증_권한/Django_JWT_RBAC_QA_검토_인계서.md`

Runtime·Model·Migration 변경은 없습니다.

## 작성자 검증

| 항목 | 결과 |
| --- | --- |
| 4역할 Matrix | `4 passed`, exit `0` |
| Accounts | `70 passed`, exit `0` |
| 문의 RBAC·IDOR | `24 passed`, exit `0` |
| Django·Migration Check | 모두 exit `0` |
| PostgreSQL Readiness | `OWNER_IMPLEMENTATION_READY`, PostgreSQL PASS |

## QA 재현 명령

```powershell
Set-Location backend
$python = ".\.venv\Scripts\python.exe"
& $python -m pytest -q -p no:cacheprovider tests/unit/accounts/test_auth_role_matrix.py
& $python -m pytest -q -p no:cacheprovider tests/unit/accounts
& $python -m pytest -q -p no:cacheprovider tests/api/test_t022_create_inquiry.py tests/api/test_t023_cancel_inquiry.py
& $python manage.py check
& $python manage.py makemigrations --check --dry-run
& $python manage.py migrate --check --noinput
& $python .\apps\accounts\readiness.py --verify-postgresql
```

## 요청 회신

```text
reviewer=김은진
review_scope=T017_AUTH_RBAC_COMPLETION
candidate_sha=<검증한 SHA>
functional_decision=PASS | FAIL
submission_decision=APPROVE | HOLD
matrix_result=<결과·exit code>
accounts_result=<결과·exit code>
inquiry_rbac_result=<결과·exit code>
postgresql_result=<결과·exit code>
remaining_blocker=<없음 또는 상세>
```

`submission_decision=APPROVE`와 `remaining_blocker=없음`을 받은 뒤 윤승혁(PM)이 T-017 WBS 완료를 판정합니다. T-017A·B·C와 기사 E2E(T-042·T-047)는 이번 승인 범위가 아닙니다.
