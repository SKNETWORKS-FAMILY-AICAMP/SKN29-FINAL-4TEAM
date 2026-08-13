# 한예나 → 최지용: Web CONS-04 전화 문의 등록 API 연동 회신

- 작성일: 2026-08-12
- 발신: 한예나 / Web
- 수신: 최지용 / Backend·DB·Public API
- 대상 기능: `CONS-04 전화 문의 등록`
- Backend 게시 SHA: `a4309d4c8d3b2cdb91e026a7d70fba2d9962c1c2`
- 작업 브랜치: `yena`
- 작업 시작 기준 HEAD: `ba384fb61c4138ca2440caa6c0540a2031a9af55`
- 현재 상태: `WEB_REMOTE_IMPLEMENTED / WEB_TEST_PASS_WITH_SCOPE_LIMIT / SHARED_SOCKET_SMOKE_BLOCKED / NOT_COMMITTED`

## 1. 결론

전달받은 CONS-04 Backend 구현·검증 보고서와 Public API 계약을 확인했고,
수정된 화면설계서에 계약 불일치가 없음을 확인했습니다.

화면설계서는 요청서에서 전달한 파일명인
`docs/planning/md/20260811_한예나_화면설계서.md`로 기존 정본을 교체했으며,
Web의 임시 LocalStorage·가짜 `PHONE-*` 등록 경로를 제거하고 아래 두
Remote API에 연결했습니다.

| Method | Path | Web 상태 |
| --- | --- | --- |
| `POST` | `/api/v1/consultant/customer-subscriptions/search` | 연결 완료 |
| `POST` | `/api/v1/consultant/phone-inquiries` | 연결 완료 |

Web Lint, TypeScript, Production Build와 전체 테스트는 통과했습니다.
다만 요청서의 자동 검증 Matrix 중 최신 응답 우선, 빈 결과, 409, 422,
등록 중복 클릭·멱등 재시도에 대한 CONS-04 전용 테스트는 아직 추가되지
않았습니다. 공용 PostgreSQL과 실제 Backend Process를 사용한 공동 Socket
Smoke도 실행정보 미전달로 차단되어 있습니다.

## 2. 확인한 인계 자료

- `20260811_최지용_to_한예나_Web_CONS04_전화문의등록_API_Runtime_연동요청_v0.1.md`
- `docs/individual/jiyong/API/Django_REST_API_Web_CONS04_상담사_전화문의등록_Runtime_구현_검증_보고서_20260811.md`
- `docs/api/consultant_phone_inquiry_api.md`
- `contracts/api/paths/consultant-phone-inquiries.yaml`
- `backend/apps/inquiries/api/serializers/consultant_phone_inquiry.py`
- `backend/apps/inquiries/api/views.py`

## 3. 화면설계서 검토·교체 결과

수정본에서 다음 내용을 Backend 정본과 대조했습니다.

| 확인 항목 | 결과 | 확인 내용 |
| --- | --- | --- |
| 검색 Route | PASS | POST Body 기반 고객·활성 구독 검색 |
| 검색 최소 길이 | PASS | 고객명 trim 후 2자, 연락처 숫자 4자리 이상 |
| 검색 DTO | PASS | 고객 공개 ID, 마스킹 연락처, 활성 구독·제품 정보 |
| 복수 구독 | PASS | 활성 구독 한 건을 후보 한 행으로 표시 |
| 등록 Route·DTO | PASS | `subscription_id`, `raw_text`, 증상·우선순위 코드 |
| 필수 Header | PASS | Correlation ID, 등록 시 Idempotency-Key |
| 성공 상태 | PASS | `CONSULTATION_REQUIRED`, `state_version=1` |
| 오류 처리 | PASS | 401·403·404·409·422·500 분기 |
| 개인정보 | PASS | 전화번호 원문 반환·저장 금지 |
| 계약 제외 항목 | PASS | 문의명·상담 메모·콜백·동의 확인을 등록 요청에서 제외 |

교체된 정본:

```text
docs/planning/md/20260811_한예나_화면설계서.md
```

다운로드로 전달받은 수정본과 본문 내용이 동일함을 비교 확인했습니다.

## 4. Web 구현 내용

### 4.1 고객·활성 구독 검색

- 이름 2자 이상 또는 연락처 숫자 4자리 이상에서 검색합니다.
- 입력 변경 후 300ms Debounce를 적용합니다.
- 이전 검색 요청의 응답은 취소 플래그로 무시하여 최신 입력의 응답만
  화면에 반영합니다. 현재 공통 HTTP Client가 외부 AbortSignal을 받지 않아
  이미 전송된 HTTP 요청 자체를 AbortController로 중단하지는 않습니다.
- 검색어는 URL Query가 아닌 JSON Body의 `query`로 전송합니다.
- 검색 중, 결과 있음, 결과 없음, 조회 실패 상태를 분리했습니다.
- 동일 고객의 복수 활성 구독은 제품별 후보 행으로 표시합니다.
- 후보에는 Backend가 반환한 `phone_masked`만 표시합니다.
- 키보드 위·아래 방향키, Enter, Esc와 포인터 선택을 지원합니다.
- 후보에서 구독을 선택하기 전에는 등록할 수 없습니다.

