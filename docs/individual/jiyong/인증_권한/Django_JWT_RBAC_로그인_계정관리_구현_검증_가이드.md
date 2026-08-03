# Django JWT·RBAC 로그인·계정관리 구현 및 검증 가이드

> 기준일: 2026-08-03
> 작성·설계 책임: Backend·Database 담당
> 협업·검토: 윤승혁(PM), 김은진(Data·QA)
> 상태: T-017 진행 중(`OWNER_IMPLEMENTATION_READY`) /
> T-017A 정책 방향 승인·Migration QA 보완 중(`POLICY_APPROVED_QA_CHANGE_REQUEST`) /
> T-017B 착수 불가
> 대상: `T-017` 인증·RBAC와 `T-017A~C` 계정관리 경계
> 데이터 범위: 합성 사용자와 내부 시연 관리자만
> 실행 원칙: `설계 결정 → 검토 → 한 작업 구현 → 즉시 검증`
> 검토 기준선: `source_main_sha=d93779bb2afde266d7fbeae3b8f8b8687db43100` /
> `candidate_ref=이 문서가 포함된 origin/jiyong Commit SHA`
> 최근 작성자 재검증: `2026-08-03 17:10 KST` / 최신 Main 기반 clean 후보

이 문서는 T-017 인증·권한의 현재 구현과 합성 사용자 계정 관리의
계약·설계 기준을 함께 제공한다. 현재 구현된 인증·권한 기능과
앞으로 구현할 Django Admin·계정
수명주기·감사 기능을 구분한다. 이 문서를 작성한 것만으로
`T-017B`·`T-017C`의 Model, Migration, Admin, Service, 오류 코드가
구현된 것은 아니다.

## 0. 2026-08-03 현재 구현·검증 요약

| 범위 | 현재 상태 | 현재 근거 | 남은 Gate |
| --- | --- | --- | --- |
| Login·Refresh·Logout·`/me` | 구현됨·4역할 작성자 검증 PASS | Account URL·View·JWT Service·4역할 Auth Matrix | 고정 후보 SHA의 비작성자 재현 |
| UUID JWT·활성/역할 재검증 | 구현됨 | UUID `sub`, Refresh 회전·폐기, 사용자 활성·역할 재검사 | T-017C 계정 세대·전체 Token 폐기 |
| 4역할 Demo Seed | 구현됨·PostgreSQL 2회 멱등 PASS | CUSTOMER·CONSULTANT·TECHNICIAN·OPERATOR Seed와 역할 집합 확인 | 고정 후보 SHA의 QA 재현 |
| Inquiry START·SUBMIT·CANCEL 권한 | 작성자 검증 완료, 고정 후보 QA 전 | 4역할, 미인증 401, 비고객 403, 타 고객 404, 실패 부수효과 0 | 후보 SHA의 QA 재현. 상담·방문은 T-042/T-047 |
| T-017A 설계 | PM 정책 방향 승인·QA 변경 요청 | 단일 User 원장·권한 분리·`is_synthetic`·`auth_version` 방향 승인, WBS v2.1 반영 | Migration·Backfill·Rollback·Seed QA 승인 |
| T-017B/C | 미구현·착수 불가 | Admin·Lifecycle·Account Audit Runtime 없음 | T-017A 완료 후 B, B PASS 후 C |

2026-08-03 17:10 KST 작성자 재검증은 4역할 Auth Matrix `4 passed`,
Accounts 전체 `70 passed`, 고객 문의 RBAC·IDOR `24 passed`다. 실제 로컬
`waterbridge` PostgreSQL에서 연결, Model/Migration parity, 미적용
Migration과 Readiness PostgreSQL Gate도 통과했다. Demo Seed 2회 멱등성은
같은 날 작성자 선행 실행과 김은진의 isolated PostgreSQL 재현에서 확인됐다.
이 증거는 공식 WBS 완료나 고정 후보 SHA의 비작성자 재현을 대체하지 않는다.

2026-08-03 17:10 KST Fetch 기준 원격 main은
`d93779bb2afde266d7fbeae3b8f8b8687db43100`이다. 원래 Dirty 작업공간과
분리한 clean 작업공간에서 신규 4역할 Matrix, 이 가이드, 간결 QA 인계서만
T-017 후보로 고정했다. 공용·타인·제출 문서 11개는 후보에서 제외했다.
이 최신 Main 기반 후보에서 Accounts `70 passed`, 문의 RBAC·IDOR `24 passed`,
Migration parity와 작성자 Readiness를 통과했다.

기존 `43/44/778/791 passed` 기록은 이전 작성자 실행 이력이다. 현재 후보
결과와 합치지 않으며, 최신 후보 SHA가 고정되면 같은 명령을 다시 실행한다.

실제 `/api/v1`에는 Accounts와 Inquiries만 마운트되어 있다. 상담·방문
URL·View·Permission은 Runtime 대상이 아니므로 기사 미배정 방문 E2E를
현재 T-017 완료 증거로 만들 수 없다.

## 1. 판정과 완료 경계

