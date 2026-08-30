# Django Admin 단일 Supervisor 운영관리 가이드

- 작성일: 2026-08-28
- 담당: 최지용(Backend·DB)
- 관련 WBS: T-017B, T-017C, T-018의 P1 운영 범위
- 현재 단계: Supervisor Runtime·RDS 적용 완료, 공개 `/admin/` Edge 연결 병합 대기
- 배포 단계: `main` 병합·릴리스 후 실제 도메인 `/admin/` E2E와 독립 QA

## 1. 결론

Water Bridge 내부 운영 기능은 Django Admin의 `/admin/` 경로로 제공하며, 등록된
단일 합성 `Supervisor`만 접근한다. ID 불일치·설정 누락 시 Fail-closed로 차단한다.

운영 화면에서는 다음 범위를 처리한다.

| 영역 | 제공 기능 | 보존·보안 기준 |
| --- | --- | --- |
| 합성 고객 계정 | 생성, 조회, 프로필 수정, 비활성화·재활성화 | 물리 삭제 대신 계정·프로필 이력 보존 |
| 합성 상담사 계정 | 생성, 조회, 프로필 수정, ID 변경, 비밀번호 설정·초기화 | 기존 비밀번호 조회 금지, Token 전부 폐기 |
| 고객 구독 | 생성, 조회, 수정, 해지 | 참조 이력 때문에 물리 삭제 대신 `CANCELLED` 처리 |
| 상담 | 담당 상담사 변경, 시작, 내용 수정, 요약 확정, 완료 | 기존 상태머신·멱등·TransitionHistory 사용 |
| 취소 | 상담 대기·진행 중 문의 전체 취소 | Inquiry·최신 활성 Consultation을 공통 상태계약으로 원자적 취소 |

## 2. 보안 구조

### 2.1 단일 Supervisor 판정

[Supervisor 정책](../../../../backend/apps/accounts/supervisor_policy.py)은 다음 조건을
모두 만족할 때만 접근을 허용한다.

- `WATERBRIDGE_SUPERVISOR_USERNAME`과 로그인 ID가 대소문자 무관하게 일치
- 인증됨, 활성 상태, 합성 계정
- 업무 역할이 `OPERATOR`
- Django 권한이 `is_staff=True`, `is_superuser=True`
- 사용 가능한 Django 비밀번호 해시가 존재

[전용 AdminSite](../../../../backend/apps/accounts/admin_site.py)는 위 판정을 모든
Admin View에 다시 적용한다. 익명 사용자는 로그인 화면으로 이동하며, 로그인된
비-Supervisor 계정은 `/admin/` 직접 입력을 포함해 403이다. 기존
`/internal/admin/` 경로는 제거되어 404다.

### 2.2 비밀번호 저장 방식

평문 비밀번호는 최초 생성·회전 순간에만 사용하고 PostgreSQL에는 단방향 해시만
저장한다. 화면·감사·명령 결과에는 비밀값을 표시하지 않으며, 회전 시
`auth_version`을 올리고 기존 Refresh Token을 모두 폐기한다.

## 3. 계정 관리 규칙

### 3.1 상담사 ID·비밀번호

[상담사 자격증명 정책](../../../../backend/apps/accounts/credential_policy.py)은 다음을
강제한다.

- ID는 합성 계정 식별을 위해 `DEMO-` 또는 `SYN-`으로 시작
- 비밀번호 길이 12~64자
- ASCII 영문과 숫자만 사용
- 영문 1자 이상, 숫자 1자 이상 필수
- 기존 비밀번호 조회 기능 없음
- 새 비밀번호 설정 또는 초기화만 가능

ID 또는 비밀번호가 바뀌면 계정 변경 사유와 비밀값이 없는
`CREDENTIAL_RECOVERY` 감사 이벤트를 기록한다. 현재 상담사 수를 코드에 6명으로
고정하지 않으므로 승인된 합성 상담사가 늘거나 줄어도 같은 관리 기능을 사용한다.

### 3.2 고객과 구독 삭제 해석

참조 중인 고객·구독의 물리 삭제는 이력을 끊으므로 기본 삭제 버튼을 제거했다.

- 고객 계정: 계정 비활성화
- 고객 프로필: `deleted_at`, `deleted_by`를 기록하는 논리 삭제
- 구독: `status_code=CANCELLED`, `ended_on` 기록

합성 데이터도 이력과 외래키를 보존하며, 예외적 물리 삭제는 제공하지 않는다.

## 4. 상담 운영 흐름

[Supervisor 상담 서비스](../../../../backend/apps/consultations/services/supervisor_consultation_service.py)는
합성 고객의 최신 상담만 잠그고 처리한다.

