# AI/Harness 상담 원인 ledger 연동 명세 — 기존 HumanReview 정책 유지

상태: 기존 HumanReview 정책·Backend 원장은 IMPLEMENTED. 추가 AI/Harness 원인 연동만 PROPOSED / IMPLEMENTATION_HOLD.
기준 main: 2305189a1fd62f6fe40bd55c6d2c1fc310a6a783
Backend 정책 기준: 95ed453c0484d2fb2c2212116c67ad830e3028ee
현재 작업 위치: 기존 dongyoon checkout. main 변경 및 선별 AI 수정은 미커밋 상태이며, 추가 원인 ledger 구현 승인을 뜻하지 않습니다.
PM: 윤승혁, 공동 검수: 최지용(Backend), 이동윤(AI), 독립 QA: 김은진

## 2026-09-01 승인 및 구현 상태

- PM이 원인 증빙·내부 Envelope·Backend 원자 저장 권고안 3개를 모두 A로
  선택했고, Backend 담당 최지용이 `1-A`와 `3-A`를 승인했다.
- 내부 `AnalysisConsultationEnvelope`와 `ConsultationCauseLedger` 계약·Pydantic
  모델 버전 `1.0.0`을 구현했다. 공개 `SymptomAnalysisResponse 4.0.0`은 변경하지
  않았다.
- 동일 식별자·분석 결과 Hash·Ledger Hash, 원인 코드별 잠금 분류,
  Safety 잠금 Rule ID, 검증 없는 해소 제안과 평가 전용 `REF-*` 사용 금지를
  계약 검증에 반영했다.
- 같은 Endpoint에서 Envelope를 실제 반환하고 Backend가 분석·원인·초기
  HumanReview를 한 Transaction으로 저장하는 활성화는 양측 변경을 함께 적용해야
  하므로 아직 `HOLD`다. 별도 Ledger Endpoint는 만들지 않는다.
- RDS Write·Migration·Public Runtime 활성은 수행하지 않았고 기존 `HOLD`를
  유지한다.

## 이미 확정된 사항 — 재승인 대상 아님

2026-08-31 정정: 기존 HumanReview 계약과 추가 원인 ledger 연동 명세를 구분한다. 아래 정책·코드·합격 기준을 다시 제안하거나 재승인 요청하지 않는다.

- CAUTION 검토용 안내는 상담 필요 여부와 무관하게 PENDING/PRE_SEND HumanReview 대상이며, 실제 사람의 승인과 유효한 Review 원장 없이 고객 공개하지 않는다. CONFIRMED 문자열이나 환경변수로 이를 우회하지 않는다. Fallback/근거 부재는 기존 REJECTED·Fail-closed 처리를 유지한다.
- HumanReview 원장·승인/수정/거절·상담 필요 변경 절차는 이미 Backend에 구현되어 있다. 아래 원인 ledger 제안은 기존 HumanReview 원장을 새로 만드는 작업이 아니다.
- NOT_REQUIRED, SAFETY_LOCKED, FAIL_CLOSED_LOCKED, NON_SAFETY_RESOLVABLE, UNKNOWN_LOCKED 및 원인 코드의 허용 조합은 기존 Backend 모델이 정의한다. Safety/Fail-closed/Unknown 해제 금지와 검증 Evidence에 의한 Non-safety 해소 조건도 고정이다.
- DANGER 누락 0, 부적절 자동 안내 0, CAUTION 자동 공개 0 및 QA 후 PM 병합 승인, RDS/Public 활성 HOLD는 PM이 이미 지정한 필수 기준이다.

근거: `backend/apps/inquiries/services/guidance_review_policy.py`, `backend/apps/inquiries/models/human_review.py`, `backend/apps/inquiries/services/human_review_service.py`, `contracts/ai/README.md`. 기준 Commit은 위 `95ed453c`다.

## 구현 전 확인할 추가 연동 결정

확인이 필요한 것은 기존 정책을 유지한 채 AI/Harness가 구조화한 원인의 증빙 필드·출처 검증·전달·원자 저장을 연결하는 v1 명세와 추가 검증 방법입니다. 사용자가 전달한 PM 요청의 '원인 ledger 계약과 합격 기준은 구현 전 확인'을 이 추가 범위에만 적용합니다. 승인 전에는 추가 원인 ledger DTO, Harness 원인 생성, Backend 전달/저장 연결을 구현하지 않습니다. 기존 HumanReview 계약 적용과 ledger와 독립적인 자연어·Safety·문진·근거 선택 수정은 계속 진행하며 공개 계약 4.0.0을 유지합니다.

