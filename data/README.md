# WaterCare Data

공식 출처에서 검증한 전처리·RAG 데이터와 개인정보가 없는 합성 시연
데이터의 기준본입니다.

## 범위

- 데이터 버전: `0.8.0`
- MVP: `WPUJAC104DWH` / WPU-JAC104D·WPU-JCC104D REV.00
- 후속 확장: WPU-IAC425 공식 원본 무결성 검증만 완료, processed·RAG 생성 예정
- 검색 차단: WPU-IAC425, WPU-IAC506, JAC104 S세대, 미검증 공통 FAQ
- 위험도: `general`, `caution`, `danger`
- 사용 안내: `NORMAL`, `PARTIAL_STOP`, `TOTAL_STOP`, `PENDING_CONSULTATION`

## 단일 실행 명령

```powershell
python data/tools/pipeline.py build processed
python data/tools/pipeline.py build rag
python data/tools/pipeline.py build synthetic
python data/tools/pipeline.py qa --verify-rebuild
python data/tools/pipeline.py inventory
python data/tools/pipeline.py finalize
```

기존 `build_step*.py` 파일은 같은 명령으로 위임하는 호환 래퍼입니다.

## 기준본

- `config/`: 경로·수량·OCR·RAG·합성 시나리오·워크플로·대표 E2E 규칙
- `schemas/`: processed·synthetic·config 정적 JSON Schema
- `templates/`: 처리 명세와 QA 문서 템플릿
- `processed/`: 공식 전처리·RAG·근거·검증 결과
- `synthetic/`: 합성 Fixture·시나리오·기대 결과

## 원본 비보관

공식 PDF·FAQ 원본은 외부 백업을 전제로 검증 후 삭제했습니다.
`raw/`에는 정책 파일 7개만 유지하며, URL·SHA-256·OCR·검수·삭제 기록으로
계보를 추적합니다. `build processed`는 정식 전처리 기준본을 검증하고,
외부 원본 경로가 제공된 경우 보존 해시와 일치하는지 확인합니다.

## 결정성

기준 생성 시각은 `2026-07-27T00:00:00+09:00`입니다. 동일 설정으로 RAG와 합성
데이터를 두 번 생성했을 때 모든 정식 파일 해시가 같아야 합니다.
대표 E2E는 지침서·WBS·기획서·화면설계서의 지정 섹션과 실제
Fixture·근거·상태 전이가 동시에 일치해야 QA를 통과합니다.
