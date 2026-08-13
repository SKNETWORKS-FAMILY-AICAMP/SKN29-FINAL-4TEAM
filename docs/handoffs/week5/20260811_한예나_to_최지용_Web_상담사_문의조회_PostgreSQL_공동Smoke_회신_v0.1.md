# 한예나 → 최지용: Web 상담사 문의 조회 PostgreSQL 공동 Smoke 회신 v0.1

## 1. 결론

현재 `main` 통합 Backend와 격리 PostgreSQL 16.14 Runtime을 대상으로 Web Mock Off 공동 Smoke를 수행했다.

- 상담사 Demo Login, `/me`, 문의 목록, 고정 문의 상세: PASS
- CUSTOMER 역할 403, 미존재 문의 404, 잘못된 Query 422: PASS
- Backend 단절 시 Mock 자동 성공 없음: PASS (`502` 유지)
- Web 요청·응답·Backend JSON Log의 `X-Correlation-ID`: PASS
- Web Test·Lint·TypeCheck·Build: PASS

판정:

```text
CONSULTANT_INQUIRY_READ_REMOTE_SMOKE=PASS
SHARED_SMOKE=PASS
```

## 2. 실행 기준

| 항목 | 확인값 |
|---|---|
| 실행일시 | 2026-08-11 17:11:37 KST |
| Network | `SAME_PC` |
| Web Branch | `yena` |
| Web·Runtime HEAD | `320bb684190e4803a3ab562efa15dc15d6001507` |
| 통합 `origin/main` | `4fb7b525789a85e1da7a68c4c41dcd771dc49328` |
| Backend 차이 | 현재 Backend 디렉터리는 `origin/main`과 차이 없음 |
| Backend URL | `http://127.0.0.1:8000` |
| Web URL | `http://127.0.0.1:5173` |
| Vite API Base | `/api/v1` |
| Vite Proxy Target | `http://127.0.0.1:8000` |
| Mock | `VITE_USE_MOCK_API=false` |
| PostgreSQL | `16.14`, `public`, Same PC Docker |
| Smoke DB | `watercare_web_smoke_20260811_170327` |
| 고정 문의 UUID | `4f829120-ecbb-5b30-9365-bf02f9044c3b` |

인계서의 Backend 코드·검증 SHA `bed0070a`, `8f41a8a`, `9d4442e`는 모두 현재 `origin/main`과 `yena`의 조상 Commit으로 확인했다.

기존 로컬 `watercare` DB에는 미적용 Migration이 있어 수정하지 않았다. 기존 데이터에 영향을 주지 않도록 별도 Smoke DB를 생성하여 전체 Migration과 Demo Seed를 적용했다.

## 3. PostgreSQL·Backend 준비 결과

| 항목 | 결과 |
|---|---:|
| PostgreSQL Socket 연결 | PASS |
| DB Vendor·Version | PostgreSQL 16.14 |
| 전체 Migration 적용 | PASS |
| `migrate --check` | PASS |
| Django `check` | PASS |
| Demo Account Seed | PASS |
| Demo Product·Subscription·Care Seed | PASS |
| 상담사 고정 문의 Seed | PASS |
| Backend Health | `200` |

Demo Seed는 문서에 명시된 순서대로 적용했다.

1. `seed_common_codes`
2. `seed_demo_accounts`
3. `seed_demo_products`
4. `seed_demo_subscriptions`
5. `seed_demo_care_records`
6. `seed_demo_consultant_inquiry`

## 4. Web 화면 Smoke

| 순서 | 확인 항목 | 결과 | 화면 증거 |
|---:|---|---:|---|
| 1 | API 모드 로그인 화면 | PASS | `DEMO AUTH · API` 표시 |
| 2 | 상담사 Demo Login | PASS | `/consultant/inquiries` 이동 |
| 3 | 상담사 문의 목록 | PASS | 실제 Seed 1건, Mock 30건 미표시 |
| 4 | 고정 문의 상세 | PASS | UUID 상세 Route와 `CONS-02 · REMOTE` 표시 |
| 5 | 고객 정보 마스킹 | PASS | 연락처 `010-****-0000` 표시 |
| 6 | Backend 상태·허용 행동 사용 | PASS | `CONSULTATION_REQUIRED · 1`, `상담 시작` 표시 |

목록에서는 `DEMO-INQ-CONSULTANT-READ-001` 한 건과 합성 고객 표시명이 확인됐다. 상세 화면에서는 제품·구독·증상·위험도·우선순위·현재 가능한 작업이 실제 API 응답 기준으로 표시됐다.

