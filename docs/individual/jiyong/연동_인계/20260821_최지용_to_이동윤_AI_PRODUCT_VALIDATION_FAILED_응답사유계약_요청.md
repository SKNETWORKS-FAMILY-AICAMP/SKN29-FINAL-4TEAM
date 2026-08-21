# AI 제품 미승인 응답 사유 계약 협업 요청

- 작성일: 2026-08-21
- 발신: 최지용(Backend·DB)
- 수신: 이동윤(AI·RAG)
- 기준선: `main@1044ca99b503f26bcb32338a994e25e215dd7b49`
- 상태: `AI_RESPONSE_CONTRACT_REQUIRED`

## 1. 요청 배경

IAC425·IAC606이 아직 Public Runtime 검색 승인 전일 때 AI 내부에서는
`RUNTIME_PRODUCT_NOT_APPROVED`를 판정한다.

현재 이 값은 AI 내부 Harness 정보이며 실제 Backend가 소비하는
`SymptomAnalysisResponse`에는 포함되지 않는다. Backend가 받는
`status=FALLBACK`과 `failure_stage=RETRIEVING|VALIDATING`만으로는
제품 미승인, 근거 없음, Schema 검증 실패를 안전하게 구분할 수 없다.

`failure_stage=RETRIEVING`만 보고 Backend가
`PRODUCT_VALIDATION_FAILED`를 적용하면 일반 No-Evidence까지 제품 미승인으로
잘못 전환할 수 있으므로 현재는 매핑을 구현하지 않는다.

## 2. 요청 사항

Backend가 실제로 소비하는 AI 응답에 기계 판독 가능한 실패 사유를
추가해 달라.

권장 예시는 다음과 같다.

```json
{
  "status": "FALLBACK",
  "fallback_reason_code": "RUNTIME_PRODUCT_NOT_APPROVED",
  "failure_stage": "RETRIEVING"
}
```

필드명은 AI 계약 정본에 맞춰 조정할 수 있지만 다음 조건은 필요하다.

1. 제품 미승인과 No-Evidence를 서로 다른 Enum 값으로 구분한다.
2. `RUNTIME_PRODUCT_NOT_APPROVED`는 실제 Backend 응답에 포함한다.
3. `failure_stage`는 감사 정보이며 Backend 상태 전이 결정값으로 사용하지 않는다.
4. 요청의 `model_code`와 응답 판단 대상 제품을 대조할 수 있어야 한다.
5. 알 수 없는 실패 사유는 기존 Fail-closed 상담 경로를 유지한다.
6. 동일 Idempotency-Key·동일 Payload Replay는 추가 Vector·Provider 호출 0회여야 한다.
7. 내부 Prompt·Chunk 원문·검색 점수·Secret은 응답에 노출하지 않는다.

## 3. Backend 적용 예정 조건

아래 조건이 모두 맞을 때만 기존 State Machine Event를 적용할 예정이다.

```text
AI status = FALLBACK
fallback_reason_code = RUNTIME_PRODUCT_NOT_APPROVED
응답 판단 제품 = Backend Subscription.ProductModel.model_code
현재 Inquiry 상태 = DRAFT 또는 QUESTIONNAIRE_IN_PROGRESS
```

적용 결과는 중간 상태 추가가 아니라 다음 Event 전이다.

```text
QUESTIONNAIRE_IN_PROGRESS
-- PRODUCT_VALIDATION_FAILED / SYSTEM --> CONSULTATION_REQUIRED
```

다른 FALLBACK 사유에는 이 Event를 적용하지 않는다.

## 4. 회신 요청

다음 내용을 비밀값 없이 회신해 달라.

- AI Commit SHA
- 확정 필드명과 Enum 목록
- `RUNTIME_PRODUCT_NOT_APPROVED` 실제 응답 예시
- No-Evidence 응답과의 차이
- IAC425 일반·누수, IAC606 일반·누수 표적 테스트 결과
- Replay 시 Vector·Provider 추가 호출 0회 결과
- Backend 계약 테스트 결과
- Correlation ID 대조 방법

## 5. 중단선

- AI 응답 사유 계약 전에는 Backend 매핑을 추정 구현하지 않는다.
- `failure_stage`만으로 `PRODUCT_VALIDATION_FAILED`를 적용하지 않는다.
- AI 내부 Issue Code를 Backend 코드에 중복 하드코딩하지 않는다.
- 이 요청은 `danger + PARTIAL_STOP` 안전 정책 변경을 포함하지 않는다.