| 작업 | 현재 판정 | 근거와 의미 |
| --- | --- | --- |
| `T-017` 가상 로그인·JWT·RBAC | 진행 중(`OWNER_IMPLEMENTATION_READY`) | 4역할 Auth·문의 RBAC·PostgreSQL 작성자 Gate는 통과했다. WBS v2.1 범위 변경은 반영됐고 후보 SHA 고정·QA 재현이 남았다. |
| `T-017A` 계정 관리 설계 | 진행 중(`POLICY_APPROVED_QA_CHANGE_REQUEST`) | PM은 정책 방향을 승인했으나 QA Migration 검토와 그 결과에 따른 T-017A 완료 상태 갱신이 남아 완료 승인이 아니다. |
| `T-017B` 내부 계정 관리 | 미구현·착수 불가(`START_NOT_ALLOWED`) | 현재 [accounts Admin](../../../../backend/apps/accounts/admin.py)은 설명 문자열만 있고 Admin 앱·Session·CSRF·URL·Custom UserAdmin이 구성되지 않았다. |
| `T-017C` 계정 수명주기·감사 | 미구현(`NOT_IMPLEMENTED`) | T-017B PASS 뒤 구현한다. 비활성화 Service, 전체 Refresh 폐기, 재활성화 전 Token 세대 차단, 계정 전용 감사 원장이 없다. |

`T-017`의 작성자 구현 준비 상태(`OWNER_IMPLEMENTATION_READY`)를
`T-017A~C` 완료로 확장
해석하지 않는다. 반대로 T-017A의 팀 검토가 남았다는 이유로 이미
검증된 Auth 4개 Endpoint를 미구현으로 되돌리지 않는다.

### 1.1 검토 기준선과 후보 식별자

| 항목 | 현재 값 | 판정 |
| --- | --- | --- |
| 최신 확인 `origin/main` | `d93779bb2afde266d7fbeae3b8f8b8687db43100` | 후보의 출발 부모 Commit |
| 검토 후보 SHA | 이 문서가 포함된 `origin/jiyong` Commit | 검토 요청 메시지의 실제 SHA와 QA Checkout SHA가 같아야 함 |
| Publication 판정 | Git 원격 Ref를 source of truth로 사용 | 문서 안에 자기 Commit SHA를 하드코딩하지 않음 |
| 후보 포함 경로 | Matrix, 이 가이드, `Django_JWT_RBAC_QA_검토_인계서.md`, 총 3개 | Runtime·Migration 변경 없음 |
| Matrix SHA-256 | `E35F4025F46C34BBDB396627174F8DE1380D040DF1E5B9EE2754D39D31F45F44` | 후보 Commit에서도 동일해야 함 |
| 후보 제외 경로 | 공용·타인·제출·3주차 문서 11개 | 명시적 Staging 전까지 모두 미스테이징 유지 |
| 작성자 작업 상태 | 최신 Main clean 작업공간에서 후보 3경로만 분리해 검증 | 원래 Dirty 13경로와 격리 |
| `/me` 계약 | `GET /api/v1/me` | Runtime·OpenAPI·QA 확인 일치, 차이 해결 |
| 기사 실제 E2E 분리 | `T-042`에서 기사 배정 Runtime·화면, `T-047`에서 최종 권한 인수 테스트 | WBS v2.1 반영 확인 |
| WBS 상태 | 원격 main v2.1에서 T-017/A `진행 중`, T-017B/C `차단` | T-017 QA 승인 뒤 PM 완료 판정 필요 |
| QA 재현 | 기존 `d4bb32e`에서 기능 PASS·제출 HOLD | Matrix가 포함된 새 후보 SHA에서 재현 필요 |

이 표의 `source_main_sha`는 출발점이지 검토 후보 SHA가 아니다. QA는 반드시
검토 요청 메시지에 적힌, 이 문서와 Matrix가 함께 포함된 `origin/jiyong`
Commit SHA를 Checkout한다. Branch 이름만으로 검증 대상을 식별하지 않는다.

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

#### 3.4.1 `is_synthetic` Backfill 판정·중단 기준

| 항목 | 제안 기준 | 현재 상태 |
| --- | --- | --- |
| 대상 모집단 | Migration 시작 시점의 `accounts.User` 전체 행 | QA 검토 대기 |
| 판정 1순위 | `seed_demo_accounts.py`의 정확한 사용자 정의와 일치 | 자동 판정 후보 |
| 판정 2순위 | CUSTOMER이며 연결된 `CustomerProfile.is_synthetic=True` | 자동 판정 후보 |
| 판정 3순위 | 완료된 `db-full` Import ledger에서 `users → accounts.User` Target이 연결되고 Dataset·Mapping·Fixture Hash가 승인된 원본과 일치 | 작성자 로컬 근거 확인·QA 승인 대기 |
| 금지 판정 | 이름·연락처·`DEMO-` 접두사만으로 합성 여부 추정 | 항상 금지 |
| 중복 검사 | `username`, 비어 있지 않은 `employee_no`, `customer_no`, Import 원본 키 | 중복 그룹이 하나라도 있으면 중단 |
| 충돌 검사 | 서로 다른 Source가 같은 User를 다른 값으로 판정 | 한 건이라도 있으면 중단 |
| 미판정 행 | 자동으로 `False` 또는 `True`를 넣지 않음 | 한 건이라도 있으면 Migration 중단 |
| 빈 DB | 대상 0건, Schema 추가만 수행 | QA 재현 필요 |
| 기존 DB | 세 판정 Source의 고유 User 합집합이 전체 User와 같아야 하며, 중복 Source는 동일한 `True` 판정만 허용 | QA 재현 필요 |
| 복구 | Migration 전 DB Backup·건수·Source Hash 고정, 실패 시 Transaction rollback | 절차 승인 필요 |

