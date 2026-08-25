# Gold v2 코드 계약 확정 회신

> 회신자: 이동윤 — AI·RAG 담당  
> 수신자: 김은진 — Data·QA 담당  
> 작성일: 2026-08-25 KST  
> Branch: `dongyoon`  
> 작업 기준 HEAD: `39e595e4c423da2b6a2e645a4163a9115f694352`  
> 변경 Commit: `PENDING_USER_COMMIT_APPROVAL`  
> 계약 버전: `2.0.0-draft.1`  
> 상태: `IMPLEMENTED_PENDING_COMMIT_AND_DATA_QA_ACK`

## 한 줄 요약

**정답 의미와 검색 조각의 역할을 분리하고 상담·차단·근거 연결을 코드로 검증하게 했으므로, 변경 Commit SHA만 고정되면 Full Corpus v3는 이 기준 그대로 작업하시면 됩니다.**

## 결론

요청하신 여섯 항목의 **규칙과 입출력 계약은 확정**했습니다. 다만 Source 내용과
실데이터까지 이미 승인됐다는 뜻은 아닙니다. 코드 계약 표적 테스트는
`PASS`지만, Gold v2 Dataset과 Full Corpus v3가 아직 없으므로 실데이터
Compatibility·Full B1 v2·공식 Metric은 `NOT_RUN`입니다.

| 번호 | 요청 항목 | 판정 | 지금 고정된 것 | 남은 Gate |
|---:|---|---|---|---|
| 1 | Gold v2 Schema | `IMPLEMENTED` | 필드, Enum, 상호 제약, 버전 | Commit·Case 이전·2인 승인 |
| 2 | Evidence Group–Child | `IMPLEMENTED` | Group 의미 단위와 Child Variant 계보 | Commit·Data Registry·Corpus v3 생성 |
| 3 | Full B1·Playground 공통 채점 | `PARTIAL_PASS` | 공통 진입점과 기존 v1 Parity | v2 실데이터 실행 |
| 4 | 상담 `CONDITIONAL/REQUIRED` | `IMPLEMENTED` | Basis Code·Condition ID 결정 규칙 | Commit·Case별 Source 조건 검수 |
| 5 | P004·P005·COLD·HOT Group ID | `AI_DECIDED_PENDING_DATA_QA_ACK` | 아래 12개 ID | Source Span·Hash·Corpus 연결 |
| 6 | Gold–Corpus 연결 검사 | `IMPLEMENTED` | Fail-closed Validator와 오류 코드 | Commit·Corpus v3 입력으로 실행 |

## 1. Gold v2 Schema

Schema와 Dataset 버전은 기존 v1과 병렬인 `2.0.0-draft.1`로 고정합니다. `draft`는
평가 의미가 미정이라는 뜻이 아니라, Case별 2인 검수가 끝나지 않았다는 뜻입니다.

- Schema: `ai/evaluation/schemas/gold_evaluation_case_v2.schema.json`
- Evidence Group Registry Row Schema:
  `ai/evaluation/schemas/evidence_group_registry_v2.schema.json`
- Case Validator: `ai/scripts/validate_gold_evaluation_v2.py`
- 공통 Scorer 계약: `evidence_group_policy_v2`
- 기존 Gold v1 원본과 Backend↔AI 공개 계약 `4.0.0`: 변경 없음

핵심 필드는 다음과 같습니다.

```json
{
  "schema_version": "2.0.0-draft.1",
  "dataset_version": "2.0.0-draft.1",
  "evaluation_status": "ACTIVE",
  "expected_retrieval_outcome": "EVIDENCE",
  "expected_execution_path": "PGVECTOR_QUERY",
  "required_evidence_group_ids": ["EVD-..."],
  "supporting_evidence_group_ids": [],
  "evidence_match_policy": "ANY",
  "expected_risk_level": "general",
  "expected_usage_guidance_status": "NORMAL",
  "expected_consultation_requirement": "CONDITIONAL",
  "consultation_basis_codes": ["SOURCE_CONDITION_PENDING"],
  "consultation_condition_ids": ["COND-SYMPTOM-PERSISTS-001"]
}
```

