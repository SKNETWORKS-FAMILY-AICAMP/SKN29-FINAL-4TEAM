# PostgreSQL 공통 인증 Row Lock 수정·재검증 보고서

## 1. 문서 정보

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-08-11 |
| 작성자 | 최지용 — Backend·DB |
| 시작 기준 | `origin/main@92b0674cd1a3376a2c058715cd5ef32222125755` |
| 검증 Branch | `codex/backend-auth-pg-fix-20260811` |
| 게시 대상 | `jiyong` |
| 코드 Commit | `bed0070a46658956dffbcfd6f65d3fbee7396433` |
| 상태 | `FIX_IMPLEMENTED / AUTHOR_VERIFIED / JIYONG_PUBLISHED / MAIN_MERGE_PENDING` |

## 2. 최종 결론

PostgreSQL Demo Login 500의 원인이던 nullable Outer Join 잠금 범위를 수정했고,
고객·상담사 인증 수명주기와 Web 상담사 조회를 실제 공통 DB Socket에서 두 번 연속 통과했다.

Backend 공통 인증 결함은 해소됐다. 다만 Mobile은 공식 Seed의 노출 가능 구독과
비어 있지 않은 추가질문 Fixture가 부족하므로 전체 Mobile 답변 공동 Smoke 완료로 판정하지 않는다.

## 3. 이전 보고서와의 관계

이 문서는 최초 검증에서 발견한 `PostgreSQL Demo Login 500`의 후속 수정·재검증 결과다.

- [최초 공통 Backend 환경·DB 검증 보고서](../개발환경/Django_PostgreSQL_공통Backend환경_DB_구축_검증_보고서_20260811.md)

최초 보고서의 실패 증거는 당시 사실로 유지하고,
현재 상태 판단은 이 후속 보고서를 우선한다.

## 4. 수정 범위

변경 파일은 Backend 관할의 3개뿐이다.

| 파일 | 변경 내용 |
|---|---|
| `backend/apps/accounts/repositories/account_repository.py` | 두 User 잠금을 자기 행으로 제한 |
| `backend/tests/unit/accounts/test_account_repository.py` | 잠금 범위 구조 회귀 신규 작성 |
| `backend/tests/api/test_customer_inquiry_read_runtime.py` | DateTime을 Offset 문자열이 아니라 동일 순간으로 비교 |

현재 변경 파일:

- [Account Repository](../../../../backend/apps/accounts/repositories/account_repository.py)
- [Account Repository 회귀 테스트](../../../../backend/tests/unit/accounts/test_account_repository.py)
- [Customer Inquiry Runtime 테스트](../../../../backend/tests/api/test_customer_inquiry_read_runtime.py)

수정하지 않은 영역:

- Web·Mobile Frontend 소스
- API Path·DTO·State Machine 계약
- Model·Migration·Seed Command
- AI Schema·Prompt·판정 정책
- 기존 개인 DB `waterbridge`

## 5. 결함 원인과 수정

### 5.1 기존 원인

`lock_active_by_pk()`와 `lock_active_by_subject()`는 다음 두 동작을 동시에 수행했다.

1. `User`를 `select_for_update()`로 잠금
2. 선택 관계인 `customer_profile`을 `select_related()`로 조회

User에서 CustomerProfile로 향하는 Reverse OneToOne은 선택 관계이므로 SQL은 `LEFT OUTER JOIN`이 된다.
기존 코드는 PostgreSQL에서 nullable Join 측까지 잠그려 했고 다음 오류를 발생시켰다.

```text
NotSupportedError:
FOR UPDATE cannot be applied to the nullable side of an outer join
```

### 5.2 적용한 수정

두 Repository 메서드 모두 User 자기 행만 잠그도록 변경했다.

```python
User.objects.select_for_update(of=("self",))
```

- `lock_active_by_pk()`: Demo Login과 Token Pair 발급 경로
- `lock_active_by_subject()`: Refresh·Logout의 현재 사용자 검증 경로

`customer_profile`은 한 번에 조회하지만 잠금 대상에서는 제외된다.
`is_active`, `role_code`, `auth_version` 등 인증 보안 상태는 User에 있으므로 직렬화 경계는 유지된다.

## 6. 회귀 테스트 보강

### 6.1 Row Lock 구조 회귀

신규 테스트는 두 Repository 메서드를 모두 호출하고 다음 인자를 정확히 검사한다.

