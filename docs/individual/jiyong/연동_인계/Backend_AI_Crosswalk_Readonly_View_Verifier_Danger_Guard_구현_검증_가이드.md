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

### 3.1 Backend·AI Embedding Fixture 교환 계약

```text
fixture_path=<REPOSITORY_ROOT>/.runtime/backend-ai/canonical_embedding_fixture_v1.json
schema_version=1.0.0
status=GENERATED_FROM_APPROVED_BASELINE_PENDING_DB_IMPORT
package_format=UTF8_COMPACT_SORTED_JSON
root_fields=schema_version,status,model_name,model_revision,dimension,index_version,chunk_set_sha256,embedding_dtype,rows
row_fields=chunk_id,chunk_text_sha256,embedding
embedding_dtype=FLOAT32
row_order=chunk_id_ASC
vector_dimension=1024
vector_rule=finite JSON numbers; Boolean·NaN·Infinity 금지
manual_rounding=NONE
nfc_policy=VALIDATE_ONLY_NO_MUTATION
json_options=ensure_ascii:false,sort_keys:true,separators:COMPACT,allow_nan:false
trailing_newline=NO
package_hash=SHA256_OF_EXACT_WHOLE_FILE_BYTES
package_hash_storage=EXECUTION_REPORT
db_replay_vector_tolerance=1e-6
```

공식 Runtime Fixture Producer는 이동윤의 AI Exporter로 제안한다. Backend Builder는
동일 계약의 회귀 검증용 Reference로 유지한다. 같은 파일의 전달 무결성은 전체 파일
SHA 일치로, 서로 다른 환경의 생성물 호환성은 Metadata 일치와 Vector `1e-6` 비교로
판정한다. 파일 내부에는 자기 자신의 SHA를 넣지 않는다. Root와 Row 필드 목록은
Contract v1의 정확한 전체 집합이며 추가 필드는 Fail-closed 처리한다.

JSON 숫자만으로 원래 Tensor dtype을 역증명할 수 없으므로 `embedding_dtype=FLOAT32`는
AI Producer의 명시적 보증값이다. Backend는 이 선언·1024차원·유한 숫자·정본 Byte를
검증하고, 실제 float32 생성 증거는 AI Exporter 실행 보고서에서 확인한다.

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
2. 대상은 기존 승인 Baseline이 있는 `waterbridge_team_integration`이며 다른 Writer를
   중지하거나 `other_active_writer=NO`를 확인한다.
3. 김은진 Host의 ACL 제한 저장소에 공식 PDF가 있어야 한다. 기대 크기는
   `5,131,906 bytes`, SHA-256은
   `0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C`다.
4. 해당 Process에만 `BACKEND_AI_OFFICIAL_SOURCE_PATH`를 주입한다.
5. `visits.0005`를 적용하지 않고 Evidence Migration 0009·0010을 준비한다.
6. `DEMO-OPERATOR-001`은 활성·합성 `OPERATOR`여야 한다.
7. DSN·Password·API Key·실제 원본 경로는 문서·채팅·로그에 남기지 않는다.

### 6.1 `visits.0005` HOLD Migration 계획

`visits.0005_replace_visit_result_assignment_fk`가 보류된 동안 인자 없는
`manage.py migrate`를 실행하지 않는다. 기존 통합 DB Baseline에서 다음 순서만 쓴다.

```powershell
$python = '.\backend\.venv\Scripts\python.exe'

& $python -B .\scripts\database\provision_team_integration.py
& $python -B .\scripts\database\provision_team_integration.py `
  --apply --confirm-database waterbridge_team_integration

& $python -B .\backend\manage.py showmigrations visits evidence --plan `
  --settings=config.settings.local

# visits.0005가 이미 [X]이면 역Migration하지 말고 즉시 중단한다.
& $python -B .\backend\manage.py migrate evidence 0010 `
  --settings=config.settings.local
& $python -B .\scripts\database\provision_team_integration.py `
  --apply --confirm-database waterbridge_team_integration
& $python -B .\backend\manage.py showmigrations visits evidence `
  --settings=config.settings.local
```

통과 기준은 `visits.0004=[X]`, `visits.0005=[ ]`, `evidence.0009=[X]`,
`evidence.0010=[X]`다. 새 빈 DB라서 다른 App Baseline도 필요한 경우 이 절차를
확대하지 않고 Host Owner가 App별 Target Migration 계획을 먼저 만든다.

### 6.2 원본·합성 Operator 사전점검

```powershell
$source = [Environment]::GetEnvironmentVariable(
  'BACKEND_AI_OFFICIAL_SOURCE_PATH', 'Process'
)
$sourceInfo = Get-Item -LiteralPath $source
$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash
if ($sourceInfo.Length -ne 5131906 -or
    $sourceHash -ne '0C6B94AF53F23211F5FE542CB7712109E4A769A6F42ED758DA7792FC62E44B2C') {
  throw 'official_source=BLOCKED'
}
'official_source=READY'

& $python -B .\backend\manage.py seed_demo_accounts `
  --settings=config.settings.local
& $python -B .\backend\manage.py shell `
  --settings=config.settings.local -c "from apps.accounts.models import User; ok=User.objects.filter(username='DEMO-OPERATOR-001', role_code=User.Role.OPERATOR, is_active=True, is_synthetic=True).exists(); print('demo_operator=' + ('READY' if ok else 'BLOCKED')); raise SystemExit(0 if ok else 1)"