1. v1 원인은 아래 기존 Backend 코드에 맞춰 결정적 AI/Harness 검사에서 생성합니다. 코드·잠금 분류를 다시 정의하지 않으며 LLM 설명 문자열과 사용자 입력을 원인 코드로 해석하지 않습니다.
2. Backend가 검증·저장한 원인 기록만 상담 해제의 권한 근거로 사용합니다. AI는 해제를 제안할 뿐 업무 상태를 변경하지 않습니다.
3. 신규 원인 전달 계약은 분석 응답 4.0.0을 조용히 확장하지 않고 별도의 내부 계약 v1로 설계합니다. 분석 결과와 같은 ai_request_id/state_version에 원자적으로 저장되는 전달 방식을 AI·Backend 공동 확정해야 합니다. 기존 Handoff v2에 미승인 필드를 끼워 넣지 않습니다.
4. ledger 누락·미지원 버전·불명확한 원인·저장 실패는 UNKNOWN_LOCKED를 유지합니다.
5. PM이 지정한 합격 임계값은 그대로 유지합니다. 추가 원인 연동의 검증 절차와 45개 Candidate Oracle의 입력 프로토콜·실행 환경은 PM·Data/QA가 확인합니다.

## PM·Backend가 결정할 최소 범위와 권고안

아래는 구현된 기능이 아니라 승인 요청용 설계안이다. 기존 CAUTION·상담 해소 정책은 변경하지 않는다.

| 결정 | 권고안 | 이유 |
| --- | --- | --- |
| AI/Harness의 원인 증빙 | 기존 Backend 원인 코드를 사용하고, 발생 검사 코드·Rule ID·검증된 Evidence 참조를 함께 생성한다. 자유 문장을 해소 권한으로 사용하지 않는다. | 무엇을 검사해서 해당 원인이 발생했는지 Backend가 검증할 수 있어야 함 |
| 추가 전달 방식 | 별도 버전의 내부 분석 응답 Envelope에 기존 `analysis_result` 4.0.0 본문과 `consultation_cause_ledger` v1을 함께 담는다. 기존 4.0.0 Endpoint·Client는 유지하고 새 계약을 선택한 AI·Backend 경로만 사용한다. 정확한 Endpoint/협상 방식은 Backend 공동 검수에서 확정한다. | 두 개의 독립 비동기 요청으로 보내면 분석 저장과 원인 도착 순서가 달라지고, 이미 잠긴 Review를 사후 변경하는 문제가 생김 |
| Backend 저장·검증 | 동일 inquiry_id/ai_request_id/state_version/model_code를 대조하고, AIRun·원인 기록·Guidance·초기 HumanReview를 한 Transaction에서 저장한다. 원인 검증 실패나 Legacy 응답은 기존 Fail-closed/Unknown 정책을 따른다. | 원장 없는 원인 문자열로 상담 잠금이 낮아지는 것을 방지 |

후속 Handoff v2의 설명 필드나 임의 Header에 원인을 숨겨 넣지 않는다. 과거 UNKNOWN_LOCKED를 새 원인 전달로 자동 해소하는 경로는 제안하지 않는다. 기존 Backend의 판단·저장 주관할은 그대로 유지한다.

PM 회신은 이 세 항목의 승인 또는 구체적 수정 사항으로 한정한다. Backend 공동 검수에서는 새 수신 경로·저장 구현의 담당자와 정확한 계약 위치를 정한다. 이를 정하기 전 새로운 HTTP Endpoint·DTO·원인 생성 코드를 작성하지 않는다.

## 기존 원인 코드·잠금 분류에 맞춘 생성·증빙 연결

| 원인 코드 | 생성 주체/증거 | 잠금 분류 |
| --- | --- | --- |
| DANGER_ASSESSMENT | Safety risk_level=danger + 승인 Rule ID | SAFETY_LOCKED |
| EXPLICIT_SAFETY_RULE | 결정적 Safety matched_safety_rule_ids | SAFETY_LOCKED |
| FAIL_CLOSED_AI_RESULT | Fallback·Schema 실패·실행 실패·검증된 Evidence 부재 | FAIL_CLOSED_LOCKED |
| HARNESS_UNSUPPORTED_FUNCTION | Harness의 제품 기능 불확실 판정과 검증 코드 | NON_SAFETY_RESOLVABLE 후보 |
| HARNESS_SCOPE_EXCEEDED | Harness의 비안전 범위 불확실 판정과 검증 코드 | NON_SAFETY_RESOLVABLE 후보 |
| UNCLASSIFIED_AI_SIGNAL | 상담 필요이나 위 원인을 증명하지 못함 | UNKNOWN_LOCKED |

미승인 제품, 검색 구성 실패, Provider/Tool 실패, 필수 입력 확인 불가, 온수·전기 위험을 NON_SAFETY_RESOLVABLE로 분류하지 않습니다. HARNESS_UNSUPPORTED_FUNCTION과 HARNESS_SCOPE_EXCEEDED도 같은 실행에 Safety/Fail-closed 원인이 하나라도 있으면 전체 상담 잠금은 해제할 수 없습니다. CAUTION의 matched Rule도 현 Backend 정책에 따라 SAFETY_LOCKED로 유지합니다.