```text
select_for_update(of=("self",))
```

SQLite가 PostgreSQL 잠금 오류를 재현하지 못하더라도,
향후 `of=("self",)`가 제거되면 기본 테스트에서도 실패한다.

### 6.2 Snapshot DateTime 회귀

기존 테스트는 UTC `Z` 문자열만 정답으로 간주했다.
OpenAPI는 RFC3339 `date-time`을 요구하므로 `Z`와 `+09:00`은 같은 순간일 수 있다.

수정 후에는 다음을 함께 검증한다.

- `updated_at` 외 Projection의 정확한 전체 일치
- 응답 DateTime Parsing 성공
- Parsing한 순간과 DB `updated_at`의 동등성

Runtime 응답 형식이나 계약은 변경하지 않았다.

## 7. 단계별 검증 결과

### 7.1 빠른 로컬 회귀

대상: Account 잠금, 인증 API, 네 역할 인증 Matrix, Customer Snapshot·질문

결과: `33 passed`

### 7.2 PostgreSQL 인증 표적

첫 실행에서 로컬 설정의 Demo Login 기본값과 테스트 기대값이 달라 1건이 실패했다.
이는 Row Lock 재발이 아니라 `DJANGO_DEMO_LOGIN_ENABLED` 테스트 환경 차이였다.

테스트 기본값을 명시적으로 비활성화하고 개별 테스트가 필요한 구간만 활성화한 결과:

- 인증·Repository·실제 Socket: `29 passed`
- 반복 핵심 인증·Socket: `7 passed`

### 7.3 PostgreSQL 관련 전체 통합 묶음

포함 범위:

- Account Repository·Login·Refresh·Logout·네 역할 Matrix
- Web 상담사 실제 Socket·목록·상세
- Mobile Snapshot·질문·추가답변
- Migration 0011 Forward/Reverse
- Visit self-row lock

결과: `61 passed`

### 7.4 Backend 전체 회귀

결과: `968 passed, 17 skipped`

17건은 실패가 아니다.
pgvector·복합 FK·PostgreSQL 구조·별도 AI Mock·TEAM_INTEGRATION Role처럼
명시적 외부 조건이 필요한 테스트만 Skip됐다.

### 7.5 계약·정적 Gate

| 검증 | 결과 |
|---|---:|
| Backend OpenAPI·Runtime Coverage | `21 passed` |
| Root Crosswalk·주차 계약·Validator | `12 passed` |
| `manage.py check` | PASS |
| `makemigrations --check --dry-run` | `No changes detected` |
| `compileall` | PASS |
| `git diff --check` | PASS |

## 8. 공통 PostgreSQL 실제 Socket 재검증

대상 DB: `waterbridge_shared_smoke_20260811`

같은 검증을 `final1`, `final2` 두 번 독립 실행했다.

두 실행에서 공통으로 통과한 항목:

- 고객 Demo Login 200 → `/me` 200 → Refresh 200
- 기존 Refresh 재사용 401
- Logout 200 → 폐기 Refresh 재사용 401
- 상담사 Demo Login·`/me`·Refresh·Logout 동일 수명주기
- 상담사 문의 목록 200·고정 문의 포함
- 상담사 문의 상세 200
- 고객 Token으로 상담사 목록 403
- 미존재 문의 404 `RESOURCE_NOT_FOUND`
- 알 수 없는 Query 422 `VALIDATION_ERROR`
- 문의 소유 고객 Snapshot 200
- 문의 소유 고객 Questions 200·현재 빈 목록
- 타 고객 Snapshot 404
- 빈 Answers 422·DB Write 없음

각 실행에서 지정한 API Correlation ID `23/23`이 응답 Header·Body·JSON Log에서 일치했다.
Health까지 포함한 `request_completed` 로그는 실행당 24건이고 `NotSupportedError`는 0건이다.
로그에는 Access·Refresh Token 문자열이 기록되지 않았다.

작성자 로컬 증거 경로는 저장소에 포함하지 않는다.

```text
C:\python-src\Final_PROJECT\.codex_artifacts\backend_auth_fix_20260811\actual_socket_final1.jsonl
C:\python-src\Final_PROJECT\.codex_artifacts\backend_auth_fix_20260811\actual_socket_final2.jsonl
```

SHA-256:

