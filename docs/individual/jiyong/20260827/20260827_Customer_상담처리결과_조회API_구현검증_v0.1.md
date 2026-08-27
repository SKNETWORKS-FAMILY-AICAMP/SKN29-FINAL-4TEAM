# Customer 상담 처리 결과 조회 API 구현·검증

- 작성일: 2026-08-27
- 담당: 최지용(Backend·DB)
- 기준 브랜치: `jiyong`
- 목적: 상담사가 확정·저장한 고객 안내를 Mobile 고객 본인에게 안전하게 제공

## 1. 결론

상담 완료 후 Mobile이 문진 화면을 다시 보여주는 Backend 공백을 해소하기 위해
고객 본인용 읽기 전용 API를 추가했다.

```http
GET /api/v1/me/inquiries/{inquiry_id}/consultation-result
Authorization: Bearer {customer_access_token}
```

이 API는 최신 완료 상담의 고객 공개 필드만 반환한다. AI Guidance, 상담사 내부
메모 또는 상담 요약을 대신 반환하지 않는다.

## 2. 안전한 공개 범위

### 공개하는 필드

| 필드 | 필수 | Mobile 사용 방법 |
|---|---:|---|
| `inquiry_id` | O | 현재 문의 일치 확인 |
| `status_code` | O | 현재 문의 상태 분기 |
| `state_version` | O | 후속 쓰기 요청의 최신 버전 |
| `result_code` | O | 처리 결과 로직 분기 |
| `result_display_label` | O | 고객 화면의 처리 결과 제목 |
| `customer_guidance` | O | 상담사가 확정한 고객 안내 본문 |
| `usage_guidance_status` | O | 사용 제한 로직 분기 |
| `usage_guidance_display_label` | O | 고객 화면의 사용 제한 문구 |
| `completed_at` | O | 상담 완료 시각 표시 |
| `allowed_actions` | O | 해결·미해결 등 현재 가능한 버튼 구성 |

### 공개하지 않는 정보

- 상담사 내부 `summary`, `consultation_note`, `additional_check`
- AI 초안·확정 요약
- 상담사 계정·사번·식별자
- 고객 전화번호·주소·계약번호와 문의 원문
- 내부 Evidence, Prompt, Trace, 상담 저장 레코드의 Correlation ID와
  Idempotency Key

Consultation 조회는 고객 공개 결과 필드만 선택하며 응답 Serializer도 위 내부
필드를 허용하지 않는다. 공통 응답 metadata의 요청 추적용 correlation_id는
기존 API 규칙대로 유지한다.

## 3. 결과 코드와 화면 문구

| 원본 코드 | 표시 필드 값 |
|---|---|
| `COMPLETED_NO_VISIT` | `상담 처리 완료` |
| `VISIT_REQUIRED` | `방문 점검 필요` |
| `REOPENED_FOLLOWUP` | `추가 상담 필요` |

| 사용 제한 코드 | 표시 필드 값 |
|---|---|
| `NORMAL` | `정상 사용 가능` |
| `PARTIAL_STOP` | `일부 기능 사용 중단` |
| `TOTAL_STOP` | `제품 사용 중단` |
| `PENDING_CONSULTATION` | `상담 확인 필요` |

Mobile은 원본 코드를 로직 분기에 사용하고, `*_display_label`을 화면에 표시한다.

## 4. 성공 응답 예시

```json
{
  "success": true,
  "data": {
    "inquiry_id": "a40c8360-5de5-44a3-8970-8aaea12cbe79",
    "status_code": "COMPLETION_PENDING",
    "state_version": 9,
    "result_code": "COMPLETED_NO_VISIT",
    "result_display_label": "상담 처리 완료",
    "customer_guidance": "필터를 다시 장착한 뒤 냉수 출수량을 확인해 주세요.",
    "usage_guidance_status": "NORMAL",
    "usage_guidance_display_label": "정상 사용 가능",
    "completed_at": "2026-08-27T13:30:00+09:00",
    "allowed_actions": []
  },
  "error": null,
  "metadata": {
    "correlation_id": "응답 추적용 값"
  }
}
```

