# Gold v2·Full Corpus v3 검색평가 회신

> 보내는 사람: 이동윤 — AI·RAG·Evaluation
>
> 받는 사람: 김은진 — Data·QA
>
> 작업 Branch: `dongyoon`
>
> 실행 기준 HEAD: `da56c2c6978a03cc797fc5cdd7c545352a3a454f`
>
> 포함된 Full Corpus v3 Commit: `15577db51795eec63f2eab9dc34d5ef23b7c9bf1`
>
> 현재 상태: `LOCAL_DIAGNOSTIC_COMPLETE_HUMAN_SIGNOFF_PENDING`
>
> 작업 변경 상태: `PENDING_USER_COMMIT_APPROVAL` — 아래 AI 산출물은 아직 미커밋

## 한 줄 요약

Gold v2와 Full Corpus v3의 근거 연결은 모두 통과했지만, Source Page와 보존용 레코드를 답변용 Child와 함께 검색하면 순위가 오염되므로 Child만 1차 검색하고 원문 페이지는 후속 문맥 확장에 사용하는 구조로 정리한 뒤 사람 승인과 pgvector 재실행을 거쳐야 합니다.

## 결론

| 항목 | 상태 | 결론 |
| --- | --- | --- |
| Full Corpus v3 Data·QA 재현 | `PASS` | 132건, Group 34건, Child 37건의 Hash와 Data 단위 테스트 142건을 재확인했다. |
| Gold v2 정답표 생성 | `STRUCTURAL_PASS_HUMAN_REVIEW_PENDING` | 60건 중 55건을 평가 대상으로 두고 5건은 근거 계약이 완성될 때까지 제외했다. 모든 행은 아직 `UNREVIEWED_DRAFT`다. |
| Main Gold–Corpus 연결 | `PASS` | Required Group 9/9, Supporting Group 3/3, 전체 Group 34/34, Child 37/37, 오류 0이다. |
| IAC425 후보 연결 | `PASS_DRAFT_ONLY` | 후보 18건과 Required Group 18/18이 연결됐다. Main Gold 편입과 사람 승인은 0/18이다. |
| 132건 혼합 Local Dense | `PARTIAL` | Main Hit@5 86.67%, IAC425 Hit@5 100%지만 무효 Source Page·Preservation Hit가 각각 91건, 50건이다. |
| 37건 Child-only Ablation | `PARTIAL_RECOMMENDED_PROFILE` | Main Hit@5 93.33%, IAC425 Hit@5 100%, 무효 Hit 0으로 개선됐다. LOW-FLOW 3건과 No-Evidence 오탐 3건은 남았다. |
| Full B1 pgvector·Runtime Policy | `NOT_RUN/HOLD` | 현재 Process에 `AI_VECTOR_DSN`이 없고 승인된 v3 pgvector Index와 Runtime Policy 실행 증거도 없다. |
| Gold 최종 승인 | `HUMAN_SIGNOFF_PENDING` | `TWO_PERSON_APPROVED`, Gold 반영 완료, 공식 B1 성능으로 표시하지 않는다. |

## 1. 새 Gold v2 정답표

생성한 Main Dataset은 다음과 같다.

- Dataset ID: `RAG-GOLD-V2`
- Dataset Version: `2.0.0-draft.1`
- 파일: `ai/evaluation/datasets/gold/rag_gold_v2.jsonl`
- 전체 60건: `ACTIVE 55 / EXCLUDED 5`
- 검수 상태: `UNREVIEWED_DRAFT 60`
- 승인된 Active: `0`
- 공식 Metric 사용: `false`
- Dataset SHA-256:
  `1987ED6EDFE18BDE6038DC350EA84CCD6B3752837F6AE0CD510AAB83EE1ED00D`

제외한 Case는 삭제하지 않고 기존 ID를 보존했다.

