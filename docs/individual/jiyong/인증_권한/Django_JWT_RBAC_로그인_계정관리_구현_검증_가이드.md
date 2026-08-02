# Django JWT·RBAC 로그인·계정관리 구현 및 검증 가이드

> 기준일: 2026-08-02
> 작성·설계 책임: Backend·Database 담당
> 협업·검토: PM, Data·QA·DevOps
> 상태: 인증·RBAC 일부 작성자 검증 완료(`T017_PARTIAL_LOCAL_VERIFIED`) /
> T-017A 설계 기준안 팀 검토 대기(`T017A_OWNER_DESIGN_READY_REVIEW_PENDING`)
> 대상: `T-017` 인증·RBAC와 `T-017A~C` 계정관리 경계
> 후속 구현: `T-017B` 2026-08-03, `T-017C` 2026-08-04~05
> 데이터 범위: 합성 사용자와 내부 시연 관리자만
> 실행 원칙: `설계 결정 → 검토 → 한 작업 구현 → 즉시 검증`

이 문서는 T-017 인증·권한의 현재 구현과 합성 사용자 계정 관리의
계약·설계 기준을 함께 제공한다. 현재 구현된 인증·권한 기능과
앞으로 구현할 Django Admin·계정
수명주기·감사 기능을 구분한다. 이 문서를 작성한 것만으로
`T-017B`·`T-017C`의 Model, Migration, Admin, Service, 오류 코드가
구현된 것은 아니다.

## 0. 2026-08-02 현재 구현·검증 요약

| 범위 | 현재 상태 | 현재 근거 | 남은 Gate |
| --- | --- | --- | --- |
| Login·Refresh·Logout·`/me` | 구현됨 | Account URL·View·JWT Service·Auth 회귀 | 비작성자·소비자 최신 후보 재현 |
| UUID JWT·활성/역할 재검증 | 구현됨 | UUID `sub`, Refresh 회전·폐기, 사용자 활성·역할 재검사 | T-017C 계정 세대·전체 Token 폐기 |
| 4역할 Demo Seed | 구현됨 | CUSTOMER·CONSULTANT·TECHNICIAN·OPERATOR Seed | 역할별 호출 예시 소비자 재현 |
| Inquiry START·SUBMIT·CANCEL 권한 | 작성자 검증 완료, 팀 기준선 반영 전 | 4역할, 미인증 401, 비고객 403, 타 고객 404, 실패 부수효과 0 | 실제 상담·방문 Endpoint E2E |
| T-017A 설계 | 설계 기준안 작성 완료 | 이 문서의 정책·인수 Matrix | PM·Data·QA 리뷰 |
| T-017B/C | 미구현 | Admin·Lifecycle·Account Audit Runtime 없음 | T-017A 승인 후 순차 구현 |

현재 작성자 회귀 증거는 Auth/RBAC 집중 `43 passed`, Inquiry 역할·소유권
집중 `44 passed, 2 skipped`, Backend 전체 SQLite `778 passed,
13 skipped`, 격리 PostgreSQL `791 passed`다. 이 수치는 팀 기준선 반영
전 작성자 검증이며 공식 WBS 완료나 비작성자 재현을 대체하지 않는다.

실제 `/api/v1`에는 Accounts와 Inquiries만 마운트되어 있다. 상담·방문
URL·View·Permission은 Runtime 대상이 아니므로 기사 미배정 방문 E2E를
현재 T-017 완료 증거로 만들 수 없다.

## 1. 판정과 완료 경계

| 작업 | 현재 판정 | 근거와 의미 |
| --- | --- | --- |
| `T-017` 가상 로그인·JWT·RBAC | 일부 작성자 검증 완료(`PARTIAL_LOCAL_VERIFIED`) | Account Auth Runtime과 Inquiry 3개 Endpoint의 4역할·IDOR Matrix를 검증했다. 상담·방문 객체 권한 E2E와 작성자 외 리뷰는 별도 Gate다. |
| `T-017A` 계정 관리 설계 | 설계 기준안 작성 완료·팀 검토 대기(`OWNER_DESIGN_READY_REVIEW_PENDING`) | 정책·인수 Matrix가 기록됐지만 WBS 완료 조건의 PM·Data·QA 검토 증거는 아직 없다. |
| `T-017B` 내부 계정 관리 | 미구현(`NOT_IMPLEMENTED`) | 2026-08-03 구현 대상이다. 현재 [accounts Admin](../../../../backend/apps/accounts/admin.py)은 설명 문자열만 있고 Admin 앱·Session·CSRF·URL·Custom UserAdmin이 구성되지 않았다. |
| `T-017C` 계정 수명주기·감사 | 미구현(`NOT_IMPLEMENTED`) | 2026-08-04~05 구현 대상이다. 비활성화 Service, 전체 Refresh 폐기, 재활성화 전 Token 세대 차단, 계정 전용 감사 원장이 없다. |

