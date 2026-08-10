# Django REST API 상담사 문의 조회 Runtime 구현·검증 가이드

- 작성일: 2026-08-10
- 담당: 최지용 — Backend·DB
- 상태: `SHARED_COMMIT_AVAILABLE / WEB_INTEGRATION_PENDING`
- 구현 Commit: `b996cf21311b0cc880514940eebbb392d722dc09` (`jiyong`)
- 대상: Web 상담사 화면의 배정 문의 목록·상세 읽기

## 1. 결론

상담사 전용 문의 목록과 상세 Runtime을 구현했다.

- `GET /api/v1/inquiries`
- `GET /api/v1/inquiries/{id}`

상세 응답은 상담사가 담당하는 문의의 제품·구독·최근 관리 정보를 제공한다.
CUSTOMER 전용 `/api/v1/me/subscriptions`를 상담사 Web에서 재사용하지 않는다.

두 GET 계약은 `CONFIRMED + IMPLEMENTED`로 갱신했다.
Backend 전체 회귀는 `889 passed, 14 skipped`이다.
Web Adapter·Mock·화면 코드는 수정하지 않았으므로 실제 Web 연동 완료는 선언하지 않는다.

## 2. 요청 배경과 채널 분리

Web 담당자는 다음을 확인 요청했다.

> `/api/v1/me/subscriptions`는 CUSTOMER 전용이다. 상담사 문의 상세에서
> 제품·구독 정보를 조회할 수 있는 상담사 권한 API가 필요하다.

이번 구현은 기존 확정 계약의 상담사 Projection을 Runtime으로 연결한 것이다.

| 채널 | 사용자 | API 경계 |
|---|---|---|
| Mobile | 이용 고객 | `/api/v1/me/subscriptions*` |
| Web | 상담사 | `/api/v1/inquiries*` |

## 3. 구현 범위

포함:

- 담당 상담사의 배정 문의 목록
- 담당 상담사의 문의 상세
- 제품 모델, 구독 상태, 관리 유형, 최근 완료 관리일
- 합성 고객의 계약상 허용된 최소 Projection
- 동일 404 객체 은닉 정책

제외:

- Web/Mobile 코드 변경
- 상담 시작·요약 저장·확정·완료 Runtime
- 방문 검토·생성·일정·확정 Runtime
- AI·Evidence 내부 로직 변경

## 4. 인증·권한·객체 범위

두 API는 활성 `CONSULTANT` 계정만 호출할 수 있다.

- 미인증: `401 AUTH_REQUIRED`
- 다른 역할: `403 FORBIDDEN`
- 본인에게 배정되지 않은 문의: `404 RESOURCE_NOT_FOUND`
- 미배정 문의: `404 RESOURCE_NOT_FOUND`
- 없는 UUID 또는 잘못된 UUID: `404 RESOURCE_NOT_FOUND`

Repository의 공통 가시성 조건은 다음과 같다.

- `assigned_user == request.user`
- `assigned_role_code == CONSULTANT`
- 삭제되지 않은 합성 고객 Profile
- 합성 고객 User

타 상담사 문의의 존재 여부를 오류 차이로 노출하지 않는다.

## 5. 목록 API

### 5.1 Endpoint

```http
GET /api/v1/inquiries
Authorization: Bearer <consultant_access_token>
```

### 5.2 Query

| Query | 규칙 |
|---|---|
| `q` | 최대 200자 |
| `status` | 반복 가능 |
| `risk_level` | `general`, `caution`, `danger` |
| `priority` | `LOW`, `NORMAL`, `HIGH`, `URGENT` |
| `from`, `to` | Asia/Seoul 기준 포함 날짜 |
| `sort` | `UPDATED_DESC`, `UPDATED_ASC`, `WAITING_DESC`, `RISK_DESC` |
| `page` | 1 이상, 기본 1 |
| `size` | 1~100, 기본 20 |

알 수 없는 Query와 유효하지 않은 값은 `422 VALIDATION_ERROR`로 거부한다.

`q` 검색 대상:

- 문의 코드
- 증상 원문
- 합성 고객 표시명
- 제품 모델 코드·이름

전화번호는 목록 검색 대상에서 제외한다.

### 5.3 결정적 동작

