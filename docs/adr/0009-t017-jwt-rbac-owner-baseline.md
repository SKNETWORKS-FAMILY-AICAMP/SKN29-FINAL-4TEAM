# ADR 0009: T-017 JWT·RBAC OWNER 기준선

> 상태: `OWNER_BASELINE_ACCEPTED`
> 결정일: 2026-07-26
> 결정자: 최지용(T-017 OWNER)
> 소비자·QA 검토: 미요청 또는 증거 미확인 — OWNER 기준선 사용의 선행조건이 아님
> 대상 WBS: `T-017`

## 1. 결정

| 항목 | OWNER 기준선 |
| --- | --- |
| Public 인증 | Bearer JWT, HS256, Django `SECRET_KEY` 서명 |
| Access 만료 | 기본 60분, `JWT_ACCESS_TTL_MINUTES`로 주입 |
| Refresh 만료 | 최초 발급 시 기본 168시간(7일), `JWT_REFRESH_TTL_HOURS`로 주입; 회전된 refresh도 최초 token의 `exp` 절대 상한을 계승 |
| Rotation | refresh 사용 시 새 access·refresh를 발급하되 Refresh 절대 만료시각은 연장하지 않음 |
| Revocation | 회전·로그아웃 시 사용한 refresh를 blacklist |
| Access 폐기 | 별도 서버 저장 없이 최대 60분 후 만료; 사용자 비활성·역할 변경은 매 요청 DB 재검증으로 즉시 차단 |
| 만료 응답 | `access_expires_in`은 3,600초, `refresh_expires_in`은 최초 Refresh 절대 만료시각까지 남은 초 |
| Claim | `sub`, `role_code`, `token_type`, `jti`, `iat`, `exp` |
| 역할 코드 | `CUSTOMER`, `CONSULTANT`, `TECHNICIAN`, `OPERATOR` |
| Demo 로그인 | 설정이 켜지고 allowlist에 있는 `DEMO-/SYN-` 합성 사용자 코드만 허용 |
| 객체 범위 | 고객은 owner, 기사는 assignee가 일치하는 객체만 허용; 목록은 Repository/Service에서 범위 제한 |

## 2. 보안 경계

- 운영 설정에서 Demo 로그인은 기본 비활성이다.
- 실제 토큰·서명키·DB 비밀번호는 Git·로그·문서에 기록하지 않는다.
- Refresh token은 응답 본문 외 로그에 남기지 않는다.
- `/me`는 전화번호·주소·비밀번호·토큰 원문을 반환하지 않는다.
- Claim 역할과 DB의 현재 역할이 다르거나 사용자가 비활성이면 401로
  차단한다.
- 상태 전이별 세부 권한은 윤승혁(PM) 관할
  `contracts/state-machine/**`를 이번 작업에서 수정하지 않는다.

## 3. 구현

- `djangorestframework-simplejwt`의 서명·만료·blacklist 기능을 사용한다.
- Custom User와 CustomerProfile의 ID는 ADR 0008의 도메인 문자열
  기준을 사용한다.
- `POST /api/v1/auth/demo-login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/me`

팀 리뷰에서 정책을 변경하면 이 ADR과 기존 Migration을 지우지 않고
후속 ADR·Migration·계약 변경으로 이력을 남긴다.
