# Data Tools

`pipeline.py`가 선언형 설정, 정적 JSON Schema와 문서 템플릿을 사용하는
단일 실행 진입점입니다.

```powershell
python data/tools/pipeline.py build processed
python data/tools/pipeline.py build rag
python data/tools/pipeline.py build synthetic
python data/tools/pipeline.py handoff rag
python data/tools/pipeline.py handoff db-smoke
python data/tools/pipeline.py handoff db-full
python data/tools/pipeline.py handoff qa
python data/tools/pipeline.py qa
python data/tools/pipeline.py inventory
python data/tools/pipeline.py finalize
```

## 선언형 기준본

- `data/config/pipeline.json`: 모델·버전·경로·기대 건수
- `data/config/faq/ocr_transcriptions.json`: 사용자 검수 OCR
- `data/config/rag/jac104_chunks.json`: RAG 청크와 근거 정의
- `data/config/synthetic/scenarios.json`: 이름·시나리오·검증 완료 Fixture
- `data/config/workflow/dataset_vocabulary.json`: 데이터셋 검증용 상태·분류값. 서비스 계약 매핑은 담당자 확정 대기
- `data/config/handoff/consumer_profiles.json`: RAG·DB Smoke·DB Full·QA 전달 파일과 선택 조건
- `data/templates/**`: 생성 문서 템플릿
- `data/schemas/**`: 생성하지 않는 정적 데이터 계약

원본 비보관 정책 때문에 `build processed`는 정식 전처리 데이터와 계보를
검증합니다. `--manual`, `--faq`를 제공하면 보존된 SHA-256과 일치하는지
추가 검사하며, `data/.temp` 입력은 거부합니다.

## 호환 명령

기존 자동화가 깨지지 않도록 다음 파일명을 얇은 래퍼로 유지합니다.

- `build_step2.py` → `build processed`
- `build_step3.py` → `build rag`
- `build_step4.py` → `build synthetic`
- `build_step5.py` → `qa`
- `build_step6_inventory.py` → `inventory`
- `build_step6_finalize.py` → `finalize`

래퍼는 기존 인자와 종료 코드를 유지하며 업무 데이터, Schema 또는 문서
본문을 포함하지 않습니다.

## 검증 범위

- JSON Schema 필수값·타입·enum·추가 필드
- ID 중복과 FK·근거 참조
- 위험 문의의 정상 사용 안내 차단
- 데이터셋 상태값과 시나리오 materialization 정합성
- 금지 코드와 내부 로컬 경로 노출
- 같은 설정으로 반복 생성했을 때 바이트 동등성

## 전달 Manifest

`handoff` 명령은 새 Fixture 사본을 만들지 않습니다. 기존 기준본의 경로,
용도, 레코드 수, 크기와 SHA-256을
`data/processed/metadata/consumer_handoff_manifest.json`에 기록합니다.

`db-smoke`는 대표 6개 시나리오만 선택하며 상태 이력·감사 이벤트를
제외합니다. `db-full`의 상태·이벤트 관련 파일은 서비스 담당자의 필드
매핑 확인 후 적재합니다.
