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
| `CR-001` | 상담사 전화 문의 수동 등록 | `HIGH_VALUE` | 중간  | 대표 E2E PASS 이후 | `PROPOSED` |

---

## 3. CR-001 — 상담사 전화 문의 수동 등록

### 배경

현재 문의 등록은 고객 Mobile App 중심이다.

하지만 앱을 사용하지 않고 고객센터로 바로 전화하는 고객도 있을 수 있으므로, 상담사가 고객의 문의를 대신 등록할 수 있는 경로가 필요할 수 있다.

### 제안

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

추가 Metadata 후보:

```text
intake_channel = PHONE
created_by_role = CONSULTANT
created_by_user_id = <상담사 ID>
```

### 영향 예상

| 영역            | 영향        |
| ------------- | --------- |
| 기획·요구사항       | 수정        |
| State Machine | 확인        |
| API Contract  | 수정 가능성 높음 |
| Database      | 확인        |
| Backend       | 수정        |
| Web           | 수정        |
| Mobile        | 없음 예상     |
| AI            | 기존 흐름 재사용 |
| Test          | 회귀 검증 필요  |

### 현재 판단

* 현재 대표 E2E는 이 기능 없이도 성립함
* 실제 고객센터 업무 현실성은 높아짐
* 기존 Inquiry Workflow 재사용 가능
* 여러 영역 수정과 회귀 검증이 필요함

**분류: `HIGH_VALUE`**

현재 P0를 중단하고 즉시 구현하지 않는다.
대표 E2E PASS 이후 Change Window에서 반영 여부를 다시 결정한다.

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
