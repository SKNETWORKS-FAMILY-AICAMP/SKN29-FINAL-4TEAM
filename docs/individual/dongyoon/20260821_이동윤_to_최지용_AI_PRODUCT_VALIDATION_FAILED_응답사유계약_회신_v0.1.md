# AI 제품 미승인 응답 사유 계약 회신

- 작성일: 2026-08-21
- 발신: 이동윤(AI·RAG)
- 수신: 최지용(Backend·DB)
- Branch: `dongyoon`
- AI 구현 Commit: `d11829424cc729fb9e35640df1cd69d7805530e6`
- 계약 버전: `4.0.0`
- 상태: `AI_RESPONSE_CONTRACT_READY_BACKEND_TRANSITION_PENDING`

## 1. 결론

`SymptomAnalysisResponse`에 판정 제품 `model_code`와 기계 판독 가능한
`fallback_reason_code`를 필수 필드로 추가했다. `FALLBACK`은 원인 코드가 반드시
있어야 하고 `SUCCEEDED`는 `fallback_reason_code=null`이어야 한다.

Backend 성공 응답 Mapper도 `NO_EVIDENCE`를 `failure_stage`가 아니라
`fallback_reason_code=NO_EVIDENCE`로만 판정하도록 변경했다. 제품 미승인은 현재
`NO_EVIDENCE`로 합쳐지지 않으며, `PRODUCT_VALIDATION_FAILED` Event 적용은 Backend
담당 후속 작업으로 남아 있다.

strict 응답 Schema에 필수 필드가 추가되는 호환성 파괴 변경이므로 계약 Major
Version을 `3.0.0`에서 `4.0.0`으로 갱신했다.

## 2. 확정 공개 필드와 Enum

```text
model_code: string, required
fallback_reason_code: string|null, required
```

`fallback_reason_code` Enum은 다음과 같다.

```text
RUNTIME_PRODUCT_NOT_APPROVED
NO_EVIDENCE
MCP_TOOL_FAILURE
OUTPUT_SCHEMA_INVALID
UNSPECIFIED_FALLBACK
null  # SUCCEEDED에서만 허용
```

`failure_stage`는 계속 실행 감사 정보다. 제품 미승인 일반 증상은
`RETRIEVING`, 누수 위험 분기는 `VALIDATING`이었지만 두 응답의 판정 사유는 모두
`RUNTIME_PRODUCT_NOT_APPROVED`였다. 따라서 Backend는 Stage만으로 제품 미승인을
판정하지 않는다.

## 3. 제품 미승인 실제 공개 응답 핵심 예시

아래 값은 IAC425 일반 증상의 결정적 Public Runtime 테스트 결과 형식이다.

```json
{
  "inquiry_id": "018f2f9b-7c30-7981-b541-1a987c88b403",
  "correlation_id": "018f2f9b-7c30-7981-b541-1a987c88e403",
  "ai_request_id": "ai-req-runtime-block-WPUIAC425SNW",
  "state_version": 1,
  "model_code": "WPUIAC425SNW",
  "status": "FALLBACK",
  "fallback_reason_code": "RUNTIME_PRODUCT_NOT_APPROVED",
  "failure_stage": "RETRIEVING",
  "retry_count": 0,
  "evidence_references": []
}
```

전체 Schema 예시는
`contracts/ai/examples/symptom-analysis/runtime-product-not-approved.json`에 추가했다.
내부 Prompt, Chunk 원문, 검색 점수, Vector와 Secret은 공개 응답에 포함하지 않았다.

## 4. No-Evidence·MCP·Schema 실패와의 차이

| 조건 | `fallback_reason_code` | 대표 Stage | Backend 현재 후보 |
| --- | --- | --- | --- |
| 제품은 알려졌으나 Public Runtime 미승인 | `RUNTIME_PRODUCT_NOT_APPROVED` | `RETRIEVING` 또는 `VALIDATING` | 없음, Backend 후속 매핑 대기 |
| 정상 검색 후 사용 가능한 근거 0건 | `NO_EVIDENCE` | `RETRIEVING` | `NO_EVIDENCE` |
| MCP Context/Evidence Tool 실패 | `MCP_TOOL_FAILURE` | `VALIDATING` | 미지정 Fail-closed |
| Harness 출력 Schema 실패 | `OUTPUT_SCHEMA_INVALID` | `VALIDATING` | 미지정 Fail-closed |
| 그 밖의 명시되지 않은 Fallback | `UNSPECIFIED_FALLBACK` | 실행 경로에 따름 | 미지정 Fail-closed |