`T-017`의 작성자 구현 준비 상태(`OWNER_IMPLEMENTATION_READY`)를
`T-017A~C` 완료로 확장
해석하지 않는다. 반대로 T-017A의 팀 검토가 남았다는 이유로 이미
검증된 Auth 4개 Endpoint를 미구현으로 되돌리지 않는다.

## 2. 설계 근거와 실제 코드

### 2.1 요구·일정 기준

- [WBS](../../../planning/md/WBS.md):
  `T-017A` 설계, `T-017B` Django Admin, `T-017C` 수명주기·감사를
  서로 다른 작업과 일정으로 정의한다.
- [요구사항정의서 v2.0](../../../planning/md/요구사항정의서.md):
  `FR-039`, `FR-042`, `NFR-019~020`, `DR-016`,
  `CR-013~014`를 정의한다.
- [API명세서 v2.0 최소 개정분](../../../planning/md/API명세서.md):
  내부 Django Admin 후보, Session·CSRF, Public API와의 분리,
  비활성화·삭제 제한과 제안 오류 코드를 정의한다.
- [ADR 0009](../../../adr/0009-t017-jwt-rbac-owner-baseline.md):
  JWT rotation·blacklist, 역할 Claim, 활성 상태·현재 역할 재검증을
  T-017 인증·권한 기준선으로 기록한다.

### 2.2 현재 구현된 사실

- [User Model](../../../../backend/apps/accounts/models/user.py)은
  내부 `BigAutoField` PK, 외부 `public_id` UUID, `role_code`,
  `is_staff`, `is_active`, `PermissionsMixin`을 가진다.
- [AuthenticationService](../../../../backend/apps/accounts/services/authentication_service.py)는
  Demo Login, JWT 발급, Refresh rotation, Logout과 사용된 Refresh
  blacklist를 구현한다.
- [AccountRepository](../../../../backend/apps/accounts/repositories/account_repository.py)는
  활성 사용자와 공개 UUID subject를 기준으로 조회한다.
- [AccountService](../../../../backend/apps/accounts/services/account_service.py)는
  민감값을 제외한 `/me` Projection을 만든다.
- [권한 모듈](../../../../backend/apps/accounts/permissions.py)은
  활성 사용자, 업무 역할, owner·assignee 범위를 fail-closed로
  검사한다.
- [인증 Controller](../../../../backend/apps/accounts/api/views.py)와
  [URL](../../../../backend/apps/accounts/api/urls.py)은
  Demo Login, Refresh, Logout, `/me`만 노출한다.
- [Auth 테스트](../../../../backend/tests/unit/accounts/test_auth_api.py)는
  비활성·역할 변경 재검증, Refresh rotation·blacklist와 안전
  Projection을 검증한다.

### 2.3 아직 구현되지 않은 사실

- [기본 설정](../../../../backend/config/settings/base.py)에
  `django.contrib.admin`, `sessions`, `messages`, Admin용 Template
  설정과 Session·Authentication·Message·CSRF Middleware가 없다.
- [최상위 URL](../../../../backend/config/urls.py)에
  `/internal/admin/` 경로가 없다.
- Custom `UserAdmin`, 계정 생성·수정 Form, 비활성화·재활성화
  Action과 서버 Guard가 없다.
- 현재 `User`에는 합성 여부를 모든 역할에서 명시하는 필드와 Token
  세대 번호가 없다.
- 기존 [AuditEvent](../../../../backend/apps/audit/models/audit_event.py)는
  문의·방문 상태 전이 전용이며 대상 유형이 `INQUIRY`·`VISIT`뿐이다.
  계정 변경 전후값을 저장할 계정 전용 감사 원장으로 사용할 수 없다.
- 아래 제안 오류 코드는 현재
  [Backend 오류 Registry](../../../../backend/common/exceptions/error_codes.py)와
  [OpenAPI](../../../../contracts/api/openapi.yaml)에 반영되지 않았다.

## 3. 계정 관리 설계 기준안

### 3.1 `accounts.User`를 단일 계정 원장으로 사용

1. 인증 가능한 고객·상담사·방문기사·운영 담당자와 내부 시연
   관리자의 계정 원장은 `accounts.User` 하나다.
2. `CustomerProfile`은 고객 업무 프로필 확장이다. 별도 로그인
   원장이나 두 번째 사용자 원장으로 사용하지 않는다.
3. DB 내부 FK는 정수 PK를 사용하고 외부 API·JWT subject는
   `public_id` UUID만 사용한다.
4. `legacy_id`, 내부 PK, Password hash, Token 원문은 Admin의 일반
   편집 필드와 Public 응답에 노출하지 않는다.
