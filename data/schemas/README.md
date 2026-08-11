# Data Schemas

모든 JSON Schema는 Draft 2020-12 기준이며 `additionalProperties: false`로
정의합니다.

## processed

- `manualPage.schema.json`: 공식 매뉴얼 페이지 레코드
- `faqNormalized.schema.json`: FAQ 스냅샷 정규화 레코드
- `faqOcrVerified.schema.json`: 이미지 FAQ 사용자 검수 전사
- `officialAsset.schema.json`: 검수 완료 공식 FAQ 이미지 자산과 사용 위치
- `faqCandidate.schema.json`: FAQ 적용성·검색 정책 후보
- `ragChunk.schema.json`: JAC104D 전용 RAG 청크
- `evidenceRegistry.schema.json`: 공식·조건부·제외 근거 정책
- `sourceInventory.schema.json`: 삭제 전 원본 계보

## synthetic

사용자·제품·구독·문의·상담·방문·후속확인·관리 이력·감사 이벤트와
기대 워크플로를 검증하는 엄격한 데이터 Schema입니다.

- `scenarioSubsetItem.schema.json`: 업무 흐름별 시나리오 부분집합 항목

## config

- `pipeline.schema.json`: 버전·모델·경로·수량·템플릿·설정 Schema 연결
- `ocrTranscriptions.schema.json`: 사용자 검수 OCR와 이미지 해시
- `ragDefinitions.schema.json`: RAG 7건과 근거 9건의 선언형 정의
- `syntheticScenarios.schema.json`: 합성 이름·시나리오·materialization
- `datasetVocabulary.schema.json`: 데이터셋 상태·위험도·사용 안내 분류값
- `consumerProfiles.schema.json`: RAG·DB·QA 전달 프로필
- `processed/experimentalManualPage.schema.json`: MVP와 분리된 확장 매뉴얼의 실험용 페이지 계약
- `representativeCase.schema.json`: 대표 문서·ID·근거·상태·수량 데이터 불변식

설정 Schema도 데이터 QA와 단위 테스트에서 검증합니다.
