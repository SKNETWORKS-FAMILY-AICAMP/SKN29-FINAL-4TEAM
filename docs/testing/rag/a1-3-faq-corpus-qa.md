# A1-3 FAQ 원문 등록·QA 결과

> 실행일: 2026-08-10 KST  
> 대상: SK매직 정수기 FAQ 원문 119건  
> 판정: `STRUCTURAL_PASS_SCOPE_REVIEW_REQUIRED`

## 범위

기존 `faq_snapshot_normalized.jsonl`에 등록된 FAQ 119건을 원문 Markdown과
대조하고, Experiment Lab에서 사용할 수 있는 텍스트 범위를 확정했다.

새 FAQ Dataset을 중복 생성하거나 기존 운영 RAG에 FAQ를 추가하지 않았다.

포함 범위:

- 원문 파일 크기·SHA-256·119개 제목 확인
- 정규화 FAQ 번호·ID 연속성 및 Schema 검사
- 제목·이미지 URL·게시자 텍스트 원문 대조
- 본문 Hash·빈 본문·문자 깨짐·정확 중복 검사
- 게시자 텍스트·검수 OCR·미전사 이미지 분리
- 게시자 모델 코드 유무와 MVP 제외 정책 검사

제외 범위:

- 추가 이미지 OCR
- Chunking·Embedding·Vector DB
- MVP 검색 및 운영 Corpus 편입
- 정확 모델 적용성 확정
- Gold Evidence 승인

## 확인 결과

| 항목 | 결과 |
|---|---:|
| 원문 FAQ | 119 |
| 정규화 FAQ | 119 |
| 게시자 텍스트 | 111 |
| 사용자 검수 OCR 텍스트 | 5 |
| 조건부 실험 텍스트 | 116 |
| 미전사 이미지 전용·검색 제외 | 3 |
| 게시자 모델 코드 있음 | 12 |
| 게시자 모델 코드 없음 | 107 |
| 누락·중복 번호 | 0 / 0 |
| 중복 ID·제목·본문 | 0 / 0 / 0 |
| 본문 Hash 불일치 | 0 |
| 문자 깨짐 의심 | 0 |
| 원문 제목·이미지 URL·게시자 텍스트 불일치 | 0 / 0 / 0 |
| QA 오류·경고 | 0 / 2 |

원문 SHA-256:

```text
670C739A69B3ACF811D763FF17F21C53EB661F7BAE1F7D505275B571FF4D3FF8
```

정규화 Dataset SHA-256:

```text
E2040220C22F26042F1662029FA45776A7261336956DF6D8C7102485A27F41F4
```

## 분류와 사용 범위

| 상태 | 건수 | 실험 사용 |
|---|---:|---|
| `PUBLISHER_TEXT` | 111 | 조건부 참고 가능 |
| `OCR_VERIFIED` | 5 | 조건부 참고 가능, 모델 적용성 별도 검토 |
| `NOT_TRANSCRIBED` | 3 | 검색 제외 |

조건부 텍스트 116건은 청킹·검색 실험의 후보 Corpus로 사용할 수 있다. 다만
107건은 게시자 모델 코드가 없으므로 JAC104/JCC104의 정확한 제품 근거로 자동
승격하지 않는다. 모델 코드가 표시된 항목도 판매 코드·세대·매뉴얼과의 일치 여부를
검토하기 전까지 기존 `mvp_rag_eligible=false`를 유지한다.

미전사 이미지 전용 FAQ 3건은 다음과 같다.

- `FAQ-SKMAGIC-0007`
- `FAQ-SKMAGIC-0009`
- `FAQ-SKMAGIC-0010`

이 항목들은 A1-3에서 OCR하지 않았으며 `retrieval_scope=EXCLUDED` 상태를 유지한다.

## 판정

```text
Conditional Experimental Text: READY (116)
Image-only Use: BLOCKED (3)
MVP Search Use: BLOCKED
Exact-model Evidence: REVIEW_REQUIRED
Gold Evidence: REVIEW_REQUIRED
```

A1-3의 원문 등록 상태 확인과 최소 구조 QA는 완료다. 다음 단계에서 실험 Corpus를
생성할 때 116건을 후보 입력으로 사용할 수 있지만, MVP나 운영 검색에 자동 편입하지
않는다.

## 산출물

- `data/processed/documents/faq/faq_snapshot_normalized.jsonl`
- `data/schemas/processed/faqNormalized.schema.json`
- `data/tools/rag_experiments/qa_faq_corpus.py`
- `data/tools/tests/test_faq_corpus_qa.py`
- `data/processed/validation/rag_experiments/faq_corpus_qa.json`