검색 요청:

```json
{
  "query": "0001",
  "limit": 10
}
```

### 4.2 전화 문의 등록

선택한 후보의 `subscription_id`와 아래 계약 필드만 전송합니다.

```json
{
  "subscription_id": "00000000-0000-4000-8000-000000000002",
  "raw_text": "전화로 접수한 누수 문의입니다.",
  "representative_symptom_code": "LEAK",
  "priority_code": "HIGH"
}
```

- 고객명, 전화번호, 제품 ID는 등록 Body에 다시 보내지 않습니다.
- 논리 등록 작업마다 Idempotency-Key를 생성합니다.
- 같은 내용의 네트워크·서버 오류 재시도에는 기존 키를 유지합니다.
- 요청 내용이 바뀌거나 409 충돌 후 명시적으로 다시 시도하면 새 키를
  사용합니다.
- 요청 시도마다 `X-Correlation-ID`를 생성합니다.
- 성공 응답의 `inquiry_id`로 CONS-02 상세 경로를 연결합니다.
- 성공 응답의 `allowed_actions`는 Remote DTO에서 그대로 보존하며 Web에서
  다음 상태나 허용 행동을 재계산하지 않습니다. 실제 Backend 응답의
  `START_CONSULTATION` 소비는 공동 Smoke에서 확인합니다.

### 4.3 오류·보안 처리

| 상태 | Web 처리 |
| ---: | --- |
| 401 | 공통 인증 Client에서 1회 Refresh 후 실패 시 세션 제거 |
| 403 | 상담사 전용 기능 안내 |
| 404 | 무효 구독 선택만 초기화하고 문의 입력 내용은 유지 |
| 409 | 새 멱등 키를 사용하는 명시적 재시도 안내 |
| 422 | 입력값 유지 및 Backend 검증 메시지 표시 |
| 500·Network·Timeout | Mock 전환 없이 입력 유지, 같은 멱등 키로 재시도 가능 |

다음 임시 성공 경로는 제거했습니다.

- `phoneInquiryLocalRepository`
- `waterbridge.phone-inquiry-records.v1` 신규 저장
- 가짜 `PHONE-*` 문의 ID 생성
- Remote 실패 후 LocalStorage 또는 Mock 성공 처리

전화번호 원문과 문의 원문은 Web LocalStorage, Analytics, 오류 로그에
저장하지 않습니다.

## 5. 변경 파일

| 파일 | 변경 내용 |
| --- | --- |
| `docs/planning/md/20260811_한예나_화면설계서.md` | 수정된 CONS-04 계약으로 기존 정본 교체 |
| `web/src/features/consultation/repositories/phoneInquiryRemoteRepository.ts` | 검색·등록 Remote Adapter와 DTO 추가 |
| `web/src/features/consultation/repositories/phoneInquiryLocalRepository.ts` | 임시 LocalStorage Repository 제거 |
| `web/src/pages/consultant/PhoneInquiryCreatePage.tsx` | 검색·선택·등록·오류·멱등성 UI 연동 |
| `web/src/pages/consultant/PhoneInquiryCreatePage.css` | 후보 패널·선택 요약·등록 상태 스타일 반영 |
| `web/tests/integration/PhoneInquiryCreatePage.test.tsx` | 검색·등록 계약과 404·보안 경계 검증 |
| `web/tests/integration/AppRouterGuards.test.tsx` | 변경된 등록 버튼 명칭 반영 |

## 6. Web 검증 결과

검증 환경:

- Node: `v26.4.0`
- npm: `11.17.0`

| Gate | 결과 |
| --- | --- |
| CONS-04 표적 통합 Test | PASS — 1 file, 3 tests |
| Web 전체 Test | PASS — 33 files, 144 tests |
| ESLint | PASS |
| TypeScript | PASS |
| Production Build | PASS — 142 modules transformed |
| `git diff --check` | PASS |
| 화면설계서 수정본 본문 비교 | PASS |

요청서의 자동 검증 항목 중 현재 CONS-04 전용 테스트 범위는 일부입니다.

| 요청된 자동 검증 | 현재 상태 |
| --- | --- |
| Adapter 요청 Path·Body·Header | PASS |
| 고객·구독 선택과 등록 성공 | PASS |
| 등록 404와 입력 유지 | PASS |
| 검색 Debounce·최신 응답 우선 | 구현 완료 / 전용 자동 Test 미작성 |
| 빈 검색 결과 | 구현 완료 / 전용 자동 Test 미작성 |
| 등록 409 | 구현 완료 / 전용 자동 Test 미작성 |
| 등록 422 | 구현 완료 / 전용 자동 Test 미작성 |
| 등록 중 중복 클릭 | 구현 완료 / 전용 자동 Test 미작성 |
| 같은 요청의 멱등 키 재시도 | 공통 Unit Test PASS / CONS-04 전용 Test 미작성 |

표적 테스트에서 확인한 내용:

