# 이동윤 → 최지용: Backend Context MCP 연결 구현·검증 회신 v0.1

최신 `main`과 동일한 `fdaf6c2efb5af86b7408753caeadd7c44a2a1327`에서
Backend 내부 AI Context API Client와 MCP 조회 Tool, Pipeline 연결을 구현했습니다.
현재 변경은 `dongyoon` 작업 디렉터리에 있으며 아직 Commit하지 않았습니다.

## 구현 결과

- `GET /api/v1/internal/ai/inquiries/{inquiry_id}/context` 전용 Read-only Client를
  구현했습니다. 인증 Token은 Process 환경변수에서만 읽고 Tool 인자·오류 메시지·
  로그에는 포함하지 않습니다.
- MCP Tool `lookup_product_context`, `get_inquiry_context`를 추가했습니다.
- `AI_RETRIEVAL_TRANSPORT=mcp`에서 두 Context Tool을 먼저 호출하고, Backend가
  반환한 `ProductModel.model_code`를 변경하지 않은 채
  `search_official_evidence`의 정확 판매코드 필터로 전달합니다.
- Context의 Inquiry ID, Correlation ID, `state_version`, 제품코드와 제품군이
  요청·Registry와 일치하지 않으면 검색과 Provider 전에 차단합니다.
- MCP 검색 결과에는 실제 Evidence의 제품코드·세대·사용 허용·Runtime 적격
  정보를 보존하도록 보완했습니다. 따라서 다른 제품 Evidence를 요청 제품으로
  덮어쓰지 않고 외부 Product Guard가 차단할 수 있습니다.
- Backend Context Timeout·조회 실패, 검색 무결과, 교차 제품 Evidence와 MCP
  검색 실패는 모두 안전 Fallback/Handoff로 종료됩니다. Context 실패 시에도
  공개 응답 필수 필드와 명시적 안전 규칙은 유지하되 pgvector 검색과 OpenAI
  Provider는 호출하지 않습니다.

## Tool 목록

- `health_check`
- `lookup_product_context`
- `get_inquiry_context`
- `search_official_evidence`

## 실행 결과

```ini
base_main_sha=fdaf6c2efb5af86b7408753caeadd7c44a2a1327
branch=dongyoon
ai_commit_sha=NOT_COMMITTED
python=3.13.13

backend_context_contract_test=7 passed
mcp_context_pipeline_targeted_test=23 passed
actual_mcp_stdio_server_and_pipeline_smoke=PASS
pip_check=PASS

backend_context_timeout_fail_closed=PASS
backend_context_failure_fail_closed=PASS
no_evidence_fail_closed=PASS
cross_model_evidence_fail_closed=PASS
context_failure_search_call=0
context_failure_provider_call=0

author_test_correlation_id=018f2f9b-7c30-7981-b541-1a987c88b402
author_test_correlation_scope=SYNTHETIC_LOCAL_STDIO_TEST

ai_unit_regression=380 passed / 1 failed / 4 warnings / 7 subtests passed
remaining_failed_test=F02
remaining_failed_reason=Retry 정책은 deterministic NO_MATCH를 1회 재시도하지만 기존 Fixture 기대값은 retry_count=0
```

## 현재 범위와 남은 조건

위 결과는 실제 MCP stdio subprocess와 로컬 합성 Backend Context HTTP Server를
사용한 작성자 검증입니다. 실제 QA Inquiry·Readonly pgvector·OpenAI를 묶은 공동
실행 결과는 아닙니다.

현재 Checkout에는 공식 통합 검증에서 선택할
`ai/configs/index_manifest_3model.json`이 없고, 이번 공동 실행에 사용할 신규
`inquiry_id`·실행 SHA와 보호된 Context API Token도 현재 Process에 주입되지
않았습니다. 따라서 IAC425·IAC606의 실제 Provider 공동 E2E와 실제 Correlation
대조는 `NOT_RUN`이며 신규 모델 Public Runtime 완료도 계속 `HOLD`입니다.

F02는 이번 변경으로 발생한 실패가 아니라 Retry SSOT와 기존 Fixture 기대값의
정책 불일치입니다. PM 결정 없이 Runtime 또는 Fixture 값을 변경하지 않았습니다.
신규 QA Inquiry·실행 SHA와 보호 환경 주입이 준비되면 같은 Commit에서 실제
Context → MCP 검색 → Provider → Backend 저장·Replay 검증을 이어갈 수 있습니다.
