# ADR 0009: T-017 JWT·RBAC 인증 기준선

> 기계 상태: `OWNER_BASELINE_ACCEPTED`
>
> 현재 해석: `ACTIVE_IMPLEMENTED_REVIEW_PENDING`
>
> 결정일: 2026-07-26
>
> 초기 결정 책임: Backend·Database 담당(T-017)
>
> 공식 완료 경계: Auth Runtime 작성자 검증 완료, 상담·방문 객체 권한
> E2E와 비작성자·소비자 재현 대기
>
> 대상 WBS: `T-017`

`OWNER_BASELINE_ACCEPTED`는
[T-017 준비도 검사](../../backend/apps/accounts/readiness.py)가
인식하는 기계 상태값이다. 인증 결정의 채택과 전체 WBS 완료 판정은
구분한다.

## 1. 결정

| 항목 | 기준 |
| --- | --- |
| Public 인증 | Bearer JWT, HS256, Django `SECRET_KEY` 서명 |
| Access 만료 | 기본 60분, `JWT_ACCESS_TTL_MINUTES`로 주입 |
| Refresh 만료 | 최초 발급 시 기본 168시간(7일), `JWT_REFRESH_TTL_HOURS`로 주입 |
| Rotation | Refresh 사용 시 새 Access·Refresh를 발급하되 최초 Refresh의 `exp` 절대 상한은 연장하지 않음 |
| Revocation | 회전·로그아웃 시 사용한 Refresh를 blacklist |
| Access 폐기 | 별도 서버 저장 없이 만료시키되 사용자 비활성·역할 변경은 매 요청 DB 재검증으로 즉시 차단 |
| 만료 응답 | `access_expires_in`은 설정된 Access TTL에서 산출하며 기본값은 3,600초; `refresh_expires_in`은 최초 Refresh 절대 만료시각까지 남은 초 |
| Claim | `sub`, `role_code`, `token_type`, `jti`, `iat`, `exp` |
| 사용자 식별자 | 내부 `BigAutoField` PK는 노출하지 않고 `public_id` UUID를 JWT `sub`와 응답 ID로 사용 |
| Legacy subject | 문자열 PK fallback을 허용하지 않음 |
| 역할 코드 | `CUSTOMER`, `CONSULTANT`, `TECHNICIAN`, `OPERATOR` |
| Demo 로그인 | 설정이 켜지고 allowlist에 포함된 `DEMO-`/`SYN-` 합성 사용자 코드만 허용 |
| 객체 범위 | 고객은 owner, 기사는 assignee가 일치하는 객체만 허용; 목록은 Repository·Service에서 범위 제한 |

식별자 전환의 결정과 완료 상태는
[ADR 0010](0010-t005-three-layer-identifier-bridge.md)과
[Physical Contract v1.3](../database/t-005/t005_physical_contract_v1.3.json)을
따른다.

## 2. 보안 경계

- 운영 설정에서 Demo 로그인은 기본 비활성이다.
- 실제 토큰·서명키·DB 비밀번호는 Git·로그·문서에 기록하지 않는다.
- Refresh Token은 응답 외 로그와 감사 문서에 남기지 않는다.
- `/me`는 전화번호·주소·비밀번호·토큰 원문을 반환하지 않는다.
- Claim 역할과 DB의 현재 역할이 다르거나 사용자가 비활성이면 401로
  차단한다.
- 내부 정수 PK와 `legacy_id`는 Public API와 JWT에 노출하지 않는다.
- 상태 전이별 역할·상태 Guard는 `contracts/state-machine/**`의 기계
  계약을 따르며, 인증 ADR에서 임의로 확장하지 않는다.

## 3. Runtime 반영

| 책임 | 구현·계약 |
| --- | --- |
| JWT 설정 | [Django 기본 설정](../../backend/config/settings/base.py) |
| 발급·회전·폐기 | [AuthenticationService](../../backend/apps/accounts/services/authentication_service.py) |
| UUID subject 조회 | [AccountRepository](../../backend/apps/accounts/repositories/account_repository.py) |
| 사용자·공개 UUID·역할 | [User Model](../../backend/apps/accounts/models/user.py) |
| Access 요청 재검증 | [JWTAuthentication](../../backend/common/authentication/jwt_authentication.py) |
| owner·assignee 권한 | [권한 모듈](../../backend/apps/accounts/permissions.py) |
| Auth Endpoint | [Account URL](../../backend/apps/accounts/api/urls.py)·[View](../../backend/apps/accounts/api/views.py) |
| 기계 API 계약 | [Auth OpenAPI Path](../../contracts/api/paths/auth.yaml) |
| 핵심 회귀 | [Auth API 테스트](../../backend/tests/unit/accounts/test_auth_api.py) |

노출 Endpoint는 다음과 같다.

- `POST /api/v1/auth/demo-login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/me`

## 4. 완료되지 않은 범위

- 상담·방문 Endpoint가 실제 Runtime에 마운트된 뒤 기사 미배정·타인
  객체 접근을 포함한 역할별 E2E가 필요하다.
- T-017B Django Admin과 T-017C 계정 수명주기·계정 감사는 별도
  작업이며 이 ADR의 Auth Endpoint 구현으로 완료됐다고 보지 않는다.
- 비작성자·Web·Mobile 소비자가 역할별 계정과 오류 예시를 독립
  재현해야 공식 완료 Gate를 충족한다.

상세 구현·미구현 경계와 재현 절차는
[Django JWT·RBAC 로그인·계정관리 구현 및 검증 가이드](../individual/jiyong/인증_권한/Django_JWT_RBAC_로그인_계정관리_구현_검증_가이드.md)를
따른다.

## 5. 검증

저장소 루트에서 Auth 계약과 Runtime을 함께 검증한다.

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\unit\accounts\test_auth_api.py -q -p no:cacheprovider
backend\.venv\Scripts\python.exe -m pytest backend\tests\unit\accounts\test_permissions.py -q -p no:cacheprovider
```

환경변수로 TTL을 바꾼 경우 JWT `exp - iat`와 응답의
`access_expires_in`·`refresh_expires_in`이 같은 설정을 반영하는지
검증한다.

## 6. 변경 원칙

알고리즘·TTL·Claim·역할·폐기 정책을 바꾸면 이 ADR의 후속 ADR,
Auth OpenAPI Schema·예시, 설정, Service와 회귀 테스트를 같은 변경
단위로 갱신한다. 적용된 Migration과 기존 ADR은 삭제하지 않는다.