`ACTIVE` Case라도 `review_status=TWO_PERSON_APPROVED`와 서로 다른 Reviewer 2명이
없으면 Draft 평가는 가능하지만 공식 Metric에는 사용할 수 없습니다. Schema
검사와 Gold–Corpus 연결 검사는 서로 다른 Gate로 유지합니다.

## 2. Evidence Group과 Child 연결 규칙

Gold의 정답 키는 페이지나 Child가 아니라 **Evidence Group**입니다.

```text
Gold.required/supporting_evidence_group_ids[]
→ Evidence Group Registry.evidence_group_id
→ Evidence Group Registry.child_ids[]
→ Full Corpus v3.source_record_id
```

확정 규칙은 다음과 같습니다.

1. Group은 하나의 의미 predicate이고, Child는 그 의미를 뒷받침하는 Source
   Variant입니다.
2. 같은 Group에 등록된 Child 중 하나가 Top-K에 들어오면 Group 한 건을
   충족합니다.
3. 같은 Group의 Child 여러 개가 검색돼도 정답 수를 중복 가산하지 않습니다.
4. 증상·위험·조치 의미가 다르면 같은 페이지여도 Group을 분리합니다.
5. Parent·Preservation·Source Page는 Group ID가 붙어 있어도 정답 Hit가 아닙니다.
6. 모든 선언 Child는 Corpus v3에 `source_record_id=child_id`로 정확히 한 번
   연결돼야 합니다. 한 Group에서 하나만 연결하고 나머지를 빠뜨리면 실패합니다.
7. 제품, 문서, 페이지, Source Variant, Source Hash, 검색 역할, 검증 상태,
   허용 사용 범위가 모두 일치해야 합니다.

Data 입력의 필수 계약은 다음과 같습니다.

- Group: `schema_version`, `evidence_group_id`, `exact_sales_code`, `document_id`,
  `topic_code`, `page_refs`, `child_ids`, `source_variant_ids`,
  `consultation_conditions`, `mapping_action`, `supersedes_group_id`,
  `activation_gates`
- Child: `child_id`, `evidence_group_id`, `source_variant_id`, 제품·문서·페이지,
  `record_type=child`, `retrieval_role=SEARCH_CANDIDATE`, 승인 범위,
  `verification_status=TEXT_AND_VISUAL_VERIFIED`, `source_file_sha256`,
  `child_text_sha256`
- Corpus: 고유 `chunk_id`, `source_record_id=child_id`, Group 연결, 동일 계보,
  `record_type=CHILD`, `retrieval_role=SEARCH_CANDIDATE`,
  `allowed_use=EXPERIMENT_ONLY`,
  `source_verification_status=TEXT_AND_VISUAL_VERIFIED`, `source_file_sha256`,
  `text_sha256=child_text_sha256`

`consultation_conditions[].source_page_refs`는 Group 전체 페이지에만 속하면 되는
것이 아니라, 같은 Condition이 선택한 `source_child_ids`의 실제 `page_refs`
합집합 안에도 있어야 합니다. Child A를 근거로 적고 Child B의 페이지만 연결하는
교차 계보는 실패합니다.

이 구조를 택한 이유는 청킹을 다시 해도 Gold의 의미 정답은 유지하고, 실제로 어떤
Child가 검색됐는지는 Registry와 Corpus 계보로 추적하기 위해서입니다.

## 3. Full B1·Playground 공통 채점

두 경로 모두 `ai/evaluation/evidence_scoring_v2.py`의
`score_gold_case()`를 단일 진입점으로 사용합니다.

- Gold v2: `score_evidence_case_v2()`로 Group/Child를 채점
- 기존 Gold v1: `score_legacy_gold_case_v1()`로 기존 결과 의미를 보존
- 기존 Full B1 v1: Report 필드 Shape는 유지하고 계산만 공통 진입점에 위임
- Playground: 페이지만 맞추던 로직을 제거하고 v1에서도
  `Evidence ID + document_id + page_refs`를 함께 확인