5. 합성 사용자 삭제 대신 `is_active=false`를 계정 상태의 단일
   기준으로 사용한다.

### 3.2 업무 역할과 관리자 권한을 분리

| 축 | 필드·기능 | 결정 |
| --- | --- | --- |
| 업무 역할 | `role_code` | `CUSTOMER`, `CONSULTANT`, `TECHNICIAN`, `OPERATOR`의 업무 범위만 표현한다. |
| Admin 진입 | `is_staff` | 내부 Admin Site 진입의 1차 조건이다. 업무 역할에서 자동 산출하지 않는다. |
| Admin 기능 | Django Group·Permission | Model별 조회·추가·변경 권한을 승인된 고정 Group에 부여한다. P0에서 사용자가 임의 위임·회수하지 못한다. |
| 최상위 비상 권한 | `is_superuser` | Bootstrap·복구용으로만 사용한다. 일반 계정 관리자 화면에서 조회·변경하지 못한다. |

`OPERATOR`는 운영 업무 역할일 뿐이다. `role_code=OPERATOR`라는 이유만으로
`is_staff`, Group, Permission을 자동 부여하지 않는다. 반대로 내부
시연 관리자가 Admin을 사용하더라도 해당 사용자의 업무 역할을
임의로 `OPERATOR`로 변경하지 않는다.

P0의 관리자 권한 위임·회수는 구현하지 않는다. 승인된 고정 Group과
초기 관리자는 Bootstrap 절차로 준비하고, 위임·회수는 `FR-040`의
P1 작업에서 별도 계약으로 구현한다.

### 3.3 내부 관리자 인터페이스

| 항목 | 설계 기준 |
| --- | --- |
| 경로 후보 | `/internal/admin/` |
| 인증 | Django Session |
| 요청 위조 방지 | CSRF |
| 접근 조건 | `is_active=True` + `is_staff=True` + 필요한 Model Permission + 서버 Guard |
| 네트워크 | 로컬·내부망·VPN·IP allowlist 중 PM이 승인한 배포 경계 |
| Public API | `/api/v1/admin/users/**`를 P0에 추가하지 않음 |
| OpenAPI | 내부 Admin HTML 인터페이스이므로 Public OpenAPI에 포함하지 않음 |

T-017B에서는 Django Admin 필수 App·Middleware·Template·Static·URL을
구성한다. Public JWT를 Admin Session 인증으로 재사용하거나 Admin
Session을 `/api/v1` 인증으로 재사용하지 않는다.

### 3.4 합성 사용자만 관리

P0 Admin은 실제 고객·직원·개인정보를 관리하지 않는다. 다음을
T-017B의 생성 Form과 Model 검증에 적용한다.

1. `accounts.User`에 `is_synthetic` Boolean을 추가하는 Migration을
   제안한다. MVP에서는 `True`만 허용한다.
2. 기존 행은 Demo Seed·Importer 원본과 `CustomerProfile.is_synthetic`
   값을 검사한 뒤 `True`로 backfill한다. 검증할 수 없는 행이 하나라도
   있으면 Migration을 중단한다.
3. `CUSTOMER`는 합성 `CustomerProfile`만 연결할 수 있다.
4. 상담사·기사·운영 담당자도 합성 이름·연락처·사번만 허용한다.
5. 실제 개인정보, 공개 회원가입, IAM·SSO·HR 연동은 구현하지 않는다.

`User.is_synthetic`은 **제안된 T-017B 필드**이며 현재 Model에는 없다.
PM·Data·QA 리뷰에서 별도 필드 대신 다른 불변식이 승인되면
Migration 전에 이 결정을 갱신한다.

### 3.5 Admin 필드 정책

| 분류 | 필드·동작 | 규칙 |
| --- | --- | --- |
| 생성 허용 | `username` | 합성 식별 규칙과 중복을 검증한다. 생성 후에는 읽기 전용이다. |
| 생성 허용 | Password 입력 | Django `set_password()` 또는 표준 Admin Password Form만 사용한다. 원문·Hash 직접 편집은 금지한다. |
| 생성·조건부 허용 | `role_code`, `employee_no` | 신규 합성 계정 생성 시 함께 검증한다. 기존 계정 변경은 T-017C의 역할 변경·Token 폐기 Service 전까지 읽기 전용이다. |
| 수정 허용 | `full_name`, `email`, `phone` | 합성값만 허용하고 실제 개인정보 입력을 금지한다. |
| Action 전용 | `is_active` | 직접 Checkbox 수정은 금지하고 비활성화·재활성화 Action과 Service로만 변경한다. |
| 강제·읽기 전용 | `is_synthetic` | MVP에서는 항상 `True`; 일반 관리자가 해제할 수 없다. |
| 읽기 전용 | `public_id`, `legacy_id`, 내부 `id` | 조회·추적에만 사용하며 변경할 수 없다. 내부 PK·legacy 값은 일반 목록에서 최소화한다. |
| 읽기 전용 | `date_joined`, `last_login`, `created_at`, `updated_at` | 서버가 관리한다. |
| 읽기 전용 | `is_staff` | 승인된 Bootstrap으로만 변경한다. 일반 계정 관리 Form에서 수정하지 않는다. |
| 금지 | `is_superuser` | 일반 Admin 화면에서 노출·부여·회수하지 않는다. |
| 금지 | Group·`user_permissions` 직접 변경 | P0 고정 Group 정책을 사용하며 `FR-040` P1 전까지 위임 UI를 제공하지 않는다. |
| 금지 | Password hash, Token, Secret | 목록·상세·감사 이력·로그에 노출하거나 저장하지 않는다. |
| 금지 | 물리 삭제 | Admin Delete 버튼·일괄 Delete Action·일반 Service를 제공하지 않는다. |