- `WAITING_DESC`: 오래 기다린 문의부터 반환
- `RISK_DESC`: danger → caution → general
- 동률은 접수 시각과 공개 UUID로 고정
- `waiting_seconds`: 현재 시각 - 문의 생성 시각, 최소 0
- `status_counts`: 상태 필터 적용 전, 나머지 검색·위험도·우선순위·날짜 필터 적용 후 집계
- 범위를 벗어난 페이지: 빈 `items`, 실제 `total` 유지

### 5.4 목록 공개 필드

목록은 계약의 14개 필드만 반환한다.

- 문의 공개 UUID·코드·상태·상태 버전
- 위험도·공개 우선순위
- 증상 요약
- 마스킹된 합성 고객명
- 제품 모델 코드
- 담당 유형 `CONSULTANT`
- 접수·수정 시각·대기 초
- 허용 Action

전화번호·주소·계약번호·시리얼·Evidence·내부 PK는 반환하지 않는다.

## 6. 상세 API

### 6.1 Endpoint

```http
GET /api/v1/inquiries/{public_uuid}
Authorization: Bearer <consultant_access_token>
```

### 6.2 제품·구독·관리 매핑

| 응답 필드 | 저장소 원천 |
|---|---|
| `product_model` | `subscription.product_model.model_code` |
| `subscription_status` | `subscription.status_code` |
| `management_type` | `subscription.management_type_code` |
| `recent_care_date` | 완료 CareRecord의 가장 최근 수행일 |

최근 관리일은 `performed_on`을 우선 사용한다.
없으면 `completed_at`을 Asia/Seoul 날짜로 변환한다.

### 6.3 상세 Section

- `inquiry`: 공개 UUID·상태·위험도·우선순위·시각
- `customer`: 합성 여부, 표시명, 합성 전화번호
- `product_and_care`: 제품·구독·관리 정보
- `symptom_and_questionnaire`: 증상과 답변 완료 문항
- `guidance_and_actions`: 사용 안내 상태·최신 안내 문구
- `state_history`: 문의 상태 이력
- `workflow`: 현재 상태·버전·허용 Action

`consultation`과 `visit`은 계약상 nullable이며 이번 읽기 Slice에서는 `null`이다.
두 Section의 쓰기 Runtime이나 다른 담당자의 Projection을 추정 구현하지 않았다.

안내문은 `APPROVED` 또는 `CONFIRMED` 상태만 공개한다.
미검토 `PENDING` 안내와 자유 JSON 답변의 AI 내부 메타데이터는 제외한다.

상세에서도 주소·서비스 주소·이메일·계약번호·시리얼·Evidence·내부 추적값을 제외한다.

## 7. 우선순위 호환 Projection

현재 Inquiry에는 공개 `priority` 컬럼이 없다.
DB·AI 관할을 변경하지 않고 응답 경계에서 보수적으로 정규화한다.

위험도 하한을 먼저 적용한다.

- danger → URGENT
- caution → 최소 HIGH
- general → 저장 우선순위 어휘 매핑

| 저장 값 | 공개 값 |
|---|---|
| `LOW` | `LOW` |
| `NORMAL`, `general_guidance` | `NORMAL` |
| `HIGH`, `consultation_recommended` | `HIGH` |
| `URGENT`, `priority_consultation` | `URGENT` |

평가 행이 없을 때도 기존 위험도에서 응답용 기본값을 계산한다.

- general → NORMAL
- caution → HIGH
- danger → URGENT

이 계산은 저장 데이터를 변경하지 않는다.

## 8. 구현 구조

| 계층 | 책임 |
|---|---|
| Permission | 활성 CONSULTANT 확인 |
| View | HTTP Method별 권한, Query 검증, 응답 Envelope |
| Serializer | 확정 Query·DTO allowlist |
| Repository | 배정·합성 범위, 필터, 정렬, Prefetch |
| Service | 개인정보 안전 Projection과 nullable Section 조립 |

기존 `/api/v1/inquiries` POST는 같은 View에 유지했다.

- GET: CONSULTANT 전용 목록
- POST: 기존 CUSTOMER 전용 문의 생성

HTTP Method별 권한을 분리해 기존 CUSTOMER 생성 동작을 보존했다.

## 9. N+1 및 읽기 전용 검증

