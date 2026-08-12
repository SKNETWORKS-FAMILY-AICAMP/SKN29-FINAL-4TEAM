# 이동윤 → 김은진 B1 행 단위 Parent·Child 구조 결정 회신 v0.1

> 작성일: 2026-08-12 KST  
> 발신자: 이동윤 / AI·RAG  
> 수신자: 김은진 / Data·QA·DevOps  
> 기준 HEAD: `78b4c45f47b58ce10f0415c804ae959aeeaaf0d7`  
> 상태: `AI_OWNER_DECISION_APPROVE_C_WITH_CONDITIONS`

## 1. 한눈에 보는 결론

**행 단위 Child를 검색하고, 선택된 Child의 Parent만 답변 Context로 확장하는
C안을 채택한다.**

```text
행 단위 Child 검색
        ↓
Child 기준 Top-K·Hit·MRR·ANY·ALL 계산
        ↓
선택된 Child의 Parent만 중복 없이 Context로 확장
```

핵심 원칙은 다음과 같다.

- 검색과 평가는 Child만 사용한다.
- Parent는 주변 문맥 제공에만 사용하고 검색 정답으로 다시 세지 않는다.
- 같은 Parent의 Child가 여러 개 검색돼도 Parent Context는 한 번만 확장한다.
- 누수 5·7·38쪽은 Evidence 하나로 평가하고, 페이지 차이는 Source Variant로
  추적한다.
- 기존 B1 v1은 유지하고 experimental v2로 먼저 검증한다.

이 결정은 데이터 생성과 Draft 실험을 시작하기 위한 구조 결정이다.
`parent_child_v2`의 운영 적용을 승인한 것은 아니다.

## 2. 이 방안이 프로젝트에 맞는 이유

우리 프로젝트는 검색 점수만 높이는 것보다 **공식 근거 추적과 안전한 안내**가 더
중요하다.

- Child는 한 행의 증상·원인·조치와 Evidence를 정확히 연결할 수 있다.
- Parent는 안전 조건, 예외와 전후 절차처럼 Child에 부족한 문맥을 보충한다.
- 검색 정답과 생성 Context를 분리하므로 평가 수치가 Parent의 넓은 범위 때문에
  부풀려지는 것을 막을 수 있다.
- 기존 v1을 보존한 별도 실험이므로 개선과 회귀를 같은 기준에서 비교할 수 있다.

즉, C안은 **Child의 검색 정밀도와 Parent의 문맥을 함께 사용하면서도 평가에는
Child만 반영하는 방식**이다.

## 3. 다른 방안과의 비교

| 방안 | 판단 | 핵심 이유 |
|---|---|---|
| A. Parent와 Child를 함께 검색 | 제외 | 같은 근거가 Top-K를 중복 점유하고 `ALL`을 과대평가할 수 있음 |
| B. Child만 검색·사용 | 대조군으로 유지 | 검색 평가는 명확하지만 최종 안내에 필요한 주변 문맥이 부족할 수 있음 |
| C. Child 검색 후 Parent 확장 | 조건부 채택 | 검색 정밀도와 답변 문맥을 분리해 함께 확보할 수 있음 |

### A안을 제외하는 이유

Parent와 Child가 같은 검색 후보에 들어가면 하나의 근거가 두 번 나타날 수 있다.
Top-K=5에서 같은 페이지가 여러 자리를 차지하면 다른 Evidence가 밀리고, Chunking
성능보다 중복 여부가 지표를 좌우한다.

특히 현재 37·38쪽 Parent에는 여러 증상의 Evidence가 함께 붙어 있다. 특정 Child
하나만 정확히 검색됐는데 Parent의 Evidence 전체를 인정하면, 실제로 검색하지 않은
근거까지 찾은 것으로 처리돼 복합 질문의 `ALL` Completion Rank가 좋아질 수 있다.

따라서 A안은 구현은 단순하지만 **중복 Hit와 평가 수치 과대계상 위험** 때문에
채택하지 않는다.

### B안을 최종 구조로 선택하지 않는 이유

Child-only는 평가 오염이 적어 좋은 검색 대조군이다. 다만 한 행만으로는 조건,
예외와 전후 절차가 빠질 수 있다. Child 크기를 늘려 문맥을 보충하면 다시 여러
증상이 섞여 행 단위 분리의 장점이 약해진다.

따라서 B안은 `child_only_v2` 대조군으로 유지한다. C안과 동일한 Child 검색 결과를
사용하되, C안에서 Parent Context를 추가했을 때의 Token과 지연시간을 별도로
측정한다.

### Runner 전체를 바로 변경하지 않는 이유

행 경계와 Source Variant가 사람 검수 전이므로 데이터와 Runner를 동시에 정식
변경하면 오류 원인을 구분하기 어렵다. 기존 결과까지 덮어쓰면 비교 기준도 사라진다.