문의·상담·방문·케어 상태와 업무 FK는 계정 Admin에서 수정하지 않는다.
각 도메인의 Service와 상태 전이 경계를 그대로 사용한다.

### 3.6 비활성화·재활성화 원칙

T-017C에서는 아래 순서를 하나의 `transaction.atomic()` 안에서
수행한다.

```text
수행자·대상 사용자 조회 및 행 잠금
→ 수행자 is_active/is_staff/Model Permission/서버 Guard 검증
→ 자기 계정·마지막 활성 계정 관리자 보호
→ 대상 상태와 요청 사유 검증
→ User.is_active 변경
→ auth_version 증가
→ 대상 사용자의 Outstanding Refresh Token 전부 blacklist
→ append-only AccountAuditEvent 생성
→ Commit
```

결정 세부사항:

1. 자기 계정 비활성화는 항상 차단한다.
2. “마지막 활성 관리자”는 단순 `OPERATOR`가 아니라
   `is_active=True`, `is_staff=True`이며 계정 변경 Permission과
   서버 Guard를 모두 통과할 수 있는 계정이다.
3. 동시 요청 두 개가 마지막 관리자 보호를 우회하지 못하도록 대상과
   관리자 후보 행을 일관된 순서로 잠근다.
4. 이미 비활성인 계정의 비활성화와 이미 활성인 계정의 재활성화는
   무음 성공으로 처리하지 않고 명시적 상태 충돌로 기록한다.
5. 모든 변경 요청에 공백이 아닌 사유를 요구한다.
6. 재활성화는 기존 Refresh blacklist를 되돌리지 않는다.

### 3.7 Token 폐기와 재활성화 전 Token 차단

현재 T-017은 사용한 Refresh Token의 rotation·logout blacklist와
매 요청 `is_active`·현재 역할 재검증을 구현한다. 그러나 비활성화
후 빠르게 재활성화하면 비활성화 전에 발급된 Access Token을 세대
기준으로 구분할 필드가 현재 없다.

T-017C에서는 다음 방어를 함께 적용한다.

1. `User.auth_version` 양의 정수 필드를 추가한다.
2. Access·Refresh JWT에 `auth_version` Claim을 넣는다.
3. 모든 보호 API와 Refresh에서 JWT Claim과 현재 User 값을
   비교한다.
4. 비활성화·재활성화·업무 역할 변경 시 `auth_version`을 증가시킨다.
5. 비활성화 Transaction 안에서 해당 사용자의 모든
   `OutstandingToken`을 `BlacklistedToken`으로 만든다.
6. Refresh·Login의 Token 발급 경계도 User 행 잠금과 현재 세대
   검증을 사용해 비활성화와의 경합을 차단한다.

따라서 재활성화 후에도 비활성화 전에 발급된 Access·Refresh Token은
세대 불일치 또는 blacklist로 거부된다. `auth_version`은
**제안된 T-017C 필드**이며 현재 JWT 계약에는 없다. 구현 시
[ADR 0009](../../../adr/0009-t017-jwt-rbac-owner-baseline.md)의
후속 ADR과 Auth Schema·테스트를 같은 변경 단위로 갱신한다.

### 3.8 물리 삭제 금지

- Custom UserAdmin의 `has_delete_permission()`은 `False`다.
- 목록의 기본 `delete_selected` Action을 제거한다.
- 일반 Account Service에 hard-delete 메서드를 만들지 않는다.
- 기존 문의·상담·방문·케어·감사 FK는 그대로 보존한다.
- 현재 일부 FK의 `PROTECT`만으로 전체 삭제 정책이 보장된다고
  판정하지 않는다. Admin·Service·인수 테스트에서 명시적으로 막는다.
- 참조가 없는 합성 테스트 계정의 예외 삭제는 일반 Admin 기능이
  아니다. 별도 승인된 유지보수 명령·대상 목록·백업·감사 증거가
  있는 경우에만 후속 작업으로 검토한다.

