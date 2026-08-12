# Web 조회 종결·Mobile 추가문진 Fixture Runtime Smoke 구현·검증 보고서

## 1. 문서 정보

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-08-11 KST |
| 작성자 | 최지용 — Backend·DB |
| 기준선 | `origin/main@254dea9113ce2e02c5c2964519a90beaa4e73cb0` |
| 상태 | `AUTHOR_VERIFIED / MOBILE_ADAPTER_PENDING` |
| 기능 Commit | `f2d1af4` — Mobile 공식 Fixture·Runtime Smoke 구현 |
| 게시 대상 | `jiyong` — 최종 게시 여부와 보고서 Commit은 Git 이력 기준 |
| 구현 범위 | Web 상담사 조회 종결, Mobile 고객문의 공식 Fixture, Backend 실제 Socket Smoke |

## 2. 한 문장 결론

상담사 Web 문의 조회는 현재 `main`과 PostgreSQL에서 다시 통과해 Backend 범위를 종결했고,
Mobile 고객문의 3 API용 공식 합성 Fixture와 실제 Socket 회귀를 추가하여
지원 구독·비어 있지 않은 질문·답변·Replay·409·422·404를 재현 가능하게 만들었다.

Mobile Adapter와 실제 외부 AI 결과 검증은 이 보고서의 완료 범위가 아니다.

## 3. 작업 범위와 관할

### 3.1 수행한 작업

1. Web 상담사 문의 목록·상세 조회 Slice를 현재 `main`에서 PostgreSQL 재검증했다.
2. 기존 Demo Seed를 변경하지 않고 Mobile 전용 Fixture 명령을 추가했다.
3. Fixture 멱등성·충돌 차단·답변 원장 비삭제 테스트를 추가했다.
4. 실제 HTTP Socket에서 Mobile 3 API와 오류·멱등 흐름을 검증했다.
5. SQLite, PostgreSQL 2회, Backend 전체 회귀, 기계계약을 검증했다.

### 3.2 수정하지 않은 관할

- `web/**`, `mobile/**`
- OpenAPI·State Machine·AI Schema·Prompt
- 기존 Demo Account·Product·Subscription·Consultant Seed
- Model·Migration·공용 데이터 Pipeline
- PM·QA의 공식 완료 상태

## 4. 1순위 — Web 상담사 문의 조회 종결

### 4.1 수신 회신 판정

한예나 회신은 다음 실제 연동을 기록한다.

- Mock Off 상담사 Demo Login·`/me`
- `GET /api/v1/inquiries`
- `GET /api/v1/inquiries/{inquiry_id}`
- CUSTOMER 403, 미존재 404, 잘못된 Query 422
- 응답·Backend Log Correlation ID 일치
- Backend 중단 시 502이며 Mock 자동 대체 없음
- Web Test·Lint·TypeScript·Build PASS

이 결과는 `CONSULTANT_INQUIRY_READ` 범위에 한해 수용한다.
상담·방문 쓰기와 전체 Web 완료로 확대하지 않는다.

### 4.2 Backend 독립 재검증

격리 PostgreSQL DB `codex_web_read_closeout_20260811`에서 다음을 재실행했다.

```text
tests/unit/inquiries/test_demo_consultant_inquiry_seed.py
tests/integration/test_consultant_inquiry_live_http_smoke.py
결과: 4 passed in 18.61s
```

판정:

```text
CONSULTANT_INQUIRY_READ_BACKEND_RUNTIME=PASS
CONSULTANT_INQUIRY_READ_SHARED_SMOKE_EVIDENCE=ACCEPTED
ADDITIONAL_BACKEND_IMPLEMENTATION=NONE
```

상세 헤더의 고정 상담사 이름·사번은 Web 담당 후속이며 Backend 범위가 아니다.

## 5. 2순위 — Mobile 공식 추가문진 Fixture

### 5.1 추가 파일

- [공식 Fixture 명령](../../../../backend/apps/inquiries/management/commands/seed_demo_mobile_followup.py)
- [Fixture 단위 테스트](../../../../backend/tests/unit/inquiries/test_demo_mobile_followup_seed.py)
- [실제 Socket 통합 테스트](../../../../backend/tests/integration/test_mobile_followup_live_http_smoke.py)

### 5.2 실행 순서

Backend 실행자가 격리 개발·Smoke DB에서 실행한다.

```powershell
cd backend
python manage.py seed_demo_accounts
python manage.py seed_demo_mobile_followup --json
```

Mobile 담당자가 SQL·Django Shell로 직접 Fixture를 만들 필요는 없다.

### 5.3 생성 데이터

| 데이터 | 값 |
|---|---|
| Demo Login | `DEMO-CUSTOMER-001` |
| 지원 모델 | `WPUJAC104DWH` |
| 구독 상태 | `ACTIVE` |
| 구독 Public ID | `d0a62011-3b89-5d39-8cd4-4c1d8c365101` |
| 문의 상태 | `QUESTIONNAIRE_IN_PROGRESS` |
| 초기 `state_version` | `2` |
| 문의 Public ID | `d0a62011-3b89-5d39-8cd4-4c1d8c365102` |
| FREE_TEXT 질문 | `d0a62011-3b89-5d39-8cd4-4c1d8c365103` |
| SINGLE_CHOICE 질문 | `d0a62011-3b89-5d39-8cd4-4c1d8c365104` |
| 공개 선택지 | `최근 교체함`, `교체하지 않음`, `모름` |

