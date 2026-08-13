# 이동윤 → 최지용: AI·RAG G1-A Embedding 연계·로컬 Runtime 사전 협업 회신 v0.3

## 1. 회신 범위와 판정

- 요청 문서: `20260813_최지용_to_이동윤_AI_RAG_G1A_Embedding연계_로컬Runtime_사전협업요청_v0.3.md`
- 검증 Commit: `111da4bcd6fd8cb7e019e545254d55b3ad7406ca`
- 검증 일자: 2026-08-13 KST
- 사전 준비 판정: `READY_FOR_IMPORTER_SCHEMA_AGREEMENT`
- Embedding 제공 판정: `REPRODUCIBLE_GENERATION_ONLY`
- 팀 G1-A 판정: `WAITING_ENVIRONMENT_READY`

승인 청크 7개의 Canonical ID·원문 SHA-256·Chunk-set SHA-256·Manifest는 모두
일치한다. 고정된 `BAAI/bge-m3` Revision으로 실제 7개 Vector를 메모리에서
재생성해 `7 × 1024`, L2 Normalize를 확인했다. Vector 값 자체는 출력하거나
파일로 저장하지 않았다.

현재 Backend Importer의 최종 Fixture Schema와 저장 경로가 합의되지 않았고,
저장소에 승인된 Vector Exporter도 없다. 따라서 지금 Export 파일을 정본으로
만들지 않고 `REPRODUCIBLE_GENERATION_ONLY`로 회신한다.

## 2. 정본 3개 정합성

검증 대상은 다음 세 파일이다.

1. `data/processed/structured/rag/mvp/rag_verified_sample.jsonl`
2. `ai/configs/canonical_evidence_identity.json`
3. `ai/configs/index_manifest.json`

확인 결과:

```text
chunk_count=7
canonical_chunk_ids=7 unique / source set과 일치
chunk_text_sha256=7/7 PASS
document_id/page_refs/model_code/product_generation/verification_status/source_hash=7/7 PASS
chunk_set_sha256=175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958
identity_manifest_chunk_set_match=PASS
embedding_model=BAAI/bge-m3
embedding_revision=5617a9f61b028005a4858fdac845db406aefb181
embedding_dimension=1024
index_type=exact_search
```

개별 원문 Hash 재계산 결과:

| Chunk ID | SHA-256 | 결과 |
| --- | --- | --- |
| `RAG-WPUJAC104DWH-COLD-TEMPERATURE-001` | `974aa279847e6c6d662683581a0763172ec8ace7e60ff57221f7c8fa892fbbdb` | PASS |
| `RAG-WPUJAC104DWH-INSTANT-HOT-WATER-SAFETY-001` | `219bfbb732f5b63ebc5467f2f2a36affd77318ac64d93b9ba353711be0a9775e` | PASS |
| `RAG-WPUJAC104DWH-LEAK-001` | `0ce7e1e7bdaed8eadb3011f84d0cd33f8462797a0357047f3d816b1e6187b602` | PASS |
| `RAG-WPUJAC104DWH-LOW-FLOW-001` | `6b063e0d66605bdf3c7b9da65111653ea48b76d7bbf0ee3f108c24261e5c3ca0` | PASS |
| `RAG-WPUJAC104DWH-NO-WATER-001` | `b02d26766304525658ffbb388e0b60c99c256719a8a730ac5ea87d9d8d0e8927` | PASS |
| `RAG-WPUJAC104DWH-NOISE-001` | `843b00524a730b43968247bbe4de0b0e802d04cb3afce551873125e2c312078c` | PASS |
| `RAG-WPUJAC104DWH-TASTE-ODOR-001` | `73e5f015b56f9143fbfe46190a4cb1e35b67b41f7db74b80daec2916531f48b3` | PASS |

정본 파일 자체의 SHA-256은 다음과 같다.

```text
ai/requirements.lock=088B1DE2E7C7C379C34F84D057B7D0A179EFFD96B2AB2CF50EAAFDFFC4D44E86
data/processed/structured/rag/mvp/rag_verified_sample.jsonl=2BF3582E42A309D846BC383BE9C3E08874512318DD4046082498DBFBC8584DD0
ai/configs/canonical_evidence_identity.json=925088A352A81180B51E5418EB3152A1244ABA3DA07569712C4D903468220B85
ai/configs/index_manifest.json=C71488A7F0A9226D804FBE0BEE3C4B911B926B4F9EF39E026DC93420B8A03D66
```

## 3. Embedding 재현 결과

실제 모델을 CPU에서 로드해 정본 7개 `chunk_text`를 한 번에 생성했다.

```text
result=PASS
chunk_count=7
dimensions=[1024]
model=BAAI/bge-m3
revision=5617a9f61b028005a4858fdac845db406aefb181
normalized=true
min_l2_norm=0.99999996
max_l2_norm=1.00000009
elapsed_seconds=13.116
vector_values_logged=false
```

현재 저장소의 재현 명령은 아래와 같다. 이 명령은 `AI_VECTOR_DSN`이 가리키는
쓰기 가능한 **개인 격리·일회성 pgvector**에서만 사용한다. 팀 DB의 AI Readonly
DSN에는 실행하지 않는다.

```powershell
$env:AI_EMBEDDING_REVISION='5617a9f61b028005a4858fdac845db406aefb181'
# AI_VECTOR_DSN은 승인된 개인 격리·일회성 pgvector 환경변수로 별도 주입
.\ai\.venv\Scripts\python.exe -m ai.scripts.build_vector_index
```