2026-08-03 로컬 PostgreSQL의 개인정보 비노출 건수 점검 결과는 다음과
같다. 이 값은 작성자 PC 관측치이며 후보 SHA의 QA 증거가 아니다.

| 점검 항목 | 관측값 |
| --- | ---: |
| 전체 User | 20 |
| 역할별 User | CUSTOMER 13 / CONSULTANT 3 / TECHNICIAN 3 / OPERATOR 1 |
| 정확한 Demo Seed User | 4 |
| 합성 CustomerProfile로 판정 가능한 CUSTOMER | 13 |
| Profile 누락·비합성 CUSTOMER | 0 |
| Demo Seed 외 비고객 User | 4 |
| Canonical `users` Fixture | 16(CUSTOMER 12 / CONSULTANT 2 / TECHNICIAN 2), 전 행 `data_classification=synthetic` |
| Canonical 기준 | Dataset `0.9.0` / Mapping `2.0.0` / Source 367 / Fixture Hash `7C407CB6F013BE584011E446650BACD4A6A958895F88448B17EE523AA5B9D068` |
| 승인 후보 Dataset·Mapping·Fixture Hash와 일치하는 완료 `db-full` Batch | 2(최초 실행·멱등 Replay) |
| Batch별 `users → accounts.User` Ledger | 각 16행·고유 Target 16·비고객 4 |
| Source/Target UUID·Business Key·행 Hash 불일치 | Batch별 0 |
| Ledger에 연결되지 않은 비고객 User | 0 |
| 세 판정 Source의 고유 User 합집합 / 미판정 User | 20 / 0 |
| 계산 Fixture Hash와 기존 Crosswalk 검증 Hash 일치 | 참 |
| username·employee_no·customer_no 중복 그룹 | 각 0 |
| CUSTOMER의 잘못된 employee_no / 비고객의 누락 employee_no | 0 / 0 |

Schema 필드만으로 비고객 User 4건을 추정하지는 않는다. 다만 로컬
PostgreSQL에서는 Canonical Fixture의 Dataset·Mapping·Fixture Hash와
일치하는 완료 Batch 두 건(최초 실행·Replay)의 Ledger가 네 User 모두를
동일 Target으로 연결했고 미연결 User는 0건이었다. 이로써 작성자 판정
근거는 보완됐지만, 김은진이 승인 Batch·Hash를 고정하고 같은 건수를
독립 재현하기 전에는 Backfill 계약이 승인된 것이 아니다. 그 전에는
`is_synthetic` Migration 후보를 만들지 않는다.

Backfill은 각 Batch에서 `source_public_id=target_public_id=User.public_id`,
`source_business_key=target_business_key=User.username`, `source_sha256`가
Canonical `users` 행 Hash와 일치하는지도 함께 검증한다. 승인 Batch Tuple,
16개 User·비고객 4개 Cardinality, UUID·Key·Hash 중 하나라도 다르거나
Replay Batch끼리 서로 다른 판정을 내리면 전체 Migration을 중단한다.
`latest_equivalence_report` 같은 파생 보고서의 과거 파일 크기·Hash는
Backfill 기준으로 사용하지 않고, 현재 Canonical Fixture에서 계산한
Fixture Hash와 Ledger의 행 Hash만 사용한다.

Backfill Migration은 구현 승인 뒤에도 한 번에 기본값을 넣지 않는다.
작성자 제안 순서는 다음과 같으며 아직 `QA_REVIEW_PENDING`이다.

1. `is_synthetic`을 임시 `null=True`·DB Default 없음으로 추가한다.
2. 승인된 불변 Manifest의 Demo Seed Tuple, 합성 CustomerProfile,
   Canonical Import Ledger만 사용해 검증된 User를 `True`로 갱신한다.
3. 모집단 100% 일치, 미판정·중복·충돌·UUID/Key/Hash 불일치 0을 같은
   Transaction에서 재검사한다.
4. 검사가 통과한 경우에만 `null=False`로 변경한다. Python·DB 자동
   Default는 두지 않고 Seed·Importer·내부 생성 Service가 값을 명시한다.
5. 현재 P0 Admin과 Demo Login은 `is_synthetic=True`만 허용한다. User
   전체를 영구적으로 `True`로 강제하는 DB Check는 향후 비합성 계정 허용
   여부를 PM이 결정하기 전에는 추가하지 않는다.

빈 DB는 대상 0건 Schema 적용 뒤 Seed가 `True`를 명시하는 경로로 검증한다.
기존 DB에서 1~19건만 판정되거나 승인 Manifest 밖 `DEMO-*` 계정이 발견되면
임의 보정하지 않고 전체 Migration을 rollback한다.

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
2. 마지막 활성 Superuser의 비활성화·Superuser 권한 회수는 차단한다.
   이 정책 방향은 윤승혁(PM)이 승인했다.