정식 전체 예시는
`contracts/api/examples/inquiries/customer-consultation-result-success.json`에 있다.

## 5. 오류 처리

| HTTP | 코드 | 의미와 Mobile 처리 |
|---:|---|---|
| 401 | `AUTH_REQUIRED` | 로그인 화면으로 이동 |
| 403 | `FORBIDDEN` | CUSTOMER 역할이 아님 |
| 404 | `RESOURCE_NOT_FOUND` | 없거나 다른 고객 문의를 같은 응답으로 은닉 |
| 409 | `CONSULTATION_RESULT_NOT_READY` | 완료 결과 준비 중 안내 후 재조회 |
| 422 | `VALIDATION_ERROR` | 요청 형식 확인 |

완료 상담, 고객 안내, 사용 제한 상태 또는 승인된 결과 코드 중 하나라도 없으면
409로 닫는다. 이때 AI Guidance를 상담 결과처럼 대체 표시하지 않는다.

## 6. 읽기 전용·DB 경계

- 조회 과정에서 Inquiry·Consultation·History를 생성하거나 수정하지 않는다.
- 기존 Model, Migration, State Machine, DB Constraint를 변경하지 않았다.
- 여러 완료 상담이 있으면 `completed_at` 기준 최신 1건만 반환한다.
- `allowed_actions`는 기존 Backend Resolver 결과를 그대로 사용한다.
- Web·Mobile·AI·배포 파일은 수정하지 않았다.

## 7. Mobile 연결 순서

1. 고객 문의 Snapshot에서 완료 결과 확인 단계인지 확인한다.
2. 위 API에 동일한 `inquiry_id`를 보낸다.
3. 200이면 `customer_guidance` 중심의 완료 결과 카드를 표시한다.
4. `result_code`, `usage_guidance_status`는 분기에만 사용한다.
5. 화면에는 두 `display_label`을 사용한다.
6. 버튼은 `allowed_actions`에 포함된 항목만 표시한다.
7. 409이면 문진 화면으로 되돌리지 말고 “처리 결과 준비 중” 상태를 표시한다.
8. 해결·미해결 쓰기 요청에는 응답의 최신 `state_version`을 사용한다.

## 8. 검증 범위

- 고객 본인만 200
- 타 고객·없는 UUID·잘못된 UUID는 동일 404
- 미인증 401, 비고객 역할 403
- 내부 메모·요약·상담사·PII·Trace 값 비노출
- 결과 미준비·필수 필드 누락 409
- AI Guidance 대체 금지
- 최신 완료 상담 선택
- 조회 전후 DB 값 무변경
- 결과·사용 제한 한글 표시 계약
- OpenAPI·예시·오류 Registry·Runtime URL 정합성

## 9. 검증 결과

최종 커밋 전 아래 검증을 실행하고 결과를 기록한다.

- 고객 조회·OpenAPI·G2·공통 오류 표적 테스트: `77 passed`
- Contract Validator: `4 passed`
- Python Compile: PASS
- Backend 전체 회귀: `1619 passed, 43 skipped`
  - Skip은 기존 PostgreSQL 전용·외부 Runtime 조건부 항목이다.
- 최신 `origin/jiyong` 동기화 후 표적 재검증: `77 passed + 4 passed`
- `git diff --check`: PASS

## 10. 후속 작업

- 양정현(Mobile): 완료 결과 카드와 해결·미해결 버튼을 이 계약에 연결
- 최지용(Backend·DB): Mobile 연결 후 동일 Inquiry의 응답·DB 무변경 확인
- 김은진(QA): 타 고객 404, 409, 내부 필드 비노출, 최신 결과 선택 독립 검증

이 문서는 Backend 계약·구현 완료 증거이며 Mobile 화면 연결과 실제 기기 E2E의
완료를 뜻하지 않는다.
