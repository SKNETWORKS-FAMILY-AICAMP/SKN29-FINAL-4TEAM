# 계정 UUID·JWT 전환·복구 가이드

> 관련 업무: 계정 식별자 표준화
> 위험도: 고위험 Schema·Token 변경

## 1. 목표

계정 내부 식별과 공개 식별을 분리하고 JWT·FK·M2M이 UUID 사용자 계약을
일관되게 사용하도록 전환한다.

## 2. 불변 조건

- 공개 API와 JWT에서 정수 PK를 노출하지 않는다.
- 기존 FK·M2M 관계와 사용자별 업무 데이터가 보존된다.
- UUID는 충돌 없이 결정적으로 Backfill한다.
- 전환 중 혼합 식별자를 조용히 허용하지 않는다.
- 적용된 Migration 파일을 수정하지 않는다.

## 3. 주요 경로

- `backend/apps/accounts/models/user.py`
- `backend/apps/accounts/migrations/**`
- `backend/common/authentication/jwt_authentication.py`
- `backend/tests/unit/accounts/**`
- `backend/tests/integration/accounts/**`

## 4. 적용 순서

1. 대상 User·FK·M2M·Token Claim 인벤토리 확인
2. 백업·복구 지점 확인
3. Nullable UUID 추가와 Backfill
4. FK·M2M 참조 전환
5. PK·Unique·Not Null 제약 확정
6. JWT 발급·검증을 UUID-only로 전환
7. 빈 DB와 기존 데이터 DB Migration
8. Token·권한·Rollback 회귀

## 5. 검증

| 항목 | 성공 조건 |
| --- | --- |
| UUID | Null·중복 0 |
| 관계 | FK·M2M 유실 0 |
| JWT | UUID `sub` 발급·검증 |
| Legacy | 정수·username 식별 Token 거부 |
| Migration | Forward·지원 Reverse·Reapply 성공 |
| 권한 | Role·객체 범위 유지 |
| PII | Token·로그·응답 비노출 |

```powershell
.\backend\.venv\Scripts\python.exe .\backend\manage.py migrate --plan
.\backend\.venv\Scripts\python.exe .\backend\manage.py migrate --noinput
.\backend\.venv\Scripts\python.exe .\backend\manage.py makemigrations `
  --check --dry-run
```

## 6. 복구 원칙

문제 발생 시 Migration Table을 수동 수정하거나 `--fake`로 우회하지 않는다.
적용 단계와 데이터 보존 여부를 확인한 뒤 승인된 Reverse 또는 새 교정
Migration을 사용한다.

## 7. 판정

식별자·관계·JWT·권한·Migration Roundtrip이 PostgreSQL에서 재현되면 기술
전환 완료다. 운영 Token 교체와 배포 판정은 별도다.