PostgreSQL에서는 nullable 상담사 관계가 `LEFT OUTER JOIN`으로 조회된다. 따라서
`select_for_update(of=("self",))`로 Consultation 본행만 잠가 nullable JOIN까지
잠그려 할 때 발생하는 PostgreSQL 오류를 차단한다.

1. 활성 합성 상담사로 담당자를 변경한다.
2. `상담 시작` 작업으로 기존 `START_CONSULTATION` 전이를 실행한다.
3. 진행 중 상태에서 요약·메모·추가 확인·고객 안내·결과를 수정한다.
4. `상담 요약 확정`으로 확정본을 만든다.
5. `상담 완료`로 `CONSULTATION_COMPLETED` 전이를 실행한다.

Supervisor가 작업을 실행하더라도 담당 상담사를 상태 Guard 판정에 사용하고,
TransitionHistory의 실제 작업자는 Supervisor로 기록한다. 이에 따라 기존 상담사
API의 소유권 규칙을 깨지 않으면서 운영자 작업자를 추적할 수 있다.

완료 직후 Inquiry는 계약상 `COMPLETION_PENDING`이다. 고객 해결·미해결 확인 등
후속 완료 흐름을 거치기 전에는 Admin이 임의로 `RESOLVED`로 바꾸지 않는다.

### 취소 경계

- Admin의 상담 취소 작업도 별도 SQL 변경이 아니라 기존
  `POST /api/v1/inquiries/{id}/cancel`과 같은 `InquiryService.cancel`을 사용한다.
- `CONSULTATION_REQUIRED`, `CONSULTATION_IN_PROGRESS`에서 Inquiry와 최신 활성
  Consultation을 함께 `CANCELLED`로 바꾸며 담당자 정보는 감사 추적을 위해
  보존한다.
- 본인 고객, 현재 배정 상담원, `INQUIRY_CANCEL` 권한 운영자만 사용할 수 있다.
  Supervisor는 운영자 권한으로 같은 객체·Guard 검사를 통과해야 한다.
- 활성 Visit이 하나라도 존재하면 State Machine이 409로 차단하고 두 레코드를
  모두 변경하지 않는다.
- 취소는 terminal 처리다. 같은 Inquiry를 되살리지 않고 필요한 경우 새 문의를
  생성한다.
- Version·Idempotency Key·Correlation ID를 두 레코드에 맞추고, 뒤 단계가
  실패하면 Inquiry·Consultation·History·멱등 기록을 모두 Rollback한다.

## 5. 로컬 생성·회전 절차

아래 값은 예시값을 문서나 Git에 적지 말고 현재 PowerShell 프로세스 또는 승인된
비밀 주입 수단으로만 설정한다.

```powershell
$env:WATERBRIDGE_SUPERVISOR_USERNAME='<합성 Supervisor ID>'
$env:WATERBRIDGE_SUPERVISOR_PASSWORD='<보호된 비밀번호>'
$env:WATERBRIDGE_SUPERVISOR_FULL_NAME='<합성 이름>'
$env:WATERBRIDGE_SUPERVISOR_EMPLOYEE_NO='<합성 사번>'
```

Backend 가상환경에서 먼저 Dry-run을 수행한다.

```powershell
python manage.py bootstrap_waterbridge_supervisor --dry-run --json
```

출력의 `secret_exposed`가 `false`이고 다른 superuser 충돌이 없을 때 적용한다.

```powershell
python manage.py bootstrap_waterbridge_supervisor --json
```

그 뒤 Backend를 실행하고 `http://127.0.0.1:8000/admin/`에서 확인한다. 명령은
다른 superuser가 있으면 자동 변경·삭제하지 않고 중단한다. 기존 계정 정리는 별도
승인 후 수행해야 한다.

## 6. AWS 배포 인계 범위

김은진 작업자는 `main` 병합 SHA를 기준으로 아래 이름의 값을 AWS Secrets
Manager 또는 동일한 보호 환경에서 주입한다. 실제 값은 문서·채팅·명령 결과에
노출하지 않는다.

| 환경변수 | Runtime 필요 | Bootstrap·회전 필요 | 비밀 여부 |
| --- | ---: | ---: | ---: |
| `WATERBRIDGE_SUPERVISOR_USERNAME` | O | O | 계정 식별자, 비밀 아님 |
| `WATERBRIDGE_SUPERVISOR_PASSWORD` | X | O | 비밀 |
| `WATERBRIDGE_SUPERVISOR_FULL_NAME` | X | O | 합성 메타데이터 |
| `WATERBRIDGE_SUPERVISOR_EMPLOYEE_NO` | X | O | 합성 메타데이터 |

배포 적용 순서는 다음과 같다.

