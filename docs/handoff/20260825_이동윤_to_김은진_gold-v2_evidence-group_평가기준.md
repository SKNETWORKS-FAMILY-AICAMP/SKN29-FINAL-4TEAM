# Gold v2·Evidence Group 평가 기준 회신

> 회신자: 이동윤 — AI·RAG 담당
> 수신자: 김은진 — Data·QA 담당
> 작성일: 2026-08-25 KST
> 기준 Branch: `dongyoon`
> 기준 HEAD: `23d1603f4fb7ed978c4bd0f653fd56ca80121e0c`
> 상태: `AI_EVALUATION_CONTRACT_V2_DECISION_PROPOSED`
> 구현 상태: `NOT_STARTED`

## 한 줄 요약

**Gold는 의미 단위 Evidence Group만 정답으로 보유하고, Child는 Registry가 연결하며, 사용 상태·상담 조건·No-Evidence·Policy Block을 분리한 공통 Scorer로 Full B1과 Playground를 동일하게 채점한다.**

## 1. 결정

기존 Gold v1에 필드를 덧붙이지 않는다. 정답 단위와 채점 의미가 호환되지 않게
바뀌므로 아래 버전을 병렬로 만든다.

| 항목 | 결정 |
|---|---|
| Gold Schema | `2.0.0-draft.1` |
| Gold Dataset | `2.0.0-draft.1` |
| Evaluation Contract | `evidence_group_policy_v2` |
| 신규 Corpus | 기존 Full Corpus v2를 보존하고 `Full Corpus v3 draft` 생성 |
| 기존 v1 Dataset·Runner·Report | 수정하지 않고 역사적 결과로 보존 |
| Backend↔AI 공개 계약 `4.0.0` | 변경하지 않음. 아래 필드는 평가 내부 전용 |

현재 Full B1은 `Evidence ID + document_id + page_refs`를 비교하지만 Playground는
`document_id + page_refs`만 비교한다. 이 차이를 유지한 채 Corpus만 고치면 같은
검색 결과에 서로 다른 판정이 다시 발생하므로 공통 Scorer를 먼저 고정한다.

## 2. Gold v2 필드

