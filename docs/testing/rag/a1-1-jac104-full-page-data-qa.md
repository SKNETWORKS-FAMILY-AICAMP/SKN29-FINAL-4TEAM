# A1-1 JAC104/JCC104 전체 페이지 데이터 QA 결과

> 실행일: 2026-08-10 KST  
> 대상: `manual_pages_jac104d.jsonl` 44건  
> 판정: `STRUCTURAL_PASS_VISUAL_REVIEW_PENDING`

## 범위

이번 검사는 기존 JAC104/JCC104 전체 44페이지 JSONL만 대상으로 했다.

포함 범위:

- JSONL 및 `ManualPage` Schema 정합성
- 1~44쪽 연속성, 페이지·Page ID 중복
- 빈 본문과 본문 중복
- 페이지별 `text_sha256` 재계산
- 문자 깨짐·비정상 제어문자
- 문서·제품·세대·버전 Metadata 일관성
- 추출 방식·본문 상태·검수 상태 조합
- 첨부 원본 PDF와 `source_file_sha256` 일치 여부

제외 범위:

- IAC425 및 FAQ 정비
- 청킹·Embedding·Vector DB
- 44페이지 전체 시각 검수
- Production Corpus 확대 승인

## 결과

| 항목 | 결과 |
|---|---:|
| 기대·실제 페이지 | 44 / 44 |
| 페이지 범위 | 1~44 |
| 고유 Page ID | 44 |
| 누락·중복 페이지 | 0 / 0 |
| 빈 본문 | 0 |
| 중복 본문 | 0 |
| 본문 Hash 불일치 | 0 |
| 문자 깨짐 의심 | 0 |
| Schema·Metadata 오류 | 0 |
| 원본 PDF Hash | 일치 |
| QA 오류·경고 | 0 / 1 |

원본 PDF SHA-256:

```text
0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C
```

Dataset SHA-256:

```text
9E13354A7A0838EF825F1D401A6C999C33A24C2F811523F85B7E29D3C032E29F
```

## 검수 상태 해석

| 상태 | 페이지 수 | 해석 |
|---|---:|---|
| `TEXT_AND_VISUAL_VERIFIED` | 1 | 텍스트·화면 검수 완료 |
| `VISUALLY_REVIEWED` | 1 | 시각 전사 검수 완료 |
| `TEXT_EXTRACTED` | 42 | 구조·Hash는 정상이나 전체 시각 검수 미완료 |

2~43쪽은 `TEXT_EXTRACTED` 상태다. 따라서 전체 44쪽은 `EXPERIMENT_ONLY`
텍스트 Corpus로 사용할 수 있지만, 42쪽을 Gold Evidence 또는 Production 승인
근거로 자동 승격하면 안 된다.

이번 A1-1에서는 실제 오류가 발견되지 않았으므로 원본 JSONL을 수정하지 않았다.

## 판정

```text
Experimental Corpus Text: READY
Gold Evidence: REVIEW_REQUIRED
Production Corpus Expansion: NOT_AUTHORIZED
```

A1-1의 구조 QA는 완료다. 42쪽 시각 검수는 별도 검수 Backlog로 관리하며,
청킹·검색 실험을 시작하기 위한 구조적 차단 사유로 취급하지 않는다.

## 산출물

- `data/tools/rag_experiments/qa_manual_pages.py`
- `data/tools/tests/test_manual_corpus_qa.py`
- `data/processed/validation/rag_experiments/jac104_manual_pages_qa.json`

재실행 예시:

```powershell
python -m data.tools.rag_experiments.qa_manual_pages `
  --source-zip "<raw_data.zip 경로>" `
  --source-entry "메뉴얼 원본, 크롤링 원본/WPU-JAC104,WPU-JCC104-냉온정수기메뉴얼.pdf"
```
