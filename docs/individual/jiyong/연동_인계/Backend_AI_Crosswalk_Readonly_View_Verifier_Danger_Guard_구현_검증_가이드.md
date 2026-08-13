# Backend·AI G1-B 공식 Evidence 7건 구현·검증 가이드

> 갱신: 2026-08-13 KST
>
> 작성 기준: `jiyong@6ae659f12c02c4abc72cb6b2645e1669c76d571d` + 로컬 후보
>
> 상태: `AUTHOR_CODE_VERIFIED / POLICY_AND_HOST_MAPPING_PENDING / PUBLISH_PENDING`

## 1. 목적과 범위

공식 RAG 7건을 Backend 정본 계층에 멱등 적재하고 Canonical Chunk ID를 연결해
AI Readonly View가 7행을 반환하도록 준비한다.

이번 변경은 Evidence Import·Crosswalk Replay·출처 Fail-closed만 다룬다. AI LLM,
Retriever, 공개 API/DTO, 화면, 팀 DB Secret은 변경하지 않는다.

## 2. 구현 파일

| 역할 | 파일 |
| --- | --- |
| 고정 입력·SHA·기대 건수 | [`backend_ai_canonical_import_v1.json`](../../../../data/config/evidence/backend_ai_canonical_import_v1.json) |
| 7×1024 Fixture 생성 | [`build_ai_canonical_embedding_fixture.py`](../../../../scripts/database/build_ai_canonical_embedding_fixture.py) |
| 입력·DB 불변조건 | [`canonical_evidence_importer.py`](../../../../backend/apps/evidence/services/canonical_evidence_importer.py) |
| Dry-run·Apply 명령 | [`import_ai_canonical_evidence.py`](../../../../backend/apps/evidence/management/commands/import_ai_canonical_evidence.py) |
| Crosswalk 멱등 보강 | [`sync_ai_canonical_crosswalk.py`](../../../../backend/apps/evidence/management/commands/sync_ai_canonical_crosswalk.py) |
| Import 회귀 | [`test_ai_canonical_evidence_import.py`](../../../../backend/tests/unit/evidence/test_ai_canonical_evidence_import.py) |
| Builder 회귀 | [`test_ai_canonical_embedding_fixture_builder.py`](../../../../backend/tests/unit/evidence/test_ai_canonical_embedding_fixture_builder.py) |
| Crosswalk 회귀 | [`test_ai_chunk_crosswalk.py`](../../../../backend/tests/unit/evidence/test_ai_chunk_crosswalk.py) |

## 3. 고정 입력과 Source Metadata

- Source Inventory: `SRC-JAC104D-MANUAL`
- Manual Page: 37·38·39
- RAG Chunk·Canonical Identity: 각 7건
- Index: `BAAI/bge-m3`, 고정 Revision, 1024차원, Exact Search
- Product: `WPUJAC104DWH`, Generation `D`
- 원문 SHA: `0C6B94AF...E44B2C`
- Chunk Set SHA: `175065B3...C9958`
- 공식 조회 URL과 이용약관 URL은 분리 저장
- 이용약관 URL: `https://www.skmagic.com/introduce/terms/termsService?tabId=tabStieTerms`
- License Note: 내부 QA·RAG 한정, 원문 비공개·재배포 전 별도 권리 확인
- Object Key: `object://official-sources/mvp/<document_code>/<sha256>.pdf`

이용약관은 사이트 약관이며 매뉴얼 RAG 이용허락 자체가 아니다. License Note와
Object Namespace는 QA 인계 제안값을 구현한 후보이므로 정책·Host Mapping 확인 전
`APPROVED_POLICY`로 확대하지 않는다.

## 4. Source Fail-closed

Importer는 다음 조건을 DB 조회 전에 확인한다.

1. 세 Metadata의 누락·빈값·공백·주변 공백 거부
2. 고정 HTTPS 이용약관 URL 외 값 거부
3. 고정 `object://official-sources/...` Key 외 값 거부
4. CLI가 아닌 Process 환경 `BACKEND_AI_OFFICIAL_SOURCE_PATH`만 사용
5. Runtime 원본이 절대경로의 File인지, 크기·SHA-256이 Inventory와 같은지 확인
6. 오류·성공 출력에 실제 Runtime 경로 미포함

현재 구현은 Runtime 원본 파일과 Object Key를 SHA로 연결한다. 실제 Object Storage
존재를 확인하는 Resolver는 없으므로 `source_object_exists=PASS`라고 기록하지 않는다.

## 5. 기대 DB 결과

```text
IngestionBatch=1, SourceDocument=1, DocumentPage=3
DocumentModelScope=1, DocumentChunk=7, ChunkEmbedding=7
Crosswalk=7, CrosswalkPageLink=8, ReadonlyViewRow=7
```

- `IngestionBatch.status=SUCCEEDED`
- `SourceDocument.status=APPROVED`, `dataset_scope=MVP`
- 7개 Chunk는 같은 SourceDocument를 참조
- Inventory 대문자 Hash는 검증 후 DB에 소문자로 저장
- 기존 자연키의 의미가 다르면 Update하지 않고 실패

