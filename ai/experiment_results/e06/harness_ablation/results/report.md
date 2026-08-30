# E06 — Harness OFF/ON Fault Injection Ablation

- Git SHA: `68666b88fcf33273906710f23a8d17f7f1faa07f`
- Result: `DRAFT_DIAGNOSTIC`
- Scope: `HARNESS_BOUNDARY_FAULT_INJECTION_ABLATION`
- Scenario: `12`
- Repeats: `10`

## Primary Metrics

| Metric | Result |
|---|---:|
| valid_non_regression_rate_harness_on | 1.0 |
| defect_interception_rate_harness_off | 0.0 |
| defect_interception_rate_harness_on | 1.0 |
| correct_control_action_rate_harness_on | 1.0 |
| retryable_recovery_rate_harness_on | 1.0 |
| terminal_fail_closed_rate_harness_on | 1.0 |
| human_review_route_rate_harness_on | 1.0 |
| consultation_handoff_creation_rate_harness_on | 1.0 |
| bounded_retry_enforcement_rate | 1.0 |

## Interpretation

- OFF는 전용 Harness 최종 검증/라우팅 계층만 제거한 경계 Ablation이다.
- upstream pipeline validator까지 제거한 실험이 아니다.
- 결함은 Harness 경계의 제어 능력을 보기 위해 의도적으로 주입했다.
- 따라서 OFF 0% interception은 production 자연 오류율을 뜻하지 않는다.
- ON의 핵심은 Wrong Product/Unverified Evidence/Schema Error를 Retry로, Safety/No-Evidence/Timeout/Tool Failure를 Fail-closed/Handoff로, Unsupported Function을 HITL로 구분하는 것이다.
