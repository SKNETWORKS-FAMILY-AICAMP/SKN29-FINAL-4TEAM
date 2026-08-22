# Backend–AI Readonly View 검색 계보 보완 구현·검증

> 작성일: 2026-08-22
>
> 작성자: 최지용(Backend·DB)
>
> 기준 소스: `a77f04ae433fe2bcff1672b519720773c356c6d8`
>
> 상태: 작성자 표적 검증 완료 / 실제 PostgreSQL·AI 50 Case 재검증 대기

## 1. 작업 목적

3모델 공식 Evidence 53건은 Backend에 적재할 수 있었지만,
AI Readonly View의 `metadata`에는 50 Case 판정에 필요한 검색 계보 4개가
모두 노출되지 않았다.

- `evidence_group_id`
- `source_variant_id`
- `parent_id`
- `retrieval_role`

이 상태에서는 제품별 검색 결과가 올바른 근거 Group·Variant·Parent에서
나왔는지 AI와 QA가 같은 기준으로 대조하기 어렵다.

## 2. 확인한 원인

- `evidence_group_id`, `source_variant_id`
  - 3모델 Chunk Metadata에는 저장됐지만 View에서 누락됐다.
- `parent_id`, `retrieval_role`
  - 승인 JSONL 입력값을 Importer가 검증했지만 DB에는 저장하지 않았다.
- 기존 View는 8개 열과 Readonly Role 경계는 유지했으나 위 계보 계약이 부족했다.

## 3. 구현 내용

### 3.1 신규 적재

3모델 Importer가 신규 `DocumentChunk.metadata`에 아래 값을 함께 저장한다.

- 승인 원본의 `parent_id`
- 승인 원본의 `retrieval_role=SEARCH_CANDIDATE`

기존 Group·Variant 값과 함께 네 계보 값이 동일 Chunk에 보존된다.

### 3.2 기존 53건 Replay 호환

이전 코드로 적재된 Chunk에는 `parent_id`, `retrieval_role`이 없다.
정확한 구형 Metadata와 일치하는 경우에는 Replay를 허용하되,
기존 Evidence 행을 임의로 갱신하지 않는다.

명시된 `parent_id` 또는 `retrieval_role`이 승인값과 다르면 Importer가 중단한다.
따라서 구형 데이터 호환을 이유로 잘못된 계보를 허용하지 않는다.

### 3.3 Additive Migration

신규 Migration:

`evidence.0013_expand_backend_ai_rag_lineage_metadata`

기존 Migration 파일을 수정하지 않고 `backend_ai_rag_chunks_v1` View만 교체한다.
View 열 수와 이름은 유지하고 `metadata` JSON에 네 계보 값을 추가한다.

기존 3모델 행의 누락값은 다음 조건을 모두 만족할 때만 안전하게 보완한다.

- Canonical ID가 `CHILD-*` 형식이다.
- Chunking Version이 `rag_child_chunks_3model/1.0.0`이다.
- Canonical ID의 제품·페이지가 실제 DB 제품·Primary Page와 일치한다.
- Group·Variant가 비어 있지 않다.
- 기존 Parent가 있으면 계산된 Parent와 일치한다.
- 기존 Retrieval Role이 있으면 `SEARCH_CANDIDATE`와 일치한다.

조건을 만족하지 않는 CHILD 행은 View에서 제외한다.
Rollback 시에는 `evidence.0010`의 기존 View 정의로 복구한다.

## 4. 변경하지 않은 범위

- View의 8개 열과 AI Readonly Role 권한
- SourceDocument·Page·Embedding·Crosswalk 원장 행
- Web·Mobile·AI 코드
- 공용 `scripts/**`
- 공개 Backend API와 State Machine
- `visits.0005` P1 HOLD
- 공식 PDF·Embedding Fixture·Secret

## 5. 작성자 검증

표적 테스트:

- `test_ai_three_model_evidence_import.py`
- `test_ai_chunk_crosswalk.py`

결과:

- `31 passed`
- Evidence Unit 전체: `251 passed / 9 skipped`
- 9개 Skip은 명시적 PostgreSQL Catalog·Constraint 전용 항목이다.
- 신규 53건의 네 계보 저장 확인
- 동일 Package Replay 변경 0 확인
- 구형 Metadata Replay 시 기존 행 비변경 확인
- 잘못된 Parent·Retrieval Role Fail-closed 확인
- View 계보 필드·CHILD Guard·Read-only SQL 계약 확인
- Django Check: PASS
- Migration drift: 없음

## 6. 아직 완료로 보지 않는 범위

작성자 검증은 실제 PostgreSQL View 결과와 AI 50 Case PASS를 대신하지 않는다.
다음 항목은 main 병합 후 동일 기준 환경에서 확인해야 한다.

1. Migration Plan에 `evidence.0013`만 추가되고 `visits.0005`는 제외되는지
2. PostgreSQL에서 기존 View 8열과 Row 수가 보존되는지
3. 53개 CHILD 행의 네 계보가 모두 비어 있지 않은지
4. AI Readonly Role이 View SELECT만 허용하는지
5. JAC104 결과에 IAC425·IAC606 근거가 섞이지 않는지
6. 50 Case Positive·미승인 제품 정책 결과가 계약과 일치하는지

## 7. 후속 인계 기준

- PM: `jiyong` 후보를 main에 병합
- 김은진: Migration·PostgreSQL View·Role·53건 계보 독립 검증
- 이동윤: QA 준비 확인 후 actual AI 50 Case와 G2·G3 실행
- 한예나·양정현: G2·G3 결과가 고정된 뒤 동일 환경의 G4 화면 실측

이번 변경은 G1 Backend·DB Blocker를 해소하는 후보이며,
G2~G6 완료나 최종 E2E PASS를 의미하지 않는다.