1. 대상 SHA와 현재 RDS Backup·복구 지점을 확인한다.
2. 새 DB Migration은 없음을 Plan에서 확인한다.
3. 보호 환경값을 주입하여 `bootstrap_waterbridge_supervisor --dry-run`을 실행한다.
4. 다른 superuser 충돌이 없을 때 실제 Bootstrap 또는 비밀번호 회전을 실행한다.
5. 애플리케이션 Runtime에는 Supervisor username을 유지한다.
6. `/admin/login/` 200, Supervisor 로그인 성공, 다른 계정 403을 확인한다.
7. 합성 고객·구독·상담 표적 작업 후 감사 이력과 기존 JWT 폐기를 확인한다.

공개 경로는 Web Edge가 `/admin`을 `/admin/`로 정규화하고 `/admin/` 요청을 Backend
Django Admin으로 전달한다. `/static/`은 Backend 이미지의 `collectstatic` 결과를
릴리스 SHA별 공유 볼륨으로 제공해 이전 릴리스 자산 혼입을 막는다. HTTPS 원본
Scheme과 Secure Session·CSRF Cookie를 유지하며 기존 `/login`·`/api/`·SPA 경로는
변경하지 않는다. Secret·계정·RDS 변경은 이 연결 작업 범위가 아니다.

## 7. 구현 파일

- 접근·Admin: [supervisor_policy.py](../../../../backend/apps/accounts/supervisor_policy.py), [admin_site.py](../../../../backend/apps/accounts/admin_site.py), [accounts/admin.py](../../../../backend/apps/accounts/admin.py)
- 자격증명·Bootstrap: [credential_policy.py](../../../../backend/apps/accounts/credential_policy.py), [bootstrap_waterbridge_supervisor.py](../../../../backend/apps/accounts/management/commands/bootstrap_waterbridge_supervisor.py)
- 운영 Runtime: [subscriptions/admin.py](../../../../backend/apps/subscriptions/admin.py), [consultations/admin.py](../../../../backend/apps/consultations/admin.py), [supervisor_consultation_service.py](../../../../backend/apps/consultations/services/supervisor_consultation_service.py)
- 취소 Runtime: [inquiry_service.py](../../../../backend/apps/inquiries/services/inquiry_service.py), [consultation_repository.py](../../../../backend/apps/consultations/repositories/consultation_repository.py)
- UI: [base_site.html](../../../../backend/apps/accounts/templates/admin/base_site.html), [waterbridge_admin.css](../../../../backend/apps/accounts/static/accounts/admin/waterbridge_admin.css)

## 8. 검증 결과

| 검증 | 결과 | 의미 |
| --- | --- | --- |
| Django `check` | PASS | Admin 등록·URL·설정 구조 정상 |
| `makemigrations --check --dry-run` | PASS, 변경 없음 | 새 Schema Migration 불필요 |
| 신규 Supervisor 표적 검증 | 11 passed | 단일 접근, Bootstrap, 잠금 범위, 상담 운영 흐름 확인 |
| 상담 취소 계약·API 표적 검증 | 91 passed, 2 skipped | 4개 상태·3개 역할·Visit 차단·원자적 Rollback 검증 |
| State Machine·Crosswalk | PASS, 13 states·39 transitions | Mermaid·OpenAPI·Action 계약 정합 |
| Backend CI 동일 3 Shard | 1,657 passed, 45 skipped | Domain 609·Platform 599·API/Integration 449 통과 |
| Supervisor 실제 PostgreSQL 복제 DB | 27 passed, 0 failed | 계정·고객·구독·상담·취소·감사 기능과 원본 DB 불변 확인 |
| PostgreSQL 취소 표적 | 32 passed | 실제 PostgreSQL에서 역할·원자성·동시 Row-lock 통과 |
| 공개 Admin Edge | 배포 자산 26 passed, Docker E2E PASS | `/admin` 308, Backend Proxy, 정적 CSS 200, 기존 SPA 200 |
| `git diff --check` | PASS | 공백·Patch 형식 오류 없음 |

45개 Skip은 별도 환경을 요구하는 PostgreSQL Constraint 또는 외부 AI Socket
항목이다. PostgreSQL 전용 2개 Row-lock 테스트는 별도 pgvector/PostgreSQL에서
통과했다. 작성자 검증은 실제 AWS RDS 적용·독립 QA·PM 판정을 대신하지 않는다.

## 9. 브랜치 게시 이후 남은 외부 Gate

공개 Edge 변경의 `main` 병합·Backend/Web 재배포, 실제 도메인 `/admin/` 로그인과 CSS·JS E2E, 김은진 독립 QA 및 윤승혁(PM) 판정은 별도 Gate다.