```

성공 출력에는 원본의 실제 Host 경로를 포함하지 않는다.

## 7. Fixture 생성

공식 QA Fixture는 이동윤의 AI Exporter 병합 후 해당 실행 보고서의 명령으로 생성한다.
기대 기본 명령과 출력 경로는 다음과 같다.

```powershell
.\ai\.venv\Scripts\python.exe -B `
  .\ai\scripts\export_canonical_embedding_fixture.py

$fixture = '.\.runtime\backend-ai\canonical_embedding_fixture_v1.json'
$fixtureHash = (Get-FileHash -Algorithm SHA256 $fixture).Hash.ToLower()
```

Backend `scripts/database/build_ai_canonical_embedding_fixture.py`는 같은 계약을 확인하는
Reference Builder이며 공식 G1-A Producer 증거를 대신하지 않는다.

기대: `row_count=7`, `dimension=1024`, `embedding_dtype=FLOAT32`, 승인
Model·Revision, `row_order=chunk_id_ASC`, NFC 7/7. Fixture는 Git 제외 `.runtime`에
두고 정확한 파일 Byte SHA만 QA 증거에 기록한다.

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

### 11.1 Fixture 계약·QA 감사 보강 재검증

| 검증 | 결과 |
| --- | --- |
| 최종 결합 표적군 | `97 passed / 0 failed` |
| Fixture Builder·Importer·G1-B Audit 표적 | `65 passed / 0 failed` |
| Crosswalk·Provision·T-028B 보조 회귀 | `32 passed / 0 failed` |
| Django Check | `0 issues` |
| Migration Drift | `No changes detected` |
| Compile·`git diff --check` | PASS |
| Ruff | `NOT_RUN — 개발환경 패키지 없음` |

로컬 `waterbridge`에 읽기 전용 Audit를 실행한 결과 PostgreSQL `16.14`, pgvector
`0.8.6`, Evidence Migration 0009·0010, View 8열은 확인됐다. 다만 Crosswalk
`0/7`, Page Link `0/8`, View `0/7`, AI Readonly Role 설정 일부가 미완료라
`status=BLOCKED`였다. 이는 감사기가 Blocker를 정상 탐지했다는 증거이며 통합환경
READY 증거가 아니다. `--require-ready --require-team-database` 실행은 대상 DB 불일치도
탐지하고 의도한 Exit Code `1`을 반환했다.

### 11.2 이전 Importer 작성자 회귀 스냅샷

| 검증 | 역사 결과 |
| --- | --- |
| Importer 단독 | `29 passed / 0 failed` |
| Importer·Builder·Crosswalk·G1-B Unit | `71 passed / 0 failed` |
| Backend 전체 | `1160 passed / 23 skipped / 0 failed` |

작성자 테스트는 Synthetic 원본으로 검증기와 orchestration을 고정했다. 공식 PDF 기반
Dry-run·Apply·Replay, 팀 PostgreSQL·View·Role은 김은진 Host에서 실행해야 한다.

### 11.3 QA 명령·결과 증빙

Secret과 실제 Host 경로를 제외하고 다음 값을 같은 실행 보고서에 남긴다.

| 구간 | 필수 증빙 |
| --- | --- |
| 기준선 | 최종 `main` 40자리 SHA, 실행 시각, Python·PostgreSQL·pgvector 버전 |
| 환경 | 대상 DB명, `other_active_writer`, `visits.0005=HOLD_CONFIRMED` |
| 원본 | 기대 크기·공개 SHA 일치, Process 경로 주입 `YES/NO` |
| Fixture | Schema·Status·dtype·정렬·NFC·7×1024·파일 SHA |
| Import | Dry-run Rollback, 최초 Created 수치, Replay `created=0 updated=0` |
| Crosswalk | Crosswalk 7, Page Link 8, Replay Unchanged 7 |
| View·Role | View 8열·7행, View SELECT만 허용, Base Table·DML·CREATE 거부 |
| Audit | 공개 가능한 Audit JSON, Exit Code, Blocker 목록 |

고의 실패 검증은 공식 통합 DB의 정본 파일을 수정하지 않는다. 폐기형 QA DB와 복사한
Fixture에서 SHA·Schema·NFC 오류를 만들거나 자동 테스트로 Transaction Rollback을
검증한다.

## 12. 다음 Gate

1. 관련 파일만 Commit·Push하고 PM이 main에 병합한다.
2. 최종 main SHA와 QA 실행서 v0.4를 고정한다.
3. 김은진이 정책값·Object↔Runtime 매핑을 확인하고 공식 PDF로 독립 실행한다.
4. 환경 판정은 `g1a_runtime_prerequisites_ready`와
   `g1b_evidence_db_ready`로 분리한다. 실제 LLM·pgvector 호출 전제와 Secret 주입이
   확인되면 G1-A 준비 완료, Import·Crosswalk·View·Role Audit가 READY면 G1-B 준비
   완료다. 둘 다 `YES`일 때만 통합 `environment_ready=YES`로 기록한다.
5. `ENVIRONMENT_READY` 후 이동윤 G1-A, 최지용·이동윤 G1-B를 수행한다.
6. 독립 E2E와 PM 최종 Gate 전에는 P0 100% 완료를 선언하지 않는다.