- 목록: 노출 3개 행에서도 최대 4 Query로 고정 검증
- 상세: 최대 5 Query로 고정 검증
- 상세 관련 Care·답변·안내·이력은 Prefetch
- GET 전후 Domain·Workflow·Idempotency·안내·관리·답변 행 무변경 검증

## 10. 작업·검증 반복 기록

1. 목록 테스트를 먼저 작성하고 미구현 실패를 확인했다.
2. Permission → Serializer → Repository → Service → View 순으로 목록을 구현했다.
3. 목록 테스트 `3 passed`를 확인했다.
4. 상세 Projection·동일 404 테스트를 추가했다.
5. 최초 상세 테스트에서 실제 공통 오류 코드가 `RESOURCE_NOT_FOUND`임을 확인해 Assertion을 계약 코드로 교정했다.
6. 신규 Runtime 테스트 `7 passed`를 확인했다.
7. OpenAPI·G2 crosswalk·Runtime coverage를 두 GET만 갱신했다.
8. 계약·Runtime·기존 문의 생성 표적 테스트 `36 passed`를 확인했다.
9. 생성·증상 제출·취소 회귀 `49 passed, 2 skipped`를 확인했다.
10. 전체 API `143 passed, 2 skipped`를 확인했다.
11. Django check, Migration 무변경, Python compile을 확인했다.
12. Backend 전체 `889 passed, 14 skipped`를 확인했다.

## 11. 최종 검증 명령과 결과

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend/tests/api/test_consultant_inquiry_runtime.py
# 7 passed

backend\.venv\Scripts\python.exe -m pytest -q backend/tests/api
# 143 passed, 2 skipped

backend\.venv\Scripts\python.exe backend\manage.py check --settings=config.settings.test
# System check identified no issues

backend\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run --settings=config.settings.test
# No changes detected

backend\.venv\Scripts\python.exe -m pytest -q backend/tests
# 889 passed, 14 skipped in 187.86s
```

14개 skip은 PostgreSQL 구조·pgvector·row-lock·통합 DB 전용 검증이다.
이번 로컬 전체 회귀에서 실패는 없다.

## 12. 계약·Gate 상태

- `listConsultantInquiries`: `CONFIRMED + IMPLEMENTED`
- `getConsultantInquiryDetail`: `CONFIRMED + IMPLEMENTED`
- 상담·방문 쓰기 9개: `NOT_IMPLEMENTED` 유지
- G2 전역 Runtime Gate: 변경하지 않음
- Consumer Integration Gate: 변경하지 않음

전역 Boolean을 열면 미구현 쓰기 API까지 개방된 것으로 오해될 수 있어 변경하지 않았다.
Web에는 두 읽기 Operation의 구현 완료를 개별 전달해야 한다.

## 13. Web 인계 기준

현재 결과는 두 GET의 Backend 인계 후보이다.
전역 Consumer Gate를 유지하므로 Web 실제 Adapter·Mock 제거는 아직 `HOLD`다.
두 GET만 선택적으로 소비하도록 별도 회신한 뒤 다음 기준으로 연동한다.

- 상담사 Access Token 사용
- 본인 배정 합성 문의로 목록·상세 호출
- 목록에서는 마스킹 고객명만 사용
- 상세에서만 계약상 허용된 합성 이름·전화번호 사용
- 제품 정보는 `product_and_care`에서 사용
- 타 배정 문의는 `RESOURCE_NOT_FOUND`로 처리
- `allowed_actions`를 Backend 응답 그대로 소비

Web Mock 제거·화면 연결은 Web 담당 범위이며 이 문서에서 완료로 간주하지 않는다.

## 14. 확인된 후속 제한

- `restricted_functions` 저장 경로가 없어 현재 빈 배열이다.
- `PARTIAL_STOP` 실사용 전 AI·DB 소유자의 저장 계약이 필요하다.
- `consultation`, `visit`은 이번 Slice에서 계약상 허용된 `null`이다.
- Inquiry Code의 Model 50자/OpenAPI 48자 차이는 후속 계약 정렬 대상이다.

## 15. 변경 경계와 Rollback

신규 조회 Runtime, 두 Operation 상태, 관련 테스트와 이 문서만 제거하면 원복할 수 있다.
Model·Migration·Seed·Web·Mobile·다른 담당자 문서는 변경하지 않았다.