```text
final1 82FB46BB7D5F864B19318980E199A91C312C05B8A5B5B89EED3EBBC01523076E
final2 7A800A6A5C8FE3A351EF8CC687F14C2EBFAADDD85214F2C3C35C832428666B27
```

## 9. DB 무변경·부수효과 확인

### 9.1 기존 개인 DB

기존 `waterbridge`는 작업 후에도 다음 Migration이 미적용 상태로 유지됐다.

- `accounts.0005_account_lifecycle_and_audit`: 미적용
- `inquiries.0011_split_followup_question_metadata_and_answers`: 미적용

따라서 기존 개인 DB에 Migration·Seed를 적용하지 않았다.

### 9.2 전용 공통 DB

| 항목 | 최종 값 |
|---|---:|
| 미적용 Migration | 0 |
| 문의 | 1 |
| 추가질문 | 0 |
| 추가답변 | 0 |
| Outstanding Token | 18 |
| Blacklisted Token | 16 |

Token 행 증가는 Login·Rotation·Logout 검증의 정상 감사 기록이다.
Actual Socket 두 실행 전후 문의 행은 `1 → 1`로 동일했다.

## 10. Web 현재 판정

Backend 관점:

```text
POSTGRESQL_AUTH_PASS
WEB_READ_ACTUAL_SOCKET_PASS
WEB_BACKEND_HANDOFF_CANDIDATE
```

Web 상담사 목록·상세 Backend Runtime과 실제 PostgreSQL 인증은 준비됐다.
다만 “Web 연결 완료”는 아니다. 실제 한예나 실행환경에서 다음을 확인해야 한다.

- 접근 가능한 Backend URL
- Mock Off·Fallback 없음
- Web Remote Adapter 실제 호출
- 같은 Correlation ID의 Backend Log 대조

이번 작업에서는 Web 인계서를 작성하지 않았다.

## 11. Mobile 현재 판정

Backend 자동검증:

```text
MOBILE_SNAPSHOT_QUESTIONS_ANSWERS_POSTGRESQL_TEST_PASS
```

공통 DB 실제 Socket:

```text
MOBILE_OWNER_SNAPSHOT_PASS
MOBILE_QUESTIONS_ROUTE_PASS_EMPTY
MOBILE_ANSWERS_SHARED_SMOKE_HOLD
```

확인된 Fixture 공백:

- `DEMO-CUSTOMER-001`의 `/me/subscriptions`는 200이지만 `items=[]`다.
- 구독 조회 Runtime은 제품 모델 코드 `WPUJAC104DWH`만 공개한다.
- 현재 Demo Product/Subscription Seed는 이 공개 조건을 충족하지 않는다.
- 공식 Seed에는 미답변 `InquiryQA`도 없다.
- 따라서 공통 DB에서 비어 있지 않은 질문·답변 200·Replay·409를 검증할 수 없다.

임의 SQL이나 Django Shell 데이터로 PASS를 만들지 않았다.
Mobile 전용 멱등 합성 Fixture를 공식 Seed로 확정한 뒤 다시 검증해야 한다.

검증 단계에서는 Frontend 인계서를 작성하지 않았으며,
게시 후 Web·Mobile 담당자별 인계요청서를 `Daily_Process/20260811`에 별도로 작성한다.

## 12. 남은 작업과 권장 순서

1. PM이 게시된 `jiyong` Commit을 검토하고 `main` 병합 SHA를 공유
2. 같은 PC 또는 LAN Backend URL·Host·CORS 확정
3. Web 담당자와 상담사 문의 조회 공동 Remote Smoke 수행
4. Mobile 노출 가능 구독·추가질문 공식 Seed 범위 결정
5. Mobile 실제 Answers 200·Replay·409 공통 DB Socket 재검증
6. Frontend별 결과 회신을 Backend Correlation Log와 대조

## 13. 최종 상태

```text
공통 인증 결함 수정: COMPLETE
PostgreSQL 관련 회귀: PASS
Backend 전체 회귀: PASS
Web Backend 실제 Socket: PASS
Mobile Snapshot 실제 Socket: PASS
Mobile Questions 실제 Socket: PASS_EMPTY
Mobile Answers 실제 Socket: HOLD_BY_OFFICIAL_FIXTURE
Frontend 소스 변경: NONE
인계요청 문서: Daily_Process 별도 작성
코드 게시 대상: jiyong
Main Merge: PENDING
```
