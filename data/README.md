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
- 위 상태·분류값은 데이터셋 검증용이며 서비스 계약 매핑은 담당자 확인 대기

## 팀원별 전달 진입점

전체 파일을 복사하지 않고 소비자 프로필이 적재·참조·제외 대상을 구분합니다.

```powershell
python data/tools/pipeline.py handoff rag
python data/tools/pipeline.py handoff db-smoke
python data/tools/pipeline.py handoff db-full
python data/tools/pipeline.py handoff qa
```

- `rag`: 검증 청크 7건만 기본 인덱싱, 매뉴얼·FAQ는 참조·평가용
- `db-smoke`: 대표 6개 문의와 참조 엔티티, 상태 이력·감사 이벤트 제외
- `db-full`: 전체 24개 문의, 서비스 상태 매핑 후 확장 적재
- `qa`: 요약·Schema·무결성·품질·Manifest 확인

명령은 데이터를 복제하지 않고
`processed/metadata/consumer_handoff_manifest.json`에 기존 파일의 경로·역할·
레코드 수·크기·SHA-256을 기록합니다.

## 단일 실행 명령

```powershell
python data/tools/pipeline.py build processed
python data/tools/pipeline.py build rag
python data/tools/pipeline.py build synthetic
python data/tools/pipeline.py handoff
python data/tools/pipeline.py qa --verify-rebuild
python data/tools/pipeline.py inventory
python data/tools/pipeline.py finalize
```

기존 `build_step*.py` 파일은 같은 명령으로 위임하는 호환 래퍼입니다.

## 기준본

- `config/`: 경로·수량·OCR·RAG·합성 시나리오·전달 프로필·데이터 vocabulary
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
Fixture·근거·데이터셋 내부 상태 이력이 동시에 일치해야 QA를 통과합니다.
