# 최지용 Auth API 계약·Runtime 정합화 보고서 v1.0

> 기준일: 2026-07-27
> 명령 실행 기준: 저장소 루트
> 범위: 구현된 Auth API 4개

## 0. 문서 책임·협업·검토

| 항목 | 내용 |
| --- | --- |
| 문서 상태 | `CURRENT` — 구현된 Auth API 4개의 계약·Runtime 검증 기준 |
| 관련 WBS | `T-017` |
| 작성·유지 책임 | 최지용 — Auth 계약·Django Runtime·검증 증거 갱신 |
| 산출물/내용 의사결정자 | 최지용 — API 명세, JWT·RBAC와 Backend 구현 기준 |
| 협업 책임 | 윤승혁(PM) — 계약·Backend 통합, 김은진 — QA·보안·로그·회귀 검증, 한예나 — Web 인증 소비, 양정현 — Mobile 인증 소비 |
| 검토 요청 대상 | 윤승혁(PM)의 계약·통합 검토, 김은진의 QA 재현과 한예나·양정현의 DTO·오류 호환성 확인 |
| 검토 상태 | **미요청 또는 증거 미확인** — 이 문서에는 완료된 리뷰의 PR·Issue·Commit 증거가 아직 연결되어 있지 않음 |
| PR 병합 담당 | 윤승혁(PM) — 작성자가 아닌 팀원 1명 이상의 리뷰 후 병합 |
| 인계 대상 | 윤승혁(PM), 김은진, 한예나, 양정현 |

검토는 최지용의 API 명세 작성이나 Auth 구현 착수를 허가하는 선행
승인이 아니다. 확정 계약과 Runtime의 통합성, 보안 회귀 및 Web·Mobile
소비 호환성을 확인하는 절차다.

## 1. 판정

Auth API 4개는 확정 명세, OpenAPI, Serializer, Django Runtime,
PostgreSQL과 실제 HTTP Smoke에서 같은 기준으로 동작한다.

| 항목 | 2026-07-27 당시 실행 결과 |
| --- | --- |
| Auth Runtime Route | 4개 |
| Health Runtime Route | 1개 |
| PostgreSQL | 16.14·`CONNECTED` |
| Access Token | 60분·3,600초 |
| Refresh Token | 최초 발급부터 최대 7일·604,800초, rotation 시 절대 만료 연장 없음 |
| Auth 집중 테스트 | 21 passed |
| Backend 전체 회귀 | 239 passed |
| 실제 HTTP Smoke | 2회 PASSED |
| Token 로그 노출 | 0건 |

ERD·테이블·API 명세는 최지용의 확정 산출물이다. 이번 작업은 확정
기준을 OpenAPI·Serializer·Runtime에 반영하고 검증한 기록이다. 표의
테스트 수와 Smoke 결과는 기록 시점 스냅샷이며 현재 Branch 완료
판정에는 같은 Commit에서 재실행한 결과를 사용한다.

## 2. 정합화 대상

| 기능 | Method·Path | 상태 |
| --- | --- | --- |
| Demo 로그인 | `POST /api/v1/auth/demo-login` | 구현·Smoke 통과 |
| 현재 사용자 | `GET /api/v1/me` | 구현·Smoke 통과 |
| Token 재발급 | `POST /api/v1/auth/refresh` | 구현·Smoke 통과 |
| 로그아웃 | `POST /api/v1/auth/logout` | 구현·Smoke 통과 |

관련 기준 파일:

- [OpenAPI](<../../../../contracts/api/openapi.yaml>)
- [Auth API Path](<../../../../contracts/api/paths/auth.yaml>)
- [Login Response Schema](<../../../../contracts/api/components/schemas/auth/LoginResponse.yaml>)
- [User Model](<../../../../backend/apps/accounts/models/user.py>)
- [CustomerProfile Model](<../../../../backend/apps/accounts/models/customer_profile.py>)
- [Auth Serializer](<../../../../backend/apps/accounts/api/serializers.py>)
- [Auth View](<../../../../backend/apps/accounts/api/views.py>)
- [Auth URL](<../../../../backend/apps/accounts/api/urls.py>)
- [JWT Authentication](<../../../../backend/common/authentication/jwt_authentication.py>)
- [Accounts 최초 Migration](<../../../../backend/apps/accounts/migrations/0001_initial.py>)