| Case | 제외 이유 | 재진입 조건 |
| --- | --- | --- |
| `0017`, `0033` | “소음이 너무 큼”을 판정할 Severity Trigger가 현 조건 Schema와 원문 근거에 정확히 연결되지 않는다. | Severity 조건 계약과 Source Condition ID 승인 |
| `0040` | 누수와 온수 분사를 한 Case에 묶은 기존 제외 결정을 유지한다. | 좁은 두 Group을 `ALL`로 쓰는 재작성 또는 단일 Case 분리 |
| `0043` | 질문에 필요한 좁은 P003 계열 Evidence Group이 v3 Registry에 없다. | 신규 Group·Child·Source Span 승인 |
| `0047` | 질문에 필요한 좁은 P006 계열 Evidence Group이 v3 Registry에 없다. | 신규 Group·Child·Source Span 승인 |

`ACTIVE`는 Runner가 읽을 평가 대상이라는 뜻이지, 사람 2인 승인을 뜻하지 않는다.

IAC425 18건은 Main Gold와 섞지 않았다.

- 파일: `ai/evaluation/datasets/candidates/iac425_gold_v2_candidates.jsonl`
- Case ID: `RAGV2-GOLD-0061~0078`
- 상태: `ACTIVE 18 / UNREVIEWED_DRAFT 18`
- Main Gold 포함 건수: `0`
- SHA-256:
  `11AAF6B8BDCDBC74AE9649745E2E5EB761ADF23C81544A5C4165F10F64321EE4`

## 2. Gold–Corpus 연결 검사

Main Gold 실제 입력으로 다시 검사한 결과는 다음과 같다.

| 검사 수치 | 결과 |
| --- | ---: |
| Gold 전체 / Active | 60 / 55 |
| Active Evidence / No-Evidence | 45 / 10 |
| Required Group 연결 | 9 / 9 |
| Supporting Group 연결 | 3 / 3 |
| Registry Group 연결 | 34 / 34 |
| Group–Child 연결 | 37 / 37 |
| Condition 참조 / 등록 | 24 / 10 |
| 오류 | 0 |

IAC425 후보의 별도 검사 결과는 다음과 같다.

| 검사 수치 | 결과 |
| --- | ---: |
| 후보 전체 / Active | 18 / 18 |
| Required Group 연결 | 18 / 18 |
| Condition 참조 / 등록 | 6 / 10 |
| 오류 | 0 |

조건 ID는 Canonical `data/**`를 수정하지 않고 AI Evaluation Overlay로 연결했다.

- Overlay 상태: `HUMAN_SIGNOFF_PENDING`
- 범위: `AI_EVALUATION_OVERLAY_NOT_CANONICAL_DATA`
- 승격 상태: `NOT_APPROVED`
- Group·Child·Corpus·조건문은 SHA-256과 Source Child/Page 계보로 고정했다.

따라서 이 PASS는 정답표와 Corpus의 구조 연결 PASS다. Data 원본에 조건 계약이
승격됐거나 Gold 라벨이 사람 승인됐다는 뜻은 아니다.

## 3. `0049` 필수·보조 근거

다음과 같이 확정했다.

- 질문: `정수기 옆에서 살충제를 뿌린 뒤 정수기에서 타는 냄새가 나요. 어떻게 해야 하나요?`
- Required:
  `EVD-WPUJAC104DWH-BURNING-ODOR-RESPONSE-001`
- Supporting:
  `EVD-WPUJAC104DWH-SPRAY-FIRE-PREVENTION-001`
- Match Policy: `ANY` — Required 배열에만 적용
- 기대 상태: `danger / TOTAL_STOP / REQUIRED / DANGER_SAFETY`

실제 검색에서는 132건 혼합 Profile이 Required Child를 3위에서 찾았지만
Supporting은 Top-5에서 놓쳤다. Child-only Profile에서는 Required가 2위,
Supporting이 3위로 모두 검색됐다. 이 결과도 Supporting을 필수 정답으로
승격하는 근거는 아니다.

## 4. `0045` 예방과 사고 후 대응 분리

