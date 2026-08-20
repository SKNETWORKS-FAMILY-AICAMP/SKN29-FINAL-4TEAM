# 이동윤 → 최지용: Backend Evidence 3모델 53건 확장용 AI 입력자료 회신 v0.1

## 1. 전달 상태

Backend 제품 확장과 3모델 구독 계약의 QA·main 반영을 기준으로, Backend Evidence
Importer·Canonical Crosswalk 구현에 필요한 AI 입력 계약을 고정했다. 이번 회신은
구현 입력 전달이며 공식 DB 적재, Runtime 활성화 또는 공동 E2E 완료를 의미하지 않는다.

머신 리더블 정본은 `ai/configs/three_model_backend_evidence_handoff.json`이다.
파일 Byte SHA-256은
`706A3E2D3DFE090501EFA72634F20E8AC11070BF847ECDC6CE17CAC8B0C3D86E`다.

## 2. Canonical Identity와 Schema

- 정본 경로: `ai/configs/canonical_evidence_identity_3model.json`
- 파일 Byte SHA-256:
  `AB98AA6CFE839366CB13ECC3839D72EE0AE99419AF85F702F0C2F1D05BDCA169`
- Chunk Set SHA-256:
  `5B022EA8F00B22FE8CF9E386D2FFE91A1A136E2C6237ED4B64BA9EDCB181A304`
- Schema: `ai/configs/schemas/CanonicalEvidenceIdentity53.schema.json`
- Schema SHA-256:
  `6B3D79508F7D7074CF83A68D5862B111888F55BFC0132C6904184DC9D386C366`
- 줄바꿈 계약: LF

전체 53건이며 모델별 구성은 `WPUJAC104DWH=15`, `WPUIAC425SNW=19`,
`WPUIAC606SNW=19`다. 각 Canonical 행의 필수 필드는 `chunk_id`, `document_id`,
`page_refs`, `model_code`, `product_generation`, `verification_status`,
`source_file_sha256`, `chunk_text_sha256`다.

실제 Chunk 본문은
`data/processed/structured/rag/expansion/rag_child_chunks_3model_v1.jsonl`에서 읽는다.
Importer는 `record_type=child`, `retrieval_role=SEARCH_CANDIDATE`,
`verification_status=TEXT_AND_VISUAL_VERIFIED`, `allowed_use=RAG_HANDOFF_ONLY`를 모두
검증해야 한다. Parent는 문맥·계보 자료이며 직접 검색 행으로 적재하지 않는다.

신규 Canonical ID는 `CHILD-*` 형식이다. 기존 Crosswalk의 `RAG-*` 전용 정규식은
확장해야 한다. Canonical ID를 UUID인 `knowledge_document_chunk.public_id`에 넣지 않고,
문서·페이지·본문 SHA-256으로 Backend Chunk를 유일하게 찾은 뒤
`knowledge_ai_chunk_crosswalk.canonical_chunk_id`에 보존한다.

## 3. Index Manifest

- 기대값: `ai/configs/three_model_index_target.json`
- 기대값 SHA-256:
  `04A94D7C72947DBA03DC27C5013DB6E0DA38EB0198FA32A61FEDD7F23804AC48`
- 실제 Manifest 예정 경로: `ai/configs/index_manifest_3model.json`
- Schema: `ai/configs/schemas/ThreeModelIndexManifest.schema.json`
- Schema SHA-256:
  `121BAA9F78AF8DA5B5F7EBECBA61388E37B8BE21D23507858A0F71620B8EBE56`

Manifest 기준은 `BAAI/bge-m3`, 고정 Revision
`5617a9f61b028005a4858fdac845db406aefb181`, 1024차원, Exact Search,
Index Version `2.0.0`, 전체 53건과 동일 Chunk Set SHA-256이다.

Backend가 원자적 Import 결과로 Embedding 53건과 모델별 `15/19/19`를 확인한 뒤 다음
명령으로 실제 Manifest를 생성한다.

```powershell
.\ai\.venv\Scripts\python.exe -m ai.scripts.generate_three_model_index_manifest `
  --indexed-at <UTC_ISO8601> `
  --confirmed-total 53 `
  --confirmed-jac104 15 `
  --confirmed-iac425 19 `
  --confirmed-iac606 19
