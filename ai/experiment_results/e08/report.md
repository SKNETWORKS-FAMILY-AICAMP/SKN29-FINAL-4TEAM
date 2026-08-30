# E08 — A2A Agent Failure Isolation

- Git SHA: `0e2d5ee2a023e5e9c35b3a724ee339b0bebf6d57`
- 결과: **4/4 PASS**
- E08-A/B: 실제 별도 Safety A2A Server Process 사용
- E08-C/D: 통제된 Fault Injection

## 실험 질문

> Safety 역할을 별도 A2A Agent로 분리해도 정상 동작하며, 해당 Agent에 장애 또는 잘못된 응답이 발생했을 때 Main Runtime의 Safety 판단까지 함께 실패하지 않는가?

## 실험 구조

```text
Main Runtime
  ↓
WaterBridgeA2ASafetyClient
  ↓
Agent Card Discovery
  ↓
A2A SDK / JSON-RPC
  ↓
Separate Safety Agent Process
  ↓
SafetyA2AAdapter
  ↓
RiskClassifier

Remote Failure / Invalid Contract
  ↓
Local Safety Fallback
```

## 결과 요약

| Case | 방식 | Remote 상태 | 최종 처리 | 결과 |
|---|---|---|---|---:|
| REMOTE_SUCCESS | 실제 프로세스 | 정상 | Remote Safety 사용 | PASS |
| AGENT_DOWN | 실제 프로세스 종료 | TIMEOUT 또는 UNAVAILABLE | Local Safety fallback | PASS |
| INVALID_IDENTITY | Fault Injection | INVALID_RESPONSE | Remote 폐기 + Local fallback | PASS |
| TIMEOUT | Fault Injection | TIMEOUT | Local Safety fallback | PASS |

## 핵심 해석

Safety 역할을 별도 A2A Agent로 분리한 상태에서 정상 통신을 확인했고, Agent 종료·Timeout·잘못된 Product Context가 발생해도 장애를 Local Safety fallback으로 격리했다.

특히 `AGENT_DOWN`은 Safety Agent를 실제 별도 프로세스로 실행한 뒤 프로세스를 종료하고 동일 Client 경계를 다시 호출하여 확인한다.

## 주장 범위

A2A 자체가 자동으로 장애 복원력을 제공한다는 의미가 아니다. A2A는 Agent 분리/통신 계약이며, 장애 격리는 WaterBridgeA2ASafetyClient의 검증 및 Local fallback 정책으로 구현했다.

따라서 발표에서는 **'A2A 덕분에 장애 복원이 자동으로 됐다'**가 아니라 **'A2A로 역할을 독립 Agent로 분리했고, 그 경계의 장애 전파 위험을 Local fallback으로 격리했다'**고 설명한다.

## 발표용 문장

> Safety Agent를 A2A Protocol 기반 독립 Agent로 분리했습니다. 실제 Agent Card Discovery와 JSON-RPC 통신을 확인했으며, Agent 프로세스를 종료하거나 별도 Timeout·잘못된 Product Context를 발생시켜도 Remote 장애가 Main Runtime으로 전파되지 않고 기존 Local Safety로 전환되는 것을 확인했습니다.

## REMOTE_SUCCESS

```json
{
  "case_id": "REMOTE_SUCCESS",
  "mode": "REAL_A2A_SERVER_PROCESS",
  "remote_server": "http://127.0.0.1:58767",
  "elapsed_ms": 405.96,
  "used_local_fallback": false,
  "failure_kind": null,
  "local_classifier_calls": 0,
  "response": {
    "inquiry_id": "11111111-1111-4111-8111-111111111111",
    "correlation_id": "22222222-2222-4222-8222-222222222222",
    "model_code": "WPUJAC104DWH",
    "product_family": "DIRECT_WATER_PURIFIER",
    "assessment": {
      "risk_level": "caution",
      "priority": "consultation_recommended",
      "requires_consultation": false,
      "matched_safety_rule_ids": [
        "SAFETY-TEMP-ABNORMAL-001"
      ],
      "detected_risks": [
        "냉/온수 미흡 및 출수량 저하"
      ],
      "safety_reason": "[냉/온수 미흡 및 출수량 저하] 키워드('미지근') 감지"
    }
  },
  "direct_local_assessment": {
    "risk_level": "caution",
    "priority": "consultation_recommended",
    "requires_consultation": false,
    "matched_safety_rule_ids": [
      "SAFETY-TEMP-ABNORMAL-001"
    ],
    "detected_risks": [
      "냉/온수 미흡 및 출수량 저하"
    ],
    "safety_reason": "[냉/온수 미흡 및 출수량 저하] 키워드('미지근') 감지"
  },
  "checks": {
    "health_ok": true,
    "agent_card_reachable": true,
    "agent_card_exposes_jsonrpc": true,
    "agent_card_exposes_a2a_endpoint": true,
    "remote_result_used": true,
    "failure_kind_none": true,
    "local_fallback_not_called": true,
    "inquiry_identity_preserved": true,
    "correlation_identity_preserved": true,
    "model_identity_preserved": true,
    "product_family_preserved": true,
    "remote_local_safety_semantics_equal": true
  },
  "pass": true
}
```