따라서 experimental Adapter로 먼저 검증하고, 통과한 구조만 정식 v2로 승격한다.

## 4. 누수 Evidence 관리 방식

누수 5·7·38쪽은 표현과 위치는 다르지만 같은 누수 근거다. 정답 ID와 출처 변형을
다음처럼 분리한다.

```text
evidence_group_id: EVD-WPUJAC104DWH-LEAK-001
├─ source_variant_id: LEAK-001-P005
├─ source_variant_id: LEAK-001-P007
└─ source_variant_id: LEAK-001-P038
```

- `evidence_group_id`는 검색 정답 판정에 사용한다.
- `source_variant_id`는 페이지와 원문 위치 추적에 사용한다.
- Variant 중 하나가 적중하면 누수 Evidence 하나를 충족한 것으로 본다.
- Variant가 여러 개 적중해도 서로 다른 Evidence 여러 개로 세지 않는다.
- `ALL`은 서로 다른 Evidence Group의 Child가 모두 검색돼야 통과한다.

이렇게 해야 기존 Gold의 누수 Evidence ID를 유지하면서 5·7·38쪽 표현도 모두 검색
후보로 보존할 수 있다.

## 5. 김은진에게 요청하는 데이터 구조

experimental Child·Parent Dataset에 다음 정보가 필요하다.

| 필드 | 용도 |
|---|---|
| `child_id`, `parent_id` | Child→Parent 연결 |
| `document_id`, `page_refs`, `source_span` | 원문 위치 역추적 |
| `evidence_group_id` | 검색 정답 판정 |
| `source_variant_id` | 페이지별 표현 구분 |
| `child_text` | 검색 임베딩 대상 |
| `child_text_sha256`, `parent_text_sha256` | 파생 데이터 검증 |
| `source_file_sha256` | 원본 파일 정합성 검증 |

각 Child에는 `evidence_group_id`가 정확히 하나만 있어야 한다.

## 6. AI Runner 반영 범위

현재 Runner는 이 구조를 그대로 지원하지 않는다.

- 기존 Child는 표의 행 경계가 아니라 Token Window로 생성된다.
- 파생 Chunk는 Source에 붙은 Evidence ID를 합집합으로 상속할 수 있다.
- `parent_id`는 기록하지만 Parent Context 중복 제거와 확장 비용은 계산하지 않는다.
- 기존 평가는 Evidence Group과 Source Variant를 구분하지 않는다.

따라서 이동윤은 기존 v1을 변경하지 않고 다음 기능을 experimental Adapter에
추가한다.

1. v2 Child·Parent Dataset 로딩
2. Child 기준 Evidence Group 평가
3. Parent Context 중복 제거
4. Parent 추가 Token과 처리 지연시간 기록
5. Dataset·Gold·Corpus·Profile Hash와 Run ID 기록

## 7. 진행 순서

| 순서 | 작업 | 담당 |
|---:|---|---|
| 1 | 5·7·37·38·39쪽 행 범위와 Source Variant 검수 | 김은진 + 검수자 |
| 2 | v2 Child·Parent JSONL, Manifest와 QA 보고서 생성 | 김은진 |
| 3 | v2 Adapter와 Child 기준 Group 평가 연결 | 이동윤 |
| 4 | `child_only_v2`와 `child_parent_context_v2` 비교 | 이동윤 |
| 5 | 영향 11건과 정상 통제 표본 검수 후 B1 재실행 | 공동 |

## 8. 정식 v2 승격 조건

다음 조건을 모두 확인한 뒤 운영 후보 승격 여부를 결정한다.

- Child당 Evidence Group 정확히 1개
- Child→Parent 연결 실패 0건
- 원본 페이지·행 범위·Hash 역추적 100%
- Gold 질문 문장의 Corpus 복사 0건
- 누수 5·7·38쪽 Source Variant 보존
- `0025`·`0027`의 Top-5 결과 별도 보고
- `0036`~`0038`의 `ALL` Completion Rank 별도 보고
- 정상 통제 표본 회귀 여부 확인
- Parent 중복 제거와 추가 Token·지연시간 기록

위 조건을 통과하기 전에는 `parent_child_v2`를 Draft 실험으로 유지한다.

## 9. 최종 회신값

```text
parent_child_option=C
option_a=REJECT_DUPLICATE_AND_METRIC_INFLATION
option_b=KEEP_AS_RETRIEVAL_CONTROL
evidence_scoring_unit=EVIDENCE_GROUP
source_lineage_unit=SOURCE_VARIANT
runner_rollout=EXPERIMENTAL_ADAPTER_THEN_V2_REVIEW
data_generation=READY_AFTER_FIELD_AND_ID_MAPPING_CONFIRMATION
production_adoption=NOT_APPROVED
```