기존 Case ID, 질문, 제품, Split, 금지 문서·모델, Source와 검수 필드는 유지한다.
정답·정책 관련 필드는 다음을 기준으로 한다.

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
  "expected_consultation_requirement": "CONDITIONAL"
}
```

### 2.1 사용 상태와 상담 필요 분리

| 필드 | 허용 값 | 의미 |
|---|---|---|
| `expected_usage_guidance_status` | `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION` | 현재 제품 기능의 사용 안내 상태 |
| `expected_consultation_requirement` | `NONE`, `CONDITIONAL`, `REQUIRED` | 현재 또는 조건부 상담 필요성 |

판정 예시는 다음과 같다.

- 정상 작동음이며 지속되면 상담: `NORMAL + CONDITIONAL`
- 확인 절차 후에도 증상이 지속됨: `NORMAL + REQUIRED`
- 누수·감전·화상 위험: `TOTAL_STOP + REQUIRED`
- 근거 부재 또는 제품 정책 차단: `PENDING_CONSULTATION + REQUIRED`

현재 Gold의 `CONSULTATION_ONLY`는 공개 AI `4.0.0` 사용 안내 상태에 없는 값이므로
v2에서는 사용하지 않는다. 공개 응답의 `requires_consultation`은
`expected_consultation_requirement=REQUIRED`일 때만 `true`로 대응한다.
`CONDITIONAL`의 실제 조건은 Evidence Group의 `consultation_conditions` 계보를
통해 검수하고 Retrieval 점수에는 포함하지 않는다.

## 3. 필수·보조 Evidence와 `ANY/ALL/NONE`

`evidence_match_policy`는 `required_evidence_group_ids`에만 적용한다.

- `ANY`: Required Group 중 하나 이상 검색되면 통과
- `ALL`: 서로 다른 Required Group을 모두 검색해야 통과
- `NONE`: Required·Supporting Group이 모두 비어 있는 No-Evidence 또는
  Policy Block Case에서만 허용
- Supporting Group: 검색 여부만 진단하고 PASS, Hit@K, MRR에는 반영하지 않음
- Required와 Supporting Group은 서로 중복될 수 없음
- Required Group이 1개면 `ANY`를 사용
- `ALL`은 서로 다른 의미 predicate를 모두 요구할 때만 사용

예를 들어 `0049`는 다음처럼 처리한다.

```text
Required   = EVD-...-BURNING-ODOR-RESPONSE-001
Supporting = EVD-...-SPRAY-FIRE-PREVENTION-001
Policy     = ANY
```

P005 의미 Group이 검색되면 핵심 정답은 통과한다. P004만 검색되면 실패하며,
P004는 원인·예방 설명의 Supporting Coverage로만 기록한다.

`0040`을 재진입시키려면 누수 Group과 지속적 온수·증기 분사 Group을 각각
Required로 두고 `ALL`을 사용한다. 그 전에는 `evaluation_status=EXCLUDED`를
유지하며 Case ID를 삭제하거나 재사용하지 않는다.

## 4. Evidence Group과 Child 연결

Gold에는 Child ID나 Manual Page ID를 정답 키로 넣지 않는다.

```text
Gold.required_evidence_group_ids
→ Evidence Group Registry.evidence_group_id
→ Evidence Group Registry.child_ids[]
→ Corpus SEARCH_CANDIDATE.source_record_id
```

연결 규칙은 다음과 같다.

1. 동일 Group의 Child는 의미적으로 동등한 Source Variant여야 한다.
2. 등록 Child 중 하나가 검색되면 해당 Group 하나를 충족한다.
3. 같은 Group의 Child 여러 개가 검색돼도 정답 수를 중복 가산하지 않는다.
4. 증상·위험도·조치가 다른 Child는 Group을 먼저 분리한다.
5. Parent와 Preservation만으로는 Gold Hit를 인정하지 않는다.
6. 제품 코드, 검증 상태, 허용 사용, Registry의 Child 계보가 모두 일치해야 한다.
7. `document_id`와 `page_refs`는 사전 계보 검증과 진단에 사용하고 관련성 점수의
   정답 키로 사용하지 않는다.

IAC425 `CAND-010`처럼 Group 하나에 P005·P045 Child Variant가 있으면 Gold에는
Group ID 한 건만 넣는다. 어느 Child가 검색돼도 통과하되 둘 다 검색됐다고 정답
두 건으로 계산하지 않는다.

## 5. No-Evidence와 Policy Block

두 필드의 조합으로 실행 경로를 구분한다.

| 상황 | `expected_retrieval_outcome` | `expected_execution_path` | Vector Query |
|---|---|---|---:|
| 정상 근거 검색 | `EVIDENCE` | `PGVECTOR_QUERY` | 1회 이상 |
| 실제 Corpus 부재 | `NO_EVIDENCE` | `PGVECTOR_QUERY` | 1회 이상 |
| 다른 제품 차단 | `NO_EVIDENCE` | `POLICY_BLOCK_PRODUCT_MISMATCH` | 0회 |
| 미지원 모델 차단 | `NO_EVIDENCE` | `POLICY_BLOCK_UNSUPPORTED_MODEL` | 0회 |
| 미지원 기능 차단 | `NO_EVIDENCE` | `POLICY_BLOCK_UNSUPPORTED_CAPABILITY` | 0회 |
| 미검증 Source 차단 | `NO_EVIDENCE` | `POLICY_BLOCK_UNVERIFIED_SOURCE` | 0회 |

- `PGVECTOR_QUERY + NO_EVIDENCE`: 실제 검색 후 공개 Evidence가 0건이어야 한다.
- `POLICY_BLOCK_*`: 검색 전에 차단되고 실제 차단 경로가 예상값과 일치해야 한다.
- No-Evidence Case의 Recall·MRR은 `0.0`이 아니라 `null`로 기록한다.
- `no_evidence_success`와 `policy_block_success`는 별도 집계한다.

`0055`는 현재 상태로 `CORPUS_ABSENCE`가 될 수 없다. 미검증 FAQ 정책 Case로
유지하려면 제품 미식별과 미검증 Source 요청이 분명한 질문으로 다시 설계하고
`POLICY_BLOCK_UNVERIFIED_SOURCE`를 사용한다. 정확 JAC104 누수 문의로 유지하면
공식 누수 Group을 기대하는 양성 Case로 바꾼다.

## 6. Full B1·Playground 공통 채점

공통 평가 함수를 하나만 SSOT로 둔다.

```text
ai/evaluation/evidence_scoring_v2.py
├─ ai/scripts/run_full_corpus_baseline_v2.py
└─ ai/app/experiments/playground.py
```

공통 출력에는 최소 다음을 포함한다.

- `covered_required_group_ids`
- `missing_required_group_ids`
- `covered_supporting_group_ids`
- `matched_variant_child_ids`
- `hit_at_1`, `hit_at_3`, `hit_at_5`
- `required_completion_rank`, `mrr`
- `expected_execution_path`, `actual_execution_path`
- `vector_query_count`
- `wrong_product_hit_count`
- `scoring_contract_version`
- `passed`

Playground는 다음 제한을 적용한다.

1. 공식 채점은 `gold_case_id`를 명시한 실행만 허용한다.
2. 질문 문자열 자동 Gold 매칭은 제거한다.
3. 임의 질문은 `NOT_SCORED`로 표시한다.
4. Top-K, 제품 필터, Corpus Hash, Embedding Revision, Threshold가 Full B1
   Profile과 다르면 `NOT_COMPARABLE`로 표시한다.
5. `document_id + page_refs` 일치는 Gold PASS가 아니라 Lineage Diagnostic이다.
6. TEST Split의 기대 근거는 Playground에 노출하지 않는다.
7. Draft Gold는 `DRAFT_SCORED`이며 공식 Metric을 허용하지 않는다.

비교 가능한 기본 Retrieval Profile은 Exact Product Filter, `Top-K=5`, Threshold
`0.4`, BGE-M3 고정 Revision·1024 Dimension을 사용한다. Profile이 다르면 같은
Gold를 사용해도 공식 비교 결과로 합치지 않는다.

## 7. 변경 파일과 소유권

### 이동윤 / AI

- 신규 `ai/evaluation/schemas/gold_evaluation_case_v2.schema.json`
- 신규 `ai/evaluation/datasets/gold/rag_gold_v2.jsonl`
- 신규 `ai/evaluation/datasets/gold/rag_gold_v2_manifest.json`
- 신규 `ai/evaluation/evidence_scoring_v2.py`
- 신규 `ai/scripts/build_gold_evaluation_v2.py`
- 신규 `ai/scripts/validate_gold_evaluation_v2.py`
- 신규 `ai/scripts/validate_gold_corpus_compatibility_v2.py`
- 신규 `ai/scripts/run_full_corpus_baseline_v2.py`
- 신규 `ai/configs/experiments/full_corpus_baseline_v2.yaml`
- 변경 `ai/app/experiments/playground.py`
- 대응 AI Unit Test

Playground Route·HTML은 공유 Interface 경로이므로 관련 소유자와 편집자·검증
순서를 먼저 합의한다. 기존 v1 Runner와 과거 Report를 v2 의미로 덮어쓰지 않는다.

### 김은진 / Data·QA

- 기존 Full Corpus v2와 Hash 보존
- 신규 Full Corpus v3 Schema·Builder·Manifest·QA
- P004·P005, COLD·HOT의 의미 단위 Evidence Group 분리
- IAC425 Group 18개·Child 19개의 Group→Child→Corpus 연결
- Coverage·Preservation·Source Span·Hash 결정성 검증
- 누락·중복·제품 혼입·검증 상태 오류 0건 확인

AI는 Data 소유 파일을 대신 수정하지 않고, Data/QA는 AI Gold·Scorer 의미를
임의 변경하지 않는다.

## 8. 선행 Gate와 표적 테스트

Full B1 전에 다음을 모두 통과해야 한다.

1. 모든 `ACTIVE` 양성 Case의 Required Group이 Registry에 정확히 1건 존재
2. 각 Required Group에 동일 제품의 검색 가능한 Child가 1건 이상 존재
3. Registry Child가 Corpus에 정확히 1건 존재하고 Source Hash·계보가 일치
4. Supporting만 검색되면 Case 실패
5. 동일 Group의 동등 Child 중 어느 하나가 검색되면 통과
6. 서로 다른 Required Group의 `ALL`에서 하나가 누락되면 실패
7. 같은 페이지라도 Group이 다르면 실패
8. Parent·Preservation만으로는 통과 불가
9. Policy Block은 Vector Query 0회
10. Corpus 부재는 검색 실행 후 Evidence 0건
11. 동일 Fixture에 대한 Full B1·Playground 결과 객체가 동일
12. Builder 재실행 Byte·Hash 일치
13. `TWO_PERSON_APPROVED` 전 공식 Metric 비공개

예정 표적 명령은 다음과 같다.

```powershell
.\ai\.venv\Scripts\python.exe -m pytest `
  ai\tests\unit\test_gold_evaluation_dataset_v2.py `
  ai\tests\unit\test_gold_corpus_compatibility_v2.py `
  ai\tests\unit\test_evidence_scoring_v2.py `
  ai\tests\unit\test_full_corpus_baseline_v2.py `
  ai\tests\unit\test_experiment_playground_v1.py -q

.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
.\ai\.venv\Scripts\python.exe -B -m unittest discover -s data\tools\tests -v
```

현재는 기준 결정 문서 작성만 완료했다. 신규 Schema·Dataset·Corpus·Scorer 구현과
위 테스트는 모두 `NOT_RUN`이며, 본 문서만으로 `TWO_PERSON_APPROVED`, Full B1
PASS 또는 운영 반영을 선언하지 않는다.

## 9. 진행 순서

1. AI가 Gold v2 Schema와 공통 Scorer 입출력 계약을 코드로 고정한다.
2. Data/QA가 그 계약에 맞춰 Full Corpus v3 후보를 생성한다.
3. AI가 승인 Case만 Gold v2로 이전하고 Compatibility Gate를 실행한다.
4. Full B1과 Playground Parity 표적 테스트를 실행한다.
5. Case별 2인 서명과 Dataset·Corpus Hash를 고정한다.
6. 같은 승인 Hash로 Full B1을 실행하고 결과 범위를 판정한다.