v2의 판정 규칙은 다음과 같습니다.

- `ANY`: Required Group 중 하나 이상이면 통과
- `ALL`: 서로 다른 Required Group을 모두 만족해야 통과
- Supporting: Coverage 진단만 하며 PASS·Hit@K·MRR에는 영향 없음
- `NONE`: Required·Supporting가 모두 빈 `NO_EVIDENCE`에만 사용
- 같은 Group Child 여러 개: Group 하나로만 계산
- No-Evidence의 Recall·MRR: `0.0`이 아니라 `null`
- Policy Block: 예상 차단 사유가 같고 Vector Query가 0회일 때만 통과
- Corpus 부재: 실제 Query가 1회 이상 실행되고 결과가 비어 있을 때만 통과
- Playground의 Top-K·제품 필터가 기준과 다르면 `NOT_COMPARABLE`이며,
  `passed`, No-Evidence 성공 등 모든 판정 Boolean을 `null`로 노출

현재 v1 `RAGV2-GOLD-0036`의 `ALL` Case에서 근거 하나만 검색되는 Fixture를
Full B1과 Playground 양쪽에 넣어 동일하게 실패하는 Parity 테스트를 통과했습니다.
Gold v2·Corpus v3 실데이터 Parity는 입력 생성 후 실행하므로 현재 `NOT_RUN`입니다.

현재 v1 Full B1과 Playground는 pgvector가 아니라 NumPy Dense Cosine 검색이므로
관측 실행 경로를 `LOCAL_DENSE_QUERY`로 기록합니다. Gold v2의
`PGVECTOR_QUERY`는 향후 v2 Runner가 실제 검색을 실행하고 관측한 경우에만
전달합니다.

## 4. 상담 필요도 결정 규칙

사용 상태와 상담 필요도는 서로 다른 축입니다. `NORMAL`은 현재 사용 가능한
상태이지, 조건부 상담 문구가 금지된다는 뜻이 아닙니다.

| `consultation_basis_codes` | 상담 필요도 | 의미 |
|---|---|---|
| `NONE` 단독 | `NONE` | 상담 조건 없음 |
| `SOURCE_CONDITION_PENDING` 단독 | `CONDITIONAL` | 지속·재발 등 Source 조건이 아직 성립하지 않음 |
| `SOURCE_CONDITION_MET` | `REQUIRED` | Source가 정한 상담 조건이 이미 성립 |
| `DANGER_SAFETY` | `REQUIRED` | 위험 규칙에 따라 즉시 상담 필요 |
| `NO_EVIDENCE` | `REQUIRED` | 공식 근거 부재로 판단 보류 |
| `POLICY_BLOCK` | `REQUIRED` | 제품·기능·Source 정책으로 검색 전 차단 |

`NONE`과 `SOURCE_CONDITION_PENDING`은 각각 단독으로만 쓸 수 있습니다. 즉시 상담
근거는 여러 개를 함께 보존할 수 있으므로 위험 입력이 미승인 제품이기도 하면
`[DANGER_SAFETY, POLICY_BLOCK] + REQUIRED`가 유효합니다.

`SOURCE_CONDITION_PENDING` 또는 `SOURCE_CONDITION_MET`을 쓰는 Case는
`consultation_condition_ids`를 1개 이상 가져야 하며, 그 ID는 해당 Case의
Required 또는 Supporting Evidence Group에 있는 `consultation_conditions`로
역추적돼야 합니다. 자유 서술만으로 “계속되면” 조건을 추가할 수 없습니다.

예시는 다음과 같습니다.

- 정상 상태이며 계속되면 상담: `NORMAL + CONDITIONAL`
- 지속 조건이 이미 충족됨: `NORMAL + REQUIRED`
- 누수·감전·화상 위험: `TOTAL_STOP + REQUIRED`
- 검색 후 근거 없음: `PENDING_CONSULTATION + REQUIRED`

