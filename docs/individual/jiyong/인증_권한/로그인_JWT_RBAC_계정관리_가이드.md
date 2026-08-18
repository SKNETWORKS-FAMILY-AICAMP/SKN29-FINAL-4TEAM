# Login·JWT·RBAC·계정관리 구현 가이드

> 관련 업무: 인증·역할 기반 접근·계정관리
> 역할: CUSTOMER·CONSULTANT·TECHNICIAN·OPERATIONS

## 1. 구현 범위

- Login·Refresh·Logout·`/me`
- JWT 사용자 식별과 Token 무효화
- 역할·활성 상태·합성 계정 검증
- 상담사·기사 배정 기반 객체 권한
- 운영자의 합성 계정 조회·변경
- Demo Login의 공개 식별자 경계

## 2. 주요 경로

- `backend/apps/accounts/**`
- `backend/common/authentication/**`
- `backend/common/permissions/**`
- `contracts/api/paths/auth.yaml`
- `contracts/api/components/schemas/auth/**`
- `contracts/state-machine/role-permissions.yaml`

## 3. 인증 원칙

- JWT `sub`에는 공개 UUID를 사용한다.
- 내부 사용자명·정수 PK·Password Hash를 응답하지 않는다.
- 비활성·잠금·회수된 계정은 기존 Token도 거부한다.
- Role만으로 객체 접근을 허용하지 않고 고객 본인·배정 관계를 함께 확인한다.
- 403과 존재 은닉이 필요한 404를 계약대로 구분한다.

## 4. 합성 계정

Demo Login은 합성 프로필만 허용하고 운영 환경에서는 기본 비활성화한다.
`demo_user_code`는 공개 별칭이며 내부 `username` 직접 입력을 허용하지 않는다.

Django Admin에서도 `is_synthetic`과 승인된 Role만 다룬다. 실제 고객 계정과
합성 계정을 한 화면·Seed·검증 DB에서 혼합하지 않는다.

## 5. 검증 Matrix

| 구간 | 확인 |
| --- | --- |
| Login | 정상·잘못된 자격·비활성·Role 오류 |
| Refresh | 정상·만료·회수 Token |
| Logout | Token 무효화와 Replay |
| `/me` | 최소 Projection과 민감정보 비노출 |
| RBAC | 역할별 허용·거부 Matrix |
| IDOR | 타 고객·미배정 상담사·미배정 기사 차단 |
| Demo | 공개 별칭 허용, 내부 username 거부 |
| Admin | 합성 계정만 허용된 필드 변경 |

## 6. 재현

```powershell
.\backend\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  .\backend\tests\unit\accounts `
  .\backend\tests\integration\accounts
```

PostgreSQL Row Lock Case는 실제 PostgreSQL QA DB에서 0 skip으로 확인한다.

## 7. 판정

인증 API, Token 회수, 역할·객체 권한, 합성 계정 경계와 로그 비노출이
통과하면 작성자 구현 완료다. 소비자 Login E2E와 PM 완료는 별도다.