Backend Mapper는 응답 `model_code`가 요청 `model_code`와 정확히 같지 않으면
`AIIdentifierMismatchError`로 거부한다. `RUNTIME_PRODUCT_NOT_APPROVED`를 받더라도
별도 Backend 변경 전에는 `PRODUCT_VALIDATION_FAILED` Event를 적용하지 않는다.

## 5. IAC425·IAC606 및 JAC104 표적 결과

결정적 Unit Runtime 결과는 다음과 같다. 실제 팀 pgvector/OpenAI 호출 결과로
확대하지 않는다.

| 제품·Case | 상태/사유 | Safety/Guidance | Vector | Provider |
| --- | --- | --- | ---: | ---: |
| IAC425 일반 | `FALLBACK/RUNTIME_PRODUCT_NOT_APPROVED` | `caution/PENDING_CONSULTATION` | 0 | 0 |
| IAC425 누수 | `FALLBACK/RUNTIME_PRODUCT_NOT_APPROVED` | `danger/TOTAL_STOP` | 0 | 0 |
| IAC606 일반 | `FALLBACK/RUNTIME_PRODUCT_NOT_APPROVED` | `caution/PENDING_CONSULTATION` | 0 | 0 |
| IAC606 누수 | `FALLBACK/RUNTIME_PRODUCT_NOT_APPROVED` | `danger/TOTAL_STOP` | 0 | 0 |
| JAC104 일반·공식 근거 Stub | `SUCCEEDED/null` | 일반 안내 | 1 | 1 |
| JAC104 누수 | `SUCCEEDED/null` | `danger/TOTAL_STOP` | 0 | 0 |

누수 Case의 Safety 우선 `danger/TOTAL_STOP`은 유지했다. 이번 변경은
`danger + PARTIAL_STOP` 정책 변경을 포함하지 않는다.

## 6. Replay와 Correlation 증거

Backend 동일 `ai_request_id`·동일 Payload Replay 단위 테스트에서:

```text
첫 요청: AI HTTP 1, 결정적 Vector/Provider 경계 계수 1/1
Replay 추가분: AI HTTP 0, Vector 0, Provider 0
AIRun/SymptomAssessment/Guidance: 각 1건 유지
```

Replay가 Backend 저장 결과를 반환하고 AI HTTP 경계를 다시 호출하지 않으므로,
그 뒤의 Vector와 Provider도 추가 호출되지 않음을 계수로 확인했다. 실제 팀
pgvector/OpenAI 공동 HTTP Replay는 `NOT_RUN`이다.

Correlation은 다음 세 값을 대조한다.

```text
요청 X-Correlation-ID Header
= 요청 Body correlation_id
= 응답 Body correlation_id
```

AI API Mock/Local 단위와 IAC 표적 테스트에서 Echo 일치를 확인했다. Backend
Adapter는 Header와 Body를 같은 값으로 전송하고, 응답 식별자 또는 `model_code`
불일치 시 계약 오류로 거부한다.

## 7. 실행 검증

```powershell
git pull --ff-only origin main
# Already up to date. 작업 전 main/dongyoon = 9ba2b3f6...

.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
# 417 passed, 4 warnings, 7 subtests passed

.\backend\.venv\Scripts\python.exe -m pytest backend\tests\unit\ai_integration -q
# 34 passed

.\ai\.venv\Scripts\python.exe -m pip check
.\backend\.venv\Scripts\python.exe -m pip check
# 양쪽 No broken requirements found.

git diff --check
# PASS
```

두 Python 실행기는 모두 `3.13.13`이다. Warning 4건은 기존
`jsonschema.RefResolver` deprecation이며 테스트 실패는 아니다.

## 8. Backend 후속 완료 조건

담당: Backend·DB

1. 계약 `4.0.0`을 기준으로
   `status=FALLBACK`,
   `fallback_reason_code=RUNTIME_PRODUCT_NOT_APPROVED`,
   응답 `model_code=Subscription.ProductModel.model_code`가 모두 맞는 경우에만
   `PRODUCT_VALIDATION_FAILED` 후보를 만든다.
2. 현재 상태·`state_version`·Guard를 다시 확인한 뒤
   `CONSULTATION_REQUIRED` 전이를 적용한다.
3. 다른/알 수 없는 Fallback 사유는 기존 상담 Fail-closed를 유지한다.
4. 실제 Django→FastAPI Local HTTP, 팀 DB 저장·Transition·Replay 공동 Case를
   별도로 실행한다. 현재 이 공동 E2E는 `NOT_RUN`이다.
