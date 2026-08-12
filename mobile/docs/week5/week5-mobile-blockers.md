# Week 5 Mobile Blockers — 2026-08-12

Backend 기준: `origin/main@e146d2349d82c964ca57baa4c77b501f8e84c1ab`

## 즉시 해제된 항목

| 항목 | 판정 | Mobile 조치 |
|---|---|---|
| 고객 구독 목록 | READY | 기존 Remote 유지 |
| 고객 구독 상세 | READY | 기존 Remote 유지 |
| 문의 생성 | READY | 기존 Remote 유지 |
| 증상 제출 | READY | 기존 Remote 유지 |
| 문의 취소 | READY | 기존 Remote 유지 |
| 고객 문의 Snapshot | READY | 실제 Remote 연결 |
| 미답변 Questions | READY | 실제 Remote 연결 |
| Follow-up Answers | READY | 실제 Remote 연결 |
| 공식 Mobile follow-up Fixture | READY | 공동 Smoke에 사용 가능 |

## 현재 Backend 차단

### CUSTOMER Guidance / Evidence

```text
상태=BLOCKED_BY_BACKEND
이유=고객용 공개 Guidance/Evidence Route 미게시
Mobile 처리=GUIDANCE_ROUTE_UNAVAILABLE fail-closed 유지
금지=AI FastAPI/VectorDB/LLM 직접 호출, Fake 성공 자동 대체
```

### CUSTOMER 상담 요청

```text
상태=BLOCKED_BY_BACKEND
이유=현재 Consultation Runtime은 IsConsultant 전용
Mobile 처리=실제 요청 성공으로 표시하지 않음
```

### TECHNICIAN Visit Remote

```text
상태=BLOCKED_BY_BACKEND
이유=현재 Visit review/create/schedule/confirm Runtime은 IsConsultant 전용
추가 차단=기사 배정 목록/상세/시작/완료/조치결과 Route 미게시
Mobile 처리=Remote 기본 경로에서 가짜 성공 금지
```

## 조건부 대표 E2E

고객→AI→상담→방문→기사 전체 대표 E2E는 다음 선행 Runtime 때문에 아직 PASS 선언할 수 없다.

```text
Customer Guidance/Evidence
Customer Consultation Request
Technician Assigned Visit List/Detail
Technician Visit Start/Complete/Result
```

위 Runtime이 열리면 같은 주 안에 즉시 재감사한다.