## 3. Runtime 계약

### 3.1 Token

| 항목 | 확정값 |
| --- | --- |
| Access 수명 | 60분·3,600초 |
| Refresh 수명 | 최초 발급부터 최대 7일·604,800초 |
| Refresh | 회전 시 기존 Token Blacklist, 새 Token은 최초 Refresh의 `exp` 계승 |
| 만료 응답 | 로그인은 `604800`, rotation은 최초 `exp`까지 남은 초 |
| Logout | 제출 Refresh 즉시 폐기 |
| Claim | 사용자 식별자·역할, 개인정보 제외 |

Settings, `.env.example`, Auth 테스트, OpenAPI Schema와 실제 Smoke의
만료값을 모두 같은 값으로 맞췄다.

### 3.2 사용자·역할

| 항목 | 기준 |
| --- | --- |
| 사용자 Model | `AbstractBaseUser + PermissionsMixin`, 문자열 PK |
| 역할 | `CUSTOMER`, `CONSULTANT`, `TECHNICIAN`, `OPERATOR` |
| Demo 로그인 | 로컬 활성화와 합성 코드 Allowlist 모두 필요 |
| 고객 범위 | 자신의 Profile과 owner 데이터만 허용 |
| 기사 범위 | 자신에게 배정된 데이터만 허용 |
| 관리자 범위 | 명시적으로 허용한 역할에만 부여 |
| 삭제 | `deleted_at` 기반 논리 삭제 |

모든 인증 요청은 Token 발급 당시 Claim만 신뢰하지 않고 현재 DB
사용자의 활성 상태와 역할을 다시 확인한다. 비활성 사용자, 변경된
역할, 잘못된 서명·만료 Token은 차단한다.

### 3.3 오류·보안

- 인증이 없거나 Token이 잘못된 요청: 401·`AUTH_REQUIRED`
- 로컬 Demo 로그인이 비활성화된 요청: 403
- Allowlist 밖 Demo 코드: 401·`AUTH_REQUIRED`
- owner·assignee 범위 밖 객체: Permission 계약에 따라 차단
- `/me`: password·phone·주소·Token을 반환하지 않음
- 로그·Smoke 출력: Access·Refresh Token을 노출하지 않음
- 오류 응답: `X-Correlation-ID`와 공통 오류 Wrapper 유지

## 4. OpenAPI 정합화

- 문서 버전 `0.5.0`
- Auth 4개 operation을 확정 Runtime과 연결
- `access_expires_in: 3600`
- `refresh_expires_in`: 1~604800초. 로그인은 604800초이며 rotation 응답은 최초 Refresh 절대 만료시각까지 남은 초
- Login·Refresh·Logout 요청 필드와 Serializer 일치
- 성공·오류 응답의 Correlation Header와 공통 Metadata 유지

확정 API 인덱스는 Public 41개와 Internal 5개다. 현재 실제 Django
Route는 Health 1개와 Auth 4개다. 나머지 API는 관련 Model·Migration
Wave 이후 Runtime으로 구현한다.

## 5. 재현 검증

저장소 루트에서 실행한다.

```powershell
Set-Location .\backend

.\.venv\Scripts\python.exe -m pytest -q `
  tests/unit/accounts/test_auth_contracts.py `
  tests/unit/accounts/test_auth_api.py `
  tests/api/test_openapi_common_contract.py

