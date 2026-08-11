# 최지용 — E2E Action 계약 적용 요청

> 처리 결과: **APPLIED** — 최초 적용 `264dfdf951f9a1853594cf36fab142a6929475d6`, 현행 기준 `main@92b0674cd1a3376a2c058715cd5ef32222125755`
> 기준: `main@ed989926b8a4e5fa2ec08593f18f5f5101e84a11`  
> 범위: `contracts/api/**`, `contracts/codes/**`, 필요한 `backend/tests/**`

## 요청

PM이 결정한 다음 8개 Action을 OpenAPI·Schema·Crosswalk에 적용해 주세요. State Machine은 변경하지 않고 신규 Operation은 Runtime 구현 전까지 `NOT_IMPLEMENTED`로 유지합니다.

| Event | operationId | Method·Path |
|---|---|---|
| `SUBMIT_ANSWERS` | `submitFollowUpAnswers` | `POST /inquiries/{id}/answers` |
| `REQUEST_CONSULTATION` | `requestConsultation` | `POST /inquiries/{id}/request-consultation` |
| `START_VISIT` | `startVisit` | `POST /visits/{visit_id}/start` |
| `VISIT_COMPLETED` | `completeVisit` | `POST /visits/{visit_id}/complete` |
| `SUBMIT_RESOLUTION_FEEDBACK` | `submitResolutionFeedback` | `POST /inquiries/{id}/resolution-feedback` |
| `FINALIZE_INQUIRY` | `finalizeInquiry` | `POST /inquiries/{id}/finalize` |
| `CUSTOMER_REPORTED_UNRESOLVED` | `reportUnresolved` | `POST /inquiries/{id}/report-unresolved` |
| `RESUME_CONSULTATION` | `resumeConsultation` | `POST /inquiries/{id}/resume-consultation` |

정상 E2E 필수는 앞의 6개이며 마지막 2개는 미해결→재상담 보조 흐름입니다.

## 필수 조건

- 모든 쓰기: `state_version`, `Idempotency-Key`, `X-Correlation-ID`, 409 충돌 정책 유지
- 방문 시작·완료: 배정 기사만 허용하고 Inquiry/Visit Version 동시 검사
- 방문 완료: `result_code`, `work_summary`, offset 포함 `completed_at` 필수
- 해결 피드백만으로 `RESOLVED` 처리 금지
- 최종 완료는 최신 해결 피드백 확인 후 마지막 처리 담당자만 허용
- 기존 Backend Model과 Payload가 충돌하면 임의 매핑하지 말고 회신

예상 주요 파일:

```text
contracts/api/openapi.yaml
contracts/api/paths/workflow.yaml
contracts/api/paths/visits.yaml
contracts/api/components/schemas/**
contracts/api/action-operation-crosswalk.yaml
contracts/codes/care-results.yaml
```

적용 후 예상 Crosswalk:

```text
RUNTIME_IMPLEMENTED=2
OPENAPI_CONFIRMED=17
CONTRACT_ONLY=0
DEFERRED=4
OpenAPI Operations=31
```

후속 Runtime 반영으로 현행 값은 `12 / 7 / 0 / 4`, OpenAPI 33 Operations다.

## 검증

```text
python -B scripts/contracts/validate_openapi.py
python -B scripts/contracts/validate_contract_crosswalk.py
python -B scripts/contracts/validate_codes.py
python -B scripts/contracts/validate_examples.py
python -B scripts/contracts/validate_state_machine.py
python -B scripts/contracts/render_state_machine.py --check
```

## 회신

```text
decision=APPLIED | CHANGE_REQUEST | HOLD
applied_commit=<전체 SHA>
changed_files=<경로>
openapi_operations=<정수>
crosswalk=<RUNTIME/OPENAPI/CONTRACT_ONLY/DEFERRED>
validation_result=<명령별 PASS/FAIL>
remaining_blocker=<없으면 NONE>
```

결정 상세가 필요하면 `docs/decisions/week5-e2e-action-decision.md`를 참고해 주세요.
