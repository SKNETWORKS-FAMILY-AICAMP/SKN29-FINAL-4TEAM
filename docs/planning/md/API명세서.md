# API 명세서 v2.0 — 사용자 계정 관리 최소 개정분

> 작성 기준일: 2026-07-30  
> 연계 문서: 요구사항정의서 v2.0, WBS v2.0, 화면설계서 v11  
> 적용 범위: `FR-039`, `FR-042`, `NFR-019~020`, `DR-016`, `CR-013~014`  
> 문서 성격: 기존 API명세서에 병합할 최소 개정분  
> 주의: 기존 문의·상담·방문·AI API 정의는 변경하지 않는다.

---

## 1. 개정 원칙

1. 합성 사용자 계정의 내부 관리는 Django Admin을 사용한다.
2. Django Admin은 Public REST API 계약에 포함하지 않는다.
3. 업무 역할 `OPERATOR`와 내부 계정 관리 권한을 분리한다.
4. 사용자 삭제는 물리 삭제가 아니라 `is_active=false` 비활성화를 기본으로 한다.
5. 비활성화 시 기존 Refresh Token을 폐기하고 신규 Login·Refresh·보호 API 접근을 차단한다.
6. Web·Mobile은 PostgreSQL을 직접 수정하지 않고 기존 Django API만 호출한다.
7. 관리자 권한 위임·회수와 본인 프로필 API는 P1 후속 계약으로 유지한다.

---

## 2. 내부 Django Admin 인터페이스

```text
경로 후보: /internal/admin/
인증: Django Session
요청 보호: CSRF
권한: is_staff + Model Permission + 서버 Guard
OpenAPI: Public /api/v1 계약에 포함하지 않음
접근 범위: 로컬·내부망·VPN·IP allowlist 중 승인된 환경
```

### 2.1 허용 범위

- 합성 고객·상담사·방문기사·운영 담당자 생성
- 사용자 목록·상세 조회
- 승인된 최소 필드 수정
- 비활성화·재활성화
- 계정 변경 감사 이력 조회

### 2.2 금지 범위

- 일반 관리자의 `is_superuser` 부여
- 자기 계정 비활성화
- 마지막 활성 관리자 비활성화
- 업무 이력이 연결된 사용자의 물리 삭제
- 문의·상담·방문 상태 직접 변경
- Public `/api/v1/admin/users/**` Endpoint의 P0 중복 구현

---

## 3. 기존 인증 API 유지

| ID | Method | Path | 기능 | v2 추가 규칙 |
| --- | --- | --- | --- | --- |
| `API-AUTH-001` | POST | `/api/v1/auth/demo-login` | 합성 사용자 로그인 | `is_active=false`이면 `401 ACCOUNT_INACTIVE` |
| `API-AUTH-002` | GET | `/api/v1/me` | 현재 사용자 조회 | 비활성 사용자의 보호 API 접근 차단 |
| `API-AUTH-003` | POST | `/api/v1/auth/refresh` | Refresh Rotation | 비활성 사용자 또는 폐기 Token은 `401` |
| `API-AUTH-004` | POST | `/api/v1/auth/logout` | Refresh 폐기 | 기존 Token 무효화 정책 유지 |

P0에서는 사용자 목록·생성·수정·비활성화·재활성화를 위한 Public 관리자 REST API를 추가하지 않는다.

---

## 4. 계정 비활성화 처리 계약

```text
Django Admin 비활성화 Action
→ Account Service 권한 검증
→ 자기 계정·마지막 관리자 보호 검증
→ transaction.atomic()
   ├─ is_active=false
   ├─ 비활성화 사유·수행자·시각 저장
   ├─ Outstanding Refresh Token 폐기
   └─ 계정 변경 감사 이력 저장
→ 이후 Login·Refresh·보호 API 접근 차단
```

### 4.1 보호 API 인증 규칙

- JWT 서명이 유효하더라도 사용자 원장의 `is_active=false`이면 요청을 거부한다.
- 비활성화 전 발급된 Access Token도 다음 보호 API 요청에서 거부한다.
- 재활성화 후에도 비활성화 전에 발급된 Refresh Token은 다시 사용할 수 없다.
- 기존 문의·상담·방문·케어 이력의 사용자 FK는 유지한다.

