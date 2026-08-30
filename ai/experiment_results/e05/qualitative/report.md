# E05-Q — Single RAG vs Multi-Agent 실제 응답 비교

- Git SHA: `95f90f843124373fc97c6cd9e258b1427e0cbde8`
- Provider: `gpt-4.1-mini-2025-04-14`
- Original E05 SHA 일치: `False`

> E05 정량 실험을 대체하지 않는 발표용 Qualitative Evidence입니다.

## NORMAL_EVIDENCE

**목적:** 정상 경로 고객-facing 결과 비교

**고객 입력:** “어제부터 냉수 버튼을 누르면 물이 졸졸 나옵니다. 전원을 껐다 켰어요.”

### Single RAG

- status: `SUCCEEDED`
- guidance: `PARTIAL_STOP`
- retrieval: `AVAILABLE`
- awaiting_customer_input: `False`

**고객에게 보이는 안내**

> 냉수 출수량이 적을 때는 원수 공급 상태와 필터 장착 상태를 확인하고, 필요한 기본 점검 후에도 증상이 지속되면 전문 상담 및 점검을 요청합니다.

**다음 행동**
- 안내된 자가조치 단계별 점검 수행
- 증상 미개선 시 상담 연결

### Multi-Agent

- status: `SUCCEEDED`
- guidance: `PARTIAL_STOP`
- retrieval: `AVAILABLE`
- awaiting_customer_input: `False`

**고객에게 보이는 안내**

> 냉수 출수량이 적을 때는 원수 공급 상태와 필터 장착 상태를 확인하고, 필요한 기본 점검 후에도 증상이 지속되면 전문 상담 및 점검을 요청합니다.

**다음 행동**
- 안내된 자가조치 단계별 점검 수행
- 증상 미개선 시 상담 연결

**Multi-Agent Handoff**
- `SUPERVISOR` → `SYMPTOM_ANALYSIS` : `START_ANALYSIS`
- `SYMPTOM_ANALYSIS` → `EVIDENCE_ANALYSIS` : `RETRIEVAL_REQUIRED`
- `EVIDENCE_ANALYSIS` → `CARE_DECISION` : `EVIDENCE_READY`
- `CARE_DECISION` → `SUPERVISOR` : `CARE_DECISION_READY`

---

## EVIDENCE_GAP_FEEDBACK

**목적:** 검색 실패 후 추가 문진 복구를 실제 문구로 확인

**고객 입력:** “정수기 상태가 이상합니다.”

### Single RAG

- status: `FALLBACK`
- guidance: `PENDING_CONSULTATION`
- retrieval: `NO_MATCH`
- awaiting_customer_input: `False`

**고객에게 보이는 안내**

> 확인 가능한 공식 매뉴얼 근거가 부족하여 자가조치 안내가 제공되지 않습니다. 상담 연결을 도와드리겠습니다.

**다음 행동**
- 전문 상담사 연결을 요청해 주세요.

**추가 질문**
- 증상은 언제부터 시작됐나요?
- 증상은 언제 또는 어떤 조건에서 발생하나요?
- 이미 확인하거나 조치해 본 내용이 있나요?

### Multi-Agent

- status: `SUCCEEDED`
- guidance: `PENDING_CONSULTATION`
- retrieval: `NO_MATCH`
- awaiting_customer_input: `True`

**고객에게 보이는 안내**

> 안전한 안내를 위해 추가 정보가 필요합니다. 표시된 질문에 답변해 주세요.

**다음 행동**
- 추가 질문에 답변해 주세요.

**추가 질문**
- 증상은 언제부터 시작됐나요?
- 증상은 언제 또는 어떤 조건에서 발생하나요?
- 이미 확인하거나 조치해 본 내용이 있나요?

**Multi-Agent Handoff**
- `SUPERVISOR` → `SYMPTOM_ANALYSIS` : `START_ANALYSIS`
- `SYMPTOM_ANALYSIS` → `EVIDENCE_ANALYSIS` : `RETRIEVAL_REQUIRED`
- `EVIDENCE_ANALYSIS` → `SYMPTOM_ANALYSIS` : `MORE_INFORMATION_REQUIRED`
- `SYMPTOM_ANALYSIS` → `CARE_DECISION` : `CUSTOMER_INPUT_PENDING`
- `CARE_DECISION` → `SUPERVISOR` : `CARE_DECISION_READY`

---

## DANGER_LEAK

**목적:** Danger에서 기존 Safety Contract 비열화 여부

**고객 입력:** “정수기 밑 바닥에 물이 새서 누수가 심합니다.”

### Single RAG

- status: `SUCCEEDED`
- guidance: `TOTAL_STOP`
- retrieval: `NOT_RUN`
- awaiting_customer_input: `False`

**고객에게 보이는 안내**

> 위험 신호가 감지되어 정수기 사용 제한 및 안전 조치가 필요합니다.

**다음 행동**
- 즉시 원수 공급 밸브(원수 밸브)를 잠그세요.
- 젖은 손으로 전원 플러그를 만지지 마시고, 안전할 때 전원을 차단해 주세요.
- 전문 기사 방문 점검을 요청하세요.

### Multi-Agent

- status: `SUCCEEDED`
- guidance: `TOTAL_STOP`
- retrieval: `NOT_RUN`
- awaiting_customer_input: `False`

**고객에게 보이는 안내**

> 위험 신호가 감지되어 정수기 사용 제한 및 안전 조치가 필요합니다.

**다음 행동**
- 즉시 원수 공급 밸브(원수 밸브)를 잠그세요.
- 젖은 손으로 전원 플러그를 만지지 마시고, 안전할 때 전원을 차단해 주세요.
- 전문 기사 방문 점검을 요청하세요.

**Multi-Agent Handoff**
- `SUPERVISOR` → `SYMPTOM_ANALYSIS` : `START_ANALYSIS`
- `SYMPTOM_ANALYSIS` → `CARE_DECISION` : `DANGER_PRIORITY`
- `CARE_DECISION` → `SUPERVISOR` : `CARE_DECISION_READY`

---