## 필드 제안

Envelope:
- contract_version, ledger_id, inquiry_id(공개 UUID), ai_request_id, correlation_id, state_version, exact model_code
- producer 및 policy_version, 실행 commit SHA, model/Prompt 식별·Hash
- causes[] 및 canonical JSON의 ledger_sha256

Cause:
- cause_id(동일 요청·생성 주체·코드에서 안정적), cause_code, origin, lock_class
- verification_code, matched_safety_rule_ids[], required_fact_codes[]
- evidence_refs[]: canonical chunk_id, 문서/제품 코드, index_version, chunk_set_sha256, source/content Hash, scenario_id
- status=ACTIVE 또는 RESOLUTION_PROPOSED, supersedes_cause_id(기존 원인을 삭제하지 않는 참조)

여기서 scenario_id는 공식 근거의 하위 조건을 식별하는 Runtime 코드이며, 45개 평가 전용 REF-* 정답 ID를 사용하지 않습니다.

ledger에는 원문, 자유로운 LLM 설명, 고객 이름·연락처·주소, DSN, Token, Source 절대 경로를 넣지 않습니다. 짧은 원문 quote의 Hash도 PII 보호를 보장하지 않으므로 원인 증거는 코드·검증된 공개 ID로 제한합니다.

## 보존·해소 규칙

- SAFETY_LOCKED, FAIL_CLOSED_LOCKED, UNKNOWN_LOCKED는 v1 자동 해소 대상이 아닙니다.
- NON_SAFETY_RESOLVABLE만 검증된 공식 Evidence의 동일 제품·세대·기능·시나리오 일치를 증명할 때 해소를 제안할 수 있습니다.
- Backend의 상담사 결정, Evidence 재검증, 기존 state_version/멱등성/이전 잠금 확인을 모두 통과해야 해소합니다.
- 새 분석이 더 낮은 위험을 반환해도 이전 잠금 기록을 삭제·치환하지 않습니다.
- CAUTION HumanReview는 상담 원인 해소와 별개입니다. 상담 불필요가 되더라도 승인 전 고객 공개 금지를 유지합니다.
- GENERAL도 근거, 필수 정보, Schema, 제품 승인 및 잠금 조건을 모두 만족해야 자동 안내합니다.
- DANGER의 안전 안내는 기존 결정적 경로를 유지하며 일반 자동 Guidance와 별도로 계측합니다.

## 고정 합격 기준과 추가 연동 검증

| Gate | 합격 조건 |
| --- | --- |
| 데이터 격리 | 45개 JSON·Oracle는 evaluation 전용, Runtime/Prompt/학습/조회 테이블 의존 0 |
| 45개 판단 평가 | 고정 Dataset Hash, final PR SHA, 모델·Prompt·근거·결과 Hash; DANGER 누락 0, 부적절 자동 안내 0, CAUTION 승인 전 공개 0 |
| 평가 Profile | 3제품 판단 평가는 격리 three_model_integration; Public 제품 승인 차단은 별도 회귀. 운영 설정을 변경하지 않음 |
| 미검증 Evidence | TOPIC_GROUP_SELECTION_PENDING/SOURCE_PAGE_ONLY를 근거 검증 PASS로 승격하지 않음; 해결되지 않은 사례는 FAIL/HOLD로 명시 |
| 50 Case | 같은 SHA, 공식 RDS Readonly View 53건(15/19/19), 43 positive/7 negative, 50/50 PASS, cross-model/direct-parent/unverified Hit 모두 0 |
| 원인 ledger | 변조·누락·재전송·stale state_version 거절, Safety/Fail-closed/Unknown 해제 0, 조건 없는 Non-safety 해소 0 |
| 회귀 | AI 전체 Unit 및 영향받는 Backend 계약·HumanReview/공개 정책 회귀 PASS |
| 독립 QA | 구현자 외 Data/QA가 같은 SHA·Hash 증거를 재현하고 검토 승인 |
| 최종 승인 | QA 통과 뒤 PM 병합 승인. RDS 쓰기·Migration·제품 활성·Public Runtime 활성은 별도 승인 전 HOLD |

## 승인 회신 형식

PM 결정: APPROVED / CHANGES_REQUESTED
확정 정책: CAUTION HumanReview·기존 코드/잠금 분류·PM 지정 0건 임계값 유지, 재승인 대상 아님
추가 승인 범위: ledger v1 증빙 필드·출처 검증·전달/원자 저장 방식 또는 수정 내용
검증 확인: 원인 연동 추가 검증 방법, 45개 입력 프로토콜·실행 모델/Profile, 50 Case 환경
Backend 공동 검수자 및 편집자:
독립 QA 담당자:
RDS/Public Runtime 활성화: HOLD
승인자·일시·근거 링크:

승인 없는 항목은 구현 완료나 최종 PASS로 표시하지 않습니다.
