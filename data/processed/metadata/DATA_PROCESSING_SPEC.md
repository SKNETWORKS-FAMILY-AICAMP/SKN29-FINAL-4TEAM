# WaterCare 데이터 처리 명세

## 1. 기준 정보

- 데이터 버전: `0.8.0`
- 기준 생성 시각: `2026-07-27T00:00:00+09:00`
- MVP 판매 코드: `WPUJAC104DWH`
- 공식 문서: WPU-JAC104D·WPU-JCC104D REV.00, 44쪽
- 출처 분류: `official`, `team_designed`, `synthetic`
- 시간 표현: ISO 8601, `+09:00`

## 2. 원본·계보 정책

공식 PDF와 FAQ 원본은 외부 백업을 전제로 검증 후 삭제했다. `data/raw/`는
정책 파일 7개만 보관한다. 저장소에서 원본 재추출은 불가능하며 다음
자료를 영구 계보로 사용한다.

- 공식 URL과 수집 로그
- 원본 파일명·크기·SHA-256·페이지 수
- 모델·세대·개정 연결표
- 이미지 FAQ OCR·이미지 해시·사용자 검수 기록
- 원본·임시 데이터 삭제 보고서

## 3. 선언형 처리 구조

```text
config/pipeline.json
├─ faq/ocr_transcriptions.json
├─ rag/jac104_chunks.json
├─ synthetic/scenarios.json
└─ workflow/dataset_vocabulary.json
        ↓
tools/pipeline.py
        ↓
processed/** + synthetic/**
        ↓
static schemas + QA + final manifest
```

Python에는 OCR 원문, RAG 본문, 합성 이름·시나리오, Schema와 Markdown
본문을 넣지 않는다. 업무 정의는 JSON, 문서는 템플릿, 데이터 계약은
정적 JSON Schema를 기준으로 한다.

## 4. 데이터 규모

| 데이터 | 건수 |
|---|---:|
| JAC104D 매뉴얼 페이지 | 44 |
| FAQ 정규화 | 119 |
| 검수 OCR FAQ | 5 |
| 공식 FAQ 이미지 자산 | 10 |
| FAQ 후보 | 20 |
| MVP RAG 청크 | 7 |
| 근거 레지스트리 | 9 |
| 합성 사용자 | 16 |
| 합성 문의 | 24 |
| 상담 | 16 |
| 방문 | 5 |
| 상태 이력 | 110 |
| 감사 이벤트 | 110 |

## 5. RAG 정책

매뉴얼 37~39쪽의 무출수, 냉수 온도, 소음, 누수, 물맛·냄새, 출수량
저하, 순간온수 안전 7개 주제만 MVP 검색에 포함한다. 조건부 FAQ와
미검증 공통 FAQ는 검색 근거로 사용하지 않는다.

각 청크에는 문서·판매 코드·세대·개정·페이지·위험도·사용 안내·안전
조치·상담 조건·금지 조치·검증 상태를 둔다.

## 6. 합성 데이터 정책

- 실제 개인정보와 운영 연락처를 사용하지 않는다.
- 공개 정치인·기업인 등 유명 인물의 이름을 의도적으로 사용하지 않는다.
- 내부 UUID와 사람이 읽는 업무 번호를 분리한다.
- 상태 변경에는 `state_version`, `idempotency_key`, `correlation_id`를 둔다.
- 위험 문의에서 정상 사용 안내를 허용하지 않는다.
- 결정적 기준 시각과 ID를 사용한다.

## 7. 검증

- 설정 파일과 processed·synthetic JSON Schema
- ID 중복·FK·페이지·문서·근거 참조
- 모델·세대·FAQ 오염 차단
- 개인정보·내부 경로·구 코드·빈 본문
- canonical 상태와 안전 우선 업무 규칙
- 설정 materialization과 정식 파일 바이트 동등성
- 기존 래퍼와 통합 CLI 결과 동등성
- 두 번 생성했을 때 파일 해시 동일성

## 8. 실행

```powershell
python -B -m unittest discover -s data/tools/tests -v
python data/tools/pipeline.py qa --verify-rebuild
python data/tools/pipeline.py inventory
python data/tools/pipeline.py finalize
```

외부 패키지는 추가하지 않는다. PDF 원문 재처리가 필요한 경우에만 기존
선택 의존성인 `pdfplumber`를 사용할 수 있으나, 현재 원본 비보관
파이프라인은 정식 전처리 기준본과 보존 해시를 검증한다.