평가 내부의 `CONDITIONAL`은 현재 공개 응답의 Boolean을 새 값으로 바꾸지
않습니다. 조건 미충족 시 공개 `requires_consultation=false`, 조건 충족 Case는
`REQUIRED`로 평가해 `true`에 대응합니다.

## 5. P004·P005·COLD·HOT Evidence Group ID

ID 값은 아래와 같이 고정합니다. 넓은 COLD·HOT Group은 새 Gold v2에서 사용하지
않고 증상 의미별 Group으로 대체합니다.

| 원천 | 확정 Evidence Group ID | 처리 |
|---|---|---|
| P004 | `EVD-WPUJAC104DWH-SPRAY-FIRE-PREVENTION-001` | 신규 |
| P004 | `EVD-WPUJAC104DWH-WATER-INGRESS-PREVENTION-001` | 신규 |
| P005 | `EVD-WPUJAC104DWH-LEAK-001` | 기존 Group 재사용, P005·P007·P038 Variant 보존 |
| P005 | `EVD-WPUJAC104DWH-BURNING-ODOR-RESPONSE-001` | 신규 |
| COLD | `EVD-WPUJAC104DWH-COLD-TEMPERATURE-NORMAL-001` | 넓은 COLD 대체 |
| COLD | `EVD-WPUJAC104DWH-COLD-TEMPERATURE-FAULT-001` | 넓은 COLD 대체 |
| HOT | `EVD-WPUJAC104DWH-HOT-STEAM-001` | 넓은 HOT 대체 |
| HOT | `EVD-WPUJAC104DWH-HOT-INTERRUPTION-001` | 넓은 HOT 대체 |
| HOT | `EVD-WPUJAC104DWH-HOT-LUKEWARM-001` | 넓은 HOT 대체 |
| HOT | `EVD-WPUJAC104DWH-HOT-NO-OUTPUT-001` | 넓은 HOT 대체 |
| HOT | `EVD-WPUJAC104DWH-HOT-MODULE-CHECK-001` | 넓은 HOT 대체 |
| HOT | `EVD-WPUJAC104DWH-HOT-CHECK-PROCESS-001` | 넓은 HOT 대체 |

기계 판독 원본은
`ai/evaluation/contracts/gold_v2_evidence_group_contract.json`입니다. 각
`groups[]` 행은 `evidence_group_registry_v2.schema.json`과 직접 호환되며,
대응 Child·Source Variant ID, 기존 Group 대체 관계, 활성화 Gate도 함께
고정했습니다. 기존 누수 Group의 동등 Variant P005·P007·P038을 누락하지
않습니다.

단, **ID 확정과 Source 승인 완료는 다릅니다.** P004·P005 신규 의미의 Source
Span 시각 검수, Child Hash 재생성, COLD·HOT Child remap, Corpus v3 연결이 모두
끝난 뒤에만 `ACTIVE` Gold가 참조할 수 있습니다.

`0049`는 P005의 `BURNING-ODOR-RESPONSE`를 Required, P004의
`SPRAY-FIRE-PREVENTION`을 Supporting으로 둡니다. 따라서 P004만 검색되는 기존의
과대 통과를 막으면서 원인·예방 설명은 별도 Coverage로 남길 수 있습니다.

## 6. Gold–Corpus 연결 검사

검사기는 `ai/scripts/validate_gold_corpus_compatibility_v2.py`입니다.
먼저 Gold Case 자체를 Schema와 논리 규칙으로 검사합니다.

```powershell
.\ai\.venv\Scripts\python.exe `
  ai\scripts\validate_gold_evaluation_v2.py `
  --dataset <gold-v2-jsonl> `
  --schema ai\evaluation\schemas\gold_evaluation_case_v2.schema.json
```

그다음 같은 Gold와 Registry·Child·Corpus의 연결을 검사합니다.

```powershell
.\ai\.venv\Scripts\python.exe `
  ai\scripts\validate_gold_corpus_compatibility_v2.py `
  --gold <gold-v2-jsonl> `
  --evidence-groups <evidence-group-jsonl> `
  --children <child-registry-jsonl> `
  --corpus <full-corpus-v3-jsonl>
```