---

## 5. 공통 오류 코드 추가

| HTTP | 오류 코드 | 발생 조건 | 클라이언트 처리 |
| ---: | --- | --- | --- |
| 401 | `ACCOUNT_INACTIVE` | 비활성 사용자의 Login·Refresh·보호 API 접근 | 세션 제거 후 계정 상태 안내 |
| 401 | `REFRESH_TOKEN_REVOKED` | 비활성화·Logout 등으로 폐기된 Refresh Token | 재로그인 안내 |
| 403 | `ACCOUNT_ADMIN_REQUIRED` | 내부 계정 관리 권한 없음 | 접근 차단 |
| 403 | `PRIVILEGE_ESCALATION_DENIED` | 일반 관리자의 상위 권한 부여 시도 | 변경 거부 |
| 409 | `LAST_ADMIN_PROTECTED` | 마지막 활성 관리자 비활성화 시도 | 현재값 유지 |
| 409 | `SELF_DEACTIVATION_DENIED` | 관리자의 자기 계정 비활성화 시도 | 현재값 유지 |
| 409 | `ACCOUNT_HARD_DELETE_BLOCKED` | 업무·감사 이력이 연결된 계정 물리 삭제 시도 | 비활성화 사용 안내 |

오류 응답은 기존 공통 오류 응답 구조와 `correlation_id` 정책을 따른다.

---

## 6. P1 후속 API — 현재 비활성 계약

다음 Endpoint는 요구사항 추적을 위해 P1 후보로만 기록하며, P0 구현·OpenAPI 활성 계약에 포함하지 않는다.

| 제안 ID | Method | Path | 기능 | 현재 상태 |
| --- | --- | --- | --- | --- |
| `API-AUTH-005` | GET | `/api/v1/me/profile` | 본인 허용 프로필 조회 | P1 제안 |
| `API-AUTH-006` | PATCH | `/api/v1/me/profile` | 본인 허용 필드 수정 | P1 제안 |
| `API-AUTH-007` | POST | `/api/v1/me/deactivation-request` | 계정 비활성 요청 | P1 제안 |

다음 필드는 본인 프로필 수정 요청에 포함할 수 없다.

- `role_code`
- `employee_no`
- `is_active`
- `is_staff`
- `is_superuser`
- Group·Permission
- 내부 PK
- 비밀번호 Hash

별도 Custom 관리자 REST API는 Django Admin 운영 결과로 필요성이 확인된 뒤에만 계약한다.

---

## 7. 최소 검증 기준

- 비staff 사용자는 Django Admin에 로그인할 수 없다.
- 업무 역할 `OPERATOR`만으로 Django Admin 접근 권한을 얻지 않는다.
- 비활성 사용자의 Login·Refresh·보호 API 접근이 모두 차단된다.
- 비활성화 후 과거 Refresh Token을 재사용할 수 없다.
- 일반 관리자는 `is_superuser`를 부여할 수 없다.
- 자기 계정과 마지막 활성 관리자의 비활성화가 차단된다.
- 업무 이력이 연결된 사용자의 물리 삭제가 차단된다.
- 생성·수정·비활성화·재활성화 이력에 수행자·사유·시각이 남는다.
- 비밀번호·Token·비밀값이 API 응답과 감사 이력에 포함되지 않는다.

---

## 8. 원본 API명세서 반영 위치

기존 API명세서에는 다음 내용만 병합한다.

1. 인증·권한 원칙에 Django Admin Session·CSRF와 Public JWT 분리 추가
2. Accounts API 표의 `API-AUTH-001~004`에 비활성 계정 처리 규칙 추가
3. 공통 오류 코드에 계정 비활성·권한 상승·마지막 관리자 보호 오류 추가
4. 내부 관리 인터페이스는 Public OpenAPI에 포함하지 않는다는 경계 명시
5. `API-AUTH-005~007`은 P1 제안 상태로 별도 표기