## 6. 실행 전제

1. 게시·병합된 최종 `main` 40자리 SHA를 Clean Checkout한다.
2. 김은진 Host의 ACL 제한 저장소에 공식 PDF가 있어야 한다.
3. 해당 Process에만 `BACKEND_AI_OFFICIAL_SOURCE_PATH`를 주입한다.
4. `waterbridge_team_integration`, Migration 0009·0010, synthetic Operator를 준비한다.
5. DSN·Password·실제 원본 경로는 문서·채팅·로그에 남기지 않는다.

## 7. Fixture 생성

```powershell
.\ai\.venv\Scripts\python.exe -B -m `
  scripts.database.build_ai_canonical_embedding_fixture

$fixture = '.\.runtime\backend-ai\canonical_embedding_fixture_v1.json'
$fixtureHash = (Get-FileHash -Algorithm SHA256 $fixture).Hash.ToLower()
```

기대: `row_count=7`, `dimension=1024`, 승인 Model·Revision. Fixture는 Git 제외
`.runtime`에 두고 SHA만 QA 증거에 기록한다.

## 8. Import Dry-run·Apply·Replay

```powershell
$python = '.\backend\.venv\Scripts\python.exe'
$env:BACKEND_AI_OFFICIAL_SOURCE_PATH = '<HOST_PROCESS_ONLY_PATH>'

& $python -B .\backend\manage.py import_ai_canonical_evidence `
  --settings=config.settings.local --embedding-fixture $fixture `
  --embedding-fixture-sha256 $fixtureHash --verified-by DEMO-OPERATOR-001

& $python -B .\backend\manage.py import_ai_canonical_evidence `
  --settings=config.settings.local --embedding-fixture $fixture `
  --embedding-fixture-sha256 $fixtureHash --verified-by DEMO-OPERATOR-001 `
  --apply --confirm-database waterbridge_team_integration
```

Apply 명령을 같은 입력으로 다시 실행한다. 최초는 기대 행만 Create·Update 0,
Replay는 Create/Update 0·기존 행과 Timestamp 불변이어야 한다. 출력에는 공개 가능한
원본·Fixture SHA와 Created/Updated/Unchanged 수치만 남긴다.

## 9. Crosswalk·READY Gate

```powershell
& $python -B .\backend\manage.py sync_ai_canonical_crosswalk `
  --settings=config.settings.local
& $python -B .\backend\manage.py sync_ai_canonical_crosswalk `
  --settings=config.settings.local --apply --verified-by DEMO-OPERATOR-001
& $python -B .\scripts\database\provision_team_integration.py `
  --apply --confirm-database waterbridge_team_integration
& $python -B .\scripts\database\audit_backend_ai_g1b_readiness.py `
  --require-ready --require-team-database
```

Crosswalk Apply를 한 번 더 실행해 `created=0 updated=0 unchanged=7`을 확인한다.
최종 기대는 Audit READY, Crosswalk 7/7, View 8열·7행, AI Role은 View SELECT만 허용이다.

## 10. 실패·복구

- Dry-run은 전체 DB 제약을 실행한 뒤 항상 Rollback한다.
- Import 실패는 단일 Transaction 전체 Rollback이며 부분 Row를 남기지 않는다.
- Crosswalk 실패는 별도 Atomic Transaction 전체 Rollback이다.
- 수동 DELETE·SQL·임의 ORM·Disposable Vector 초기화를 사용하지 않는다.
- 복구가 필요하면 Host Owner가 폐기형 DB를 재생성해 Migration부터 반복한다.

## 11. 작성자 검증 결과

| 검증 | 결과 |
| --- | --- |
| Importer 단독 | `29 passed / 0 failed` |
| Importer·Builder·Crosswalk·G1-B Unit | `71 passed / 0 failed` |
| Backend 전체 | `1160 passed / 23 skipped / 0 failed` |
| Django Check | `0 issues` |
| Migration Drift | `No changes detected` |
| Compile·`git diff --check` | PASS |
| Ruff | `NOT_RUN — 개발환경 패키지 없음` |

작성자 테스트는 Synthetic 원본으로 검증기와 orchestration을 고정했다. 공식 PDF 기반
Dry-run·Apply·Replay, 팀 PostgreSQL·View·Role은 김은진 Host에서 실행해야 한다.

## 12. 다음 Gate

1. 관련 파일만 Commit·Push하고 PM이 main에 병합한다.
2. 최종 main SHA와 QA 실행서 v0.4를 고정한다.
3. 김은진이 정책값·Object↔Runtime 매핑을 확인하고 공식 PDF로 독립 실행한다.
4. `ENVIRONMENT_READY` 후 이동윤 G1-A, 최지용·이동윤 G1-B를 수행한다.
5. 독립 E2E와 PM 최종 Gate 전에는 P0 100% 완료를 선언하지 않는다.
