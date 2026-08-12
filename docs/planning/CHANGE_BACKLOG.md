# WaterBridge Change Backlog

> 저장 위치: `docs/planning/CHANGE_BACKLOG.md`
> 목적: 구현 중 새로 발견된 요구사항을 바로 개발하지 않고 기록·검토하기 위한 변경 후보 목록

## 1. 운영 원칙

새로운 아이디어나 요구사항은 자유롭게 등록하되, 승인 전에는 기존 Scope·Contract·WBS에 반영하지 않는다.

```text
변경 발견
→ CHANGE_BACKLOG 등록
→ 영향·가치·일정 검토
→ APPROVED / DEFERRED / REJECTED
→ 승인된 항목만 구현
```

### 분류

| 분류            | 기준                   | 처리           |
| ------------- | -------------------- | ------------ |
| `MUST_FIX`    | 없으면 핵심 흐름·안전·계약이 깨짐  | 즉시 검토        |
| `HIGH_VALUE`  | 없어도 MVP는 성립하지만 가치가 큼 | 대표 E2E 이후 검토 |
| `IMPROVEMENT` | 편의·고도화 성격            | 후순위          |

### 상태

`PROPOSED` → `APPROVED` → `IMPLEMENTING` → `IMPLEMENTED`

필요 시 `DEFERRED`, `REJECTED`, `CANCELLED` 사용.

### 변경 판단 기준

1. 이 기능 없이 대표 E2E가 성립하는가?
2. 실제 서비스에서 빠지면 비현실적인가?
3. 기존 State·API·DB·AI 흐름을 재사용할 수 있는가?
4. 수정해야 할 영역은 몇 개인가?
5. 기존 테스트의 회귀 범위는 어느 정도인가?

---

## 2. 변경 요청 목록

| ID       | 제목              | 분류           | 영향도 | 권장 시점          | 상태         |
| -------- | --------------- | ------------ | --- | -------------- | ---------- |
| `CR-001` | 상담사 전화 문의 수동 등록 | `HIGH_VALUE` | 중간  | 2026-08-11 승인 Change Window | `IMPLEMENTING` |

---

## 3. CR-001 — 상담사 전화 문의 수동 등록

### 배경

현재 문의 등록은 고객 Mobile App 중심이다.

하지만 앱을 사용하지 않고 고객센터로 바로 전화하는 고객도 있을 수 있으므로, 상담사가 고객의 문의를 대신 등록할 수 있는 경로가 필요할 수 있다.

### 승인 결정

- 승인일: `2026-08-11`
- 승인 주체: PM
- 결정: `APPROVED → IMPLEMENTING`
- 구현 Owner: 최지용(Backend·DB·Public API), 한예나(Web 소비)
- 원칙: 기존 CUSTOMER `POST /api/v1/inquiries`는 변경하지 않고
  CONSULTANT 전용 Operation 2개로 분리한다.
- Backend 진행 상태: `AUTHOR_VERIFIED` (2026-08-11)
- Web 진행 상태: `REMOTE_ADAPTER_AND_SHARED_SMOKE_PENDING`

### 구현안

전화 문의 전용 Workflow를 새로 만들지 않고, **문의 생성 경로만 추가한 뒤 기존 Workflow에 합류**시킨다.

```text
고객 App ─────┐
              ├→ Inquiry 생성 → 기존 AI·상담·방문 Workflow
상담사 전화 접수 ┘
```

### 최소 범위

상담사가:

1. 기존 고객 조회
2. 구독 제품 선택
3. 고객 증상 입력
4. 문의 생성

이후 흐름은 기존 Inquiry Workflow를 재사용한다.

서버 저장 기준:

```text
channel_code = PHONE
initiated_by = <인증 상담사>
assigned_role_code = CONSULTANT
assigned_user = <인증 상담사>
status_code = CONSULTATION_REQUIRED
state_version = 1
```

### 확정 Public API

| Actor | Method | Path | 목적 |
| --- | --- | --- | --- |
| `CONSULTANT` | `POST` | `/api/v1/consultant/customer-subscriptions/search` | 합성 고객의 활성 구독 후보 검색 |
| `CONSULTANT` | `POST` | `/api/v1/consultant/phone-inquiries` | 선택한 활성 구독에 전화 문의 등록 |

- 검색어는 URL·접근 로그 노출을 줄이기 위해 Query String이 아니라 JSON
  Body로 전달한다.
- 검색 결과는 합성·비삭제 고객의 `ACTIVE` 구독만 반환하며 전화번호는
  마스킹한다.
