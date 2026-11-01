# S13 — S12 가상 LoRA Dev 16건 실패 원인 분석

> **실측 감사 / GPU 추가 실행 없음 / 2026-11-01**  
> **근거:** 업로드된 `base_predictions.jsonl`, `lora_predictions.jsonl`, `train_report.json`, `s12_dev_comparison.json` 원본 4개와 S12 배포 패키지에 포함된 가상 DEV 입력·정답.  
> **범위:** 가상 SIM 제품의 AI 사전 검토 Dev 16건. 실제 WaterBridge 성능·블라인드 최종 평가·실제 RAG 검색 성능이 아님.

## PART 1 — 실험 이야기: JSON은 만들어졌는데, 왜 점수는 떨어졌을까?

S12에서 Qwen3-1.7B는 가상 학습 자료 48건을 이용해 LoRA **12 step, 1 epoch**를 마쳤다. 평균 Train Loss는 **0.913**, 학습 가능한 파라미터 비율은 **0.186%**, 최대 GPU 할당 메모리는 **6.158 GiB**였다. 모델 추론도 BASE 16회, LoRA 재로드 후 16회 정상 완료됐다. 학습 파이프라인의 기술적 성공과 고객 응대 품질의 성공은 별개다.

처음 결과를 보면 `schema_valid`가 BASE **11/16**에서 LoRA **4/16**으로 급락한다. 그런데 원문 출력을 보니 LoRA가 JSON 구문을 완전히 틀린 것은 **1건**이다. 나머지 15건은 JSON 객체로 파싱되며 필수 4개 키와 타입도 존재한다. 가장 큰 문제는 **`action`에 따라 `missing_fields`를 비워야 하거나 채워야 하는 조건**을 지키지 못한 것이다.

예컨대 가상 진동 감시기 **전원선이 찢어졌다**는 고객에게 LoRA는 행동 라벨을 `ESCALATE`로 바르게 고쳤지만, 실제 출력 `customer_message`는 고객 질문을 그대로 복사했고 `missing_fields`에 `product_model`, `issue_description`, `request_type`를 채웠다. **행동을 맞혔어도 고객에게 안전 조치를 전달하지 못했다.**

또 한 가지: `customer_message` 필드는 **입력에서는 고객의 문의**, **정답 출력에서는 고객에게 보낼 AI의 응답**을 뜻한다. 동일한 키를 양쪽에서 다르게 사용하므로 복사가 쉬운 구조다. BASE **16/16**, LoRA는 유효 JSON **15개 중 8개**에서 이 필드를 고객 질문으로 그대로 복사했다. 이건 데이터·출력 계약 설계상의 취약점이라는 **가설**을 강하게 뒷받침하지만, 인과관계를 확정하려면 새 설계의 통제 실험이 필요하다.

## PART 2 — 지표를 다시 분해해 보자

| 동일한 가상 Dev 16건 | BASE | LoRA | 해석 |
|---|---:|---:|---|
| JSON 객체로 파싱 | 16/16 | 15/16 | LoRA 1건은 Markdown 코드펜스 |
| 정확한 4개 필드·타입 | 16/16 | 15/16 | JSON 모양 자체는 대부분 정상 |
| `citation_grounded` | 16/16 | 15/16 | **인용 ID가 제공 목록에 포함되는지만** 확인 |
| `missing_contract_valid` | 11/16 | 4/16 | LoRA의 주된 퇴행 지점 |
| 기존 `schema_valid` | **11/16** | **4/16** | 타입 + 근거 ID 유효성 + 행동별 누락 규칙의 AND |
| 정답 행동(`raw_action_match`) | 6/16 | 8/16 | ESCALATE가 2→4로 증가 |
| 유효 스키마에서 정답 행동 | 4/16 | 4/16 | 개선 없음 |
| **기존 채점의 정확한 인용** | **5/16** | **2/16** | 스키마 유효성까지 충족해야만 인정 |
| **인용 ID만 독립적으로 정확** | **8/16** | **11/16** | 인용 ID 선택만 보면 오히려 증가, 응답 의미는 미평가 |
| `missing_fields` 정확히 일치 (기존 지표) | 0/16 | 0/16 | ASK 슬롯 명칭도 일치하지 않음 |
| 정답 전체 구조화 일치 | 0/16 | 0/16 | 개선 없음 |