### 3.9 계정 전용 append-only 감사 원장

현재 `audit.AuditEvent`는 문의·방문 전이 전용이므로 재사용하지 않는다.
T-017C 전에 다음 논리 계약을 별도 Model·Migration으로 확정한다.

| 후보 필드 | 규칙 |
| --- | --- |
| `id`, `public_id` | 내부 정수 PK와 외부 추적 UUID |
| `target_user` | `accounts.User`, `on_delete=PROTECT` |
| `actor` | 수행한 내부 관리자, `on_delete=PROTECT` |
| `event_type` | `CREATE`, `UPDATE`, `DEACTIVATE`, `REACTIVATE`, `ROLE_CHANGE`, `PASSWORD_RESET` allowlist |
| `before_values`, `after_values` | 승인된 핵심 필드만 담는 JSON Object |
| `reason` | 공백이 아닌 변경 사유 |
| `correlation_id` | 요청·로그 연결 UUID |
| `occurred_at` | 서버 발생 시각 |
| `data_classification` | `synthetic` 고정 |

Password, Token, Secret, Password hash는 전후값에 넣지 않는다. 감사
Model은 일반 Admin에서 추가·수정·삭제를 금지하고 읽기 전용으로만
노출한다. 저장은 Account Lifecycle Service의 create-only Repository
한 곳에서 수행한다. QuerySet `update()`·`delete()`와 Model 갱신을
차단하는 구현·테스트가 필요하다.

Model명·테이블명·JSON Schema·DB-level 불변식은 Data·QA의 Migration·QA
검토 후 T-017C 구현 직전에 확정한다. 현재 계정 감사 Model이 존재한다고
간주하지 않는다.

## 4. 오류 코드 제안과 Machine Contract 경계

| HTTP | 제안 코드 | 발생 조건 |
| ---: | --- | --- |
| 401 | `ACCOUNT_INACTIVE` | 비활성 사용자의 Login·Refresh·보호 API 접근 |
| 401 | `REFRESH_TOKEN_REVOKED` | 폐기됐거나 이전 `auth_version`의 Refresh 재사용 |
| 403 | `ACCOUNT_ADMIN_REQUIRED` | 내부 계정 관리 권한 없음 |
| 403 | `PRIVILEGE_ESCALATION_DENIED` | 상위 권한·`is_superuser` 부여 시도 |
| 409 | `LAST_ADMIN_PROTECTED` | 마지막 활성 계정 관리자 비활성화 시도 |
| 409 | `SELF_DEACTIVATION_DENIED` | 자기 계정 비활성화 시도 |
| 409 | `ACCOUNT_HARD_DELETE_BLOCKED` | 물리 삭제 시도 |

위 값은 [기획 API명세서](../../../planning/md/API명세서.md)의
**제안**이다. 현재 Backend 오류 Registry·OpenAPI·JSON 예시·Runtime
테스트에 없으므로 클라이언트가 소비할 Machine Contract가 아니다.
현재 비활성·역할 변경 Auth 실패는 공통 `AUTH_REQUIRED`로 정규화된다.

오류 코드를 활성화하려면 다음을 한 Commit에서 처리한다.

1. PM의 코드·HTTP·노출 메시지 결정
2. Backend 오류 Registry 추가
3. OpenAPI와 JSON 예시 추가
4. Authentication·Admin/Lifecycle 예외 Mapping
5. Web·Mobile 소비자 검토
6. 계약·Runtime·회귀 테스트

내부 Admin Form 오류는 HTML Form·Message로 처리하며 Public API
오류 코드를 자동으로 노출하지 않는다.

## 5. T-017B 구현 경계 — 2026-08-03

### 5.1 구현할 것

- Django Admin·Session·Message·Static 필수 App과 Middleware
- CSRF와 Admin Template 설정
- `/internal/admin/` URL
- 합성 사용자용 Custom UserAdmin·생성/수정 Form
- 위 필드 Allowlist·Readonly·금지 정책
- 비staff·OPERATOR-only 접근 차단
- 물리 삭제 UI·Action 차단
- 비활성화·재활성화 Action의 Service 호출 연결점
- 고정 계정 관리자 Group·Permission Bootstrap 절차
- Admin 접근·Field·CSRF·권한 단위 테스트

### 5.2 구현하지 않을 것

- Public `/api/v1/admin/users/**`
- 실제 사용자·회원가입·SSO·IAM·HR 연동
- Group·Permission 위임·회수 UI
- 본인 프로필 수정 API
- 대량 Import·대량 삭제
- T-017C 감사·Token 세대 기능을 검증 없이 앞당긴 부분 구현

### 5.3 Migration 영향

