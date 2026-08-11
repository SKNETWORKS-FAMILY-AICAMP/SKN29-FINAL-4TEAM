# A2 Gold Evaluation Dataset v1 구축·QA 결과

> 실행일: 2026-08-11 KST
> Dataset: `RAG-GOLD-V1` / `1.0.0-draft.2`
> 판정: `STRUCTURAL_PASS_HUMAN_REVIEW_PENDING`

## 범위

청킹·검색·Embedding 실험에서 공통으로 사용할 평가 Case 60건의 초안을
구성했다. 정답은 특정 `chunk_id`가 아니라 다음 Lineage로 기록했다.

```text
Document → Page Refs → Section → Evidence Unit
```

기존 Retrieval Case, FAQ 질문, RAG·Safety·Structuring 평가 Case를 우선
재사용했다. 새 변형 질문과 Label은 자동 승인하지 않고 전부 사람 검수 대기로
표시했다.

제외 범위:

- Embedding·검색·LLM 실행
- 검색 결과 측정
- 2인 검수의 대리 수행
- Draft Label의 자동 Gold 승인
- 운영 Dataset 편입

## Case 구성

| 유형 | 건수 |
|---|---:|
| 정상·직접 증상 표현 | 20 |
| 구어체·간접 표현 | 10 |
| 오타·축약 표현 | 5 |
| 복합 증상 | 5 |
| Safety·위험 표현 | 10 |
| 근거 없음 | 5 |
| 다른 제품 Hard Negative | 5 |
| 합계 | 60 |

Split은 다음과 같이 고정했다.

| Split | 건수 | 용도 |
|---|---:|---|
| `DEV` | 35 | 반복 실험·튜닝 |
| `TEST` | 15 | 최종 후보 비교, 튜닝 금지 |
| `SAFETY` | 10 | 위험·중단 정책 검증 |

## Gold Evidence Schema

각 Case는 다음 정보를 필수로 가진다.

- Case ID·Dataset Version·Split·질문 유형
- 질문과 대상 제품 코드
- `document_id`
- `page_refs`
- `section_id`
- `evidence_unit_id`
- Evidence 일치 정책 `ANY`·`ALL`·`NONE`
- 근거 없음 기대값
- 위험도와 안내 정책
- 금지 문서·제품
- 기존 질문 출처와 원본 Case ID
- Label 생성 방식과 검수 상태

`expected_chunk_ids`는 Schema에서 허용하지 않는다. 청킹 전략이 달라져도 동일한
Evidence 단위로 검색 성공 여부를 판정하기 위해서다.

## 자동 QA 결과

| 검사 | 결과 |
|---|---:|
| Schema 오류 | 0 |
| Evidence Registry·Manual Page 참조 오류 | 0 |
| 기존 Retrieval·FAQ·평가 Case 참조 오류 | 0 |
| 유형·Split 분포 오류 | 0 |
| 중복 질문 | 0 |
| 근거 없음·Evidence 정책 불일치 | 0 |
| Safety 위험도·중단 정책 오류 | 0 |
| Manifest Dataset·Schema Hash 불일치 | 0 |
| 전용 회귀 테스트 | 5 통과 |

Dataset SHA-256:

```text
9B52AF026B7C8F21AC4D59ECD4D0F2E1A528E78448225EBE1F5E542A71A8E54A
```

## D-02 누수 근거 보정

원본 PDF 5·7·38페이지를 표적 시각 검수한 결과, 세 페이지 모두 제품 누수 시
원수 밸브 차단·전원 플러그 분리·상담센터 연락을 직접 안내하는 완전 근거로
확인했다. `EVD-WPUJAC104DWH-LEAK-001`의 `page_refs`를 `[5,7,38]`로
보정했으며, 같은 Evidence Unit을 사용하는 8개 Case에 일관되게 반영했다.

이 보정은 Draft Label 오류 수정이며 사람 2인 Gold 승인을 의미하지 않는다.

## 검수 상태

현재 60건 모두 다음 상태다.

```text
label_generation=ASSISTED_DRAFT_NOT_APPROVED
review_status=UNREVIEWED_DRAFT
reviewer_ids=[]
```

따라서 구조·Lineage 검증을 마친 **실험용 Draft**로는 사용할 수 있지만, 공식
Gold 성능 수치나 최종 후보 선정 근거로 사용할 수 없다. 각 Label을 2인이 검수한
뒤에만 `TWO_PERSON_APPROVED`로 승격해야 한다.

## 판정

```text
Schema and Lineage: READY
Experiment Draft Use: READY
Gold Approved Use: BLOCKED
Automatic Label Approval: PROHIBITED
```

## 테스트 환경

A2 전용 테스트 5건과 D-01·D-02 영향 범위 회귀 테스트를 기존 `test_env`에서
실행했다. 새 가상환경 생성이나 패키지 설치는 수행하지 않았다.

## 산출물

- `ai/evaluation/schemas/gold_evaluation_case_v1.schema.json`
- `ai/evaluation/datasets/gold/rag_gold_v1.jsonl`
- `ai/evaluation/datasets/gold/rag_gold_v1_manifest.json`
- `ai/scripts/build_gold_evaluation_v1.py`
- `ai/scripts/validate_gold_evaluation_v1.py`
- `ai/tests/unit/test_gold_evaluation_dataset.py`
- `ai/evaluation/reports/dataset_qa/rag_gold_v1_qa.json`
