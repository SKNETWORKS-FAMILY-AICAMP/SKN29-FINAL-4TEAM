# 2026-08-21 AI·RAG 3모델 Runtime·Safety 확인 회신 v0.1

## 결론

- `PASS — Candidate`: 53개 Canonical Child와 일치하는 3모델 Manifest를 준비했고,
  재생성 가능한 격리 PostgreSQL/pgvector에서 승인된 Migration·Importer·Crosswalk
  경로와 실제 `three_model_integration` 검색을 실행했다.
- `PASS — AI Component`: 온수 히터·순간온수 모듈·온수 음용 제한용 독립 Rule
  `SAFETY-HOT-WATER-HEATER-001`을 추가했다. 대표 3개 입력의 최종 Public AI 결과는
  `danger + PARTIAL_STOP + requires_consultation=true`다.
- `HOLD — 공식 Readonly Gate`: 공식 팀 DB AI Readonly 연결은 `ConnectionTimeout`이고,
  격리 50 Case도 현재 Backend View Metadata 계약 때문에 `7/50`이다. Public Runtime은
  활성화하지 않는다.
- `HOLD — Backend danger 전달`: Backend mapper는 danger에 `TOTAL_STOP`만 허용하므로
  새 AI 결과 `danger + PARTIAL_STOP`을 현재 거절한다. Backend·PM 정책 정렬 전
  `DANGER_DETECTED` 공동 E2E 완료로 표시할 수 없다.
- `NOT_RUN`: Data QA의 원본 합성 30건 파일은 현재 checkout과 보호 Runtime에서
  확인되지 않았다. 아래 3개 Case ID에는 요청문에 적힌 조건을 재구성한 AI 회귀
  입력을 사용했으며, 원본 30건 재실행으로 확대하지 않는다.

## 실행 Identity

- Branch: `dongyoon`
- 실행 기준 HEAD: `32edf4a7a20ad5edfe9aa179ce5a1773f5027e76`
- Worktree: `DIRTY` — 기존 Prompt v3/Provider 변경을 보존했고 이번 변경도 아직
  Commit에 포함되지 않았다. 위 SHA는 변경 전 기준 Commit이지 변경 포함 SHA가 아니다.
- Python: `3.13.13`
- RAG Profile: `AI_RAG_RUNTIME_PROFILE=three_model_integration`
- Pipeline Runtime: `single_rag`
- Activation scope: `INTEGRATION_VERIFICATION_ONLY`
- Public Runtime activation: `HOLD`

## 1. 3모델 Manifest

추가 파일은 `ai/configs/index_manifest_3model.json`이다.

- Manifest file SHA-256:
  `3FA0F26C0C2C2628F9D4410C061FF17DD8D6CE9C6E0B76358CBB0BB0A9C28A1E`
- `index_version=2.0.0`
- `chunk_count=53`
- `dimension=1024`
- 모델/Revision: `BAAI/bge-m3` /
  `5617a9f61b028005a4858fdac845db406aefb181`
- Chunk Set SHA-256:
  `5B022EA8F00B22FE8CF9E386D2FFE91A1A136E2C6237ED4B64BA9EDCB181A304`
- 문서 Hash 3개와 Canonical Identity의 Index Version·Chunk Set이 일치한다.
- 보호 Embedding 입력은 본문을 출력하지 않고 53개 고유 ID, 53개 유한 1024차원
  Vector, Canonical ID Set 일치, 모델별 `15/19/19`만 확인했다.

이 Manifest는 격리 Candidate 입력으로 검증됐다. 공식 팀 DB 53건 적재와
Readonly 50 Case PASS를 의미하지 않는다.

## 2. 실제 격리 pgvector 실행 결과

재생성 가능한 임시 Container에서 전체 Migration 후 승인된 관리 명령만 사용했다.
ORM·수동 SQL로 업무 데이터를 우회하지 않았다. 실행 후 Container는 Label을 확인해
제거했다.

- Migration plan: `No planned migration operations.`
- Evidence Dry-run: `53`, 모델별 `15/19/19`
- Evidence Apply: Chunk 53, Embedding 53 생성
- Evidence Replay: Chunk 53, Embedding 53 unchanged
- Crosswalk Dry-run: 53
- Crosswalk Apply: created 53
- Crosswalk Replay: unchanged 53
- Readonly View 행 수:
  - `WPUJAC104DWH`: 15
  - `WPUIAC425SNW`: 19
  - `WPUIAC606SNW`: 19
- 실제 Exact-model 대표 검색·Pipeline·Harness:
  `8 passed in 25.90s`

공식 50 Case 검증 결과는 다음과 같다.

- 전체: `7/50 PASS`
- Positive Evidence Group Hit: `0/43`
- Negative No Evidence: `7/7`
- Cross-model Hit: `0`
- Unverified Evidence Hit: `0`
- Direct Parent 판정 Hit: `215`

현재 `backend_ai_rag_chunks_v1` View는 `evidence_group_id`, `source_variant_id`,
`parent_id`, `retrieval_role`을 Metadata에 투영하지 않는다. AI에서 누락된
`retrieval_role=None`은 `SEARCH_CANDIDATE`가 아니므로 215개 Positive Hit가 모두
Direct Parent로 판정되고, Evidence Group ID도 없어 Positive Group Hit가 성립하지
않는다.