## AGENT_DOWN

```json
{
  "case_id": "AGENT_DOWN",
  "mode": "REAL_A2A_SERVER_PROCESS_TERMINATED",
  "remote_server": "http://127.0.0.1:58767",
  "elapsed_ms": 1009.875,
  "exception_propagated": null,
  "used_local_fallback": true,
  "failure_kind": "TIMEOUT",
  "failure_taxonomy_note": "실제 Agent 프로세스 종료는 A2A SDK/Agent Card discovery의 동작과 timeout budget에 따라 TIMEOUT 또는 UNAVAILABLE로 관측될 수 있다. E08-B는 둘 중 하나를 Remote 장애로 인정한다.",
  "local_classifier_calls": 1,
  "response": {
    "inquiry_id": "11111111-1111-4111-8111-111111111111",
    "correlation_id": "22222222-2222-4222-8222-222222222222",
    "model_code": "WPUJAC104DWH",
    "product_family": "DIRECT_WATER_PURIFIER",
    "assessment": {
      "risk_level": "caution",
      "priority": "consultation_recommended",
      "requires_consultation": false,
      "matched_safety_rule_ids": [
        "SAFETY-TEMP-ABNORMAL-001"
      ],
      "detected_risks": [
        "냉/온수 미흡 및 출수량 저하"
      ],
      "safety_reason": "[냉/온수 미흡 및 출수량 저하] 키워드('미지근') 감지"
    }
  },
  "checks": {
    "server_confirmed_down": true,
    "main_runtime_exception_not_propagated": true,
    "result_available": true,
    "local_fallback_used": true,
    "failure_kind_is_remote_failure": true,
    "local_classifier_called_once": true,
    "original_model_preserved": true,
    "safety_result_available": true
  },
  "pass": true
}
```

## INVALID_IDENTITY

```json
{
  "case_id": "INVALID_IDENTITY",
  "mode": "CONTROLLED_FAULT_INJECTION",
  "injected_remote_model": "WPUIAC606SNW",
  "expected_model": "WPUJAC104DWH",
  "used_local_fallback": true,
  "failure_kind": "INVALID_RESPONSE",
  "local_classifier_calls": 1,
  "final_response": {
    "inquiry_id": "11111111-1111-4111-8111-111111111111",
    "correlation_id": "22222222-2222-4222-8222-222222222222",
    "model_code": "WPUJAC104DWH",
    "product_family": "DIRECT_WATER_PURIFIER",
    "assessment": {
      "risk_level": "caution",
      "priority": "consultation_recommended",
      "requires_consultation": false,
      "matched_safety_rule_ids": [
        "SAFETY-TEMP-ABNORMAL-001"
      ],
      "detected_risks": [
        "냉/온수 미흡 및 출수량 저하"
      ],
      "safety_reason": "[냉/온수 미흡 및 출수량 저하] 키워드('미지근') 감지"
    }
  },
  "checks": {
    "remote_response_rejected": true,
    "failure_kind_invalid_response": true,
    "local_classifier_called_once": true,
    "wrong_remote_model_not_released": true,
    "inquiry_identity_preserved": true,
    "safety_result_available": true
  },
  "pass": true
}
```

## TIMEOUT

```json
{
  "case_id": "TIMEOUT",
  "mode": "CONTROLLED_FAULT_INJECTION",
  "configured_timeout_seconds": 0.03,
  "injected_remote_delay_seconds": 0.25,
  "elapsed_ms": 44.74,
  "used_local_fallback": true,
  "failure_kind": "TIMEOUT",
  "local_classifier_calls": 1,
  "final_response": {
    "inquiry_id": "11111111-1111-4111-8111-111111111111",
    "correlation_id": "22222222-2222-4222-8222-222222222222",
    "model_code": "WPUJAC104DWH",
    "product_family": "DIRECT_WATER_PURIFIER",
    "assessment": {
      "risk_level": "caution",
      "priority": "consultation_recommended",
      "requires_consultation": false,
      "matched_safety_rule_ids": [
        "SAFETY-TEMP-ABNORMAL-001"
      ],
      "detected_risks": [
        "냉/온수 미흡 및 출수량 저하"
      ],
      "safety_reason": "[냉/온수 미흡 및 출수량 저하] 키워드('미지근') 감지"
    }
  },
  "checks": {
    "local_fallback_used": true,
    "failure_kind_timeout": true,
    "local_classifier_called_once": true,
    "original_model_preserved": true,
    "safety_result_available": true
  },
  "pass": true
}
```