`PASS` 조건은 다음과 같습니다.

1. Registry의 모든 행이 Draft 2020-12 Row Schema와 일치함
2. `ACTIVE` Gold의 Required·Supporting Group이 Registry에 존재하고 제품이 같음
3. Group의 `child_ids`와 `source_variant_ids`가 1:1이며 중복이 없음
4. Gold 미편입 후보를 포함한 모든 Registry Group의 선언 Child가 Corpus에 연결됨
5. 모든 Child가 Group을 역참조하고 고아 Child가 없음
6. 제품·문서·페이지·Variant·Source File Hash·Child Text Hash 계보가 일치함
7. 상담 Condition의 페이지가 선택한 Source Child의 실제 페이지에 속함
8. Parent·Preservation·Supporting-only 양성·중복 ID가 차단됨
9. `TEXT_AND_VISUAL_VERIFIED`와 허용 사용 범위가 맞음
10. `NO_EVIDENCE`와 `POLICY_BLOCK_*`의 Group 배열·실행 경로가 맞음
11. Required·Supporting Group의 문서·제품이 Case의 금지 목록과 겹치지 않음

CLI는 원문, 식별자, 파일 경로, Secret을 출력하지 않고 `status`, 숫자형
`counts`, `error_code_counts`만 출력합니다. 성공은 exit `0`, 실패는 exit `1`로
CI에서 차단할 수 있습니다. Data·QA는 `evidence_group_rows=18`,
`child_rows=19`, `linked_evidence_groups=18`, `linked_group_children=19`를 같은
실행에서 확인하면 IAC425의 18 Group·19 Child 연결 완료 여부를 숫자로 증명할 수
있습니다.

## 검증 결과

실행 명령:

```powershell
.\ai\.venv\Scripts\python.exe -m pytest `
  ai\tests\unit\test_evidence_scoring_v2.py `
  ai\tests\unit\test_gold_corpus_compatibility_v2.py `
  ai\tests\unit\test_gold_evaluation_dataset_v2.py `
  ai\tests\unit\test_gold_v2_evidence_group_contract.py `
  ai\tests\unit\test_full_corpus_baseline_v1.py `
  ai\tests\unit\test_experiment_playground_v0.py `
  -q -p no:cacheprovider
```

결과: `78 passed, 30 subtests passed`

추가 확인:

- 변경 Python 파일 `py_compile`: `PASS`
- `git diff --check`: `PASS`
- AI 전체 Unit: `548 passed, 4 warnings, 37 subtests passed`
- Gold v2 Dataset 생성: `NOT_RUN`
- Full Corpus v3 Compatibility: `NOT_RUN`
- Full B1 v2 실데이터 평가: `NOT_RUN`
- Provider·pgvector·Backend E2E: `NOT_RUN`

표적 Unit PASS를 실데이터 검색 품질이나 운영 Runtime PASS로 확대하지 않습니다.
경고 4건은 기존 `jsonschema.RefResolver` 폐기 예정 경고입니다.

## Data·QA 진행 가능 범위와 회신 요청

변경 Commit SHA가 전달되면 다음 작업은 시작하셔도 됩니다.

1. 기존 Full Corpus v2와 Hash 보존
2. 위 12개 ID와 대응 Child 계보를 Full Corpus v3에 반영
3. IAC425 Group 18개·Child 19개를 같은 규칙으로 전부 연결
4. P004·P005 Source Span 시각 검수와 Hash 재생성
5. COLD·HOT 기존 Child의 Group remap
6. Compatibility Validator 실행 결과 `PASS`와 Count 회신

회신에는 아래 정보만 부탁드립니다.

- 기준 Commit SHA
- Full Corpus v3·Group Registry·Child Registry의 버전과 Hash
- Group 18개·Child 19개 연결 Count
- Compatibility `status`, `counts`, `error_code_counts`
- P004·P005 Source Span 검수자와 판정

Gold 원본 반영, `TWO_PERSON_APPROVED`, Full B1 v2 실행은 위 회신을 받은 뒤 AI
담당이 진행합니다.