T-017B 후보 Migration은 `User.is_synthetic` 추가와 기존 합성 행
검증·backfill이다. Django `sessions` 앱 추가 시 내장 Session
Migration도 생긴다. 다음 영향 검사를 통과하기 전 기본 DB에 적용하지
않는다.

1. 현재 T-005 계약의 `accounts_user` 필드 정의와 ERD 차이 확인
2. 빈 PostgreSQL 전체 Migration
3. 기존 `waterbridge` 백업·`migrate --plan` 검토
4. 기존 20개 User의 합성 근거와 backfill 결과 확인
5. Demo Seed 2회와 기존 Auth 38건 회귀
6. T-005 Auditor·Schema Validator·전체 Backend 회귀

T-005 계약 문서가 필드 수준 Hash를 관리한다면 Model·Migration·계약을
같은 Commit에서 갱신한다. 테이블 수 32를 임의로 변경하지 않는다.

## 6. T-017C 구현 경계 — 2026-08-04~05

### 6.1 구현할 것

- `User.auth_version`과 후속 ADR·JWT Claim
- 비활성화·재활성화·역할 변경 Account Lifecycle Service
- 행 잠금·자기 계정·마지막 관리자·상태 충돌 Guard
- 대상 사용자의 Outstanding Refresh 전체 blacklist
- 계정 전용 append-only Audit Model·Repository
- 수행자·사유·전후값·correlation_id 기록
- 재활성화 전 Access·Refresh 재사용 차단
- 정상·오류·동시성·rollback·감사 불변성 테스트

### 6.2 구현하지 않을 것

- 계정 물리 삭제
- P1 관리자 권한 위임·회수
- P1 본인 프로필 API
- 기존 문의·방문 `AuditEvent` 구조의 무리한 확장
- Password·Token·Secret의 감사 저장

### 6.3 Migration 영향

- `accounts.User.auth_version` 추가와 기존 행 기본 세대 backfill
- 계정 감사 신규 테이블과 `PROTECT` FK·Index·CheckConstraint
- Auth Claim 변경에 따른 기존 Token 무효화 정책
- T-005 계약 밖 Django 보조 테이블과 T-005 32개 업무 계약 테이블의
  수치를 분리한 검증

Migration은 빈 DB → 복원 가능한 격리 DB → 승인된 기본 DB 순서로
검증한다. 기본 DB에서 Migration 파일을 수정·삭제하거나 과거
Migration을 squash하지 않는다.

## 7. 인수 테스트 매트릭스

| ID | 단계 | 시나리오 | 기대 결과 |
| --- | --- | --- | --- |
| `A-DES-01` | T-017A | User 단일 원장·권한 4축·삭제·감사 정책 검토 | PM·Data·QA 결정과 이견이 기록됨 |
| `A-DES-02` | T-017A | 현재 구현/미구현 교차검증 | Admin·Lifecycle·Audit를 구현 완료로 오기하지 않음 |
| `B-ADM-01` | T-017B | 비staff 사용자의 Admin 접근 | Login/접근 거부 |
| `B-ADM-02` | T-017B | `OPERATOR`, `is_staff=False` 접근 | 업무 역할만으로 Admin 권한을 얻지 못함 |
| `B-ADM-03` | T-017B | 승인된 staff+Permission 접근 | 허용 Model과 Action만 표시 |
| `B-ADM-04` | T-017B | 합성 사용자 생성 | 표준 Password Hasher, 역할·사번·합성 불변식 통과 |
| `B-ADM-05` | T-017B | 금지 필드 변경 | `is_superuser`, Group·Permission, 내부 ID, Password hash 변경 거부 |
| `B-ADM-06` | T-017B | Admin POST의 CSRF 누락 | 403으로 차단 |
| `B-ADM-07` | T-017B | 물리 삭제·일괄 삭제 | UI·Action·서버 모두 차단 |
| `C-LIF-01` | T-017C | 계정 비활성화 | `is_active=false`, `auth_version` 증가, Refresh 전체 blacklist, 감사 1건 |
| `C-LIF-02` | T-017C | 비활성 계정 Login·Refresh·보호 API | 모두 거부 |
| `C-LIF-03` | T-017C | 재활성화 뒤 과거 Access·Refresh 재사용 | 세대 불일치 또는 blacklist로 거부 |
| `C-LIF-04` | T-017C | 자기 계정 비활성화 | Transaction 전체 rollback |
| `C-LIF-05` | T-017C | 마지막 활성 관리자 비활성화 | 동시 요청에서도 한 건도 보호 우회 못함 |
| `C-LIF-06` | T-017C | 중간 Token 폐기·감사 저장 실패 | User 상태까지 전체 rollback |
| `C-AUD-01` | T-017C | 생성·수정·비활성·재활성 | 대상·수행자·사유·전후값·시각·correlation_id 기록 |
| `C-AUD-02` | T-017C | 감사 수정·삭제 시도 | 일반 Admin·ORM 경계에서 차단 |
| `C-AUD-03` | T-017C | 감사 Payload 검사 | Password·Token·Secret 없음 |
| `M-PG-01` | T-017B/C | 빈 PostgreSQL Migration | drift·미적용·고아 FK 0 |
| `M-PG-02` | T-017B/C | 기존 합성 DB Migration | User·업무 FK·Seed 행 보존 |
| `R-AUTH-01` | T-017B/C | 기존 Auth·Permission 회귀 | T-017 Auth 4개와 owner·assignee 범위 유지 |
| `R-ALL-01` | T-017B/C | 전체 Backend·Data Gate | 같은 Commit에서 모두 PASS |