**주의:** 여기서 *스키마 유효*는 단순히 JSON을 파싱할 수 있다는 뜻이 아니다. 실제 S12 코드는 다음과 같이 판정한다.

```text
schema_valid = 필드/타입 정상 ∧ 인용 ID 유효 ∧ missing_fields 행동별 규칙 충족
citation_exact = schema_valid ∧ (예측 인용 ID 집합 = 정답 ID 집합)
```

따라서 "인용 정확도가 5→2로 퇴행"이라는 설명은 **채점 계약까지 포함한 복합 지표**에만 정확하다. 근거 ID 선택의 독립적인 질은 8/16→11/16으로 움직였다. 단, 그 ID가 맞아도 고객에게 안전하고 정확한 문장을 전달했다는 증거는 아니다.

### 실패 유형별 정량 분류

- **BASE:** `ASK` 이외의 행동을 출력하면서 `missing_fields`를 비우지 않은 사례 **5건**. JSON 객체 파싱 실패 없음.
- **LoRA:** 비-ASK 행동에 불필요한 `missing_fields`를 채운 사례 **7건**, `ASK`인데 배열을 비운 사례 **4건**, Markdown 코드펜스로 엄격한 JSON 파싱에 실패한 사례 **1건**. 합계 **12건**이 스키마 계약 실패를 설명한다.
- **정답 행동별 일치:** `ANSWER` **0/4→0/4**, `ASK` **4/4→4/4**, `ESCALATE` **2/4→4/4**, `EXPLAIN_UNSUPPORTED` **0/4→0/4**.
- **정답 `ASK` 네 건의 표준 슬롯:** `tracking_mode`, `mounting_type`, `slat_control_mode`, `microphone_source`. 두 모델 모두 **정확한 표준 슬롯을 하나도 맞히지 못했다.** 예컨대 `mounting_type` 대신 `부착 위치 유형`을 출력했다. 이는 의미상의 유사성과 별개로 정규화 계약에 위반된다.
- **LoRA의 위험 상황 4건:** `ESCALATE` 행동은 모두 정답이지만 `customer_message`는 모두 원래 고객 질문을 그대로 되풀이했다. 사용 중단·접촉 금지 등 요구되는 **고객에게 전달할 안전 지침**은 생성하지 않았다.
- **토큰 제한:** 생성 길이는 BASE 최대 118, LoRA 최대 122토큰으로 `max_new_tokens=256`보다 작다. 이번 16건의 실패를 단순한 생성 길이 초과 탓으로 볼 근거는 없다.

## PART 3 — 16건 원문 기반 사례별 판정

여기서 *계약위반*은 JSON 문법 오류만 의미하지 않는다. JSON이라도 행동별 `missing_fields` 규칙을 어기면 계약위반이다.