.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe ..\scripts\smoke\check_backend_auth.py
```

Smoke 사전조건과 전체 실행 순서는
[공유 패키지 인계서](<./20260727_최지용_Django_PostgreSQL_공유패키지_인계서_v1.0.md>)를
따른다.

## 6. 실제 HTTP 검증

| 시나리오 | 결과 |
| --- | --- |
| `/health` Liveness·Correlation | 통과 |
| 허용 Origin CORS | 통과 |
| 미허용 Origin CORS 차단 | 통과 |
| Demo 로그인 | 200 |
| Access 수명 | 3,600초 |
| 최초 Refresh 수명 | 604,800초 |
| 회전 Refresh 수명 | 최초 Refresh의 `exp`를 유지하며 남은 초 반환 |
| Access로 `/me` | 통과 |
| `/me` 안전 Projection | 통과 |
| Refresh rotation | 통과 |
| 이전 Refresh 재사용 | 401 |
| Logout | 200·`revoked=true` |
| 폐기 Refresh 재사용 | 401 |
| 미인증 `/me` | 401 |
| Allowlist 밖 Demo 코드 | 401 |
| Runtime 로그 Token Scan | 0건 |

## 7. 현재 범위와 다음 작업

현재 완료:

- User·CustomerProfile Model
- Accounts 최초 Migration
- Demo Seed 4종
- Auth 4 API
- JWT rotation·blacklist
- customer owner·technician assignee 범위
- OpenAPI·Serializer·Runtime 정합성
- PostgreSQL·실제 HTTP Smoke

후속:

- T-005 Wave 1 검증
- T-005 Wave 2 구현·검증
- T-022 문의 Model·Migration·Service·API 수직 흐름
- 이후 Workflow·제품·구독·지식·AI API Runtime

다음 작업은 T-005 Wave 1이며, Wave 1 검증이 끝난 뒤에만 Wave 2로
이동한다. Wave 2 검증 후 T-022를 구현한다.

## 8. 연결 문서

- [공유 패키지 인계서](<./20260727_최지용_Django_PostgreSQL_공유패키지_인계서_v1.0.md>)
- [Django·PostgreSQL Migration 검증](<./20260727_최지용_Django_PostgreSQL_Migration_검증보고서_v1.0.md>)
- [API 계약 인계 가이드](<../technical/backend/api_contract_handover_guide.md>)
- [ADR-0009](<../../../adr/0009-t017-jwt-rbac-owner-baseline.md>)

## 9. 변경 이력

| 버전 | 날짜 | 내용 |
| --- | --- | --- |
| v1.0 | 2026-07-27 | Auth 구현·RBAC·JWT 60분/7일·PostgreSQL·Smoke·OpenAPI 증거를 최신 기준으로 통합 |
| v1.1 | 2026-07-27 | Refresh rotation이 최초 절대 만료시각을 연장하지 않도록 Runtime·OpenAPI·회귀 검증 기준 정합화 |

## 10. 인계 사항

| 대상 | 전달 항목 | 다음 행동 | 완료 확인 | 현재 상태 |
| --- | --- | --- | --- | --- |
| 윤승혁(PM) | Auth 4개 계약, JWT·RBAC 기준, 현재 Runtime과 OpenAPI 정합화 결과 | 공통 계약·Backend 통합 충돌을 확인하고 비작성자 리뷰 후 PR 병합 | 통합 검토 의견 또는 승인 기록과 병합 Commit이 남음 | 작성자 정합화 완료, 검토·병합 증거 미확인 |
| 김은진 | Auth 집중 테스트, 전체 회귀, 실제 HTTP Smoke, Token·개인정보 비노출 기준 | PostgreSQL 환경에서 인증·권한·rotation·logout·로그 노출을 재현 검증 | 실행 결과와 발견 사항이 PR 또는 Issue에 남고 핵심 테스트가 통과 | 작성자 검증 완료, 제3자 QA 증거 미확인 |
| 한예나 | Demo 로그인·`/me`·재발급·로그아웃, CORS, 401·403·404와 Token 수명 | Web API 계층에서 네 Endpoint와 오류 Wrapper·Header 호환성을 확인 | Web 연동 결과 또는 필드·오류 차이가 PR 또는 Issue에 남음 | 인계 자료 준비 완료, Web 소비 확인 미확인 |
| 양정현 | Demo 로그인·`/me`·재발급·로그아웃, Authorization Header, 401·403과 Token 수명 | Mobile 네트워크 계층에서 인증 갱신·로그아웃·오류 처리를 확인 | Mobile 연동 결과 또는 필드·오류 차이가 PR 또는 Issue에 남음 | 인계 자료 준비 완료, Mobile 소비 확인 미확인 |
| 최지용 | 계약·QA·Web·Mobile 검토에서 확인된 재현 가능한 차이 | OpenAPI·Serializer·Runtime·테스트를 같은 변경 단위로 수정하고 다시 검증 | Auth 집중 테스트·Smoke·전체 회귀 결과가 갱신됨 | 회신 대기 |

합성 사용자 코드는 공유할 수 있지만 실제 Secret, Token, Password와
개인정보는 인계하지 않는다. 완성형 회원가입·비밀번호 재설정·소셜
로그인은 현재 Auth 인계 범위가 아니다.