3. 마지막 활성 실무 계정 관리자를 보호해야 한다는 요구는 WBS v2.1에서
   확정됐다. 보호 대상은 단순 `OPERATOR`가 아니라
   `is_active=True`, `is_staff=True`이며 계정 변경 Permission과
   서버 Guard를 모두 통과할 수 있는 계정으로 판정하도록 제안한다. 정확한
   Group, Permission, Guard 판정식과 비상 복구 계정 범위만
   `PM_DECISION_PENDING`이다.
4. 동시 요청 두 개가 두 보호 범위를 우회하지 못하도록 모든 관리자 권한
   부여·회수와 Group·Permission M2M 변경을 단일 Account Service로만
   수행한다. Transaction 시작 시 공통 PostgreSQL advisory lock 또는 전용
   Sentinel 행을 잠근 뒤 대상 User, 관리자 후보, 관련 Group·Permission·
   through 행을 정해진 순서로 잠근다. 직접 Admin M2M 저장은 금지한다.
5. 이미 비활성인 계정의 비활성화와 이미 활성인 계정의 재활성화는
   무음 성공으로 처리하지 않고 명시적 상태 충돌로 기록한다.
6. 모든 변경 요청에 공백이 아닌 사유를 요구한다.
7. 재활성화는 기존 Refresh blacklist를 되돌리지 않는다.

| 보호 대상 | 현재 결정 | 구현 전 남은 결정 |
| --- | --- | --- |
| 마지막 활성 Superuser | 정책 방향 승인 | 동시성·rollback QA |
| 마지막 활성 실무 계정 관리자 | 보호 요구 확정 | Group·Permission·서버 Guard 판정식·비상 계정 범위 PM 확정 |
| `OPERATOR` 역할 | 관리자 권한과 분리 승인 | 역할만으로 보호 대상·Admin 권한 부여 금지 |

User 행만 잠그면 `PermissionsMixin`의 Group·Permission through-table을
동시에 수정하는 요청이 보호 검사를 우회할 수 있다. 구현 전 PM·QA는 공통
advisory key 또는 Sentinel Model 중 하나를 고정하고, 서로 다른 두 관리자의
동시 권한 회수가 마지막 권한 보유자를 0명으로 만들지 못하는 PostgreSQL
동시성 테스트를 승인한다.

#### 3.6.1 실무 계정 관리자 보호 범위 제안

QA가 재현할 수 있도록 아래 값을 구체 후보로 제안한다. 아직 Machine
Contract나 Migration 값이 아니며 PM·QA 결정 전 구현하지 않는다.

| 항목 | 작성자 제안 | 상태 |
| --- | --- | --- |
| 고정 Group | `WATERBRIDGE_ACCOUNT_MANAGERS` | `PM_DECISION_PENDING` |
| 핵심 Custom Permission | `accounts.manage_synthetic_accounts` | `PM_DECISION_PENDING` |
| 복구 Superuser 집합 | 활성·staff·superuser·사용 가능한 Password를 모두 만족 | 정책 승인·QA 동시성 대기 |
| 실무 관리자 집합 | 활성·staff·고정 Group·핵심 Permission·필수 User/Profile Permission·사용 가능한 Password를 모두 만족 | 세부 Permission 승인 대기 |
| 업무 역할 | `OPERATOR`를 관리자 판정에 사용하지 않음 | 정책 승인 |
| 실패 처리 | 변경 후 두 집합 중 하나라도 0명이면 `LAST_ADMIN_PROTECTED` 후보로 409·전체 rollback | 오류 계약 승인 대기 |
| 동시성 Lock | 전용 Singleton Sentinel 행 → 대상/수행자 User → Group·Permission through 행 순서 | QA 방식 결정 대기 |

Superuser의 자동 Permission만으로 실무 관리자 집합에 포함시키지 않는다.
한 계정이 두 집합의 마지막 구성원이라면 어느 한 자격 제거로 한 집합이
0명이 되는 요청도 차단한다. Group 삭제·Permission 축소·M2M `clear()`와
자기 계정 비활성화도 동일 Service·Lock·감사 경계를 우회할 수 없다.

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
4. 비활성화·재활성화·업무 역할·관리자 권한·Password/인증 자격 증명
   변경 또는 복구 시 `auth_version`을 증가시킨다.
5. 비활성화 Transaction 안에서 해당 사용자의 모든
   `OutstandingToken`을 `BlacklistedToken`으로 만든다.
6. Refresh·Login의 Token 발급 경계도 User 행 잠금과 현재 세대
   검증을 사용해 비활성화와의 경합을 차단한다.

세부 필드·배포안은 아래의 작성자 제안으로 고정하고 Data·QA 승인을
받는다. 정책 방향 승인만으로 구현값이 승인된 것으로 보지 않는다.