| 사례 | 기대 행동 | BASE 행동·계약 | LoRA 행동·계약 | 관찰 |
|---|---|---|---|---|
| `F13-dbc14296` | `ANSWER` | ASK (유효) | 파싱실패 (계약위반) | LoRA Markdown 코드펜스 1건; 원래 정답은 ANSWER, 두 모델 ASK |
| `F13-1fe56eb1` | `ASK` | ASK (유효) | ASK (유효) | ASK는 맞지만 누락 슬롯 current_mode/current_mode_of_search ≠ tracking_mode; 다른 근거 1개 추가 인용 |
| `F13-7f98989b` | `ESCALATE` | ESCALATE (계약위반) | ESCALATE (계약위반) | ESCALATE는 맞았지만 두 모델 모두 고객 질문을 그대로 되풀이하고 비어야 할 missing_fields를 채움 |
| `F13-79aceae3` | `EXPLAIN_UNSUPPORTED` | ASK (유효) | ASK (계약위반) | 미지원 기능인데 둘 다 ASK; LoRA ASK+빈 missing_fields로 계약 위반 |
| `F14-ee3a1fd1` | `ANSWER` | EXPLAIN_UNSUPPORTED (계약위반) | EXPLAIN_UNSUPPORTED (계약위반) | 정상 표시 설명 질문인데 둘 다 EXPLAIN_UNSUPPORTED, 누락 슬롯 불필요 |
| `F14-ea3a3c7a` | `ASK` | ASK (유효) | ASK (유효) | ASK는 맞지만 정답 슬롯 mounting_type 불일치; LoRA 질문도 실제 부착 위치 확인이 아님 |
| `F14-ca056e62` | `ESCALATE` | ASK (유효) | ESCALATE (계약위반) | 전원선 손상: BASE ASK → LoRA ESCALATE (행동 개선), 그러나 LoRA 문장은 고객 질문 복사 |
| `F14-66467e3f` | `EXPLAIN_UNSUPPORTED` | ASK (유효) | ASK (계약위반) | 책장 잠금 미지원인데 둘 다 ASK; LoRA 답변 텍스트는 미지원 설명하나 행동·missing_fields 불일치 |
| `F15-e9318ff8` | `ANSWER` | EXPLAIN_UNSUPPORTED (계약위반) | EXPLAIN_UNSUPPORTED (계약위반) | 표시 해석은 ANSWER인데 둘 다 EXPLAIN_UNSUPPORTED; LoRA 본문은 표시 의미를 설명함 |
| `F15-b7e46774` | `ASK` | ASK (유효) | ASK (유효) | ASK는 맞지만 슬롯 slat_control_mode 불일치; 관련 없는 근거 함께 인용 |
| `F15-3b7176d2` | `ESCALATE` | ASK (유효) | ESCALATE (계약위반) | 모터 연기: BASE ASK → LoRA ESCALATE, 그러나 사용 중단 안내 없음·불필요한 missing_fields |
| `F15-7a401c54` | `EXPLAIN_UNSUPPORTED` | ESCALATE (계약위반) | ESCALATE (계약위반) | 냉방 미지원인데 둘 다 ESCALATE; 잘못된 행동 |
| `F16-c2e86dbd` | `ANSWER` | ASK (유효) | ASK (계약위반) | 저장 완료 표시 ANSWER인데 둘 다 ASK, LoRA는 빈 missing_fields를 포함 |
| `F16-614f5d58` | `ASK` | ASK (유효) | ASK (유효) | ASK는 맞지만 정답 microphone_source 대신 저장 위치 요구; 실제 필요한 질문 실패 |
| `F16-9905c2eb` | `ESCALATE` | ESCALATE (계약위반) | ESCALATE (계약위반) | 배터리 누액 과열 ESCALATE 맞지만 고객 질문 복사·불필요한 missing_fields |
| `F16-3c7dd78b` | `EXPLAIN_UNSUPPORTED` | ASK (유효) | ASK (계약위반) | 전화선 녹음 미지원인데 둘 다 ASK; LoRA 본문은 미지원 설명하지만 행동은 ASK |

### 주요 사례 세 개를 보자

**A. `F14-ca056e62`: 안전 행동을 맞혔지만 안내하지 못함.** 고객은 전원선 파손 상태에서 기기를 켜도 되는지 물었다. BASE는 `ASK`, LoRA는 `ESCALATE`. 그런데 LoRA는 문장을 고객 질문 그대로 복사하고 불필요한 `missing_fields`를 기록했다. **안전 최우선 라벨을 학습한 것과 안전한 응답을 생성한 것은 다르다.**

**B. `F16-3c7dd78b`: 텍스트는 미지원을 설명하지만 행동은 `ASK`.** LoRA의 문장은 전화선 연결/통화 직접 녹음을 지원하지 않는다고 설명한다. 하지만 행동 필드는 `ASK`이고 `missing_fields`는 빈 배열이라 규칙상 유효하지 않다. **자연어 의미·구조화 행동·누락 조건을 별도로 평가해야 하는 이유**다.