기존의 모호한 물 유입 질문을 실제 사고 후 대응 질문으로 좁혔다.

- 새 질문: `정수기 안쪽에서 실제로 물이 흘러나오고 전원이 켜져 있어요. 지금 어떻게 해야 하나요?`
- Required: `EVD-WPUJAC104DWH-LEAK-001`
- 기대 상태: `danger / TOTAL_STOP / REQUIRED / DANGER_SAFETY`
- 실제 Child-only 검색: P005 누수 Child 1위, P007 누수 Variant 2위

P004의
`EVD-WPUJAC104DWH-WATER-INGRESS-PREVENTION-001`은 예방 Group으로 따로
보존했으며 `0045`의 사고 후 필수 근거로 사용하지 않았다. 예방만 묻는 새 질문은
기존 승인 질문에 없으므로 Main Gold에 임의 추가하지 않았다. 필요하면 별도
질문과 새 Case ID를 승인받아 추가해야 한다.

## 5. “증상이 계속되면 상담” 조건 연결

조건은 문구를 Gold에 복사하는 방식이 아니라, Source Child와 조건문 Hash에
연결한 Condition ID로 관리한다.

| 질문 상태 | Gold 값 | 의미 |
| --- | --- | --- |
| 현재는 기본 확인 단계이고 “계속되면” 조건이 아직 충족되지 않음 | `CONDITIONAL + SOURCE_CONDITION_PENDING + condition_id` | 현재 안내 상태와 향후 상담 조건을 분리한다. |
| 질문에 “필터 교체 후에도”, “2시간이 지나도”처럼 조건 충족이 명시됨 | `REQUIRED + SOURCE_CONDITION_MET + condition_id` | 이미 조건이 충족됐으므로 상담 필요를 참으로 채점한다. |
| 누수·타는 냄새 등 즉시 중단 Safety | `REQUIRED + DANGER_SAFETY` | 지속 조건을 기다리지 않는다. |
| 검색 근거 없음 | `REQUIRED + NO_EVIDENCE` | 빈 Evidence와 상담 필요를 함께 요구한다. |
| 제품·기능·미검증 출처 차단 | `REQUIRED + POLICY_BLOCK` | Vector 결과가 아니라 실제 정책 경로를 검증한다. |

등록한 조건은 JAC104 4개, IAC425 6개다.

- JAC104: 필터 교체 후 미출수, 2시간 후 냉수 이상, 필터 교체 후 저유량,
  온수 스팀 지속
- IAC425: 2시간 후 냉수 이상, 온수 스팀 지속, 필터 교체 후 저유량,
  잠금 해제 후 온수 미출수, 필터 교체 후 미출수, 미세 입자 지속

소음 Severity는 현 Trigger Enum과 원문 조건을 정확히 표현하지 못해 억지로
Condition ID를 만들지 않았다. 그래서 관련 Main Case 두 건을 제외했다.

## 6. 실제 검색 진단 결과

공통 실행 조건은 다음과 같다.

- Model: `BAAI/bge-m3`
- Revision: `5617a9f61b028005a4858fdac845db406aefb181`
- 1024차원, L2 정규화, CPU, 로컬 Snapshot만 사용
- Dense Cosine Exact, `top_k=5`, threshold `0.4`
- 점수 계산 전 Exact 제품 필터
- 실제 경로: `LOCAL_DENSE_QUERY`
- Gold 기대 경로: `PGVECTOR_QUERY`
- 사람 승인 대기 Dataset을 명시적으로 허용한 비공식 진단 실행

### 6.1 Main Gold 55건

| 지표 | 혼합 132건 | Child-only 37건 |
| --- | ---: | ---: |
| Evidence Case | 45 | 45 |
| Group Hit@1 | 0.511111 | 0.577778 |
| Group Hit@3 | 0.711111 | 0.866667 |
| Group Hit@5 | 0.866667 | 0.933333 |
| Recall@5 | 0.877778 | 0.933333 |
| MRR | 0.631852 | 0.721852 |
| Required Group 성공 | 39/45 | 42/45 |
| Supporting 전체 회수 | 6/8 | 7/8 |
| 무효 Top-K Hit | 91 | 0 |
| Corpus-absence 검색 0건 | 1/4 | 1/4 |

