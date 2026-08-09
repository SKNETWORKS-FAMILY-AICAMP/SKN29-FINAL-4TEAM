# Django Admin 합성계정 구현·검증 가이드

> 기준일: 2026-08-08
> WBS 범위: T-017B
> 구현 상태: 작성자 구현·SQLite·PostgreSQL 검증 완료
> 공식 상태: 독립 QA와 WBS 완료 확인 전

## 1. 목적과 완료 경계

이 문서는 합성 사용자만 관리하는 내부 Django Admin과
`User.is_synthetic` Backfill을 재현한다. 다음 항목을 T-017B 결과로 본다.

- 내부 URL `/internal/admin/`
- 합성계정 생성·조회·프로필 수정
- 명시적 비활성화·재활성화 Action
- OPERATOR·staff·Model Permission의 3중 접근 경계
- 물리 삭제·권한 상승·Superuser 변경 차단
- 빈 DB·기존 DB·Rollback 검증

다음은 T-017C 범위이므로 이 문서에서 완료로 선언하지 않는다.

- `auth_version`과 과거 Token 일괄 폐기
- 계정 Lifecycle 전용 Service·API
- Account AuditEvent와 사유·전후값 저장
- 마지막 활성 관리자·권한 보유자 보호

## 2. 구현 파일

| 영역 | 파일 | 책임 |
| --- | --- | --- |
| Model | `backend/apps/accounts/models/user.py` | `is_synthetic` 기본값 `False` |
| Migration | `backend/apps/accounts/migrations/0004_add_user_is_synthetic.py` | 기존 사용자 판정·안전 중단 |
| Admin Form | `backend/apps/accounts/admin_forms.py` | 허용 필드만 입력·수정 |
| Admin | `backend/apps/accounts/admin.py` | 접근·조회·변경·Action 경계 |
| 권한 Bootstrap | `backend/apps/accounts/management/commands/bootstrap_account_admin.py` | 고정 Group·Permission·staff 부여/회수 |
| 설정·URL | `backend/config/settings/base.py`, `backend/config/urls.py` | Admin·Session·CSRF·내부 URL |
| Seed·Importer | `seed_demo_accounts.py`, `operations_service.py` | 합성 사용자 명시 저장 |
| Login 조회 | `account_repository.py` | Demo/SYN 로그인 시 합성 사용자만 허용 |

## 3. `is_synthetic` 정책

신규 일반 사용자는 `False`가 기본이다. Demo Seed, 공식 합성 Importer,
내부 Admin 생성만 `True`를 명시한다. 사용자명 접두어만 보고 전체 기존
데이터를 추측 분류하지 않는다.

기존 사용자는 다음 증거 중 하나가 있을 때만 `True`로 Backfill한다.

1. 공식 Demo 사용자명 4개와 정확히 일치
2. 연결된 `CustomerProfile.is_synthetic=True`
3. 완료된 `db-full` Import Ledger의 `users → accounts.User` 매핑과
   source/target 공개 ID·업무 Key가 일치

다음 중 하나라도 발견하면 Migration 전체를 중단한다.

- 미판정 사용자 1명 이상
- username·employee_no·customer_no 중복
- Import Ledger source/target 충돌
- Backfill 후 null 잔존

오류에는 건수만 출력하며 사용자 식별자·개인정보는 출력하지 않는다.

## 4. Admin 접근·변경 정책

접근자는 다음 조건을 모두 충족해야 한다.

1. 인증·활성 계정
2. `is_staff=True`
3. `role_code=OPERATOR`
4. `accounts.User`의 `add`, `change`, `view` Permission

고정 Group에는 `delete_user`를 부여하지 않는다.

```powershell
python manage.py bootstrap_account_admin --settings=config.settings.local
python manage.py bootstrap_account_admin --grant SYN-OPERATOR-001 --settings=config.settings.local
python manage.py bootstrap_account_admin --revoke SYN-OPERATOR-001 --settings=config.settings.local
```

`--grant` 대상은 활성·합성·OPERATOR이며 Superuser가 아니어야 한다.
`--revoke`는 Group과 staff 접근을 함께 회수한다.

