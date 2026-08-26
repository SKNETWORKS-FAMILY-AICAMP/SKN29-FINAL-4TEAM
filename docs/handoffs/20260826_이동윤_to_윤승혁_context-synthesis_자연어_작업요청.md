# 윤승혁 작업 요청 — 상담 맥락 합성 Agent 연결

승혁님, 상담사에게 문의가 넘어갈 때 고객이 지금까지 말한 내용, 실제로 해본
조치, 안전 판정, 확인된 근거와 아직 확인되지 않은 내용을 상담사가 바로 읽을 수
있도록 `ConsultationContextSynthesisAgent`를 기존 Harness와 Consultation
Handoff 사이에 연결해 주세요.

구체적으로는 자동 안내가 확정된 `AUTO_GUIDANCE`와 고객 답변을 더 기다리는
`CUSTOMER_INPUT_PENDING`에서는 이 Agent를 호출하지 말아 주세요. 반대로
`DANGER_HANDOFF`, `FAIL_CLOSED_CONSULTATION`, `HARNESS_ESCALATE`처럼 상담사에게
실제로 넘기는 경우와 `PRE_SEND_HUMAN_REVIEW`에서 상담사가 검토해야 하는 경우에는
맥락 합성 결과를 상담사에게 전달되는 데이터에 포함해 주세요.

합성 입력을 만들 때는 현재 Pipeline의 `answer_text`를 문진 답변으로 사용하고,
고객이 실제로 수행한 조치는 `StructuredSymptom.actions_taken`에서 가져와 주세요.
앞으로 하도록 제안한 `UsageGuidance.next_actions`를 고객이 이미 수행한 조치로
기록하면 안 됩니다.

근거는 같은 실행에서 Harness가 승인한 `accepted_evidence_chunk_ids`와 일치하는
Evidence만 넘겨 주세요. `ctx.evidence_references`에 있다는 이유만으로 전부 넘기지
말고, 승인 목록에 없는 근거는 합성 입력과 최종 Handoff에서 제외해 주세요.
`runtime_product_approved`도 모델명으로 다시 추정하지 말고 현재 Harness의
`ProductContext.runtime_approved` 값을 그대로 전달해 주세요.

Danger와 Runtime 미승인 제품에서는 합성용 LLM Provider를 호출하지 말고,
Agent가 만드는 결정론적 브리프를 사용해 즉시 기존 상담 Handoff를 계속 진행해
주세요. 일반 상담 분기에서도 합성 Provider의 Timeout, 거부, 출력 Schema 오류,
출처 검증 실패가 발생했다고 기존 Handoff를 취소하거나 자동 안내로 되돌리면 안
됩니다. 이 경우에도 Fallback 브리프를 붙여 논리적인 Handoff 한 건을 유지해
주세요. Backend 전달 재시도는 기존 bounded retry를 그대로 사용하면 됩니다.

Handoff Input과 Result에는 합성된 구조화 브리프, 합성 성공/Fallback 상태,
Fallback 사유와 `state_version`이 보존되도록 해 주세요. 다만 Backend는 현재 알 수
없는 필드를 거부하므로, 새 필드 이름과 저장 방식은 최지용과 먼저 합의한 뒤
Backend 계약과 동시에 연결해 주세요. 기존 문자열 필드 안에 JSON을 숨겨 넣는
방식은 사용하지 말아 주세요.

최소 테스트로는 다음을 확인해 주세요.

1. `AUTO_GUIDANCE`, `CUSTOMER_INPUT_PENDING`에서는 합성 Agent 호출이 0회인지
   확인해 주세요.
2. Danger와 Runtime 미승인 제품에서는 합성 Provider 호출이 0회인지 확인해
   주세요.
3. Provider 성공, Timeout, 거부, 잘못된 출력 모두에서 기존 Handoff가 없어지지
   않는지 확인해 주세요.
4. Harness가 승인하지 않은 Evidence가 브리프와 Handoff에 들어가지 않는지 확인해
   주세요.
5. `inquiry_id`, `correlation_id`, `ai_request_id`, `state_version`, exact
   `model_code`가 Handoff 결과까지 그대로 유지되는지 확인해 주세요.
6. `answer_text`와 실제 `actions_taken`이 전달되고, Prompt·검색 점수·Vector·내부
   오류·연락처 같은 비공개 정보가 Provider 요청이나 Backend Payload에 포함되지
   않는지 확인해 주세요.

완료 회신에는 수정한 파일, 실행한 테스트 명령과 결과, Backend 계약 반영 여부,
그리고 현재 상태가 `CONNECTED`, `PARTIAL`, `HOLD` 중 무엇인지 적어 주세요. 실제
Backend 저장·Replay까지 실행하지 않았다면 Unit Test가 통과해도 `CONNECTED`로
표시하지 말아 주세요.

상세 계약과 현재 구현 상태는
`docs/handoffs/20260826_이동윤_to_윤승혁_consultation-context-synthesis-runtime-connection.md`
를 참고해 주세요.