| 항목 | 작성자 제안 | 상태 |
| --- | --- | --- |
| 필드 | `PositiveIntegerField(default=1, null=False)` + `auth_version >= 1` Check | `QA_REVIEW_PENDING` |
| 기존 User Backfill | 모든 기존 행을 `1`로 설정 | `QA_REVIEW_PENDING` |
| JWT Claim | Access·Refresh 모두 `auth_version` 포함 | 정책 방향 승인·세부 QA 대기 |
| 요청 검증 | 보호 API·Refresh에서 Claim이 Boolean이 아닌 정수이고 `>=1`이며 현재 User 값과 정확히 같은지 검증 | `PROPOSED` |
| Claim 오류 | 누락·문자열·Boolean·0·음수·과거·미래 Version은 모두 정보 차이 없이 401 Fail-closed | `PROPOSED` |
| 증가 이벤트 | 비활성·재활성·업무 역할·staff/superuser·관리 Group/Permission·Password 변경/Reset·인증 자격 복구 | PM·QA 범위 확정 필요 |
| Refresh 폐기 | 상태 변경 Transaction 안에서 대상의 Outstanding Refresh 전체 blacklist | 정책 방향 승인·동시성 QA 대기 |
| Application rollback | 구버전이 새 보안 세대를 무시할 수 있어 단독 rollback 금지 | 배포·rollback Runbook 승인 필요 |
| Migration rollback | 발급 중단 → 모든 Refresh 폐기 → Access 무효화(서명키 회전·전역 not-before 또는 최대 TTL 경과) → 구/신 코드 의존성 제거 → 필드 제거 순서 | 빈 DB·기존 DB·배포 순서 재현 필요 |

구버전 애플리케이션은 `auth_version`을 검사하지 않으므로 단순히 필드를
제거하고 “다시 로그인”을 안내하는 rollback은 금지한다. 먼저 Login·Refresh
발급과 계정 변경을 일시 중단하고 모든 Refresh를 폐기한다. 이어 기존
Access를 서명키 회전이나 전역 `not-before`로 무효화하거나, 발급이 차단된
상태로 최대 Access TTL이 끝날 때까지 기다린 뒤에만 구버전 코드와 Schema로
되돌린다. 선택한 무효화 수단과 구/신 코드 배포 순서는 QA Runbook에서
하나로 고정한다.

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
| `event_type` | `CREATE`, `UPDATE`, `DEACTIVATE`, `REACTIVATE`, `ROLE_CHANGE`, `ADMIN_PERMISSION_CHANGE`, `PASSWORD_CHANGE`, `PASSWORD_RESET`, `CREDENTIAL_RECOVERY` allowlist |
| `before_values`, `after_values` | `role_code`, `is_active`, `is_staff`, `is_superuser`, 정렬된 Group·Permission Codename, `auth_version`만 허용. Password 변경은 값 대신 변경 발생 표시만 기록 |
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

## 5. T-017B 구현 경계 — 착수 보류

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

## 6. T-017C 구현 경계 — T-017B PASS 후

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
| `C-LIF-05A` | T-017C | 마지막 활성 Superuser 비활성·권한 회수 | 항상 차단 |
| `C-LIF-05B` | T-017C | Group·Permission 기반 마지막 실무 관리자 권한 회수 | direct M2M·Service 어느 경로에서도 차단 |
| `C-LIF-05C` | T-017C | Superuser와 실무 관리자 자격을 함께 가진 마지막 계정 변경 | 두 보호 불변식을 모두 유지 |
| `C-LIF-05D` | T-017C | 서로 다른 관리자 두 명의 동시 권한 회수 | 공통 Lock으로 직렬화되어 활성 권한 보유자 0명 금지 |
| `C-LIF-06` | T-017C | 중간 Token 폐기·감사 저장 실패 | User 상태까지 전체 rollback |
| `C-AUTH-01` | T-017C | `auth_version` 누락·문자열·Boolean·0·음수·과거·미래 값 | 보호 API·Refresh 모두 동일한 401 Fail-closed |
| `C-AUD-01` | T-017C | 생성·수정·비활성·재활성·역할/관리권한·Password/자격 복구 변경 | 대상·수행자·사유·허용된 전후값·시각·correlation_id 기록 |
| `C-AUD-02` | T-017C | 감사 수정·삭제 시도 | 일반 Admin·ORM 경계에서 차단 |
| `C-AUD-03` | T-017C | 감사 Payload 검사 | Password·Token·Secret 없음 |
| `M-PG-01` | T-017B/C | 빈 PostgreSQL Migration | drift·미적용·고아 FK 0 |
| `M-PG-02` | T-017B/C | 기존 합성 DB Migration | User·업무 FK·Seed 행 보존 |
| `R-AUTH-01` | T-017B/C | 기존 Auth·Permission 회귀 | T-017 Auth 4개와 owner·assignee 범위 유지 |
| `R-ALL-01` | T-017B/C | 전체 Backend·Data Gate | 같은 Commit에서 모두 PASS |

T-047A의 최종 보안 테스트는 위 테스트를 반복·확장한다. T-017B/C
구현 Commit에서는 해당 단계의 테스트를 먼저 작성하고, 각 구현 직후
표적 → PostgreSQL → 전체 회귀 순서로 검증한다.

### 7.1 4역할 인증 수명주기 Matrix — 작성자 로컬 증거