Backend·Database 담당 완료 조건은 기존 Migration을 수정하지 않는 Additive
Migration으로 위 검색 계보 필드를 안전하게 투영하고, 공식 팀 DB에 적용한 뒤 같은
50 Case에서 `50/50`, Positive 43, Negative 7, Cross-model 0, Direct Parent 0,
Unverified 0을 재현하는 것이다.

## 3. 온수 위험 Safety Rule

추가 Rule은 `SAFETY-HOT-WATER-HEATER-001`이다.

- 탐지 범위: 히터 고장·이상, 순간온수 모듈 점검, 온수 음용 금지/중단
- 위험도: `danger`
- 사용 안내: `PARTIAL_STOP`
- 상담 필수: `true`
- 제한 기능: 온수 출수 및 음용
- 기존 `SAFETY-LEAK-001`, `SAFETY-ELECTRICAL-001`은 재사용하지 않았다.

`SYN-IAC606-108`, `SYN-IAC425-109`, `SYN-JAC104-031`이라는 Test ID로 대표 입력을
고정했고, Rule Classifier와 최종 Pipeline Public 결과를 모두 검증했다. 최종 AI
결과는 세 Case 모두 `danger + PARTIAL_STOP + 상담 필수 + Evidence 0`이다.

다만 `backend/integrations/ai/response_mapper.py`는 danger에 `TOTAL_STOP`을 강제한다.
현재 Mapper 실행은 새 결과를 `AIResponseValidationError`로 거절했다. AI 계약은
danger에서 `NORMAL`만 금지하고 `PARTIAL_STOP`을 허용하므로, Backend·PM이
`PARTIAL_STOP` 허용 여부를 결정하고 Mapper/DB 불변식/상태 전이 테스트를 함께
정렬해야 한다.

## 4. 제품 미승인 Public·Backend 계약

기본 MVP Profile에서 IAC 제품은 Vector/LLM 전에 내부
`RUNTIME_PRODUCT_NOT_APPROVED`로 차단된다. 그러나 이 내부 Issue Code는 Public
Schema에 노출되지 않는다. 실제 Public 결과는 다음과 같다.

- `status=FALLBACK`
- `failure_stage=RETRIEVING`
- `risk_level=caution`
- `requires_consultation=true`
- `guidance_status=PENDING_CONSULTATION`
- Evidence 0

Backend mapper는 이 결과를 `is_no_evidence=true`, `event_candidate=NO_EVIDENCE`로
전달한다. 현재 계약과 구현은 일치하지만, “제품 미승인”과 “승인 제품의 정상 검색
0건”이 Backend 경계에서 같은 `NO_EVIDENCE`로 합쳐진다. 두 원인을 업무적으로
구분해야 한다면 공개 Reason Code 또는 별도 Event 정책 결정이 필요하다. 임의로
`RETRIEVING`을 다른 Stage로 바꾸지는 않았다.

## 5. LF·SHA 확인

- `ai/configs/canonical_evidence_identity.json`: CR/CRLF 0건
- LF file SHA-256:
  `925088A352A81180B51E5418EB3152A1244ABA3DA07569712C4D903468220B85`
- `.gitattributes`의 `text eol=lf` 규칙 확인
- `ai/tests/unit/test_canonical_identity_line_endings.py`로 LF와 고정 File SHA를
  회귀 테스트에 추가했다.

`175065B3...` 값은 이 파일의 Byte SHA가 아니라 기존 7-Chunk Set SHA다. 두 값을
같은 SHA로 취급하지 않는다.

## 6. 실행 증거

- AI 표적 Safety/Pipeline 회귀: `74 passed`
- 3모델 Manifest/Safety/Integration 표적: `34 passed, 8 skipped`
  - 이때 8 skipped는 `AI_THREE_MODEL_E2E=1`이 없는 기본 실행이다.
- 실제 격리 3모델 E2E: `8 passed in 25.90s`
- 격리 Readonly 50 Case: `FAIL 7/50`, 사유는 위 Metadata Gate
- AI 전체 Unit: `415 passed, 4 warnings, 7 subtests passed`
- AI `pip check`: `PASS`
- Backend AI mapper 기존 회귀: `7 passed`
- 공식 팀 DB Readonly Query: `BLOCKED / ConnectionTimeout`
- Data QA 원본 30건 재실행: `NOT_RUN`
- Backend 저장·상태 전이 동일 Inquiry 공동 E2E: `NOT_RUN`

## 다음 Owner

1. Backend·Database: Readonly View 검색 계보 Metadata Additive Migration
2. Backend·PM: danger `PARTIAL_STOP` 수용 여부와 Mapper/DB 불변식 정렬
3. Data QA: 원본 30건 파일/경로와 고정 SHA 전달 후 동일 입력 재실행
4. 환경 Owner: 공식 팀 DB AI Readonly 연결 복구
5. AI: 위 입력 수신 후 30건 재실행, 공식 50 Case, Backend 공동 E2E 재검증