T-047A의 최종 보안 테스트는 위 테스트를 반복·확장한다. T-017B/C
구현 Commit에서는 해당 단계의 테스트를 먼저 작성하고, 각 구현 직후
표적 → PostgreSQL → 전체 회귀 순서로 검증한다.

## 8. 협업자 검토 항목

### 8.1 PM

- `/internal/admin/`의 배포 접근 경계
- 고정 계정 관리자 Group 이름과 최소 Permission
- 마지막 활성 관리자의 업무 정의
- 기존 계정의 `role_code` 변경 허용 시점
- `User.is_synthetic`, `auth_version` 추가 결정
- 제안 오류 코드의 Public Machine Contract 승격 여부
- T-017A 승인과 T-017B/C 일정·완료 경계

### 8.2 Data·QA·DevOps

- 기존 User 합성 판정과 `is_synthetic` backfill의 fail-closed 조건
- Session·User·Audit Migration의 빈 DB·기존 DB 재현
- Refresh 전체 blacklist와 재활성화 전 Token 재사용 차단
- 마지막 관리자 동시성·Transaction rollback 테스트
- 계정 감사 JSON Allowlist·append-only 불변식
- Demo Seed 2회와 Auth·T-005·전체 회귀 영향
- 배포에서 Admin URL·Session Cookie·CSRF·비밀값 노출 방지

검토자는 구현을 대신하지 않는다. 정책 이견은 코드부터 임의 수정하지
말고 이 문서에 `결정/보류/변경 요청`으로 기록한 뒤 후속 ADR·Migration
범위를 확정한다.

### 8.3 T-017A 검토 결정 기록

이 표는 2026-08-01 검토 요청 패킷의 활성 내용을 이 기준 문서로
흡수한 것이다. PM은 단일 계정 원장·역할/관리자 권한 분리·마지막 관리자
보호·오류 계약·B/C 구현 순서를, Data·QA는 `is_synthetic` backfill·빈 DB와
기존 DB Migration·Token 폐기·rollback/동시성·감사 JSON Allowlist를
판정한다. 실제 검토 회신 전에는 빈 칸을 임의로 승인 처리하지 않는다.

| 검토자·역할 | 결정 | 변경 요청·계약 차이 | 결정일·근거 |
| --- | --- | --- | --- |
| 윤승혁(PM·State 계약) | `APPROVE / HOLD / CHANGE_REQUEST` |  |  |
| 김은진(Data·QA·DevOps) | `APPROVE / HOLD / CHANGE_REQUEST` |  |  |

두 검토 결과와 WBS 상태 갱신 증거가 기록되기 전에는 T-017A를 팀 완료로
표시하지 않으며, T-017B/C Runtime·Migration을 착수하지 않는다. 공통 회신
필드는 [Backend 팀 검토 및 인계 체크리스트](../연동_인계/Backend_팀_검토_인계_체크리스트.md)의
반환 형식을 사용한다.

## 9. 팀 인계 순서

| 순서 | 담당 | 작업 | 반환 증거 |
| ---: | --- | --- | --- |
| 1 | Backend·Database | T-017A 설계 기준안과 현재 Auth 증거 기록 | Branch·Commit·이 문서·readiness JSON |
| 2 | PM | 권한·접근·마지막 관리자·오류 코드 정책 검토 | 승인/변경 요청과 결정일 |
| 3 | Data·QA | Migration·합성 backfill·Token·감사·테스트 검토 | 재현 계획·위험·필수 QA 항목 |
| 4 | Backend·Database | 반영된 T-017A를 기준으로 T-017B 한 작업씩 구현·검증 | Admin 표적 테스트·PostgreSQL·전체 회귀 |
| 5 | Data·QA | T-017B 비작성자 재현 | 빈 DB·기존 DB·Admin 보안 결과 |
| 6 | Backend·Database | T-017C Lifecycle·감사를 한 작업씩 구현·검증 | Token·동시성·감사·rollback 증거 |
| 7 | Data·QA | T-017C와 T-047A 후보 독립 QA | 테스트 Matrix 결과·잔여 위험 |
| 8 | PM | 리뷰 증거 확인 후 `main` 병합 | 병합된 40자리 `main` SHA |