[4역할 Auth Matrix 테스트](../../../../backend/tests/unit/accounts/test_auth_role_matrix.py)는
Seed를 실제 실행한 뒤 Login → JWT Claim → `GET /api/v1/me` → Refresh
rotation → 새 Access의 `/me` → Logout → 폐기 Refresh 재사용 401을 역할별로
검증한다. Token 원문은 결과 문서에 저장하지 않는다.

| 역할 | Demo 별칭 | Login | Access·Refresh `sub` UUID·역할 | `/me` | Refresh | Logout·폐기 재사용 | 결과 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CUSTOMER | `DEMO-CUSTOMER-001` | PASS | PASS | Profile 포함·ID/역할 일치 | 새 Token·동일 사용자 PASS | 200·재사용 401 | PASS |
| CONSULTANT | `DEMO-CONSULTANT-001` | PASS | PASS | Profile `null`·ID/역할 일치 | 새 Token·동일 사용자 PASS | 200·재사용 401 | PASS |
| TECHNICIAN | `DEMO-TECHNICIAN-001` | PASS | PASS | Profile `null`·ID/역할 일치 | 새 Token·동일 사용자 PASS | 200·재사용 401 | PASS |
| OPERATOR | `DEMO-OPERATOR-001` | PASS | PASS | Profile `null`·ID/역할 일치 | 새 Token·동일 사용자 PASS | 200·재사용 401 | PASS |

실행 명령은 `python -m pytest -q -p no:cacheprovider tests/unit/accounts/test_auth_role_matrix.py`이며
2026-08-03 17:10 KST 최신 Main 후보 재실행 결과는 `4 passed in 9.65s`, Exit code 0이다.

### 7.2 PostgreSQL·Migration·Seed·회귀 증거

| 검증 | 환경 | 2026-08-03 현재 증거 | 판정 경계 |
| --- | --- | --- | --- |
| Accounts 전체 | `d93779b` 기반 후보 / SQLite | `70 passed in 26.89s`, Exit 0 | 기존 66 + 신규 Matrix 4 |
| 문의 RBAC·IDOR | `d93779b` 기반 후보 / SQLite | `24 passed in 8.08s`, Exit 0 | 실제 경로 `tests/api/test_t022_create_inquiry.py`, `tests/api/test_t023_cancel_inquiry.py` |
| Django System Check | `config.settings.local` | `System check identified no issues`, Exit 0 | 설정·App 등록 기본 Gate |
| Model/Migration parity | `d93779b` 기반 후보·로컬 local 설정 | `No changes detected`, Exit 0 | 현재 Model drift 없음 |
| PostgreSQL 연결 | 로컬 `waterbridge` / PostgreSQL 16 | `CONNECTED` | 비밀값·DSN 미기록 |
| 미적용 Migration | `migrate --check --noinput` | PASS | 자동 Migration 실행 없음 |
| Demo Seed 2회 | 작성자 로컬·QA isolated PostgreSQL | 작성자 `created=0, updated=4` 2회, QA `updated=4` 2회 | 반복 실행 가능 |
| Seed 역할 집합 | 로컬 PostgreSQL | User 4명·역할 4종·정확히 일치 | 실제 값 대신 건수만 기록 |
| 현재 User·Role | 로컬 PostgreSQL | User 20, CUSTOMER 13·CONSULTANT 3·TECHNICIAN 3·OPERATOR 1 | 개인정보·식별값 미출력 |
| 식별자·역할 불변식 | 로컬 PostgreSQL | username·employee_no·customer_no 중복 0, 역할/employee_no 모순 0 | Backfill 작성자 관측값 |
| `db-full` Ledger | 로컬 PostgreSQL | 완료 Batch 2, Hash/Version 각 1종, 최신 User Item 16·UUID/Key 불일치 0·Projected 0 | QA가 승인 Batch와 Hash를 고정해야 함 |
| Accounts Readiness | local + PostgreSQL | `OWNER_IMPLEMENTATION_READY`, Auth 함수 39, PostgreSQL 3 Gate PASS, Exit 0 | `TEAM_REVIEWED`만 남음 |
| 김은진 비작성자 재현 | `d4bb32e` isolated PostgreSQL | 기능 PASS·제출 HOLD | Matrix 파일이 포함된 새 후보 SHA 재현 필요 |

위 결과는 작성자 증거다. 김은진은 이 문서가 포함된 고정 후보 SHA에서
Accounts 70, 문의 24, PostgreSQL, Migration, Seed, Readiness를 같은 명령으로
독립 재현해야 한다.

재현 작업 디렉터리는 Repository의 `backend`이며 PowerShell 명령은 아래와
같다. `manage.py`는 `config.settings.local`을 사용하고 `.env`의 비밀값은
출력하지 않는다. Seed 두 명령은 지정된 로컬 검증 DB의 Demo 계정 4건을
생성 또는 갱신하므로 QA가 격리한 DB에서만 실행한다.