Child-only에서 남은 양성 Miss는 `0013`, `0020`, `0023`이며 모두
`LOW-FLOW` Group이다. 이 세 질문은 “쫄쫄”, “물이 잘 안 나옴”, “졸졸”을
사용하지만 근거 Child는 긴 원인·조치 문단 중심이라 다른 증상 Child에 밀렸다.

No-Evidence 중 `0053`만 검색 0건이었고 `0051`, `0052`, `0054`는 오탐이
남았다. 가격·실시간 방문·외관 색상 질문을 Dense Threshold만으로 거르는 것은
불안정하므로, 사람 승인 후 지원 범위 Policy로 선차단할지 DEV에서 별도로
결정해야 한다.

`0055~0060`은 이 Runner가 Runtime Policy Evaluator를 호출하지 않으므로
`NOT_RUN_RUNTIME_POLICY`, Vector 호출 0회로 남겼다. 기대 경로를 결과에 복사해
가짜 PASS로 만들지 않았다.

### 6.2 IAC425 후보 18건

| 지표 | 혼합 132건 | Child-only 37건 |
| --- | ---: | ---: |
| Evidence Case | 18 | 18 |
| Group Hit@1 | 0.277778 | 0.777778 |
| Group Hit@3 | 0.722222 | 1.000000 |
| Group Hit@5 | 1.000000 | 1.000000 |
| MRR | 0.529630 | 0.879630 |
| Required Group 성공 | 18/18 | 18/18 |
| 무효 Top-K Hit | 50 | 0 |

Child-only에서도 Top-1이 아닌 후보는 `0069`, `0072`, `0075`, `0078`이다.
모두 Top-3 안에는 들어왔지만 후보 라벨 자체가 아직 사람 승인 전이므로 공식
IAC425 Gold 성능으로 사용할 수 없다.

### 6.3 청킹·검색 역할 판정

이번 비교에서 가장 큰 문제는 원문 내용 누락보다 검색 역할 혼입이다.

1. `CHILD`만 1차 Vector 검색과 Gold Group 채점 대상으로 사용한다.
2. Exact 제품, `TEXT_AND_VISUAL_VERIFIED`, 허용 사용 범위를 점수 계산 전에
   제한한다.
3. `SOURCE_PAGE`는 Child 적중 후 인용·문맥 확장용으로만 가져오고 독립 정답
   Hit로 채점하지 않는다.
4. `PRESERVATION`은 계보·재생성 QA용으로 유지하고 고객 답변 검색에서는
   제외한다.
5. LOW-FLOW는 한 개의 긴 Child를 그대로 늘리기보다 같은 Evidence Group 아래
   증상 Anchor와 원인별 Source Child를 분리하고, 적중 후 Sibling을 합치는
   실험을 DEV에서 수행한다.
6. “쫄쫄/졸졸/물줄기가 약함” 같은 검색 Alias는 원문 Evidence가 아니라
   Retrieval Metadata로 분리하고 승인·Hash를 남긴다.

Full Corpus v3 원본은 수정하지 않았다. 위 역할 변경은 AI Profile에서 먼저
Ablation으로 검증했으며, Canonical `retrieval_role` 변경이 필요하면 Data·QA가
별도 버전에서 반영해야 한다.

## 실행·검증 증거