## 5. HTTP 상태·Correlation ID 결과

모든 요청은 Web 개발 서버의 `/api/v1` Proxy를 통해 Backend로 전달했다.

| 요청 | 상태 | Correlation ID | 응답·Log 일치 |
|---|---:|---|---:|
| `POST /auth/demo-login` — CONSULTANT | `200` | `e9ec5ab6-1eab-41f2-bb8f-abda59eb6cae` | PASS |
| `GET /me` | `200` | `0ae41801-7d97-4e22-bc5d-1399ff2bcc22` | PASS |
| `GET /inquiries` | `200` | `fefd7466-0591-4464-a77b-e5652a8dc035` | PASS |
| `GET /inquiries/{inquiry_id}` | `200` | `fa69144d-9fc2-4f8d-aa6b-75db6d7cc952` | PASS |
| CUSTOMER Token → `GET /inquiries` | `403` | `567d3c3e-4eb8-4141-8311-2384dedffd35` | PASS |
| 미존재 `GET /inquiries/{inquiry_id}` | `404` | `9c0c15de-3cc6-44c4-a262-1e89348f05c4` | PASS |
| `GET /inquiries?risk_level=unknown` | `422` | `47a5d9d7-77e2-477a-9bda-3627f8dc58bb` | PASS |

Backend JSON Log에서 각 ID가 정확히 1건씩 확인됐고 Method·Route·Status가 응답과 일치했다. Token·비밀번호·DSN은 기록하지 않았다.

## 6. Mock 자동 Fallback 확인

Backend Process를 중단한 상태에서 Web Proxy로 상담사 Demo Login을 다시 요청했다.

| 항목 | 결과 |
|---|---|
| Backend Listener | `0` |
| Web Proxy 응답 | `502` |
| Mock 로그인 자동 성공 | 발생하지 않음 |
| 판정 | `mock_fallback=DISABLED` |

검증 후 동일한 격리 PostgreSQL Backend를 다시 기동하고 Health `200`을 재확인했다.

## 7. Web Gate 결과

| Gate | 결과 |
|---|---:|
| Unit·Integration Test | `33 files, 142 tests passed` |
| Lint | PASS |
| TypeScript | PASS |
| Build | PASS |

## 8. 비차단 관찰사항

문의 목록 상단은 `/me`의 합성 상담사 표시명을 사용하지만, 문의 상세 워크스페이스 헤더에는 `한유진 · STAFF-CONS-01`이 정적으로 표시된다.

- 문의 목록·상세 Runtime DTO, 권한, 상태, Correlation ID 검증에는 영향이 없어 이번 공동 Smoke의 Blocker로 판정하지 않았다.
- 추후 상세 워크스페이스 공통 헤더도 인증 세션의 상담사 표시명·직원번호를 사용하도록 Web UI 정합화가 필요하다.

## 9. 요청 형식 회신

```text
sender=한예나
receiver=최지용
scope=CONSULTANT_INQUIRY_READ_SHARED_SMOKE
backend_runtime_sha=320bb684190e4803a3ab562efa15dc15d6001507
backend_main_sha=4fb7b525789a85e1da7a68c4c41dcd771dc49328
web_branch=yena
web_head=320bb684190e4803a3ab562efa15dc15d6001507
smoke_at_kst=2026-08-11 17:11:37 KST
network_topology=SAME_PC
backend_url=http://127.0.0.1:8000
vite_backend_proxy_target=http://127.0.0.1:8000
vite_use_mock_api=false
login_200=PASS
me_consultant_200=PASS
list_200=PASS
detail_200=PASS
role_403=PASS
missing_404=PASS
query_422=PASS
mock_fallback=DISABLED
correlation_id=fa69144d-9fc2-4f8d-aa6b-75db6d7cc952
correlation_match=PASS
web_remote_test=PASS
web_full_test=PASS
web_lint=PASS
web_typecheck=PASS
web_build=PASS
shared_smoke=PASS
blocker=NONE
```

## 10. 최종 판정

인계서의 완료 기준을 현재 통합 `main` SHA에서 모두 충족했다.

```text
BACKEND_AUTH_FIX=PASS
WEB_CONSULTANT_READ_ACTUAL_SOCKET=PASS
WEB_FRONTEND_REMOTE_SMOKE=PASS
CONSULTANT_INQUIRY_READ_REMOTE_SMOKE=PASS
```