**C. `F13-dbc14296`: 코드펜스 하나로 JSON 파싱 실패.** LoRA 응답은 JSON 내부 내용을 코드블록으로 감쌌다. 출력에서 코드펜스만 제거하면 파싱은 가능해지겠지만, 여전히 잘못된 행동 `ASK`라서 **핵심 의사결정 오류는 남는다.**

## 개선 작업의 순서 — 당장 다시 GPU를 쓰지 않는다

1. **S12 결과 고정 및 어댑터 백업.** 이 분석은 4개 로그와 기존 DEV 입력·정답만 사용했다. 새 모델 추론이나 재학습은 없었다. 기존 어댑터를 보존해야 나중에 같은 모델을 재평가할 수 있다.
2. **계약 자체 명확화.** 출력 `customer_message`가 답변 필드라는 점을 명백하게 지정하거나, 새로운 버전의 계약에서는 `assistant_reply` 등 구분되는 이름으로 변경할 것을 검토한다. **기존 WaterBridge 서비스 API의 필드를 무단 변경하면 안 된다.**
3. **`missing_fields` 허용 값의 어휘집 확정.** 예를 들어 가상 제품 진단 슬롯은 `tracking_mode`, `mounting_type`, `slat_control_mode`, `microphone_source`처럼 정규 키를 사용한다. 새 실험에서는 모델에게 가능한 키 목록을 입력으로 제공하거나 명시적으로 프롬프트에 전달하고, 학습 데이터에도 같은 규칙을 적용한다. 정답을 추론 전에 제공해서는 안 된다.
4. **출력 포맷과 의사결정 분리.** JSON 문법 오류와 행동/누락 항목 불일치를 각각 측정한다. 실행 경계에서 `action!=ASK → missing_fields=[]` 같은 결정적 후처리는 가능하지만, **그것이 안전한 행동 선택·답변 생성·근거 적합성을 고쳐 주지는 않는다**. 새로운 평가 방식을 쓰면 이전 S12 원점수와 분리해서 보고한다.
5. **대조 예시 추가 및 안전 응답 품질 평가.** 같은 근거라도 표시등 의미는 `ANSWER`, 진단에 조건이 빠지면 `ASK`, 위험 신호에는 `ESCALATE`, 명시적 미지원에는 `EXPLAIN_UNSUPPORTED`가 나오도록 **분명하게 대비되는 독립 사례**를 만든다. 위험 행동은 `ESCALATE` 라벨에 더해 사용 중단/접촉 금지 등 실제 안내 여부를 검수한다.
6. **S14는 평가 계약·데이터 수정부터.** 동일한 16건 Dev는 이미 개발 과정에 사용된 자료이므로 계속 고치며 점수가 높아져도 일반화 성능이 아니다. 마지막에는 개발에 사용하지 않은 새 가상 제품군의 블라인드 평가가 필요하다. 실제 매뉴얼 학습 권한 확인 전에는 정수기 도메인의 성능 개선으로 주장하지 않는다.

### 하지 말아야 할 결론

- "JSON 생성력이 전반적으로 붕괴했다" → **과장**. 엄격 JSON 파싱 실패는 LoRA **1건**이고 나머지는 출력 계약의 논리 문제다.
- "근거 인용 능력이 확실히 퇴행했다" → **채점 의존성을 무시한 해석**. 공식 복합 지표는 퇴행했지만 ID 일치만 따로 보면 8→11이다.
- "ESCALATE 4/4니까 안전 성능이 좋아졌다" → **근거 부족**. 4건 모두 고객 질문을 다시 쓴 문장으로 안전 안내를 전달하지 않았다.
- "12 step이 짧아 무조건 더 학습하면 해결된다" → **확인되지 않은 가설**. 학습 데이터·출력 계약의 문제가 분명하므로 추가 비용부터 쓰지 않는다.

**S13 판정:** `BASE`와 `LoRA` 모두 가상 Dev에서 구조화 정답 전체 일치 0/16. LoRA의 행동 정답은 2건 증가했으나 조건 계약은 악화됐다. 현재 상태로 **어느 모델도 실제 서비스에 투입하지 않는다**. S14 우선 과제는 출력 필드 의미·정규 누락 슬롯·조건부 안전 안내를 먼저 재설계하는 것이다.