```powershell
.\ai\.venv\Scripts\python.exe -B -m unittest discover -s data\tools\tests -q
.\ai\.venv\Scripts\python.exe -B -m ai.scripts.build_gold_evaluation_v2
.\ai\.venv\Scripts\python.exe -B ai\scripts\build_gold_v2_evidence_group_registry.py
.\ai\.venv\Scripts\python.exe -B ai\scripts\validate_gold_evaluation_v2.py --dataset ai\evaluation\datasets\gold\rag_gold_v2.jsonl --schema ai\evaluation\schemas\gold_evaluation_case_v2.schema.json
.\ai\.venv\Scripts\python.exe -B ai\scripts\validate_gold_corpus_compatibility_v2.py --gold ai\evaluation\datasets\gold\rag_gold_v2.jsonl --evidence-groups ai\evaluation\datasets\gold\full_corpus_v3_evidence_groups_gold_v2.jsonl --children data\processed\structured\rag\experimental\full_corpus_v3_children.jsonl --corpus data\processed\structured\rag\experimental\full_corpus_chunks_v3.jsonl
.\ai\.venv\Scripts\python.exe -B -m pytest ai\tests\unit -q -p no:cacheprovider
.\ai\.venv\Scripts\python.exe -B -m ai.scripts.run_full_corpus_baseline_v2 --profile ai\configs\experiments\full_corpus_baseline_v2.yaml --allow-review-pending
.\ai\.venv\Scripts\python.exe -B -m ai.scripts.run_full_corpus_baseline_v2 --profile ai\configs\experiments\full_corpus_baseline_v2_child_only.yaml --allow-review-pending
.\ai\.venv\Scripts\python.exe -B -m ai.scripts.run_full_corpus_baseline_v2 --profile ai\configs\experiments\full_corpus_baseline_v2_iac425_candidates.yaml --allow-review-pending
.\ai\.venv\Scripts\python.exe -B -m ai.scripts.run_full_corpus_baseline_v2 --profile ai\configs\experiments\full_corpus_baseline_v2_iac425_candidates_child_only.yaml --allow-review-pending
```

- Python: `3.13.13`
- Data Unit: `142 tests`, `OK`
- Gold·Scorer·Compatibility·Runner 표적: `88 passed, 34 subtests passed`
- AI 전체 Unit: `593 passed, 4 warnings, 41 subtests passed`
- Dependency: `No broken requirements found`
- Gold Schema: Main·IAC425 모두 오류 0,
  `STRUCTURAL_PASS_HUMAN_REVIEW_PENDING`
- Gold–Corpus: Main·IAC425 모두 오류 0, `PASS`
- 실제 BGE-M3 Local Dense: 네 Profile 모두 exit `0`
- pgvector·Runtime Policy·Provider·Backend 저장 E2E: `NOT_RUN`

혼합 두 Profile은 CPU에서 동시에 재생성했으므로 기록된 Batch 시간은 경쟁 영향을
받았다. 따라서 이번 문서에서는 품질과 후보 수만 비교하며 해당 시간을 운영
Latency 근거로 사용하지 않는다.

## 회신 요청

김은진님은 아래 항목을 승인 또는 반려해 주세요.

1. Main Gold 55건의 질문·라벨과 제외 5건의 사유
2. JAC104 4개·IAC425 6개 Condition ID와 Source Child 연결
3. `0045` 사고 후 누수 Case와 예방 Case 분리 원칙
4. `0049` Required/Supporting 구분
5. IAC425 후보 18건의 사람 검수 결과와 Main Gold 편입 여부
6. Canonical Data에서 `CHILD=검색`, `SOURCE_PAGE=문맥 확장`,
   `PRESERVATION=QA 전용` 역할을 다음 버전에 반영할지 여부

이 회신이 끝나기 전에는 `TWO_PERSON_APPROVED`, Gold 반영 완료, 공식 Full B1
성능 승인으로 표시하지 않는다. 승인 뒤에는 Child-only Runtime Profile로
pgvector Index를 만들고, 실제 Policy Evaluator를 포함한 Full B1을 다시
실행해야 한다. 현재 변경에는 새 Commit SHA가 없으므로 김은진님에게 전달할
구현 Commit은 사용자 확인과 커밋 후 별도로 회신한다.