한 단계가 실패하면 다음 단계로 넘어가지 않는다. 팀원은 개인 작업
Branch를 임의 기준선으로 사용하지 않고 PM이 병합한 `main` SHA를
공용 기준으로 사용한다.

## 10. 합성 Demo Login 실행·보안 기준

공개 Demo Login은 `POST /api/v1/auth/demo-login`을 사용한다. 내부
고객번호나 사용자명을 직접 노출하지 않고 승인된 `DEMO-*` 또는
`SYN-*` 별칭만 받는다.

| 점검 | 허용·차단 기준 |
| --- | --- |
| 기능 플래그 | 로컬·시연 환경에서 명시적으로 활성화하며 운영 기본값은 비활성 |
| Allowlist | `DJANGO_DEMO_LOGIN_CODES`에 등록된 별칭만 허용 |
| 접두사 | `DEMO-`, `SYN-`만 허용하고 내부 `CUS-*` 직접 요청은 거부 |
| 사용자 상태 | 활성 사용자만 허용 |
| 역할 | 고객 별칭은 CUSTOMER 역할에만 연결 |
| 응답·로그 | Token·Password·실제 개인정보를 문서·Git·로그에 남기지 않음 |

현재 역할 Seed 별칭은 다음 네 역할을 제공한다.

- `DEMO-CUSTOMER-001`
- `DEMO-CONSULTANT-001`
- `DEMO-TECHNICIAN-001`
- `DEMO-OPERATOR-001`

합성 고객 Importer 계정 확인에는 승인된 `SYN-CUSTOMER-001` 별칭을
사용할 수 있다. 이 별칭은 내부 사용자명을 바꾸는 기능이 아니라
`CustomerProfile.customer_no`를 통해 활성 CUSTOMER 계정을 찾는
안전한 조회 경계다.

수동 확인 순서는 Demo Login → `/me` → Refresh → 보호 API → Logout →
폐기 Token 401이다. 실제 Token 값은 문서나 터미널 공유 로그에 복사하지
않고, 검증 후 Demo Login 기능 플래그를 필요한 기본 상태로 되돌린다.

## 11. T-017A 완료 체크리스트

- [x] 현재 T-017 Auth 구현과 T-017A/B/C 경계를 분리했다.
- [x] `accounts.User` 단일 원장을 결정했다.
- [x] `role_code`와 `is_staff`·Group·Permission을 분리했다.
- [x] `OPERATOR` 자동 Admin 승격을 금지했다.
- [x] `/internal/admin/` Session·CSRF 후보를 정의했다.
- [x] 합성 사용자 범위와 필드 정책을 정의했다.
- [x] 물리 삭제·자기 계정·마지막 관리자 보호를 정의했다.
- [x] Transaction·Refresh blacklist·Token 세대 방어를 정의했다.
- [x] 계정 전용 append-only 감사 원장의 논리 요구를 정의했다.
- [x] 오류 코드를 Machine Contract 미반영 제안으로 구분했다.
- [x] T-017B/C Migration 영향과 인수 테스트를 정의했다.
- [ ] PM 정책 검토 증거
- [ ] Data·QA Migration·QA 검토 증거
- [ ] WBS의 T-017A 승인·상태 갱신

따라서 현재 최종 판정은 설계 기준안 작성 완료·팀 검토 대기
(`OWNER_DESIGN_READY_REVIEW_PENDING`)다.
리뷰 전에는 T-017A를 공식 완료로 표시하지 않고, T-017B/C 기능이
이미 존재한다고 팀에 전달하지 않는다.

## 12. 유지보수 원칙과 완료 조건

- 요구·일정은 WBS와 요구사항정의서, Public 계약은 API 명세·OpenAPI·오류
  코드 Registry, 인증 기준은 ADR과 Django Runtime을 source of truth로
  삼는다.
- User 필드·Migration·Admin Form·Lifecycle Service·Token 정책·감사
  Payload가 바뀌면 관련 기계 계약과 테스트를 같은 변경 묶음에서 갱신한다.
- T-017A는 정책·데이터 불변식·Migration·QA 검토와 WBS 상태 갱신 증거가
  있어야 팀 완료로 표시한다.
- T-017B/C는 실제 Model·Migration·Admin·Service·오류 계약 구현과 표적
  테스트, PostgreSQL, 전체 회귀, 비작성자 재현을 모두 통과해야 완료로
  표시한다.
- 한국어 판정이 우선이며 보조 상태 코드는 자동화·검색용이다. 상태 코드
  하나만으로 공식 완료나 팀 기준선 반영을 선언하지 않는다.