Customer Public ID는 `seed_demo_accounts`가 만든 환경별 값을 `--json` 출력에 포함한다.
Mobile 제품 코드에서는 Customer·Subscription·Inquiry·Question UUID를 상수로 고정하지 않는다.
실제 구독은 `/api/v1/me/subscriptions`로 조회하고,
Smoke 실행 시에만 출력된 Crosswalk를 대조한다.

### 5.4 안전 정책

- 기존 Demo Seed를 변경하지 않는다.
- 기존 `WPUJAC104DWH`가 활성·지원 상태이면 읽어서 사용한다.
- 같은 코드의 제품이 비활성·미지원이면 임의 수정하지 않고 실패한다.
- 전용 구독·문의·질문의 고정 식별자가 충돌하면 실패한다.
- 같은 DB에서 답변 원장이 생긴 뒤에는 이를 삭제·초기화하지 않는다.
- 소비된 Fixture는 새 격리 DB에서 다시 생성한다.
- Command를 소비 전 반복 실행해도 중복 행을 만들지 않는다.

## 6. 3순위 — Backend 실제 Socket Smoke

### 6.1 검증 흐름

```text
Demo Customer Login
→ 지원 구독 목록 200
→ 문의 Snapshot 200, state_version=2
→ 미답변 질문 2건 200
→ FREE_TEXT 답변 200, state_version=3
→ 동일 Idempotency-Key Replay 200, 중복 저장 없음
→ 계약 외 선택지 422
→ 오래된 state_version 409 STATE-CONFLICT-01
→ SINGLE_CHOICE 답변 200, state_version=4
→ 질문 목록 []
→ Snapshot state_version=4
→ 타 고객 404
→ 미존재 문의 404
→ 알 수 없는 Query 422
```

모든 요청은 요청 Header·응답 Header·응답 Body의 Correlation ID를 대조했다.
Request Log에는 Access Token과 고객 답변 원문이 포함되지 않음을 자동 검증했다.

### 6.2 AI 경계

성공한 고유 답변 2건은 Commit 후 AI 재평가 Callback을 정확히 2회 예약했다.
Replay·422·409는 Callback을 추가하지 않았다.

테스트에서는 외부 AI HTTP 호출을 Mock으로 격리했다.
따라서 `답변 저장 후 Callback 발생`은 PASS지만
`실제 AI 서비스 응답·Guidance/Evidence 저장 완료`는 별도 공동 Smoke 대상이다.

## 7. 검증 결과

| 검증 | 결과 |
|---|---:|
| 신규 Fixture 단위 테스트 | `4 passed` |
| 신규 SQLite 실제 Socket | `1 passed` |
| Mobile 3 API·구독 표적 SQLite | `32 passed` |
| PostgreSQL 격리 DB r1 | `32 passed` |
| PostgreSQL 격리 DB r2 | `32 passed` |
| Web 조회 PostgreSQL 종결 재검증 | `4 passed` |
| Backend OpenAPI·Runtime 표적 | `18 passed` |
| Backend 전체 | `973 passed, 17 skipped` |
| Root 계약·Safety | `42 passed, 1 cache warning` |
| Django Check | `0 issues` |
| Migration drift | `No changes detected` |
| compileall | PASS |
| `git diff --check` | PASS |

PostgreSQL 반복 DB:

```text
codex_mobile_followup_20260811_r1 → 32 passed in 50.38s
codex_mobile_followup_20260811_r2 → 32 passed in 50.30s
```

17개 Skip은 pgvector·PostgreSQL 전용 구조·외부 AI Mock·TEAM_INTEGRATION Role 등
명시적 별도 조건이며 이번 Fixture·Mobile 3 API 실패가 아니다.

Root 경고는 `.pytest_cache` 쓰기 권한 경고이며 계약 테스트 실패가 아니다.

## 8. 현재 완료·미완료 판정

```text
WEB_CONSULTANT_INQUIRY_READ=COMPLETE
MOBILE_3API_CONTRACT=IMPLEMENTED
MOBILE_OFFICIAL_FIXTURE=AUTHOR_VERIFIED
MOBILE_BACKEND_ACTUAL_SOCKET=PASS
MOBILE_FRONTEND_ADAPTER=NOT_STARTED
MOBILE_DEVICE_REMOTE_SMOKE=NOT_RUN
EXTERNAL_AI_RESULT_SMOKE=NOT_RUN
GIT_PUBLISH_TARGET=JIYONG
```

## 9. 후속 Gate

1. `jiyong` 게시 SHA를 팀에 전달하고 PM이 `main` 반영 여부를 결정한다.
2. Backend 담당자가 격리 DB에 Seed를 적용하고 접근 가능한 URL을 제공한다.
3. 양정현이 Retrofit·DTO·Mapper·Repository·UiState·오류 처리를 구현한다.
4. 양정현 Unit·Build PASS 후 실제 단말 공동 Smoke를 실행한다.
5. 외부 AI 결과는 이동윤 담당 Runtime과 별도 공동 검증한다.

## 10. 참고

- [Mobile 3 API 기존 구현 보고서](./Django_REST_API_Mobile_고객문의_조회_추가답변_VisitLock_Runtime_구현_검증_보고서_20260810.md)
- [추가답변 Runtime 문서](./Django_REST_API_고객_추가문진_답변_Runtime_구현_검증_인계서.md)
- [수신한 Mobile 회신](../../../../../Daily_Process/20260811/20260811_양정현_to_최지용_Mobile_고객문의3API_계약확인_연동착수_회신_v0.1.md)
- [수신한 Web 회신](../../../../../Daily_Process/20260811/20260811_한예나_to_최지용_Web_상담사_문의조회_PostgreSQL_공동Smoke_회신_v0.1.md)