```

공식 53×1024 Embedding Fixture 자체는 이 구현 입력 패키지에 포함하지 않았다. Backend
Importer 구현이 준비된 뒤 AI가 별도 생성하고 승인된 보호 채널로 전달해야 하며 Git,
문서와 채팅에는 Vector 본문을 남기지 않는다.

## 4. 검색 및 평가 계약

Backend의 `ProductModel.model_code`는 변환하지 않고 AI 요청의 `model_code`로 전달한다.
검색은 점수 계산 전에 `exact_sales_code == model_code`를 적용하며 교차 모델 Fallback은
허용하지 않는다. 현재 공통 검색 기준은 Top-5와 공식 검증 필수다.

- 평가 파일: `data/config/rag/three_model_evaluation_cases.json`
- 평가 파일 SHA-256:
  `B0316CE050C91C8900E805E85A5F8FFF836CCD2E04CDCF328437C2C68A70FBF1`
- Schema: `data/schemas/config/threeModelRagEvaluation.schema.json`
- Schema SHA-256:
  `991FA7F916CA57D471D12266D43E60E3C04A99DE888EC024E25900C0D996A2D8`

합격 기준은 정상 43건 모두 기대 Evidence Group의 검증 Variant 중 하나 이상이
Top-5에 포함되고, 부정 7건은 모두 검색 전에 No Evidence로 차단되는 것이다. 교차 모델,
Parent 직접 반환, 미검증 근거는 각각 0건이어야 한다. 기존 Disposable Candidate의
50/50 결과는 공식 DB 결과가 아니며, Readonly View 53건이 준비된 뒤 다시 실행한다.

## 5. Crosswalk 필수 검증

Backend는 다음 항목을 모두 확인해야 한다.

1. Identity 파일 Byte SHA-256과 Crosswalk에 저장할 Manifest SHA-256 일치
2. Identity Schema Version, 상태, Chunk ID 정렬·유일성 및 전체 53건
3. 모델별 15/19/19와 판매코드·세대 쌍 일치
4. Identity와 Index Manifest의 Index Version·Chunk Set SHA-256 일치
5. `document_id`, `page_refs`, Source SHA-256과 승인된 SourceDocument·Page 일치
6. `chunk_text_sha256`으로 활성 Backend Chunk가 정확히 1건 조회되는지 확인
7. Embedding 모델·Revision·1024차원·본문 SHA-256과 활성 Embedding 일치
8. 검증된 Model Scope, 승인 상태, 미해결 Data Quality Issue 0건 확인
9. Crosswalk·Readonly View 전체 53건 및 모델별 15/19/19 확인
10. Parent 직접 노출 0건과 AI Role의 SELECT-only 권한 유지

기존 Importer와 Crosswalk의 `EXPECTED_CHUNK_COUNT=7`, `APPROVED_CHUNK_COUNT=7`,
7행 전용 Fixture 검증 및 `RAG-*` 전용 ID 검증은 정본 계약에서 읽는 53건 기준으로
교체해야 한다.

## 6. AI 전체 회귀 잔여 1건

기존 2건 중 개인정보 테스트는 AI 담당 범위에서 수정했다.

- 테스트 ID:
  `test_provider_request_redacts_pii_and_excludes_raw_occurrence_condition`
- 기존 기대: 미등록·개인정보 형태의 모델 코드에서도 Provider가 호출되고
  `UNKNOWN_MODEL`로 마스킹
- 기존 실제: 최신 제품 Fail-closed Guard가 Provider 전에 차단하여 요청 목록 0건
- 조치: 지원 판매코드의 Provider 개인정보 비노출 테스트와 미등록 판매코드의
  Provider 호출 0회 테스트로 분리
- 결과: PASS

남은 실패는 다음 1건이다.

- 테스트 ID:
  `test_ai_owned_backend_integration_fixture[F02]`
- 시나리오: 정상 검색 결과 0건
- 기존 Fixture 기대값: `retry_count=0`
- 현재 Harness 실제값: `retry_count=1`
- 원인: Harness가 No Evidence를 `RETRY_RETRIEVAL`로 판정하고 동일 검색을 한 번 더
  실행함

이 항목은 단순 Fixture 오기가 아니라 Retry 정책 선택이 필요하다.

- 선택 A — No Evidence 재시도 0회: 기존 F02·일시 장애 한정 Retry 정책 유지,
  동일 Embedding·DB Query 반복 비용과 상담 전환 지연 없음. 권장안이다.
- 선택 B — Harness 의미 재시도 1회: 현재 Runtime을 유지하고 F02 Fixture·No Evidence
  예시·Retry 정책 문서를 `retry_count=1`로 변경한다. 모든 근거 0건 요청에 Embedding과
  DB Query가 한 번 추가된다.
- 선택 C — 원인별 분리: 정상 검색 0건은 0회, 실제 연결·Timeout·일시 오류만 1회,
  교차 모델·미검증 근거 차단의 재시도 여부는 별도로 결정한다.

현재 전체 AI Unit은 `338 passed`, `1 failed`, `5 warnings`, `7 subtests passed`다.
PM의 Harness Retry 결정 전에는 F02 기대값이나 Runtime을 임의 변경하지 않는다.

## 7. 현재 Gate

```ini
ai_backend_53_input_contract=READY
canonical_identity=READY_53
canonical_identity_schema=READY
index_manifest_schema_and_generator=READY
official_embedding_fixture=PENDING_GENERATION_AND_PROTECTED_DELIVERY
backend_importer_crosswalk_implementation=BACKEND_OWNER
official_readonly_50_case=NOT_RUN
ai_full_regression=HOLD_F02_RETRY_POLICY_DECISION
joint_e2e=HOLD_UNTIL_BOTH_SIDES_READY
```