- 등록 요청은 `subscription_id`만 신뢰하고 고객·제품 관계는 Backend가
  다시 조회한다.
- 기존 고객용 문의 생성 Path·DTO·권한은 유지한다.

### Backend·DB 작업

1. `Inquiry.priority_code`를 기존 `support_inquiry` 테이블에 Forward
   Migration으로 추가한다. 신규 테이블은 만들지 않는다.
2. 상담사 권한, 합성 데이터, 활성 구독, Idempotency·Correlation 경계를
   Route→Serializer→Service→Repository에서 검증한다.
3. `REGISTER_PHONE_INQUIRY`를 `null → CONSULTATION_REQUIRED` 전이로 기록하고
   기존 상담 Workflow에 합류시킨다.
4. 전화 접수 시 AI·RAG 자동 실행은 하지 않는다. 상담사가 기존
   `START_CONSULTATION` 흐름을 이어간다.

### Web 작업

1. CONS-04의 임시 LocalStorage·가짜 `PHONE-*` 성공 경로를 실제 Remote
   Adapter로 교체한다.
2. 검색 Debounce, 결과 없음·오류·선택 상태와 복수 활성 구독 선택을
   구현한다.
3. 고객·구독 후보를 선택하기 전 등록을 차단하고 성공한 `inquiry_id`로
   CONS-02 상세에 이동한다.
4. 전화번호 원문, 문의 원문, Token을 LocalStorage·Analytics·오류 로그에
   저장하지 않는다.

### 영향 예상

| 영역            | 영향        |
| ------------- | --------- |
| 기획·요구사항       | 수정        |
| State Machine | `REGISTER_PHONE_INQUIRY` 초기 전이 추가 |
| API Contract  | 상담사 전용 Operation 2개 추가 |
| Database      | 기존 Inquiry에 `priority_code` 추가, 신규 테이블 없음 |
| Backend       | 검색·등록 수직 Slice 추가 |
| Web           | CONS-04 Remote Adapter·상태 처리 추가 |
| Mobile        | API·화면 변경 없음, 새 문의 조회 호환 회귀만 확인 |
| AI·RAG        | 자동 호출 없음, 기존 분석 정책·Schema 변경 없음 |
| Test          | 계약·권한·멱등·PostgreSQL·전체 회귀 필요 |

### 제외·후속 결정

| 항목 | 이번 Slice 판정 | 이유 |
| --- | --- | --- |
| 수동 문의 제목 컬럼 | 제외 | 기존 원장 필드가 없고 문의 코드·증상·원문으로 표시 가능 |
| 신규 고객 즉시 생성 | 제외 | 기존 구독 고객 검색 범위만 승인 |
| 상담 메모 동시 저장 | 제외 | 기존 `Consultation` 생성 이후의 별도 책임 |
| 콜백 예약·동의 확인 | 후속 | 별도 정책·보존 계약 필요 |
| 실제 개인정보 | 금지 | 개발·테스트·발표는 합성 데이터만 허용 |
| AI·RAG 자동 분석 | 제외 | 전화 접수는 상담 대기열 진입이 목적 |

### 완료 기준

- 두 Operation의 OpenAPI·Route·Serializer·권한·Service·Repository가
  일치한다.
- 타 역할은 403, 비합성·비활성·삭제·미존재 구독은 존재를 숨긴다.
- 같은 Idempotency-Key와 같은 요청은 결과를 재생하고 다른 요청은
  409로 거부한다.
- 상태 이력에 `REGISTER_PHONE_INQUIRY`, 상담사, Correlation ID가 남는다.
- PostgreSQL Migration·표적 API·기존 CUSTOMER 생성·상담 조회 회귀가
  통과한다.
- Web 실제 연동과 공동 Smoke는 Backend 작성자 검증과 별도로 기록한다.

---

## 4. 신규 Change Request 템플릿

```markdown
## CR-XXX — 제목

### 배경
왜 필요한지

### 제안
최소 변경으로 어떻게 해결할지

### 영향
- State Machine:
- API:
- DB:
- Backend:
- Web/Mobile:
- AI:
- Test:

### 분류
MUST_FIX / HIGH_VALUE / IMPROVEMENT

### 권장 시점
현재 P0 / 대표 E2E 이후 / 후속 버전

### 상태
PROPOSED

### 결정 기록
- 결정일:
- 결정: APPROVED / DEFERRED / REJECTED
- 사유:
```

---

> **새 아이디어를 막지 않는다. 다만 승인 전 즉시 구현하지 않는다.**
