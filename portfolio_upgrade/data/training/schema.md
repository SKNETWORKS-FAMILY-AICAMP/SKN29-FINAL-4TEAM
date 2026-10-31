# S06 — 정답 스키마 v1: PDF 대조 결과 반영

> **S06 상태:** PDF 내용 검수 15/15 완료. 행동 라벨 재판정 2건, 학습 사용 범위·모델 입력 근거 확정 미완료. `examples_v0.jsonl`은 보존. `examples_pdf_reviewed_v1.jsonl`은 **학습 전 검수 데이터**다.

## 1. 객체의 네 부분

| 부분 | 역할 | 모델 입력 여부 |
|---|---|---|
| `input` | 제품 코드·고객 발화·이미 확인된 조건·실제 검색 근거 | **예**. 단 `evidence`는 아직 비어 있음 |
| `target` | 기대 행동·고객 답변·필수 조치·금지 주장 | **정답**. 추론 입력에 몰래 넣지 않기 |
| `provenance` | 출처·PDF 해시/쪽·Gold ID·원래 S04 기록·데이터 분할 | 평가자/개발자용 메타데이터 |
| `review` | PDF 검수 상태·행동 재검토 여부·학습 제한 조건 | 데이터 관리용 메타데이터 |

## 2. 이번 검수로 확정한 필드

- `target.action` — 기존 S04 라벨 그대로 보존. 현재 `ANSWER`, `ASK`, `ESCALATE`만 15건. `TOOL_REQUEST`는 없음.
- `target.assistant_message` — **제안된 고객용 답변**을 PDF와 대조해 채움. 실제 서비스 결과가 아니다.
- `target.forbidden_claims` — 원문 적용 조건을 넘지 않도록 검수자가 정한 금지 주장. **제조사 원문 인용이 아니라 검수 기준**이다.
- `target.cited_evidence_ids` — 여전히 `null`. 실제 검색 결과/제공 문단이 확정되지 않아 인용의 타당성을 검증할 수 없음.
- `provenance.manual_pdf_source` — 문서 제목·개정번호·파일명·SHA-256, 페이지별 근거 요약을 추가.
- `review.pdf_reviewed` / `review.pdf_hash_matched` — 실제 PDF 확인 후 `true`.
- `review.action_label_review_status` — `consistent_with_manual` 또는 `needs_review_ASK_vs_ANSWER`.
- `review.training_ready` — **15건 모두 `false`**. 원문 검수만으로 학습 사용 승인·입력 근거/인용 계약까지 끝난 것이 아님.

## 3. `verified`가 의미하는 것과 의미하지 않는 것

`review.status=verified`는 **원본 PDF에서 조치의 적용 조건과 응답 초안을 확인했다**는 뜻이며 다음을 보증하지 않는다.

- 기존 RAG 검색기가 해당 근거를 실제로 찾았는가?
- 모델의 API가 이 답변을 실제로 생성했는가?
- 합성 데이터나 원본 설명서를 SFT 학습에 사용할 권한/사용 조건이 정리됐는가?
- 학습한 모델이 다른 질문에 일반화되는가?

버튼명 혼동 2건은 PDF 원문 자체는 검수했어도 `ASK` 라벨에 반론이 있어 `needs_review`로 남겨 둔다.

## 4. 학습 전 Gate (S07~S08)

1. **행동 판단:** 버튼명 2건 `ASK`/`ANSWER` 판정 규칙 통일. 원본 S04 라벨을 덮어쓰지 말고 별도 최종 결정·근거 기록.
2. **인덱스 정합성:** `NO_INDEX_GOLD_DESPITE_PDF_EVIDENCE` 사례 2건과 팀 `safe_actions` 누락 3건을 **별도 근거 보강** 대상으로 관리.
3. **학습 데이터 사용 범위:** S04 `source_use_limit`가 오프라인 평가용으로 작성된 이유와 원본 사용설명서/합성 자료의 라이선스·재배포 조건 확인.
4. **입력 계약:** 실제 검색기의 문서 텍스트·제품 코드·인용 ID를 기준선과 SFT 모두에 동일하게 주는 S08 설계.
5. **누출 검사:** `train`만 데이터 생성에 사용. Dev 6건, Holdout 6건은 학습/문구 복제에 사용하지 않는다.

**검수 기록:** [`s06_review_cards.md`](s06_review_cards.md), [`s06_pdf_review_summary.json`](s06_pdf_review_summary.json), [`s06_pdf_review_log.csv`](s06_pdf_review_log.csv).