1. 검색 요청이 POST JSON Body로 전송되는지 확인
2. 검색·등록 요청에 Correlation ID가 포함되는지 확인
3. 등록 요청에 Idempotency-Key가 포함되는지 확인
4. 등록 Body에 계약의 네 필드만 포함되는지 확인
5. 마스킹 연락처만 화면에 표시되는지 확인
6. 성공한 `inquiry_id`가 CONS-02 상세 경로에 연결되는지 확인
7. 등록 404에서 고객 선택만 초기화되고 문의 원문은 유지되는지 확인
8. 전화 문의 원문이 기존 LocalStorage Key에 저장되지 않는지 확인

## 7. 실제 공동 Socket Smoke 요청

Web 코드 연동은 완료됐지만 실제 공용 PostgreSQL·Backend Process를 사용한
Socket Smoke는 아직 실행하지 않았습니다. 요청서에는
`backend_runtime_sha`와 `migration_0013=APPLIED`가 고정되어 있으나
`backend_url`이 placeholder이고 로그인·검색 Seed·로그 확인 방법이 없어
현재 공동 Smoke 상태는 `BLOCKED`입니다. 아래 조건이 준비되면 공동 확인이
가능합니다.

1. Migration `inquiries.0013_inquiry_priority_code` 적용
2. 검증할 Backend 실행 SHA와 접근 가능한 Base URL
3. 로그인 가능한 합성 CONSULTANT 계정 또는 Demo Login Code
4. 이름 또는 연락처 일부로 검색 가능한 합성 고객·ACTIVE 구독
5. Backend Log에서 Correlation ID를 확인하는 방법
6. Web 실행 시 `VITE_USE_MOCK_API=false`

공동 Smoke 범위:

| 시나리오 | 기대 결과 |
| --- | --- |
| 고객명 검색 | 200, 활성 구독 후보 표시 |
| 연락처 일부 검색 | 200, 마스킹 연락처 후보 표시 |
| 결과 없음 | 200, 빈 결과 안내 |
| 복수 활성 구독 | 제품별 후보 선택 가능 |
| 전화 문의 등록 | 201, `CONSULTATION_REQUIRED` |
| 동일 키·동일 요청 | 201, 기존 결과 Replay |
| 동일 키·다른 요청 | 409, 새 키 재시도 안내 |
| 무효·비활성 구독 | 404, 선택 초기화 |
| 잘못된 입력 | 422, 입력 유지 |
| Web↔Backend 추적 | 요청·응답·Backend Log Correlation ID 일치 |

## 8. 현재 Git 상태 주의

Backend 게시 SHA
`a4309d4c8d3b2cdb91e026a7d70fba2d9962c1c2`는 현재 Web 기준 HEAD에 포함된
것을 확인했습니다.

이 문서 작성 시점의 Web 변경은 아직 Commit되지 않았습니다. 따라서
`ba384fb61c4138ca2440caa6c0540a2031a9af55`는 작업 시작 기준 HEAD이며,
이번 CONS-04 Web 변경을 포함한 게시 SHA가 아닙니다.

Commit·Push 후에는 게시된 Web SHA를 별도로 전달하겠습니다.

## 9. 상태 회신

아래 블록은 요청서의 필드 순서와 허용값 형식을 그대로 사용합니다.
`web_head`는 현재 Git HEAD이지만 이번 변경은 아직 Commit 전이므로 해당
SHA에 CONS-04 Web 변경이 포함됐다는 뜻은 아닙니다. Adapter PASS 범위는
Path·Body·Header·등록 성공·404를 확인한 3개 통합 테스트이며, CONS-04
전용 Debounce·빈 결과·409·422·중복 클릭·재시도 테스트는 미실행입니다.

```text
sender=한예나
scope=WEB_CONS04_PHONE_INQUIRY_REMOTE
backend_runtime_sha=a4309d4c8d3b2cdb91e026a7d70fba2d9962c1c2
web_branch=yena
web_head=ba384fb61c4138ca2440caa6c0540a2031a9af55
adapter_test=PASS
web_full_test=PASS
lint=PASS
typecheck=PASS
build=PASS
search_200=NOT_RUN
register_201=NOT_RUN
replay_201=NOT_RUN
conflict_409=NOT_RUN
role_403=NOT_RUN
hidden_404=NOT_RUN
validation_422=NOT_RUN
mock_fallback=DISABLED
correlation_match=NOT_RUN
shared_smoke=BLOCKED
blocker=backend_url, consultant_login, searchable synthetic ACTIVE subscription seed, correlation log check method not supplied; Web changes not committed
```

## 10. Backend 회신 요청 형식

```text
backend_base_url=<접근 가능한 실행 주소>
backend_runtime_commit_sha=<실행 SHA>
migration_0013=<APPLIED | NOT_APPLIED>
consultant_login=<합성 상담사 로그인 방법>
search_query=<합성 고객명 또는 연락처 일부>
expected_subscription_id=<선택 가능한 공개 구독 UUID>
correlation_log_check=<Backend 로그 확인 방법>
postgresql_verification=<PASS | NOT_TESTED>
shared_smoke_candidate_time=<가능 시간>
notes=<추가 안내>
```
