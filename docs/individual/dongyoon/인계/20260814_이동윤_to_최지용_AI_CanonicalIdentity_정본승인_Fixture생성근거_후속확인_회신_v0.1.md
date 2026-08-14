# 이동윤 → 최지용: AI Canonical Identity 정본 승인·Fixture 생성 근거 후속 확인 회신 v0.1

> 작성일: 2026-08-14  
> 검증 기준: `main@ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7`  
> 범위: Canonical Identity 승인, Fixture provenance, 재생성·재전송 판정  
> 제외: 실제 QA Host 접근, Secret·DSN, Fixture·Embedding Vector 본문, G1-A Phase B 실행

## 1. 판정

AI Canonical Identity는 현재 AI 승인 정본이 맞다. 최신 main에서 LF checkout 계약과
Backend Importer 보강을 확인했고, Windows 기존 checkout의 잔존 CRLF를 LF로 다시
materialize한 뒤 Importer 회귀 `44 passed / 0 failed`를 재현했다.

Fixture 생성 커밋과 현재 main의 Identity·Exporter·Model Revision·Chunk Set은
변경되지 않았다. 현재 Fixture SHA도 기존 전달 SHA와 같으므로 재생성·재전송은
필요하지 않다. QA 전달 완료는 요청서의 `qa_fixture_received=YES`를 외부 수신 ACK로
인용하며, AI가 QA Host 파일을 직접 열어 재검증했다는 의미로 확대하지 않는다.

```ini
reviewer=이동윤
latest_main_sync=PASS
backend_lf_fix_visible=YES
canonical_identity_approval=APPROVED
canonical_identity_path=ai/configs/canonical_evidence_identity.json
approved_identity_sha256=925088a352a81180b51e5418eb3152a1244aba3da07569712c4d903468220b85
approval_basis=AI Canonical Identity 원시 바이트 SHA·Backend Manifest 기대 SHA·Exporter 생성 Commit 당시 SHA 동일

exporter_in_main=YES
exporter_path=ai/scripts/export_canonical_embedding_fixture.py
fixture_generated_commit_ref=626a7a4584d381085615d80b2269b8155322176d
fixture_sha256=759379308abdafbe66ef205e13cd829d8ad49714d0b824032eb0fbc58546d019
fixture_identity_sha256=925088a352a81180b51e5418eb3152a1244aba3da07569712c4d903468220b85
fixture_contract=7x1024,FLOAT32,chunk_id_ASC,NFC_7_OF_7
artifact_delivery_to_qa=YES
fixture_resend_required=NO
fixture_regeneration_reason=NONE

qa_environment_ready=NO_WAITING
g1a_phase_b_ready=WAITING_QA
blockers=PHASE_B_QA_ENVIRONMENT_READY_NOT_RECEIVED
evidence_paths=.gitattributes,ai/configs/canonical_evidence_identity.json,ai/configs/index_manifest.json,ai/scripts/export_canonical_embedding_fixture.py,ai/tests/unit/test_canonical_embedding_fixture_exporter.py,backend/tests/unit/evidence/test_ai_canonical_evidence_import.py,data/config/evidence/backend_ai_canonical_import_v1.json
```

## 2. 최신 main·LF 계약 확인

```ini
local_branch=dongyoon
local_head=ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7
origin_main=ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7
verification_start_worktree=CLEAN
canonical_config_diff=NONE
identity_git_attribute=text eol=lf
index_manifest_git_attribute=text eol=lf
backend_lf_regression_test=VISIBLE_IN_MAIN
```

현재 main Git blob과 LF로 materialize한 작업 파일의 SHA는 다음과 같이 Backend
Manifest 기대값과 일치한다.

| 파일 | LF 원시 바이트 SHA-256 | Backend 기대값 | 판정 |
| --- | --- | --- | --- |
| `ai/configs/canonical_evidence_identity.json` | `925088a352a81180b51e5418eb3152a1244aba3da07569712c4d903468220b85` | 동일 | PASS |
| `ai/configs/index_manifest.json` | `91027e88dec6c3bff1e590aaf4479ca021ac284eb0bdc8e1eec6c76473da667e` | 동일 | PASS |

기존 Windows checkout에는 `index_manifest.json`의 CRLF 작업 파일이 남아 첫 실행이
`25 passed / 19 failed`였다. `.gitattributes`와 main blob은 이미 LF였으며 파일을
LF로 다시 materialize한 뒤 같은 명령이 `44 passed / 0 failed`로 통과했다. 따라서
이 실패는 Canonical 내용 변경 근거가 아니라 기존 checkout 바이트 상태의 재현
증거다. Fresh Checkout에서는 두 파일이 LF인지 먼저 확인한다.

## 3. Canonical Identity 승인 근거

- `schema_version=1.0.0`
- `status=AI_SOURCE_IDENTITY_FIXED_BACKEND_MAPPING_PENDING`
- AI Canonical Key는 `chunk_id`이며 Backend 공개 ID 생성 책임을 침범하지 않는다.
- 승인 7개 Chunk의 Identity SHA는 Exporter Commit과 현재 main에서 동일하다.
- `626a7a4584d381085615d80b2269b8155322176d..ccf30f2d30ae556ffce4b9f7b009f5e04854aeb7`
  구간에서 Identity, Index Manifest, Exporter, 승인 7개 JSONL의 내용 변경은 없다.

따라서 줄바꿈 문제를 이유로 Identity JSON 내용이나 Backend Manifest 기대 Identity
SHA를 변경하지 않는다.

## 4. Fixture 생성 근거

| 항목 | 확인값 |
| --- | --- |
| Exporter Commit | `626a7a4584d381085615d80b2269b8155322176d` |
| Exporter | `ai/scripts/export_canonical_embedding_fixture.py` |
| Identity SHA at generation | `925088a352a81180b51e5418eb3152a1244aba3da07569712c4d903468220b85` |
| Fixture SHA | `759379308abdafbe66ef205e13cd829d8ad49714d0b824032eb0fbc58546d019` |
| Model Revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| Chunk Set SHA | `175065B3A487D73FF5B06F359B018CEA416719C88684EDA58C33C996107C9958` |
| Shape·Type | `7x1024`, `FLOAT32` |
| Ordering·NFC | `chunk_id_ASC`, `7/7` |
| Git Artifact Commit | `NO` |

Fixture 본문과 Vector는 이 회신문에 포함하지 않는다. Artifact 내부에 생성 Commit
필드가 없으므로 위 Commit SHA와 Fixture SHA를 별도 provenance 증거로 사용한다.

## 5. 실행 증거와 경계

```powershell
.\backend\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  backend\tests\unit\evidence\test_ai_canonical_evidence_import.py
# 44 passed in 7.37s, exit 0

.\ai\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  ai\tests\unit\test_canonical_embedding_fixture_exporter.py
# 10 passed in 0.29s, exit 0
```

위 결과는 Canonical 파일·Importer·Exporter 계약 확인이다. 실제 QA Host Import,
Crosswalk, Readonly View, 실제 pgvector·OpenAI 호출을 PASS로 대체하지 않는다.

## 6. 다음 단계

김은진이 Fresh Checkout 기준으로 아래를 회신할 때까지 G1-A Phase B는 대기한다.

```ini
backend_importer_tests=44 passed,0 failed
readiness_audit=READY
crosswalk=7/7
readonly_view=8 columns/7 rows
environment_ready=YES
g1a_joint_execution_ready=YES
```

`ENVIRONMENT_READY=YES` 수신 후 실제 pgvector·OpenAI G1-A를 시작한다. 그 전에는
Unit·Health 결과를 실제 G1-A PASS로 보고하지 않는다.