```powershell
$backendPython = ".\.venv\Scripts\python.exe"
& $backendPython -m pytest -q -p no:cacheprovider tests/unit/accounts/test_auth_role_matrix.py
& $backendPython -m pytest -q -p no:cacheprovider tests/unit/accounts
& $backendPython -m pytest -q -p no:cacheprovider tests/api/test_t022_create_inquiry.py tests/api/test_t023_cancel_inquiry.py
& $backendPython manage.py check
& $backendPython manage.py makemigrations --check --dry-run
& $backendPython manage.py migrate --check --noinput
& $backendPython manage.py seed_demo_accounts
& $backendPython manage.py seed_demo_accounts
& $backendPython .\apps\accounts\readiness.py --verify-postgresql
```

기존 문서에는 문의 회귀 경로가 `tests/unit/inquiries/...`로 적혀 있었지만
현재 파일은 `tests/api/...`에 있다. 잘못된 경로에서는 기능 실패가 아니라
`file or directory not found`로 0개 테스트가 실행됐으며, 위 실제 경로로
바로잡아 `24 passed`를 확인했다. 이후 QA는 이 수정된 명령만 사용한다.

## 8. 협업자 검토 항목

### 8.1 PM

- `/internal/admin/`의 배포 접근 경계
- 고정 계정 관리자 Group 이름과 최소 Permission
- 마지막 활성 관리자의 업무 정의
- 기존 계정의 `role_code` 변경 허용 시점
- `User.is_synthetic`, `auth_version` 추가 결정
- 제안 오류 코드의 Public Machine Contract 승격 여부
- T-017A 승인과 T-017B/C 일정·완료 경계

### 8.2 Data·QA

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

### 8.3 T-017·T-017A 검토 결정 기록

2026-08-03 회신은 “정책 방향”과 “WBS 완료”를 서로 다른 결정으로
기록한다. `APPROVE` 한 단어를 T-017A 완료나 T-017B 착수 허용으로
확대 해석하지 않는다.

| 검토 범위 | 검토자 | 결정 | 남은 조건 | 기준일 |
| --- | --- | --- | --- | --- |
| T-017 WBS 완료 | 윤승혁(PM) | `HOLD`, 상태는 `진행 중` | 최신 main 통합 후보 SHA·김은진의 PostgreSQL·4역할 Matrix 재현 | 2026-08-03 KST |
| T-017A 정책 방향 | 윤승혁(PM) | `APPROVE` | 완료 승인이 아님. Migration QA와 T-017 선행 Gate 필요 | 2026-08-03 KST |
| T-017 Local Runtime QA | 김은진 | 기능 `PASS`, 제출 `HOLD` | `d4bb32e`에 Matrix 파일 없음. 새 후보 SHA 재현 필요 | 2026-08-03 KST |
| T-017A Data·QA | 김은진 | `CHANGE_REQUEST` | Backfill·`auth_version`·관리자 보호·Migration QA | 2026-08-03 KST |
| `/me` 경로 | 김은진 | 정합 확인 | `GET /api/v1/me`, 추가 변경 없음 | 2026-08-03 KST |

WBS v2.1은 `T-042`에서 기사 배정·미배정 Runtime과 화면을 구현하고,
`T-047`에서 역할별 최종 권한 인수 테스트를 수행하도록 원격 main에
반영됐다. T-017A Data·QA 승인 전에는 T-017A를 팀 완료로 표시하지 않으며,
`t017b_start_allowed=false`를 유지한다. 공통 회신
필드는 [Backend 팀 검토 및 인계 체크리스트](../연동_인계/Backend_팀_검토_인계_체크리스트.md)의
반환 형식을 사용한다.

## 9. 팀 인계 순서

| 순서 | 담당 | 작업 | 반환 증거 |
| ---: | --- | --- | --- |
| 1 | Backend·Database | 4역할 Matrix·Accounts·문의 RBAC·PostgreSQL·Seed 로컬 검증 | 이 문서의 7.1~7.2와 테스트 파일 — 완료 |
| 2 | 윤승혁(PM) | WBS를 T-017/A 진행 중, B/C 차단으로 수정하고 T-042/T-047 범위 반영 | 원격 main WBS v2.1 — 완료 |
| 3 | Backend·Database | 비고객 4건의 Ledger 판정 근거와 `auth_version` rollback·실무 관리자 보호 요구 보완 | 3.4·3.7 갱신 — 작성자 보완 완료, PM·QA 세부 확정 대기 |
| 4 | Backend·Database | 최신 main 기반 후보 3파일 Commit·SHA 고정·`origin/jiyong` Push | 이 문서가 포함된 후보 Commit |
| 5 | 김은진(Data·QA) | Accounts 70·문의 24·PostgreSQL·Seed·4역할 Matrix 독립 재현 | Exit code·환경·관찰 결과 |
| 6 | 윤승혁(PM)·김은진(Data·QA) | T-017A 완료와 T-017B 착수 여부 최종 결정 | WBS·Migration QA 양쪽 결과 |
| 7 | Backend·Database | 허용된 경우에만 T-017B 구현·검증 | Admin 표적·PostgreSQL·전체 회귀 |
| 8 | Data·QA | T-017B 비작성자 재현 | 빈 DB·기존 DB·Admin 보안 결과 |
| 9 | Backend·Database | T-017B PASS 뒤 T-017C 구현·검증 | Token·동시성·감사·rollback 증거 |
| 10 | Data·QA·윤승혁(PM) | T-017C/T-047A QA와 최종 병합 판정 | 잔여 위험·병합된 main SHA |

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