의존성 SSOT는 `ai/requirements.lock`이다. 주요 고정 버전은 다음과 같다.

```text
sentence-transformers==5.5.1
torch==2.13.0
transformers==5.14.1
psycopg==3.2.9
Python=3.13.13
```

## 4. Backend Importer 입력 제안

최종 Schema·경로는 최지용의 Importer 계약과 합의 후 고정한다. 현재 제안하는
최소 Row 필드는 다음과 같다.

```text
chunk_id
text_sha256
model
revision
dimension
vector
```

추적 강화를 위해 다음 필드도 후보로 제안한다.

```text
index_version
chunk_set_sha256
normalized
```

Package Hash는 최종 Schema가 합의된 뒤 아래 방식으로 산정하는 것을 제안한다.

1. Row를 `chunk_id` 오름차순으로 정렬한다.
2. 각 Row를 UTF-8 Canonical JSON으로 직렬화한다.
3. Key는 사전순, 공백 없음, 문자열은 NFC, 줄바꿈은 LF로 고정한다.
4. Vector 숫자의 타입·직렬화 정밀도는 Importer 계약에서 고정한다.
5. 고정된 전체 Package Byte에 SHA-256을 계산한다.

Vector 부동소수점 직렬화 규칙을 합의하기 전에 Package Hash 기대값을 먼저
고정하면 실행환경에 따른 미세한 표현 차이가 생길 수 있으므로, 현재는 방법만
제안하고 Hash 값은 생성하지 않는다.

## 5. AI 회귀 검증

```powershell
.\ai\.venv\Scripts\python.exe -m pytest ai\tests\unit -q
.\ai\.venv\Scripts\python.exe -m pip check
.\ai\.venv\Scripts\python.exe -m ai.scripts.verify_local_runtime
```

결과:

```text
AI Unit=219 passed, 0 failed, 0 skipped, 5 warnings, 7 subtests passed, exit 0
pip check=PASS
Schema/Canonical 표적=1 passed, exit 0
GUIDANCE_ONLY/Timeout 504/No-Evidence/Danger Fail-closed=전체 Unit 회귀 내 PASS
local_actual_llm=NOT_RUN
local_runtime_verifier=FAIL, exit 1
local_runtime_blocker=OPENAI_API_KEY 미주입
```

`verify_local_runtime`의 Exit 1은 제품 Assertion 실패가 아니라 승인된 실제 OpenAI
Key가 없는 환경에서의 Fail-closed 결과다. Unit·Mock 결과를 실제 LLM PASS로
확대하지 않는다.

## 6. 공동 G1-A 선행조건

다음 신호를 받기 전까지 팀 G1-A는 실행하지 않는다.

```text
audit=READY / exit 0
crosswalk=7/7
backend_ai_rag_chunks_v1=8 columns / 7 rows
role_matrix=1 passed / 0 skipped
ai_view_select=ALLOW
ai_base_table_select=DENY
ai_view_dml=DENY
ai_schema_create=DENY
```

환경 준비 후 `waterbridge_ti_ai_readonly` DSN과 `OPENAI_API_KEY`를 실행 Process의
환경변수로만 주입하고, 최신 `main` 40자리 SHA를 다시 고정한다.

## 7. 요청 회신 형식

```ini
reviewer=이동윤
prepared_commit=111da4bcd6fd8cb7e019e545254d55b3ad7406ca
canonical_7_verified=YES
embedding_capability=REPRODUCIBLE_GENERATION_ONLY
generation_command=.\ai\.venv\Scripts\python.exe -m ai.scripts.build_vector_index
dependency_lock=ai/requirements.lock
proposed_row_fields=chunk_id,text_sha256,model,revision,dimension,vector,index_version,chunk_set_sha256,normalized
package_hash_method=chunk_id 정렬 + 합의된 Canonical JSON/UTF-8/LF Byte의 SHA-256;Vector 타입·정밀도 선행 고정 필요
ai_unit_tests=219 passed,0 failed,0 skipped,exit 0
local_actual_llm=NOT_RUN
team_g1a=WAITING_ENVIRONMENT_READY
blockers=OPENAI_API_KEY 미주입;Backend Importer Fixture Schema·저장 경로 미합의;팀 Audit·Crosswalk·View·Role READY 신호 대기
evidence_paths=data/processed/structured/rag/mvp/rag_verified_sample.jsonl;ai/configs/canonical_evidence_identity.json;ai/configs/index_manifest.json;ai/scripts/build_vector_index.py;ai/requirements.lock;ai/tests/unit/test_schemas_and_configs.py
```

## 8. 최지용에게 요청하는 다음 입력

1. Backend Importer의 Fixture Schema 초안과 저장 경로
2. Vector 숫자 타입과 직렬화 정밀도
3. Canonical JSON 또는 다른 Package 포맷 결정
4. Package Hash 계산 대상 Byte 경계
5. Importer Dry-run·Apply·Replay·Rollback 완료 후 최신 병합 SHA
6. 김은진의 `ENVIRONMENT_READY` 신호

위 입력을 받은 뒤 승인 Exporter 또는 일회성 Export 절차를 별도 변경으로 만들고,
작성자 검증 후 공동 G1-A를 실행한다.
