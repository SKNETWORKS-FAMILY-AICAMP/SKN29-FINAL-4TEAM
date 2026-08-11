# A1-2 IAC425 전체 페이지 데이터 생성·QA 결과

> 실행일: 2026-08-10 KST  
> 대상: WPU-IAC425 REV.02 공식 매뉴얼 52쪽  
> 판정: `STRUCTURAL_PASS_VISUAL_REVIEW_PENDING`

## 범위

이번 작업은 IAC425 공식 PDF를 Experiment Lab에서 사용할 페이지 Dataset으로
추출·정규화하고 최소 QA하는 범위다.

포함 범위:

- 원본 PDF 크기·SHA-256·52쪽 확인
- 페이지별 텍스트 추출 및 공백 정규화
- 페이지 번호 제거와 Section Metadata 부여
- 명시적 추출 오류 보정
- 이미지 기반 52쪽 뒷표지 시각 전사
- Schema·페이지 연속성·중복·본문 Hash·문자 깨짐 검사
- MVP 및 운영 Corpus 혼입 차단 Metadata
- 대표 페이지 1·12·40·43·52쪽 렌더링 검수

제외 범위:

- Chunking·Embedding·Vector DB
- MVP 검색·화면 노출
- Gold Evidence 승인
- 전체 52쪽의 세부 시각 검수

## 생성 결과

| 항목 | 결과 |
|---|---:|
| 원본 PDF 페이지 | 52 |
| 생성 JSONL 페이지 | 52 |
| Section | 18 |
| 누락·중복 페이지 | 0 / 0 |
| 빈 본문 | 0 |
| 중복 본문 | 0 |
| 본문 Hash 불일치 | 0 |
| 문자 깨짐 의심 | 0 |
| QA 오류·경고 | 0 / 1 |
| `EXPERIMENT_ONLY` | 52 |
| `mvp_use=true` | 0 |

원본 PDF SHA-256:

```text
97C027CE75BEC40386307C867DD3983513CB70FAC687F2D2DB6F1167EC9CAEC8
```

생성 Dataset SHA-256:

```text
D9708B3877E4126DA7388906BC637EEB0BF69BEEF9B1B8E91454FF70A74ADF05
```

## 추출 및 검수 상태

| 상태 | 페이지 수 | 설명 |
|---|---:|---|
| `TEXT_EXTRACTED` | 47 | 자동 추출·정규화 완료, 전체 시각 검수 대기 |
| `VISUAL_SPOT_CHECKED` | 4 | 1·12·40·43쪽 대표 렌더링 대조 |
| `VISUALLY_REVIEWED` | 1 | 52쪽 이미지 기반 뒷표지 전사 |

명시적 보정 페이지:

- 1쪽: `Water Puri/f_ier`를 화면의 `Water Purifier`로 정정
- 40쪽: 중복 추출된 `작은 홀` 라벨을 화면 기준 한 번으로 정정
- 52쪽: 자동 추출 본문이 없어 화면을 기준으로 뒷표지 텍스트 전사

자동 추출문 전체를 임의 교정하지 않았으며, 보정한 페이지와 보정 ID는 각 JSONL
레코드의 `manual_correction_ids`에 기록했다.

## 범위 차단

모든 페이지는 다음 값을 가진다.

```text
scope_role=expansion
mvp_use=false
allowed_use=EXPERIMENT_ONLY
exact_sales_code=WPUIAC425SNW
version=REV.02
```

따라서 이번 결과는 실험 Corpus로만 사용할 수 있고 기존 JAC104 MVP 검색 인덱스나
제품 선택 화면에 자동으로 포함하지 않는다.

## 판정

```text
Experimental Corpus Text: READY
MVP Search Use: BLOCKED
Gold Evidence: REVIEW_REQUIRED
Production Corpus Expansion: NOT_AUTHORIZED
```

A1-2의 페이지 Dataset 생성과 구조 QA는 완료다. 나머지 47쪽의 전체 시각 검수는
별도 Backlog이며, Experiment Lab의 텍스트 검색 실험을 위한 구조적 차단 사유는 아니다.

## 산출물

- `data/processed/documents/manuals/expansion/manual_pages_iac425.jsonl`
- `data/schemas/processed/experimentalManualPage.schema.json`
- `data/tools/rag_experiments/build_iac425_pages.py`
- `data/tools/rag_experiments/qa_iac425_pages.py`
- `data/tools/tests/test_iac425_manual_corpus.py`
- `data/processed/validation/rag_experiments/iac425_manual_pages_qa.json`