## 11. T-017·T-017A 완료 체크리스트

- [x] 최신 `origin/main=d93779b` 출발 SHA를 고정하고 별도 clean 작업공간에서 후보 3파일을 격리 검증했다.
- [x] 4역할 Login·JWT Claim·`/me`·Refresh·Logout Matrix 4건을 추가·통과했다.
- [x] Accounts 70건과 문의 RBAC·IDOR 24건을 통과했다.
- [x] 작성자 로컬 PostgreSQL·Migration parity·Seed 2회·Readiness를 통과했다.
- [x] 최신 main 기반 검토 후보 범위를 Matrix·가이드·간결 인계서로 고정
- [ ] 고정 후보 SHA의 김은진 비작성자 재현
- [x] 원격 main WBS v2.1의 T-017/A `진행 중`, B/C `차단`, T-042/T-047 범위 변경 확인
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
- [x] 윤승혁(PM)의 T-017A 정책 방향 승인 기록
- [ ] 마지막 활성 실무 계정 관리자 Group·Permission·비상 계정 범위 확정
- [x] 비고객 User 4건의 Canonical Import ledger·Dataset·Mapping·Fixture Hash 연결을 작성자 로컬에서 확인
- [ ] Data·QA의 승인 Batch·Hash 고정과 비작성자 Backfill 건수 재현
- [ ] Data·QA Migration·QA 검토 증거
- [ ] WBS의 T-017A 완료 승인

따라서 현재 최종 판정은 T-017 진행 중·작성자 구현 Gate PASS,
T-017A 정책 방향 승인·Migration QA 변경 요청
(`POLICY_APPROVED_QA_CHANGE_REQUEST`)이다. T-017A를 공식 완료로 표시하지
않고 `t017b_start_allowed=false`를 유지한다.

## 12. 유지보수 원칙과 완료 조건

- 요구·일정은 WBS와 요구사항정의서, Public 계약은 API 명세·OpenAPI·오류
  코드 Registry, 인증 기준은 ADR과 Django Runtime을 source of truth로
  삼는다.
- User 필드·Migration·Admin Form·Lifecycle Service·Token 정책·감사
  Payload가 바뀌면 관련 기계 계약과 테스트를 같은 변경 묶음에서 갱신한다.
- 커밋·Push 전 PASS는 로컬 작성자 증거다. 고정 후보 SHA의 김은진 재현과
  윤승혁(PM)의 WBS 확인을 팀 승인으로 별도 기록한다.
- 윤승혁(PM)의 `APPROVE`는 T-017A 정책 방향 승인이지 T-017A 완료 승인이
  아니다. Data·QA Migration 승인 전에는 T-017B Runtime·Migration을 만들지
  않는다.
- main WBS v2.1의 T-017/A `진행 중`, T-017B/C `차단`을 기준으로 사용한다.
  검토 후보는 최신 main 기반 clean 작업공간에서 분리하며 원래 Dirty 경로를 포함하지 않는다.
- T-017A는 정책·데이터 불변식·Migration·QA 검토와 WBS 상태 갱신 증거가
  있어야 팀 완료로 표시한다.
- T-017B/C는 실제 Model·Migration·Admin·Service·오류 계약 구현과 표적
  테스트, PostgreSQL, 전체 회귀, 비작성자 재현을 모두 통과해야 완료로
  표시한다.
- 한국어 판정이 우선이며 보조 상태 코드는 자동화·검색용이다. 상태 코드
  하나만으로 공식 완료나 팀 기준선 반영을 선언하지 않는다.

## 13. 작성자 검증 후 다음 작업 Gate

1. 후보는 Matrix·이 가이드·간결 QA 인계서 3경로만 포함한다.
2. Cached 경로·Numstat·`git diff --cached --check`를 확인한 뒤 생성된
   `origin/jiyong` 후보 SHA를 김은진에게 전달한다.
3. 김은진은 그 SHA에서 이 문서 7장의 Matrix·Accounts·문의 RBAC·
   PostgreSQL·Migration·Seed·Readiness 명령을 독립 재현한다.
4. T-017은 김은진 재현 PASS와 윤승혁(PM) 완료 판정 뒤에만 완료로 바꾼다.
5. T-017A는 승인 Batch·Hash, Backfill 건수, `auth_version` 배포·rollback,
   고정 관리자 Group·Permission·비상 계정 범위를 PM·QA가 결정한 뒤에만
   완료 처리한다. 그전에는 T-017B/C Model·Migration·Admin·Lifecycle을
   구현하지 않는다.
6. QA 대기 중에는 Public Runtime을 늘리지 않고 T-018 첫 GET 계약·테스트
   Matrix 검토와 현재 T-023 CANCEL·이력·`allowed_actions`의 동작 보존형
   Characterization만 별도 변경 후보로 준비할 수 있다. T-017 후보와 같은
   Commit에 섞지 않는다.
7. 공식 T-017 Gate 뒤 기능 순서는 T-018 읽기 Slice → T-022 잔여 입력
   Slice와 T-019 읽기 Slice → 승인된 T-023 Event → Backend↔AI다.