## 5. 화면에서 허용하는 값

생성 시 허용:

- `username`: `DEMO-` 또는 `SYN-` 접두어
- `password1`, `password2`: Django Password Hasher 사용
- `role_code`, `employee_no`
- `full_name`, `email`, `phone`

개인정보 오입력 차단:

- 이름은 `Synthetic`, `Demo`, `합성` 중 하나를 포함
- Email은 비우거나 예약된 `.invalid` 도메인 사용
- 전화번호는 비우거나 숫자 `0`만 사용
- 직원 역할의 사번은 `DEMO-` 또는 `SYN-`으로 시작

생성 시 서버가 강제:

- `is_synthetic=True`
- `is_active=True`
- `is_staff=False`
- `is_superuser=False`

생성 후 변경 가능:

- `full_name`, `email`, `phone`

읽기 전용 또는 미노출:

- username·공개/내부 ID·role·employee_no
- is_synthetic·is_active·is_staff
- is_superuser·Group·개별 Permission
- 생성·수정·로그인 시각

물리 삭제는 개별·Bulk 모두 금지한다. Superuser는 조회만 가능하며 POST
변경은 403이다. 비활성화 Action은 요청자 자신과 Superuser를 건너뛴다.

## 6. 적용 전 점검

```powershell
python manage.py check --settings=config.settings.local
python manage.py makemigrations --check --dry-run --settings=config.settings.local
python manage.py migrate --plan --settings=config.settings.local
```

DB 이름은 `.env` 원문이나 DSN을 출력하지 말고 다음처럼 안전한 검사기로
확인한다.

```powershell
python scripts/database/check_postgresql_connection.py
```

출력의 `current_database`, `current_schema`, PostgreSQL Version만 증거로
사용한다.

## 7. 적용·검증

```powershell
cd backend
python manage.py migrate --noinput --settings=config.settings.local
python manage.py migrate --check --noinput --settings=config.settings.local
python -m pytest -q tests/unit/accounts
```

핵심 Test:

- 비staff·비OPERATOR·Permission 미보유 접근 차단
- 고정 Group 반복 실행과 Grant/Revoke
- 생성 시 합성·비staff·비Superuser 강제
- 보호 필드 POST 변조 무시
- 물리 삭제·Superuser 변경 403
- 자기 자신·Superuser 비활성화 보호
- CSRF 없는 Admin POST 403
- 실제 개인정보로 보일 수 있는 이름·Email·전화 입력 거부
- 빈 DB·기존 DB Backfill·미판정 중단·Rollback

## 8. Rollback

반드시 전용 검증 DB나 복구 가능한 환경에서 먼저 실행한다.

```powershell
python manage.py migrate accounts 0003 --noinput --settings=config.settings.local
python manage.py migrate accounts 0004 --noinput --settings=config.settings.local
```

`0003`으로 내리면 `is_synthetic` 컬럼만 제거된다. Admin·Session 테이블은
별도 Django Migration이므로 자동 삭제하지 않는다. 운영 데이터가 있는
Admin/Session Migration을 `zero`로 내리는 작업은 이 가이드의 자동
Rollback 범위가 아니다.

## 9. 2026-08-08 검증 결과

| 검증 | 결과 |
| --- | --- |
| 계정·공식 Importer 표적 회귀 | `89 passed` |
| PostgreSQL 빈 DB | Forward·Rollback·재적용 PASS, 사용자 0 |
| PostgreSQL 기존 DB 복제 | 사용자 20/20 분류, 미판정 0 |
| 원본 로컬 `waterbridge` | 사용자 20/20, `accounts.0004` 적용 |
| 해당 Slice 검증 시점 전체 Backend 회귀 | `817 passed, 13 skipped` |

13개 Skip은 기존 PostgreSQL·pgvector 전용 표식이며 이번 계정 기능 실패가
아니다. 독립 QA는 구현 방향이 아니라 위 명령과 보호 경계를 재현해 결과를
확인한다. 작업 식별은 기준일·Branch·Migration 이름·변경 파일·실행
결과를 사용한다.
